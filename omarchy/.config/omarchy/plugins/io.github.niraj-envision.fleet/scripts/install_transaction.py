#!/usr/bin/python3
"""Crash-consistent, descriptor-bound Fleet installer transaction."""

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import signal
import stat
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 2048
JOURNAL_VERSION = 1
MANIFEST_NAME = ".fleet-installed-files.json"


class SafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Fingerprint:
    existed: bool
    mode: int = 0
    uid: int = -1
    gid: int = -1
    dev: int = -1
    ino: int = -1
    size: int = -1
    mtime_ns: int = -1
    sha256: str = ""


@dataclass
class Change:
    path: str
    before: dict
    after: object
    backup: object
    desired_mode: int
    planned: object = None
    status: str = "prepared"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def home_path():
    raw = os.environ.get("HOME")
    if not raw or not os.path.isabs(raw):
        raise SafetyError("HOME must be an absolute path")
    home = Path(os.path.abspath(raw))
    expected = os.lstat(home)
    if not stat.S_ISDIR(expected.st_mode) or expected.st_uid != os.getuid():
        raise SafetyError("HOME must be a real directory owned by the current user")
    if expected.st_mode & 0o022:
        raise SafetyError("HOME must not be group/world writable")
    return home


def xdg_home(name, fallback):
    raw = os.environ.get(name)
    path = Path(raw) if raw else home_path() / fallback
    if not path.is_absolute():
        raise SafetyError("%s must be an absolute path" % name)
    require_under_home(path)
    return Path(os.path.abspath(path))


def require_under_home(path):
    home = home_path()
    absolute = Path(os.path.abspath(path))
    try:
        absolute.relative_to(home)
    except ValueError:
        raise SafetyError("Refusing path outside HOME: %s" % path)


def require_entry_name(name):
    if not name or name in (".", "..") or os.path.basename(name) != name:
        raise SafetyError("Unsafe directory entry name: %r" % name)


def open_directory_fd(path, create=False, mode=0o700):
    """Walk a HOME-relative directory through verified directory descriptors."""
    require_under_home(path)
    home = home_path()
    absolute = Path(os.path.abspath(path))
    parts = absolute.relative_to(home).parts
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    expected = os.lstat(home)
    fd = os.open(str(home), flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            raise SafetyError("HOME changed while opening")
        for part in parts:
            require_entry_name(part)
            try:
                child = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise SafetyError("Required directory does not exist: %s" % absolute)
                try:
                    os.mkdir(part, mode, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
                child = os.open(part, flags, dir_fd=fd)
            st = os.fstat(child)
            if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
                os.close(child)
                raise SafetyError("Unsafe directory in path: %s" % absolute)
            if st.st_mode & 0o022:
                os.close(child)
                raise SafetyError("Group/world-writable directory in path: %s" % absolute)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def secure_directory(path, create=False, mode=0o700):
    fd = open_directory_fd(path, create=create, mode=mode)
    os.close(fd)


def read_regular_at(dirfd, name, display_path, optional=False):
    require_entry_name(name)
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
             getattr(os, "O_NONBLOCK", 0))
    try:
        fd = os.open(name, flags, dir_fd=dirfd)
    except FileNotFoundError:
        if optional:
            return None, Fingerprint(False)
        raise SafetyError("Required file does not exist: %s" % display_path)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise SafetyError("Target is not a regular file: %s" % display_path)
        if st.st_uid != os.getuid() or st.st_nlink != 1:
            raise SafetyError("Target has unsafe ownership or links: %s" % display_path)
        if st.st_mode & 0o022:
            raise SafetyError("Target is group/world writable: %s" % display_path)
        if st.st_size > MAX_FILE_BYTES:
            raise SafetyError("Target exceeds %d bytes: %s" % (MAX_FILE_BYTES, display_path))
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise SafetyError("Target grew beyond the size limit: %s" % display_path)
        data = b"".join(chunks)
    finally:
        os.close(fd)
    return data, Fingerprint(True, stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid,
                             st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
                             digest(data))


def read_regular(path, optional=False):
    require_under_home(path)
    dirfd = open_directory_fd(Path(path).parent)
    try:
        return read_regular_at(dirfd, Path(path).name, path, optional=optional)
    finally:
        os.close(dirfd)


def current_fingerprint_at(dirfd, name, display_path):
    data, fp = read_regular_at(dirfd, name, display_path, optional=True)
    return fp if data is not None else Fingerprint(False)


def current_fingerprint(path):
    data, fp = read_regular(path, optional=True)
    return fp if data is not None else Fingerprint(False)


def planned_state(data, mode):
    if data is None:
        return {"existed": False, "mode": 0, "size": -1, "sha256": ""}
    return {"existed": True, "mode": mode, "size": len(data), "sha256": digest(data)}


def matches_planned(actual, planned):
    if not planned or actual.existed != bool(planned.get("existed")):
        return False
    if not actual.existed:
        return True
    return (actual.mode == int(planned.get("mode", -1)) and
            actual.size == int(planned.get("size", -1)) and
            actual.sha256 == str(planned.get("sha256", "")))


def matches_restored(actual, before):
    if actual.existed != before.existed:
        return False
    if not actual.existed:
        return True
    return (actual.mode == before.mode and actual.uid == before.uid and
            actual.size == before.size and actual.sha256 == before.sha256)


def verify_expected_at(dirfd, name, display_path, expected):
    actual = current_fingerprint_at(dirfd, name, display_path)
    if actual != expected:
        raise SafetyError("Concurrent change detected; refusing to replace %s" % display_path)


def atomic_replace(path, data, mode, expected):
    path = Path(path)
    require_under_home(path)
    dirfd = open_directory_fd(path.parent)
    temp_name = ".%s.fleet.%s.tmp" % (path.name, secrets.token_hex(12))
    try:
        verify_expected_at(dirfd, path.name, path, expected)
        if data is None:
            if expected.existed:
                os.unlink(path.name, dir_fd=dirfd)
                os.fsync(dirfd)
            return Fingerprint(False)
        fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), mode, dir_fd=dirfd)
        try:
            os.fchmod(fd, mode)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        verify_expected_at(dirfd, path.name, path, expected)
        os.replace(temp_name, path.name, src_dir_fd=dirfd, dst_dir_fd=dirfd)
        os.fsync(dirfd)
        return current_fingerprint_at(dirfd, path.name, path)
    finally:
        try:
            os.unlink(temp_name, dir_fd=dirfd)
        except FileNotFoundError:
            pass
        os.close(dirfd)


