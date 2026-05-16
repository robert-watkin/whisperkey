"""`whisperkey` command — the single entry point.

  whisperkey run        foreground voice loop (what the service runs; for debug)
  whisperkey start      start the background service (detached, survives terminal)
  whisperkey stop       stop it
  whisperkey restart    restart it
  whisperkey status      running? autostart on?
  whisperkey logs [-f]  service logs (journal)
  whisperkey enable     autostart on login
  whisperkey disable    cancel autostart
"""

from __future__ import annotations

import argparse
import sys

from . import service


def _add_run_flags(p: argparse.ArgumentParser):
    p.add_argument("--model", help="tiny|base|small|medium|large-v3")
    p.add_argument("--language", help='language code, or "" to auto-detect')
    p.add_argument("--hotkey", help="pynput GlobalHotKeys string, e.g. <ctrl>+<alt>+<space>")
    p.add_argument("--output", choices=["paste", "type", "clip"], help="delivery mode")
    p.add_argument("--input-device", dest="input_device", help="mic name/index substring")
    p.add_argument("--no-notify", action="store_true", help="disable desktop notifications")
    p.add_argument("--no-indicator", action="store_true", help="disable the on-screen badge")


def _run(args) -> int:
    # Imported lazily so management subcommands don't pay the heavy import cost.
    from .app import serve
    from .config import load

    overrides = {
        "model": args.model,
        "language": args.language,
        "hotkey": args.hotkey,
        "output": args.output,
        "input_device": args.input_device,
    }
    if args.no_notify:
        overrides["notify"] = False
    if args.no_indicator:
        overrides["indicator"] = False
    serve(load(overrides))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="whisperkey",
        description="Talk → text in the focused window. Local Whisper, on-device.",
    )
    sub = p.add_subparsers(dest="cmd")

    runp = sub.add_parser("run", help="foreground voice loop (for debugging)")
    _add_run_flags(runp)
    sub.add_parser("start", help="start the background service")
    sub.add_parser("stop", help="stop the background service")
    sub.add_parser("restart", help="restart the background service")
    sub.add_parser("status", help="show service state")
    logp = sub.add_parser("logs", help="show service logs")
    logp.add_argument("-f", "--follow", action="store_true", help="follow live")
    sub.add_parser("enable", help="autostart on login")
    sub.add_parser("disable", help="cancel autostart")

    args = p.parse_args(argv)

    if args.cmd is None:
        p.print_help()  # bare `whisperkey` → help, never silently start the loop
        return 0
    if args.cmd == "run":
        return _run(args)
    if args.cmd == "logs":
        return service.logs(args.follow)

    dispatch = {
        "start": service.start,
        "stop": service.stop,
        "restart": service.restart,
        "status": service.status,
        "enable": service.enable,
        "disable": service.disable,
    }
    fn = dispatch.get(args.cmd)
    if fn is None:
        p.print_help()
        return 0
    print(f"whisperkey: {fn()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
