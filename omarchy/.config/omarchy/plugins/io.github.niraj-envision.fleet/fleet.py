#!/usr/bin/python3
"""Fleet -- a VPS manager for Omarchy.

Starts a loopback-only web server, opens every configured SSH connection so
the fleet is live before the window finishes painting, then launches the UI as
a chromeless browser window.
"""
import argparse
import errno
import fcntl
import logging
import logging.handlers
import os
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "server"))

import api          # noqa: E402
import appmeta      # noqa: E402
import desktop      # noqa: E402
import hosts        # noqa: E402
import httpd        # noqa: E402
import paths        # noqa: E402
import ptys         # noqa: E402
import sshmgr       # noqa: E402
import store        # noqa: E402
import theme        # noqa: E402
import vpn          # noqa: E402

BANNER = "\033[1;36m▚\033[0m Fleet"
LOCK_FILE = os.path.join(paths.STATE_DIR, "fleet.lock")
_lock_fh = None
OMARCHY_WEBAPP = "/usr/share/omarchy/bin/omarchy-launch-webapp"
BROWSERS = (
    ("/usr/bin/chromium", "chromium"),
    ("/usr/bin/google-chrome-stable", "google-chrome-stable"),
    ("/usr/bin/brave", "brave"),
    ("/usr/bin/firefox", "firefox"),
)
XDG_OPEN = "/usr/bin/xdg-open"


def setup_logging(debug=False):
    """Errors go to a size-capped file; the console stays quiet on purpose.

    Fleet normally runs detached behind a desktop launcher, so stderr goes
    nowhere. Without a log, a background failure is invisible.
    """
    os.makedirs(paths.STATE_DIR, exist_ok=True)
    root = logging.getLogger("fleet")
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    root.handlers.clear()
    fh = logging.handlers.RotatingFileHandler(
        paths.LOG_FILE, maxBytes=1_000_000, backupCount=2)
    try:
        os.chmod(paths.LOG_FILE, 0o600)
    except OSError:
        pass
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    root.addHandler(fh)
    if debug:
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)-7s %(name)s  %(message)s"))
        root.addHandler(sh)
    # Anything that escapes a worker thread should still reach the log.
    def _thread_hook(args):
        root.error("unhandled exception in %s", args.thread.name,
                   exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = _thread_hook
    return root


def acquire_lock():
    """Refuse to start a second server.

    Two instances would both rewrite runtime.json and fight over the same ssh
    control sockets. An advisory lock beats a pid check because it is released
    by the kernel if the process dies, so a crash never leaves a stale claim.
    """
    global _lock_fh
    os.makedirs(paths.STATE_DIR, exist_ok=True)
    fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW |
                 os.O_NONBLOCK, 0o600)
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or
            st.st_nlink != 1):
        os.close(fd)
        raise RuntimeError("unsafe Fleet lock file")
    # Fleet 1.1.x created this app-owned file through the process umask, so an
    # otherwise-safe existing installation may have left it at 0644. Migrate
    # only the already descriptor-bound, user-owned regular file.
    if stat.S_IMODE(st.st_mode) & 0o077:
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    _lock_fh = os.fdopen(fd, "r+")
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EAGAIN):
            return False
        raise
    _lock_fh.seek(0)
    _lock_fh.truncate()
    _lock_fh.write(str(os.getpid()))
    _lock_fh.flush()
    return True