def write_new_regular_at(dirfd, name, data, mode):
    require_entry_name(name)
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), mode, dir_fd=dirfd)
    try:
        os.fchmod(fd, mode)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def checkpoint_journal(tx_dirfd, operation, state, changes):
    payload = {"version": JOURNAL_VERSION, "operation": operation, "state": state,
               "changes": [asdict(change) for change in changes]}
    data = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    temp = ".journal.%s.tmp" % secrets.token_hex(12)
    try:
        write_new_regular_at(tx_dirfd, temp, data, 0o600)
        os.replace(temp, "journal.json", src_dir_fd=tx_dirfd, dst_dir_fd=tx_dirfd)
        os.fsync(tx_dirfd)
    finally:
        try:
            os.unlink(temp, dir_fd=tx_dirfd)
        except FileNotFoundError:
            pass


def acquire_lock(state_dir):
    dirfd = open_directory_fd(state_dir, create=True)
    try:
        fd = os.open("install.lock", os.O_RDWR | os.O_CREAT |
                     getattr(os, "O_NOFOLLOW", 0) |
                     getattr(os, "O_NONBLOCK", 0), 0o600, dir_fd=dirfd)
    finally:
        os.close(dirfd)
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or
            st.st_nlink != 1 or stat.S_IMODE(st.st_mode) & 0o077):
        os.close(fd)
        raise SafetyError("Unsafe installer lock")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise SafetyError("Another Fleet install or recovery is already running")
    return fd


def state_directory():
    return xdg_home("XDG_STATE_HOME", ".local/state") / "fleet" / "installer"


def app_paths():
    home = home_path()
    data = xdg_home("XDG_DATA_HOME", ".local/share")
    config = xdg_home("XDG_CONFIG_HOME", ".config")
    return {
        "app": data / "fleet",
        "launcher": home / ".local/bin/fleet",
        "desktop": data / "applications/Fleet.desktop",
        "icon": data / "icons/hicolor/256x256/apps/fleet.png",
        "bindings": config / "hypr/bindings.lua",
        "hyprland": config / "hypr/hyprland.lua",
        "runtime": xdg_home("XDG_STATE_HOME", ".local/state") / "fleet/runtime.json",
    }


