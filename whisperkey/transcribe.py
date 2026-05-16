"""faster-whisper wrapper. Model is loaded once at startup and kept warm."""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model: str = "base", compute_type: str = "int8", language: str = "en"):
        self.language = language or None
        # device="cpu" — this box has no NVIDIA GPU. int8 keeps it fast-ish.
        # First run downloads the model from Hugging Face (~140 MB for base).
        self.model = WhisperModel(model, device="cpu", compute_type=compute_type)

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=1,  # greedy: ~2x faster on CPU, negligible loss on clear dictation
            condition_on_previous_text=False,  # phrases are independent; avoids drift + speeds up
            vad_filter=True,  # drops leading/trailing silence -> faster, cleaner
        )
        return " ".join(s.text.strip() for s in segments).strip()