def launch_window(url, mode="webapp"):
    """Open the UI. Prefers Omarchy's own webapp launcher so the window lands
    with the right app-id for Hyprland rules and no browser chrome."""
    try:
        if mode == "webapp" and os.access(OMARCHY_WEBAPP, os.X_OK):
            subprocess.Popen([OMARCHY_WEBAPP, url], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "omarchy-launch-webapp"
        for browser, name in BROWSERS:
            if os.access(browser, os.X_OK):
                args = ([browser, "--app=" + url]
                        if name != "firefox" else [browser, url])
                subprocess.Popen(args, start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return name
        subprocess.Popen([XDG_OPEN, url], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "xdg-open"
    except Exception as e:
        return "failed: %s" % e


def write_runtime(port, token):
    import json
    target = os.path.join(paths.STATE_DIR, "runtime.json")
    temporary = os.path.join(paths.STATE_DIR, ".runtime.%s.tmp" % secrets.token_hex(12))
    data = (json.dumps({"port": port, "token": token, "pid": os.getpid(),
                        "started": int(time.time())}) + "\n").encode()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(temporary, target)
        dirfd = os.open(paths.STATE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main():
    ap = argparse.ArgumentParser(prog="fleet", description="VPS manager for Omarchy")
    ap.add_argument("--version", action="version", version="Fleet " + appmeta.VERSION)
    ap.add_argument("--port", type=int, default=0, help="bind port (default: ephemeral)")
    ap.add_argument("--no-open", action="store_true", help="do not launch a window")
    ap.add_argument("--browser", default="webapp",
                    choices=["webapp", "browser"], help="how to open the UI")
    ap.add_argument("--no-connect", action="store_true",
                    help="skip opening SSH connections at start")
    ap.add_argument("--debug", action="store_true",
                    help="verbose logging on the console, tracebacks in API errors")
    args = ap.parse_args()

    paths.ensure_dirs()
    if args.debug:
        os.environ["FLEET_DEBUG"] = "1"
    log = setup_logging(args.debug or bool(os.environ.get("FLEET_DEBUG")))

    if not acquire_lock():
        print("%s is already running. Use \033[1mfleet\033[0m to open its window, "
              "or \033[1mfleet stop\033[0m first." % BANNER, file=sys.stderr)
        return 1

    store.init()
    vpn.ensure_dirs()
    sshmgr.bootstrap()

    token = secrets.token_urlsafe(24)
    try:
        srv = httpd.serve(api.router, paths.WEB_DIR, token, port=args.port)
    except OSError as e:
        print("%s cannot bind port %s: %s" % (BANNER, args.port or "(any)", e),
              file=sys.stderr)
        log.error("bind failed: %s", e)
        return 1
    port = srv.server_address[1]
    # Chromium derives a Wayland app_id from the URL host, so a dedicated
    # *.localhost name (which resolves to 127.0.0.1 per spec) gives the window
    # a stable identity for Hyprland rules even on an ephemeral port.
    url = "http://fleet.localhost:%d/?t=%s" % (port, token)
    write_runtime(port, token)

    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # Same port on IPv6 loopback so http://fleet.localhost works whichever
    # family the browser resolves first.
    srv6 = httpd.serve_v6(api.router, paths.WEB_DIR, token, port)
    if srv6:
        threading.Thread(target=srv6.serve_forever, daemon=True).start()
    api.poller.start()
    api.ThemeWatcher().start()
    desktop_watcher = desktop.Watcher()
    desktop_watcher.start()

    n = len(hosts.load())
    log.info("started on 127.0.0.1:%d with %d host(s)", port, n)
    print("%s  \033[2mlistening on\033[0m 127.0.0.1:%d  \033[2mtheme\033[0m %s  "
          "\033[2mhosts\033[0m %d" % (BANNER, port, theme.current_name(), n))

    tunnels = [v for v in vpn.load() if v.get("auto")]
    if not args.no_connect and tunnels:
        print("   opening %d VPN tunnel%s..." % (len(tunnels),
                                                 "" if len(tunnels) == 1 else "s"))
        vpn.autostart()

    if not args.no_connect and hosts.settings().get("connect_on_start") and n:
        print("   opening %d SSH connection%s..." % (n, "" if n == 1 else "s"))
        sshmgr.connect_all(async_=True)

    if not args.no_open:
        how = launch_window(url, args.browser)
        print("   window: %s" % how)
    else:
        print("   open: %s" % url)

    stopping = threading.Event()

    def shutdown(*_):
        if stopping.is_set():
            return
        stopping.set()
        print("\n%s shutting down" % BANNER)
        log.info("shutting down")
        api.poller.stop_flag.set()
        desktop_watcher.stop_flag.set()
        for s in ptys.list_sessions():
            ptys.close_session(s["id"])
        # ssh masters and VPN tunnels are both left up deliberately: the
        # masters stay warm via ControlPersist, and a route you may still be
        # using should not disappear because a window closed.
        for server in filter(None, (srv, srv6)):
            threading.Thread(target=server.shutdown, daemon=True).start()
        try:
            os.unlink(os.path.join(paths.STATE_DIR, "runtime.json"))
        except OSError:
            pass

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        while not stopping.is_set():
            stopping.wait(5)
            ptys.reap()
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
