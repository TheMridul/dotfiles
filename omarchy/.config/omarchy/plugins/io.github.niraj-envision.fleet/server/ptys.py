"""PTY-backed terminal sessions.

A session is a real pseudo-terminal running `ssh` against a host's existing
master connection, so opening a terminal costs one fork rather than a fresh
handshake. Sessions outlive the websocket that created them and keep a capped
scrollback, which is what lets you reload the app window -- or close and
reopen it -- and find your shells exactly where you left them.
"""
import fcntl
import os
import pty
import signal
import struct
import termios
import threading
import time
import uuid

import sshmgr

MAX_SCROLLBACK = 256 * 1024
# Sessions outlive the window on purpose, so nothing reaps them while they are
# merely detached. That makes an upper bound necessary: each one is a live ssh
# process and a pty on both ends.
MAX_SESSIONS = 48

_sessions = {}
_lock = threading.RLock()


class Session:
    def __init__(self, host, cols=100, rows=30, command=None, title=None, local=False):
        self.id = uuid.uuid4().hex[:12]
        self.host_id = None if local else host["id"]
        self.host_name = "local" if local else host["name"]
        command = str(command)[:1024 * 1024] if command is not None else None
        title = str(title)[:160] if title is not None else None
        self.title = title or (self.host_name if not command else command.split()[0][:160])
        self.cols = max(20, min(int(cols), 500))
        self.rows = max(5, min(int(rows), 200))
        self.created = int(time.time())
        self.command = command
        self.local = local
        self.alive = True
        self.exit_code = None
        self.scrollback = bytearray()
        self.subscribers = []          # callables taking (bytes)
        self._sub_lock = threading.RLock()

        env = dict(os.environ) if local else sshmgr.env_for(host, interactive=True)
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        if local:
            argv = [os.environ.get("SHELL", "/bin/bash"), "-l"]
        else:
            argv = sshmgr.base_args(host) + ["-t"]
            if command:
                argv += ["--", command]
            elif host.get("shell"):
                argv += ["--", host["shell"]]

        pid, fd = pty.fork()
        if pid == 0:                    # child: only ever execs
            try:
                os.execvpe(argv[0], argv, env)
            except Exception:
                os._exit(127)
        self.pid, self.fd = pid, fd
        self._set_size(self.cols, self.rows)
        threading.Thread(target=self._reader, daemon=True).start()

    # ---------------------------------------------------------------- io
    def _set_size(self, cols, rows):
        try:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def resize(self, cols, rows):
        self.cols = max(20, min(int(cols), 500))
        self.rows = max(5, min(int(rows), 200))
        self._set_size(self.cols, self.rows)

    def write(self, data):
        if not self.alive:
            return
        if isinstance(data, str):
            data = data.encode()
        try:
            os.write(self.fd, data)
        except OSError:
            self.alive = False

    def _reader(self):
        while True:
            try:
                chunk = os.read(self.fd, 65536)
            except OSError:
                chunk = b""
            if not chunk:
                break
            self.scrollback += chunk
            if len(self.scrollback) > MAX_SCROLLBACK:
                # Trim on a chunk boundary rather than mid-escape-sequence where
                # possible; a stray byte here would corrupt the replayed screen.
                del self.scrollback[:len(self.scrollback) - MAX_SCROLLBACK]
            self._fanout(chunk)
        self.alive = False
        try:
            _, status = os.waitpid(self.pid, os.WNOHANG)
            self.exit_code = os.waitstatus_to_exitcode(status)
        except (ChildProcessError, OSError, ValueError):
            self.exit_code = -1
        self._fanout(b"\r\n\x1b[38;5;244m[session ended]\x1b[0m\r\n")

    def _fanout(self, chunk):
        with self._sub_lock:
            subs = list(self.subscribers)
        for s in subs:
            try:
                s(chunk)
            except Exception:
                self.unsubscribe(s)

    # -------------------------------------------------------- subscribers
    def subscribe(self, fn, replay=True):
        with self._sub_lock:
            self.subscribers.append(fn)
        if replay and self.scrollback:
            try:
                fn(bytes(self.scrollback))
            except Exception:
                pass

    def unsubscribe(self, fn):
        with self._sub_lock:
            if fn in self.subscribers:
                self.subscribers.remove(fn)

    # -------------------------------------------------------------- close
    def close(self):
        self.alive = False
        for sig in (signal.SIGHUP, signal.SIGKILL):
            try:
                os.kill(self.pid, sig)
            except OSError:
                break
            time.sleep(0.05)
            try:
                if os.waitpid(self.pid, os.WNOHANG)[0]:
                    break
            except (ChildProcessError, OSError):
                break
        try:
            os.close(self.fd)
        except OSError:
            pass

    def info(self):
        return {"id": self.id, "host_id": self.host_id, "host_name": self.host_name,
                "title": self.title, "cols": self.cols, "rows": self.rows,
                "created": self.created, "alive": self.alive,
                "command": self.command, "local": self.local,
                "bytes": len(self.scrollback)}


# ------------------------------------------------------------------ registry

def open_session(host, cols=100, rows=30, command=None, title=None, local=False):
    reap()
    with _lock:
        if len(_sessions) >= MAX_SESSIONS:
            raise RuntimeError(
                "too many open terminals (%d). Close some before opening more."
                % MAX_SESSIONS)
    s = Session(host, cols, rows, command, title, local)
    with _lock:
        _sessions[s.id] = s
    return s


def get(sid):
    with _lock:
        return _sessions.get(sid)


def list_sessions(host_id=None):
    with _lock:
        vals = list(_sessions.values())
    return [s.info() for s in vals
            if host_id is None or s.host_id == host_id]


def close_session(sid):
    with _lock:
        s = _sessions.pop(sid, None)
    if s:
        s.close()
    return bool(s)


def close_for_host(host_id):
    with _lock:
        ids = [i for i, s in _sessions.items() if s.host_id == host_id]
    for i in ids:
        close_session(i)


def reap():
    """Drop sessions whose process exited and that nobody is watching."""
    with _lock:
        dead = [i for i, s in _sessions.items()
                if not s.alive and not s.subscribers
                and time.time() - s.created > 30]
        for i in dead:
            _sessions.pop(i, None)
    return len(dead)
