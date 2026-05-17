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

_SENTINEL = object()  # phrase queue: capture fully stopped and drained
_END = object()  # raw queue: stream closed, no more audio will ever arrive


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
        """Signal end-of-capture. Close the mic stream (PortAudio flushes its
        final callbacks into _raw as part of stop/close), *then* enqueue an
        explicit end marker. The worker drains every captured block in order
        and only finishes when it sees that marker — so toggling off the moment
        you stop speaking can't lose the last phrase to a queue-empty race."""
        if not self._running:
            return
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._raw.put(_END)

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

        def finalize(*, forced: bool = False) -> None:
            nonlocal buf, in_phrase, silence_run, phrase_len
            speech = phrase_len - silence_run
            # min_speech rejects ambient blips between phrases. On an explicit
            # stop the user deliberately ended input, so commit even a short
            # final phrase — keep only a tiny floor so a one-frame noise spike
            # doesn't get sent to Whisper as a "phrase".
            floor = min(self.min_speech, 0.15) if forced else self.min_speech
            if buf and speech > floor:
                self._phrases.put(np.concatenate(buf).reshape(-1).astype(np.float32))
            buf, in_phrase, silence_run, phrase_len = [], False, 0.0, 0.0

        while True:
            block = self._raw.get()  # blocks; _END (enqueued by stop) ends it
            if block is _END:
                break
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

        finalize(forced=True)  # flush whatever was mid-sentence at stop()
        self._phrases.put(_SENTINEL)
