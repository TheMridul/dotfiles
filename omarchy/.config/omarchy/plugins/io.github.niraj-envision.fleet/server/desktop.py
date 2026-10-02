"""Compositor awareness: where the bar is, and whether Fleet is fullscreen.

A Wayland client is not told its own position or fullscreen state -- that is
the compositor's business, and `window.screenY` is meaningless there. So the
answer is fetched from Hyprland instead of guessed in the page.

Hyprland publishes an event stream on a unix socket, so this costs one idle
socket read rather than a poll, and the UI learns about a fullscreen toggle
the moment it happens.
"""
import json
import logging
import os
import socket
import subprocess
import threading
import time

log = logging.getLogger("fleet.desktop")

WINDOW_TITLE = "Fleet"
HYPRCTL = "/usr/bin/hyprctl"
_state = {"bar": None, "compositor": "", "fullscreen": False}
_lock = threading.RLock()
_on_change = None


def set_hook(fn):
    global _on_change
    _on_change = fn


def snapshot():
    with _lock:
        return dict(_state)


def _hyprctl(args):
    try:
        p = subprocess.run([HYPRCTL] + args + ["-j"], capture_output=True, timeout=5)
        if p.returncode != 0:
            return None
        return json.loads(p.stdout.decode(errors="replace"))
    except Exception:
        return None


def read_bar():
    """Bar height and edge, read from the live layer surface.

    Not assumed, because the bar's size follows the theme's font and scale.
    """
    data = _hyprctl(["layers"])
    if not data:
        return None
    for mon in data.values():
        for layers in (mon.get("levels") or {}).values():
            for layer in layers:
                ns = str(layer.get("namespace") or "")
                if "bar" not in ns.lower():
                    continue
                h = int(layer.get("h") or 0)
                if h <= 0:
                    continue
                return {"namespace": ns, "height": h,
                        "position": "top" if int(layer.get("y") or 0) <= 0 else "bottom"}
    return None


def read_fullscreen():
    data = _hyprctl(["clients"])
    if not data:
        return False
    for c in data:
        if c.get("title") == WINDOW_TITLE and str(c.get("class", "")).startswith("chrome-"):
            # 0 none, 1 maximised (respects the bar already), 2 fullscreen.
            return int(c.get("fullscreen") or 0) >= 2
    return False


def refresh(emit=True):
    bar = read_bar()
    fs = read_fullscreen()
    with _lock:
        changed = (_state["bar"] != bar) or (_state["fullscreen"] != fs)
        _state["bar"] = bar
        _state["fullscreen"] = fs
        _state["compositor"] = "hyprland" if os.access(HYPRCTL, os.X_OK) else ""
        out = dict(_state)
    if changed and emit and _on_change:
        try:
            _on_change(out)
        except Exception:
            log.exception("desktop change hook failed")
    return out


def _socket_path():
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    run = os.environ.get("XDG_RUNTIME_DIR")
    if not sig or not run:
        return None
    for candidate in ("%s/hypr/%s/.socket2.sock" % (run, sig),
                      "/tmp/hypr/%s/.socket2.sock" % sig):
        if os.path.exists(candidate):
            return candidate
    return None


# Events that can change whether Fleet is fullscreen, or move the bar.
_WATCH = ("fullscreen>>", "activewindow>>", "openwindow>>", "closewindow>>",
          "monitoradded>>", "monitorremoved>>", "configreloaded>>",
          "workspace>>", "focusedmon>>")


class Watcher(threading.Thread):
    """Follow Hyprland's event stream, falling back to a slow poll."""
    daemon = True

    def __init__(self):
        super().__init__(name="desktop-watcher")
        self.stop_flag = threading.Event()

    def run(self):
        refresh(emit=False)
        while not self.stop_flag.is_set():
            path = _socket_path()
            if not path:
                # Not under Hyprland (or headless): poll gently so a bar that
                # appears later is still picked up, then stop trying hard.
                self.stop_flag.wait(30)
                refresh()
                continue
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(path)
                    s.settimeout(None)
                    buf = b""
                    while not self.stop_flag.is_set():
                        chunk = s.recv(8192)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            ev = line.decode(errors="replace")
                            if any(ev.startswith(w) for w in _WATCH):
                                refresh()
            except Exception:
                self.stop_flag.wait(3)
