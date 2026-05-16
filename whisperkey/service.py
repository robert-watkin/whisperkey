"""systemd --user service: install + start/stop/status/logs/enable.

A user service is the right detached mechanism here — survives terminal close,
auto-restarts on crash, logs to the journal, and can autostart on login. It
needs the graphical session's DISPLAY/XAUTHORITY to reach X (xdotool + the GTK
badge), so `start`/`restart` import those into the user manager first.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

UNIT_NAME = "whisperkey.service"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
UNIT_PATH = UNIT_DIR / UNIT_NAME
BIN = "%h/.local/bin/whisperkey"  # the PATH symlink created by setup.sh

_UNIT = f"""\
[Unit]
Description=whisperkey voice-to-text
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={BIN} run
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""


def _sc(*args: str, check: bool = False, capture: bool = False):
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=check, text=True,
        capture_output=capture,
    )


def have_systemd() -> bool:
    return shutil.which("systemctl") is not None


def install_unit() -> bool:
    """Write the unit if missing/changed. Returns True if it was (re)written."""
    UNIT_DIR.mkdir(parents=True, exist_ok=True)
    if UNIT_PATH.exists() and UNIT_PATH.read_text() == _UNIT:
        return False
    UNIT_PATH.write_text(_UNIT)
    _sc("daemon-reload")
    return True


def _import_x_env():
    # Pull DISPLAY/XAUTHORITY from the calling shell into the user manager so
    # the service can talk to X. Harmless if already set or vars absent.
    _sc("import-environment", "DISPLAY", "XAUTHORITY")


def start() -> str:
    if not have_systemd():
        return "systemctl not found — run `whisperkey run` in a terminal instead"
    install_unit()
    _import_x_env()
    r = _sc("start", UNIT_NAME, capture=True)
    return "started" if r.returncode == 0 else f"start failed: {r.stderr.strip()}"


def stop() -> str:
    r = _sc("stop", UNIT_NAME, capture=True)
    return "stopped" if r.returncode == 0 else f"stop failed: {r.stderr.strip()}"


def restart() -> str:
    install_unit()
    _import_x_env()
    r = _sc("restart", UNIT_NAME, capture=True)
    return "restarted" if r.returncode == 0 else f"restart failed: {r.stderr.strip()}"


def status() -> str:
    active = _sc("is-active", UNIT_NAME, capture=True).stdout.strip()
    enabled = _sc("is-enabled", UNIT_NAME, capture=True).stdout.strip() or "not-installed"
    return f"state: {active or 'inactive'}   autostart: {enabled}"


def logs(follow: bool) -> int:
    args = ["journalctl", "--user", "-u", UNIT_NAME, "-n", "60", "--no-pager"]
    if follow:
        args = ["journalctl", "--user", "-u", UNIT_NAME, "-n", "30", "-f"]
    return subprocess.run(args).returncode


def enable() -> str:
    install_unit()
    r = _sc("enable", UNIT_NAME, capture=True)
    return "autostart on login: ON" if r.returncode == 0 else f"enable failed: {r.stderr.strip()}"


def disable() -> str:
    r = _sc("disable", UNIT_NAME, capture=True)
    return "autostart on login: OFF" if r.returncode == 0 else f"disable failed: {r.stderr.strip()}"
