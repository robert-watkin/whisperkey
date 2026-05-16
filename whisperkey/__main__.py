"""Enables `python -m whisperkey` — same entry as the `whisperkey` command."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
