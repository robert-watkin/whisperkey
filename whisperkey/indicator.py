"""Optional always-on-top recording badge (GTK 3 via PyGObject).

A tiny borderless, non-focusable pill in the top-right corner: red while
listening, amber while a phrase transcribes, hidden when idle. Never steals
input focus, so paste/type still lands in the app you were using.

GTK is optional: if PyGObject isn't importable, every method is a safe no-op
and the app falls back to notifications only.
"""

from __future__ import annotations

_AVAILABLE = False
try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    _AVAILABLE = True
except (ImportError, ValueError):
    pass

_STYLES = {
    "listening": ("#e23b3b", "●  listening"),
    "working": ("#d6892a", "●  transcribing…"),
}


class Indicator:
    def __init__(self, enabled: bool):
        self.available = bool(enabled and _AVAILABLE)
        self._win = None
        self._label = None
        self._css = None

    # --- GTK-thread internals --------------------------------------------
    def _build(self):
        self._win = Gtk.Window(type=Gtk.WindowType.POPUP)  # override-redirect: no focus theft
        self._win.set_keep_above(True)
        self._win.set_accept_focus(False)
        self._win.set_focus_on_map(False)
        self._win.set_skip_taskbar_hint(True)
        self._win.set_skip_pager_hint(True)
        self._win.set_resizable(False)
        self._label = Gtk.Label()
        for setter in ("set_margin_top", "set_margin_bottom"):
            getattr(self._label, setter)(6)
        for setter in ("set_margin_start", "set_margin_end"):
            getattr(self._label, setter)(16)
        self._win.add(self._label)
        self._css = Gtk.CssProvider()
        self._label.get_style_context().add_provider(
            self._css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    def _position(self):
        disp = Gdk.Display.get_default()
        mon = disp.get_primary_monitor() or disp.get_monitor(0)
        geo = mon.get_geometry()
        w, h = self._win.get_size()
        self._win.move(geo.x + geo.width - w - 24, geo.y + 28)

    def _set_main(self, state):
        if not self._win:
            return False
        if state not in _STYLES:  # "hidden" or anything unknown
            self._win.hide()
            return False
        color, text = _STYLES[state]
        self._css.load_from_data(
            f"* {{ background:{color}; color:#ffffff; font-weight:bold;"
            f" font-family:Sans; font-size:12pt; border-radius:7px; }}".encode()
        )
        self._label.set_text(text)
        self._win.show_all()
        self._position()
        return False

    # --- public, thread-safe ---------------------------------------------
    def set(self, state: str):
        if self.available:
            GLib.idle_add(self._set_main, state)

    def run(self) -> bool:
        """Block in the GTK loop. Returns True if it ran, False if it couldn't
        (caller then falls back to just joining the hotkey listener)."""
        if not self.available:
            return False
        try:
            self._build()
            GLib.timeout_add(250, lambda: True)  # keep Python ticking for signals
            Gtk.main()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"whisperkey: indicator disabled ({e})", flush=True)
            self.available = False
            return False

    def quit(self):
        if self.available:
            GLib.idle_add(Gtk.main_quit)
