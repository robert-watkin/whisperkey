#!/usr/bin/env bash
# One-shot setup for whisperkey on Ubuntu 24.04 (X11).
set -euo pipefail
cd "$(dirname "$0")"

echo "==> system deps (needs sudo)"
sudo apt-get update -qq
# libportaudio2: mic capture · xdotool: paste/type + window detect
# python3-gi + gir1.2-gtk-3.0: the on-screen badge (optional, degrades to notify)
sudo apt-get install -y libportaudio2 xdotool python3-gi gir1.2-gtk-3.0

echo "==> python venv (--system-site-packages so the GTK badge can import gi)"
rm -rf venv
python3 -m venv --system-site-packages venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -e .   # installs deps + the `whisperkey` entry point

echo "==> exposing the 'whisperkey' command on PATH (~/.local/bin)"
mkdir -p "$HOME/.local/bin"
ln -sf "$(pwd)/venv/bin/whisperkey" "$HOME/.local/bin/whisperkey"

echo
echo "==> done. The Whisper model downloads on first run (~140 MB for 'base')."
echo "    Foreground/debug : whisperkey run"
echo "    Background       : whisperkey start   (then: status | logs -f | stop)"
echo "    Autostart        : whisperkey enable"