def acquire_application_lock(wait_seconds=5):
    """Keep Fleet stopped while its installed payload is being changed."""
    lock_path = xdg_home("XDG_STATE_HOME", ".local/state") / "fleet/fleet.lock"
    dirfd = open_directory_fd(lock_path.parent, create=True)
    try:
        fd = os.open(lock_path.name, os.O_RDWR | os.O_CREAT |
                     getattr(os, "O_NOFOLLOW", 0) |
                     getattr(os, "O_NONBLOCK", 0), 0o600, dir_fd=dirfd)
    finally:
        os.close(dirfd)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1:
        os.close(fd)
        raise SafetyError("Unsafe Fleet application lock")
    # Releases before 1.2.0 could create this app-owned lock at 0644. Tighten
    # only the descriptor-bound, user-owned, single-link regular file.
    if stat.S_IMODE(st.st_mode) & 0o077:
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise SafetyError("Fleet is still running or restarted during setup; retry")
            time.sleep(0.05)


def list_tree_files(root, skip_cache=False):
    """List regular files below root without following a pathname or link."""
    root = Path(root)
    try:
        rootfd = open_directory_fd(root)
    except SafetyError:
        if not os.path.lexists(root):
            return []
        raise
    out = []

    def walk(fd, prefix):
        for name in sorted(os.listdir(fd)):
            require_entry_name(name)
            if skip_cache and (name == "__pycache__" or name.endswith((".pyc", ".pyo"))):
                continue
            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            rel = prefix / name
            if stat.S_ISDIR(st.st_mode):
                child = os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) |
                                getattr(os, "O_NOFOLLOW", 0), dir_fd=fd)
                try:
                    opened = os.fstat(child)
                    if opened.st_uid != os.getuid() or opened.st_mode & 0o022:
                        raise SafetyError("Unsafe directory in managed tree: %s" % (root / rel))
                    walk(child, rel)
                finally:
                    os.close(child)
            elif stat.S_ISREG(st.st_mode):
                out.append(rel)
                if len(out) > MAX_FILES:
                    raise SafetyError("Managed tree exceeds %d files" % MAX_FILES)
            else:
                raise SafetyError("Special file in managed tree: %s" % (root / rel))

    try:
        walk(rootfd, Path())
    finally:
        os.close(rootfd)
    return out


BEGIN_BINDING = "-- BEGIN io.github.niraj-envision.fleet binding"
END_BINDING = "-- END io.github.niraj-envision.fleet binding"
BEGIN_WINDOW = "-- BEGIN io.github.niraj-envision.fleet window rule"
END_WINDOW = "-- END io.github.niraj-envision.fleet window rule"

BINDING_BODY = """-- BEGIN io.github.niraj-envision.fleet binding
-- Fleet starts the server on first run and focuses its existing window later.
o.bind("SUPER + SHIFT + V", "Fleet (VPS manager)", os.getenv("HOME") .. "/.local/bin/fleet")
-- END io.github.niraj-envision.fleet binding
"""

WINDOW_BODY = """-- BEGIN io.github.niraj-envision.fleet window rule
-- Fleet's SSH terminals must remain fully opaque inside its Chromium webapp.
local FLEET = { class = "^chrome-.*$", title = "^Fleet$" }
o.window(FLEET, { tag = "-chromium-based-browser" })
o.window(FLEET, { tag = "-default-opacity" })
o.window(FLEET, { opacity = "1.0 1.0" })
-- END io.github.niraj-envision.fleet window rule
"""

LEGACY_BINDING = """-- Fleet: the VPS manager -------------------------------------------------
-- `fleet` starts the server on first run and focuses the existing window
-- afterwards, so the same key always lands you in front of your servers.
o.bind("SUPER + SHIFT + V", "Fleet (VPS manager)", os.getenv("HOME") .. "/.local/bin/fleet")"""

LEGACY_WINDOW = """-- Fleet, the VPS manager (SUPER+SHIFT+V) ---------------------------------
-- Fleet runs as a Chromium web app, so Omarchy's browser rules tag it as a
-- browser and make it translucent. It is full of SSH terminals, where
-- see-through text over a wallpaper is genuinely hard to read, so drop both
-- opacity tags and pin it fully opaque.
--
-- Matched on title rather than class on purpose: Chromium opens web apps in
-- the already-running browser session, which ignores --class and derives the
-- Wayland app-id from the URL. That app-id is not stable, so the class alone
-- would silently stop matching. The title comes from Fleet's own <title>.
local FLEET = { class = "^chrome-.*$", title = "^Fleet$" }
o.window(FLEET, { tag = "-chromium-based-browser" })
o.window(FLEET, { tag = "-default-opacity" })
o.window(FLEET, { opacity = "1.0 1.0" })"""


