"""The voice loop: warm the model, register the global toggle hotkey, serve.

Press hotkey  -> start listening (badge appears)
(speak; each phrase you finish is delivered as you pause)
Press again   -> stop, flush the last phrase, done

paste/type: each phrase delivered immediately. clip: accumulated, copied once.
Invoked by `whisperkey run` (see whisperkey.cli); the systemd service runs that.
"""

from __future__ import annotations

import signal
import sys
import threading

from pynput import keyboard

from .audio import PhraseStream
from .config import Config
from .indicator import Indicator
from .notify import toast
from .output import emit
from .transcribe import Transcriber


class VoxKey:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.stream = PhraseStream(
            cfg.samplerate, cfg.input_device, cfg.vad_threshold,
            cfg.silence_hangover, cfg.min_speech, cfg.max_segment,
        )
        self.indicator = Indicator(cfg.indicator)
        self.active = False
        self._lock = threading.Lock()
        self._consumer: threading.Thread | None = None

        print(f"whisperkey: loading whisper '{cfg.model}' (cpu/{cfg.compute_type})…", flush=True)
        toast("whisperkey starting", f"loading model '{cfg.model}'…", cfg.notify)
        self.transcriber = Transcriber(cfg.model, cfg.compute_type, cfg.language)
        print(f"whisperkey: ready. hotkey = {cfg.hotkey}  output = {cfg.output}", flush=True)
        toast("whisperkey ready", f"{cfg.hotkey} to dictate", cfg.notify)

    def _toggle(self):
        with self._lock:
            if not self.active:
                self.active = True
                self.stream.start()
                self.indicator.set("listening")
                print("● listening…", flush=True)
                toast("🎤 listening", "speak; pause to commit a phrase", self.cfg.notify)
                self._consumer = threading.Thread(target=self._consume, daemon=True)
                self._consumer.start()
            else:
                self.active = False
                self.stream.stop()  # consumer drains, then exits on sentinel
                print("… finishing", flush=True)

    def _consume(self):
        parts: list[str] = []
        n = 0
        try:
            while True:
                phrase = self.stream.get()
                if phrase is None:  # capture stopped and drained
                    break
                self.indicator.set("working")
                text = self.transcriber.transcribe(phrase).strip()
                self.indicator.set("listening")
                if not text:
                    continue
                n += 1
                if self.cfg.output == "clip":  # accumulate, copy once at the end
                    parts.append(text)
                    print(f"  [buffered {n}] {text}", flush=True)
                    toast(f"📋 phrase {n} buffered", text, self.cfg.notify)
                else:  # paste / type: deliver each phrase as you pause
                    status = emit(text + " ", self.cfg)
                    print(f"  [{status}] {text}", flush=True)
                    toast(f"✍️ phrase {n}", text, self.cfg.notify)

            if self.cfg.output == "clip" and parts:
                status = emit(" ".join(parts), self.cfg)
                toast(f"✅ {status}", f"{n} phrase(s)", self.cfg.notify)
            else:
                toast("✅ done", f"{n} phrase(s)" if n else "(nothing heard)", self.cfg.notify)
            print(f"whisperkey: done — {n} phrase(s)", flush=True)
        except Exception as e:  # noqa: BLE001 — never let the hotkey loop die
            print(f"  ERROR: {e}", flush=True)
            toast("❌ whisperkey error", str(e), self.cfg.notify, urgency="critical")
        finally:
            self.indicator.set("hidden")

    def run(self):
        listener = keyboard.GlobalHotKeys({self.cfg.hotkey: self._toggle})
        listener.start()

        def _shutdown(*_):
            self.indicator.quit()
            listener.stop()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)  # systemctl --user stop
        try:
            # indicator.run() blocks in the GTK loop and returns True; if the
            # GUI can't start it returns False and we just wait on the listener.
            if not self.indicator.run():
                listener.join()
        except KeyboardInterrupt:
            pass
        listener.stop()
        print("\nwhisperkey: bye", flush=True)


def serve(cfg: Config):
    try:
        VoxKey(cfg).run()
    except Exception as e:  # noqa: BLE001
        print(f"whisperkey: fatal: {e}", file=sys.stderr)
        sys.exit(1)
