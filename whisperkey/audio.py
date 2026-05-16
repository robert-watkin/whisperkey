"""Mic capture with energy-based VAD that yields finalized speech *phrases*.

Why phrases, not word-streaming: Whisper revises earlier words as it gets more
context. Typing word-by-word into someone else's input box would mean sending
backspaces to fix already-typed text — fragile the moment focus/mouse moves.
Committing a whole phrase once you pause is final and safe, and still feels
live. A phrase ends after `silence_hangover` seconds of quiet.
"""

from __future__ import annotations

import queue
import threading

import numpy as np
import sounddevice as sd

_SENTINEL = object()  # pushed to the phrase queue when capture has fully stopped


class PhraseStream:
    def __init__(
        self,
        samplerate: int,
        device: str | int | None,
        vad_threshold: float,
        silence_hangover: float,
        min_speech: float,
        max_segment: float,
    ):
        self.samplerate = samplerate
        self.device = device
        self.vad_threshold = vad_threshold
        self.silence_hangover = silence_hangover
        self.min_speech = min_speech
        self.max_segment = max_segment

        self.block = max(1, int(samplerate * 0.05))  # 50 ms analysis frames
        self._raw: queue.Queue = queue.Queue()
        self._phrases: queue.Queue = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._worker: threading.Thread | None = None
        self._running = False

    # --- sounddevice side -------------------------------------------------
    def _callback(self, indata, frames, time, status):  # noqa: ARG002
        self._raw.put(indata.copy())

    def start(self) -> None:
        for q in (self._raw, self._phrases):
            while not q.empty():
                q.get_nowait()
        self._running = True
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype="float32",
            device=self.device,
            blocksize=self.block,
            callback=self._callback,
        )
        self._stream.start()
        self._worker = threading.Thread(target=self._segment_loop, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Signal end-of-capture. The worker drains buffered audio, flushes any
        in-progress phrase, then enqueues the sentinel."""
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get(self) -> np.ndarray | None:
        """Block until the next finalized phrase. Returns None when capture has
        stopped and all audio has been drained."""
        item = self._phrases.get()
        return None if item is _SENTINEL else item

    # --- segmentation -----------------------------------------------------
    def _segment_loop(self) -> None:
        block_dur = self.block / self.samplerate
        buf: list[np.ndarray] = []
        in_phrase = False
        silence_run = 0.0
        phrase_len = 0.0

        def finalize() -> None:
            nonlocal buf, in_phrase, silence_run, phrase_len
            speech = phrase_len - silence_run
            if buf and speech >= self.min_speech:
                self._phrases.put(np.concatenate(buf).reshape(-1).astype(np.float32))
            buf, in_phrase, silence_run, phrase_len = [], False, 0.0, 0.0

        while self._running or not self._raw.empty():
            try:
                block = self._raw.get(timeout=0.1)
            except queue.Empty:
                continue
            mono = block.reshape(-1)
            rms = float(np.sqrt(np.mean(mono**2))) if mono.size else 0.0
            speaking = rms > self.vad_threshold

            if speaking:
                in_phrase = True
                buf.append(block)
                phrase_len += block_dur
                silence_run = 0.0
            elif in_phrase:
                buf.append(block)  # keep trailing silence; Whisper likes the pad
                phrase_len += block_dur
                silence_run += block_dur
                if silence_run >= self.silence_hangover:
                    finalize()

            if in_phrase and phrase_len >= self.max_segment:
                finalize()  # force-flush a long monologue with no pause

        finalize()  # flush whatever was mid-sentence when stop() was called
        self._phrases.put(_SENTINEL)