def strip_managed(text, begin, end):
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == begin]
    stops = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == end]
    if not starts and not stops:
        return text
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise SafetyError("Malformed or duplicate Fleet managed markers")
    return "".join(lines[:starts[0]] + lines[stops[0] + 1:])


def strip_legacy(text, block):
    count = text.count(block)
    if count > 1:
        raise SafetyError("Duplicate legacy Fleet configuration block")
    return text.replace(block, "", 1) if count else text


def transform_config(text, begin, end, legacy, block, install):
    text = strip_managed(text, begin, end)
    text = strip_legacy(text, legacy)
    text = text.rstrip() + "\n"
    if install:
        text += "\n" + block
    return text


def source_file(repo_dir, relative):
    path = repo_dir / relative
    data, fp = read_regular(path)
    if data is None:
        raise SafetyError("Missing source file: %s" % path)
    mode = 0o755 if fp.mode & 0o111 else 0o644
    return data, mode


def build_operations(repo_dir, install, with_hypr):
    paths = app_paths()
    app = paths["app"]
    desired = {}
    if install:
        for directory in (app, paths["launcher"].parent, paths["desktop"].parent,
                          paths["icon"].parent):
            secure_directory(directory, create=True)
        source_relatives = [Path(name) for name in
                            ("fleet.py", "README.md", "CHANGELOG.md", "VERSION")]
        for tree in ("server", "web", "tests"):
            source_root = repo_dir / tree
            for rel in list_tree_files(source_root, skip_cache=True):
                source_relatives.append(Path(tree) / rel)
        for relative in source_relatives:
            target = app / relative
            secure_directory(target.parent, create=True)
            desired[target] = source_file(repo_dir, relative)
        manifest = {"version": 1, "files": [str(p) for p in sorted(source_relatives)]}
        desired[app / MANIFEST_NAME] = ((json.dumps(manifest, indent=2) + "\n").encode(), 0o600)
        desired[paths["launcher"]] = source_file(repo_dir, Path("bin/fleet"))
        desired[paths["desktop"]] = source_file(repo_dir, Path("share/applications/Fleet.desktop"))
        desired[paths["icon"]] = source_file(repo_dir, Path("share/icons/fleet.png"))
        existing = list_tree_files(app)
        for relative in existing:
            target = app / relative
            if target not in desired:
                desired[target] = (None, 0o600)
    else:
        existing = list_tree_files(app)
        desired = {app / relative: (None, 0o600) for relative in existing}
        for key, mode in (("launcher", 0o755), ("desktop", 0o644), ("icon", 0o644)):
            if os.path.lexists(paths[key].parent):
                desired[paths[key]] = (None, mode)

    if (install and with_hypr) or not install:
        specs = (("bindings", BEGIN_BINDING, END_BINDING, LEGACY_BINDING, BINDING_BODY),
                 ("hyprland", BEGIN_WINDOW, END_WINDOW, LEGACY_WINDOW, WINDOW_BODY))
        for key, begin, end, legacy, block in specs:
            target = paths[key]
            try:
                data, fp = read_regular(target, optional=True)
            except SafetyError:
                if not os.path.lexists(target.parent):
                    continue
                raise
            if data is None:
                continue
            transformed = transform_config(data.decode("utf-8"), begin, end,
                                           legacy, block, install).encode("utf-8")
            desired[target] = (transformed, fp.mode)

    operations = []
    for path in sorted(desired, key=lambda item: str(item)):
        data, mode = desired[path]
        before_data, before = read_regular(path, optional=True)
        if data is None and before_data is None:
            continue
        if data is not None and before_data == data and before.mode == mode:
            continue
        operations.append((path, before, data, mode))
    if len(operations) > MAX_FILES:
        raise SafetyError("Install plan exceeds %d files" % MAX_FILES)
    return operations


def write_backup(tx_dirfd, name, data, mode):
    write_new_regular_at(tx_dirfd, name, data, mode)
    return name


def fp_from_dict(value):
    return Fingerprint(**value)


