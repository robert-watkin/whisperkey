# whisperkey

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Linux%20%2F%20X11-lightgrey.svg)](#known-limits--next)

Talk to your AIs instead of typing. Press a global hotkey and speak — each
phrase is typed straight into whatever window has focus (your Claude Code /
ChatGPT / editor prompt box) the moment you pause. Press the hotkey again to
stop.

**Local only.** Speech-to-text runs on-device via Whisper
([faster-whisper](https://github.com/SYSTRAN/faster-whisper)). No audio leaves
the machine. No API key. No subscription.

## Requirements

- Linux with an **X11** session (Wayland not yet supported — see
  [Known limits](#known-limits--next))
- Python **3.11+**
- A working microphone
- ~140 MB free disk for the default Whisper `base` model (downloaded on first
  run); CPU-only inference works fine — no GPU required.

## Why this shape

- **Local faster-whisper, CPU/int8** — this box has no NVIDIA GPU. `base` is
  ~near-realtime; `small` is more accurate but a few seconds for a paragraph.
  Switch with `--model small`.
- **Toggle hotkey** (`Ctrl+Alt+Space` by default) — press to start, press to
  stop. No held-key strain for long prompts.
- **Phrase streaming, not word streaming** — text commits per phrase when you
  pause (energy VAD). Whisper revises earlier words as it hears more, so
  word-by-word typing would mean backspacing inside someone else's input box —
  fragile. Whole-phrase commits are final and safe, and still feel live.
- **Clipboard + paste delivery** (default). Per-keystroke injection drops
  characters in TUIs like Claude Code (they drop synthetic key events under
  render load — no `xdotool` delay fixes this reliably). Pasting delivers the
  whole phrase atomically. The focused window's class is auto-detected to send
  the right chord (`Ctrl+Shift+V` for terminals, `Ctrl+V` for GUI apps).
  `output = "type"` keeps the old per-key behaviour as a fallback.

## Setup

```bash
git clone https://github.com/robert-watkin/whisperkey.git
cd whisperkey
./setup.sh          # installs libportaudio2 + xdotool (sudo), makes venv
```

`setup.sh` is Ubuntu/Debian-centric (uses `apt`). On other distros, install
the equivalents of `libportaudio2`, `xdotool`, `python3-gi`, and
`gir1.2-gtk-3.0`, then `pip install -e .` inside a venv built with
`--system-site-packages` (so GTK can be imported for the optional badge).

First run downloads the Whisper model (~140 MB for `base`) from Hugging Face.

## Use

After `setup.sh`, `whisperkey` is on your PATH:

```bash
whisperkey run                  # foreground (for debugging / first test)
whisperkey run --model small    # better accuracy, slower on CPU
whisperkey run --output clip    # clipboard only, paste manually
whisperkey run --no-indicator   # disable the on-screen badge

whisperkey start                # run detached as a background service
whisperkey status               # running? autostart?
whisperkey logs -f              # follow the service log
whisperkey stop
whisperkey enable               # autostart on login (whisperkey disable to undo)
```

Then: focus your AI prompt box → `Ctrl+Alt+Space` → speak naturally → text
appears phrase-by-phrase as you pause → `Ctrl+Alt+Space` again to stop. A red
**● listening** badge sits top-right while active (amber while a phrase
transcribes); notifications show each phrase as it lands.

`whisperkey start` runs it under a systemd --user service — no terminal needed,
auto-restarts on crash, `whisperkey enable` makes it start on login. (Pre-setup,
`./whisperkey.sh run …` still works as a fallback launcher.)

### Tuning (optional, config file)

If phrases cut off mid-sentence, raise `silence_hangover`. In a noisy room,
raise `vad_threshold`. See the table below.

## Config file (optional)

`~/.config/whisperkey/config.toml` — any `Config` field overrides the default; CLI
flags still win over the file.

```toml
model = "small"
hotkey = "<ctrl>+<alt>+<space>"   # named keys need <angle brackets>
output = "paste"          # paste (robust, default) | type (legacy) | clip
paste_settle_ms = 120     # wait before paste; raise if first phrase pastes empty
# paste_key_terminal = "ctrl+shift+v"   # override if your terminal differs
# paste_key_gui = "ctrl+v"
type_delay_ms = 30        # only used by legacy output = "type"
indicator = true          # on-screen badge; false = notifications only
language = "en"
vad_threshold = 0.012     # RMS speech gate; raise in a noisy room
silence_hangover = 0.7    # seconds of quiet that ends a phrase
min_speech = 0.3          # ignore blips shorter than this (s)
max_segment = 15.0        # force-flush a pause-less monologue (s)
```

## Layout

| File | Role |
|------|------|
| `whisperkey/cli.py` | `whisperkey` command — run + service subcommands |
| `whisperkey/service.py` | systemd --user unit install + start/stop/logs |
| `whisperkey/app.py` | hotkey loop, state machine, phrase consumer thread |
| `whisperkey/audio.py` | mic capture + energy-VAD phrase segmentation |
| `whisperkey/transcribe.py` | faster-whisper, loaded once, kept warm |
| `whisperkey/output.py` | clipboard+paste / type / clip delivery, window detect |
| `whisperkey/indicator.py` | optional GTK always-on-top recording badge |
| `whisperkey/config.py` | defaults → TOML → CLI precedence |
| `whisperkey/notify.py` | notify-send toasts |

## Known limits / next

- X11 only. Wayland would need `ydotool` + a uinput permission setup.
- Phrase-level streaming (commits when you pause), not word-level. Deliberate —
  see the note above.
- Paste mode **overwrites the clipboard** with each phrase (no save/restore
  yet). Manual `output = "type"` avoids this if you need the clipboard intact.
- Energy VAD is simple; very quiet speech in a loud room may need
  `vad_threshold` tuning. A learned VAD (silero/webrtc) is a possible upgrade.
- Possible v2: local-default + a "send this clip to Groq" accuracy hotkey.

## Contributing

This is primarily a personal tool — published in case it's useful to anyone
else. Issues and small PRs are welcome, but I may be slow to respond and I'll
push back on changes that drift from the design choices noted above (local-
only, phrase streaming, paste-by-default). If you want to take it in a
different direction, fork freely — that's what the MIT license is for.

## License

[MIT](LICENSE) — © 2026 Robert Watkin.
