#!/usr/bin/env bash
# Launcher: runs whisperkey from its venv. Pass through any CLI flags.
set -euo pipefail
cd "$(dirname "$0")"
exec ./venv/bin/python -m whisperkey "$@"