def rollback_changes(tx_dir, changes, tx_dirfd, operation):
    for change in reversed(changes):
        path = Path(change.path)
        before = fp_from_dict(change.before)
        actual = current_fingerprint(path)
        if change.status == "rolled-back":
            if not matches_restored(actual, before):
                raise SafetyError("Rolled-back target changed: %s" % path)
            continue
        if change.status == "prepared":
            if actual != before:
                raise SafetyError("Unstarted target changed: %s" % path)
            change.status = "rolled-back"
            checkpoint_journal(tx_dirfd, operation, "rolling-back", changes)
            continue
        if change.status == "applying":
            if actual == before:
                change.status = "rolled-back"
                checkpoint_journal(tx_dirfd, operation, "rolling-back", changes)
                continue
            if not matches_planned(actual, change.planned):
                raise SafetyError("In-flight target has an unknown state: %s" % path)
        elif change.status == "rolling-back":
            if matches_restored(actual, before):
                change.status = "rolled-back"
                checkpoint_journal(tx_dirfd, operation, "rolling-back", changes)
                continue
            if change.after is not None and actual != fp_from_dict(change.after):
                raise SafetyError("Rollback target changed concurrently: %s" % path)
            if change.after is None and not matches_planned(actual, change.planned):
                raise SafetyError("Rollback target has an unknown state: %s" % path)
        elif change.status == "applied":
            if change.after is None or actual != fp_from_dict(change.after):
                raise SafetyError("Applied target changed; refusing rollback: %s" % path)
        else:
            raise SafetyError("Unknown transaction status %r" % change.status)

        change.status = "rolling-back"
        checkpoint_journal(tx_dirfd, operation, "rolling-back", changes)
        if before.existed:
            if not change.backup:
                raise SafetyError("Missing backup for %s" % path)
            data, unused = read_regular_at(tx_dirfd, change.backup,
                                           tx_dir / change.backup)
            atomic_replace(path, data, before.mode, actual)
        else:
            atomic_replace(path, None, change.desired_mode, actual)
        change.status = "rolled-back"
        checkpoint_journal(tx_dirfd, operation, "rolling-back", changes)
    checkpoint_journal(tx_dirfd, operation, "rolled-back", changes)


def parse_journal(tx_dir, tx_dirfd):
    data, unused = read_regular_at(tx_dirfd, "journal.json", tx_dir / "journal.json")
    payload = json.loads(data.decode("utf-8"))
    if payload.get("version") != JOURNAL_VERSION:
        raise SafetyError("Unsupported Fleet transaction journal")
    raw = payload.get("changes")
    if not isinstance(raw, list) or len(raw) > MAX_FILES:
        raise SafetyError("Invalid Fleet transaction plan")
    return payload, [Change(**item) for item in raw]


def rollback_locked(tx_dir, include_committed=True):
    expected = Path(os.path.abspath(state_directory() / "transactions"))
    tx_dir = Path(os.path.abspath(tx_dir))
    if tx_dir.parent != expected:
        raise SafetyError("Transaction is outside Fleet's transaction directory")
    txfd = open_directory_fd(tx_dir)
    try:
        payload, changes = parse_journal(tx_dir, txfd)
        if payload.get("state") == "rolled-back":
            return
        if payload.get("state") == "committed" and not include_committed:
            return
        rollback_changes(tx_dir, changes, txfd, str(payload.get("operation") or "unknown"))
    finally:
        os.close(txfd)


def rollback(tx_dir):
    lockfd = acquire_lock(state_directory())
    app_lockfd = None
    try:
        stop_running()
        app_lockfd = acquire_application_lock()
        rollback_locked(tx_dir)
    finally:
        if app_lockfd is not None:
            os.close(app_lockfd)
        os.close(lockfd)


def recover_pending():
    state = state_directory()
    lockfd = acquire_lock(state)
    root = state / "transactions"
    rootfd = open_directory_fd(root, create=True)
    app_lockfd = None
    try:
        pending = []
        for name in sorted(os.listdir(rootfd)):
            require_entry_name(name)
            st = os.stat(name, dir_fd=rootfd, follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode):
                raise SafetyError("Unexpected entry in Fleet transaction directory")
            txfd = open_directory_fd(root / name)
            try:
                journal, unused = read_regular_at(
                    txfd, "journal.json", root / name / "journal.json", optional=True)
                payload = None
                if journal is not None:
                    payload, unused = parse_journal(root / name, txfd)
            finally:
                os.close(txfd)
            # No target can be touched before the complete journal is durable,
            # so a transaction killed while staging backups needs no rollback.
            if journal is None:
                continue
            if payload.get("state") not in ("committed", "rolled-back"):
                pending.append(root / name)
        if pending:
            stop_running()
            app_lockfd = acquire_application_lock()
            for tx_dir in pending:
                rollback_locked(tx_dir, include_committed=False)
    finally:
        if app_lockfd is not None:
            os.close(app_lockfd)
        os.close(rootfd)
        os.close(lockfd)


