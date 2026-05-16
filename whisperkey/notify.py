"""Thin notify-send wrapper. Silent no-op if disabled or unavailable."""

from __future__ import annotations

import shutil
import subprocess

_HAVE = shutil.which("notify-send") is not None
_TAG = "whisperkey"


def toast(summary: str, body: str = "", enabled: bool = True, urgency: str = "low") -> None:
    if not enabled or not _HAVE:
        return
    try:
        subprocess.Popen(
            ["notify-send", "-a", _TAG, "-u", urgency, "-h", f"string:x-canonical-private-synchronous:{_TAG}",
             summary, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass
