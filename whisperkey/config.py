"""Configuration: defaults, optional TOML file, CLI overrides.

Precedence (low -> high): dataclass defaults -> ~/.config/whisperkey/config.toml
-> CLI overrides (a dict supplied by whisperkey.cli).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "whisperkey" / "config.toml"


@dataclass
class Config:
    # Whisper model size: tiny | base | small | medium | large-v3.
    # No GPU on this box -> CPU/int8. base ~= near-realtime; small = better
    # accuracy, a few seconds for a paragraph; medium is slow on CPU.
    model: str = "base"
    compute_type: str = "int8"  # int8 is the right CPU tradeoff
    language: str = "en"  # set "" to auto-detect (slower)

    # pynput GlobalHotKeys syntax. Named keys need angle brackets (<space>),
    # letters do not (<ctrl>+<alt>+v). Toggle: press to start, press to stop.
    hotkey: str = "<ctrl>+<alt>+<space>"

    samplerate: int = 16000  # Whisper wants 16 kHz mono
    input_device: str | None = None  # None = system default mic

    # Phrase segmentation (energy-based VAD). Tune via the config file if your
    # mic/room needs it; defaults suit normal dictation with natural pauses.
    vad_threshold: float = 0.012  # RMS above this = speech (raise if noisy room)
    # Lower hangover = phrases commit sooner (feels more live) at the cost of
    # splitting on longer mid-sentence pauses. 0.5 s is the dictation sweet
    # spot; raise toward 0.7 if your natural clause pauses get chopped.
    silence_hangover: float = 0.5  # seconds of quiet that ends a phrase
    min_speech: float = 0.3  # ignore blips shorter than this (seconds)
    max_segment: float = 10.0  # force-flush a pauseless monologue sooner (s)

    # "paste" -> set clipboard, send the paste chord (atomic, robust; default)
    # "type"  -> inject keystrokes one by one (fragile in TUIs; legacy fallback)
    # "clip"  -> copy to clipboard only, you paste manually
    output: str = "paste"

    # Paste chords. Terminals (incl. Claude Code) need ctrl+shift+v; GUI apps
    # use ctrl+v. The focused window's class is auto-detected to pick one.
    paste_key_terminal: str = "ctrl+shift+v"
    paste_key_gui: str = "ctrl+v"
    # Substrings matched (case-insensitive) against the focused window class to
    # decide "this is a terminal". Add yours if auto-detect misses it.
    terminal_classes: tuple[str, ...] = (
        "terminal", "konsole", "xterm", "rxvt", "alacritty", "kitty",
        "tilix", "wezterm", "foot", "ptyxis", "contour", "st-256color",
    )
    # ms to wait after copying before sending the paste chord (clipboard +
    # focus settle). Raise if the first phrase occasionally pastes empty.
    paste_settle_ms: int = 120

    # Per-keystroke delay (ms) for the legacy "type" mode only.
    type_delay_ms: int = 30

    notify: bool = True  # desktop notifications via notify-send

    # Floating always-on-top "● listening" badge while a session is active.
    # Falls back silently to notifications if GTK is unavailable at runtime.
    indicator: bool = True

    def merged_with_file(self) -> "Config":
        if not CONFIG_PATH.exists():
            return self
        data = tomllib.loads(CONFIG_PATH.read_text())
        known = {f.name for f in fields(self)}
        for k, v in data.items():
            if k in known:
                setattr(self, k, v)
        return self


def load(overrides: dict | None = None) -> Config:
    """defaults -> ~/.config/whisperkey/config.toml -> overrides dict."""
    cfg = Config().merged_with_file()
    known = {f.name for f in fields(cfg)}
    for k, v in (overrides or {}).items():
        if v is not None and k in known:
            setattr(cfg, k, v)
    return cfg