def apply(repo_dir, install, with_hypr):
    operation = "install" if install else "uninstall"
    state = state_directory()
    lockfd = acquire_lock(state)
    app_lockfd = None
    try:
        stop_running()
        app_lockfd = acquire_application_lock()
        operations = build_operations(repo_dir, install, with_hypr)
        root = state / "transactions"
        rootfd = open_directory_fd(root, create=True)
        tx_name = "%s-%d-%s" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid(),
                                 secrets.token_hex(4))
        try:
            os.mkdir(tx_name, 0o700, dir_fd=rootfd)
            os.fsync(rootfd)
        finally:
            os.close(rootfd)
        tx_dir = root / tx_name
        txfd = open_directory_fd(tx_dir)
        changes = []
        journal_ready = False
        try:
            for index, (path, before, desired, mode) in enumerate(operations):
                original, verify = read_regular(path, optional=True)
                if verify != before:
                    raise SafetyError("Concurrent change before backup: %s" % path)
                backup = None
                if original is not None:
                    backup = write_backup(txfd, "%04d.original" % index,
                                          original, before.mode)
                changes.append(Change(str(path), asdict(before), None, backup, mode,
                                      planned_state(desired, mode), "prepared"))
            checkpoint_journal(txfd, operation, "prepared", changes)
            journal_ready = True
            print(tx_dir, flush=True)
            for change, (path, before, desired, mode) in zip(changes, operations):
                change.status = "applying"
                checkpoint_journal(txfd, operation, "applying", changes)
                after = atomic_replace(path, desired, mode, before)
                change.after = asdict(after)
                change.status = "applied"
                checkpoint_journal(txfd, operation, "applying", changes)
            checkpoint_journal(txfd, operation, "committed", changes)
            return tx_dir
        except BaseException:
            if journal_ready:
                rollback_changes(tx_dir, changes, txfd, operation)
            raise
        finally:
            os.close(txfd)
    finally:
        if app_lockfd is not None:
            os.close(app_lockfd)
        os.close(lockfd)


def stop_running():
    paths = app_paths()
    runtime = paths["runtime"]
    secure_directory(runtime.parent, create=True)
    data, fp = read_regular(runtime, optional=True)
    if data is None:
        return
    try:
        payload = json.loads(data.decode("utf-8"))
        pid = int(payload["pid"])
        if pid < 2:
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        raise SafetyError("Refusing malformed Fleet runtime file")
    proc = Path("/proc/%d" % pid)
    if proc.exists():
        try:
            owner = os.stat(proc).st_uid
            cmdline = (proc / "cmdline").read_bytes().split(b"\0")
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise SafetyError("Cannot verify the running Fleet process") from exc
        else:
            expected = str(paths["app"] / "fleet.py").encode()
            if owner != os.getuid() or expected not in cmdline:
                raise SafetyError("Runtime PID is not the expected Fleet process")
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 5
            while proc.exists() and current_fingerprint(runtime).existed and \
                    time.monotonic() < deadline:
                time.sleep(0.05)
            if proc.exists() and current_fingerprint(runtime).existed:
                raise SafetyError("Fleet did not stop within five seconds")
    actual = current_fingerprint(runtime)
    if not actual.existed:
        return
    if actual != fp:
        raise SafetyError("Fleet runtime changed while stopping; retry")
    atomic_replace(runtime, None, fp.mode, fp)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    install = sub.add_parser("install")
    install.add_argument("--repo-dir", required=True, type=Path)
    install.add_argument("--with-hypr", action="store_true")
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("--repo-dir", required=True, type=Path)
    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("transaction", type=Path)
    sub.add_parser("recover")
    sub.add_parser("stop")
    args = parser.parse_args()
    try:
        if args.command == "rollback":
            rollback(args.transaction)
        elif args.command == "recover":
            recover_pending()
        elif args.command == "stop":
            stop_running()
        else:
            repo = args.repo_dir.resolve(strict=True)
            secure_directory(repo)
            apply(repo, args.command == "install",
                  bool(getattr(args, "with_hypr", False)))
        return 0
    except (OSError, UnicodeError, ValueError, SafetyError, json.JSONDecodeError) as exc:
        print("fleet installer: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
