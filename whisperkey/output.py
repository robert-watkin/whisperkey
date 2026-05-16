"""Deliver transcribed text to the focused app.

Three modes:
  paste — set the clipboard, then send the paste chord. The app receives the
          whole string atomically (terminals: bracketed paste). No per-key
          race, so nothing can be dropped. This is the robust default.
  type  — xdotool types it character by character. Fragile in TUIs (Claude
          Code, vim) which drop synthetic key events under render load.
  clip  — copy only; you paste manually.

X11 session, so xdotool/xclip are the tools.
"""

from __future__ import annotations

import shutil
import subprocess
import time


def _to_clipboard(text: str) -> bool:
    for tool, args in (("xclip", ["-selection", "clipboard"]), ("wl-copy", [])):
        if shutil.which(tool):
            try:
                subprocess.run([tool, *args], input=text.encode(), check=True)
                return True
            except subprocess.SubprocessError:
                continue
    return False


def _active_window_class() -> str:
    """Lowercased class of the focused window, '' if undetectable."""
    if not shutil.which("xdotool"):
        return ""
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowclassname"],
            capture_output=True, text=True, timeout=1.0,
        )
        return out.stdout.strip().lower()
    except (subprocess.SubprocessError, OSError):
        return ""


def _send_keys(chord: str) -> bool:
    if not shutil.which("xdotool"):
        return False
    try:
        subprocess.run(["xdotool", "key", "--clearmodifiers", chord], check=True)
        return True
    except subprocess.SubprocessError:
        return False


def _type_it(text: str, delay_ms: int) -> bool:
    if not shutil.which("xdotool"):
        return False
    try:
        # --clearmodifiers so a still-held hotkey modifier can't corrupt input.
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", str(delay_ms), "--", text],
            check=True,
        )
        return True
    except subprocess.SubprocessError:
        return False


def _paste(text: str, cfg) -> str:
    if not _to_clipboard(text):
        return "FAILED: no clipboard tool"
    cls = _active_window_class()
    # Unknown class -> assume terminal: ctrl+shift+v is harmless in most GUI
    # apps, but ctrl+v is a no-op in a terminal (the exact failure we're fixing).
    is_term = (not cls) or any(t in cls for t in cfg.terminal_classes)
    chord = cfg.paste_key_terminal if is_term else cfg.paste_key_gui
    time.sleep(max(0, cfg.paste_settle_ms) / 1000.0)  # clipboard + focus settle
    where = f"{cls or '?'}/{'term' if is_term else 'gui'}"
    if _send_keys(chord):
        return f"pasted [{where} {chord}]"
    if _type_it(text, cfg.type_delay_ms):
        return f"paste key failed — typed instead [{where}]"
    return f"FAILED: clipboard set but no xdotool [{where}]"


def emit(text: str, cfg) -> str:
    """Deliver `text` per cfg.output. Returns a short human-readable status."""
    if not text:
        return "nothing heard"

    if cfg.output == "paste":
        return _paste(text, cfg)

    if cfg.output == "type":
        if _type_it(text, cfg.type_delay_ms):
            return "typed"
        if _to_clipboard(text):
            return "xdotool failed — copied to clipboard"
        return "FAILED: no xdotool and no clipboard tool"

    # cfg.output == "clip"
    if _to_clipboard(text):
        return "copied to clipboard"
    return "FAILED: no clipboard tool"
