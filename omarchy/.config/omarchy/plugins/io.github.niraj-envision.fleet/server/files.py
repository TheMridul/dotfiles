"""Remote and local file browsing, transfer and editing.

Listing rides the same multiplexed SSH connection everything else uses, so
opening a directory costs one round trip. Transfers use `scp`, including
`scp -3` for VPS-to-VPS copies, which routes through this machine without
either server needing credentials for the other.

`this-computer` is a first-class location here, which is what makes one
clipboard cover remote->remote, remote->local and local->remote with a single
copy/paste model instead of three separate features.
"""
import os
import pwd
import grp
import shlex
import shutil
import stat as statmod
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import boundedproc
import sshmgr

LOCAL = "local"
TEXT_EDIT_LIMIT = 2 * 1024 * 1024        # refuse to open an "editor" on a blob
LIST_LIMIT = 5000


# --------------------------------------------------------------- listing

def remote_target(path):
    """Quote a path for the remote shell, keeping ~ meaningful.

    shlex.quote would turn `~` into a literal directory name, so the home
    shortcut is expanded to $HOME here instead -- outside the quotes, and
    nowhere else, so the rest of the path stays injection-safe.
    """
    path = (path or "~").strip() or "~"
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        return '"$HOME"/%s' % shlex.quote(path[2:])
    return shlex.quote(path)


def _list_script(path):
    """Portable one-shot directory listing.

    `stat -c` covers GNU coreutils and BusyBox, which is every Linux VPS in
    practice; `%N` is used for the name because it quotes, so spaces survive
    and symlink targets come back in the same field.
    """
    q = remote_target(path)
    return r"""
target=%s
cd -- "$target" 2>/dev/null || { printf '__ERR__\tnot a directory or not readable\n'; exit 2; }
printf '__PWD__\t%%s\n' "$(pwd -P)"
printf '__WHO__\t%%s\t%%s\n' "$(id -un)" "$(id -u)"
printf '__NOW__\t%%s\n' "$(date +%%s)"
df -Pk . 2>/dev/null | awk 'NR==2 {printf "__DF__\t%%s\t%%s\t%%s\n", $2, $3, $4}'
if command -v stat >/dev/null 2>&1; then
  find . -maxdepth 1 -mindepth 1 -exec stat -c 'E|%%s|%%Y|%%A|%%U|%%G|%%N' {} + 2>/dev/null
else
  ls -lA 2>/dev/null | awk 'NR>1 {printf "L|%%s\n", $0}'
fi
printf '__END__\n'
""" % q


def _parse_name(field):
    """GNU stat %N: 'name' or 'name' -> 'target'."""
    link = ""
    if "' -> '" in field:
        left, right = field.split("' -> '", 1)
        field = left + "'"
        link = right.rstrip("'")
    name = field.strip()
    if len(name) >= 2 and name[0] == "'" and name[-1] == "'":
        name = name[1:-1]
    if name.startswith("./"):
        name = name[2:]
    return name, link


def parse_listing(out):
    res = {"path": "", "entries": [], "df": None, "user": "", "uid": None,
           "error": "", "now": None}
    for line in out.splitlines():
        if line.startswith("__ERR__"):
            res["error"] = line.split("\t", 1)[-1]
        elif line.startswith("__PWD__"):
            res["path"] = line.split("\t", 1)[-1]
        elif line.startswith("__WHO__"):
            f = line.split("\t")
            res["user"] = f[1] if len(f) > 1 else ""
            res["uid"] = int(f[2]) if len(f) > 2 and f[2].isdigit() else None
        elif line.startswith("__NOW__"):
            # The host's own clock. Ages are computed against this rather than
            # the browser's, so a server whose clock differs from this machine
            # does not report files modified in the future.
            try:
                res["now"] = int(line.split("\t", 1)[-1])
            except ValueError:
                pass
        elif line.startswith("__DF__"):
            f = line.split("\t")
            if len(f) > 3:
                res["df"] = {"total": int(f[1]) * 1024, "used": int(f[2]) * 1024,
                             "avail": int(f[3]) * 1024}
        elif line.startswith("E|"):
            parts = line[2:].split("|", 5)
            if len(parts) < 6:
                continue
            size, mtime, perms, owner, group, namefield = parts
            name, link = _parse_name(namefield)
            if not name or name in (".", ".."):
                continue
            kind = ("dir" if perms.startswith("d") else
                    "link" if perms.startswith("l") else
                    "special" if perms[0] in "cbps" else "file")
            try:
                res["entries"].append({
                    "name": name, "kind": kind, "size": int(size),
                    "mtime": int(mtime), "perms": perms, "owner": owner,
                    "group": group, "link": link,
                    "exec": kind == "file" and "x" in perms[1:10],
                })
            except ValueError:
                continue
    res["truncated"] = len(res["entries"]) > LIST_LIMIT
    res["total"] = len(res["entries"])
    res["entries"] = res["entries"][:LIST_LIMIT]
    return res


def _local_listing(path):
    path = os.path.abspath(os.path.expanduser(path or "~"))
    res = {"path": path, "entries": [], "df": None, "error": "",
           "user": pwd.getpwuid(os.getuid()).pw_name, "uid": os.getuid(),
           "now": int(time.time())}
    try:
        names = os.listdir(path)
    except OSError as e:
        res["error"] = e.strerror or str(e)
        return res
    try:
        u = shutil.disk_usage(path)
        res["df"] = {"total": u.total, "used": u.used, "avail": u.free}
    except OSError:
        pass
    res["total"] = len(names)
    res["truncated"] = len(names) > LIST_LIMIT
    for n in names[:LIST_LIMIT]:
        full = os.path.join(path, n)
        try:
            st = os.lstat(full)
        except OSError:
            continue
        mode = st.st_mode
        kind = ("link" if statmod.S_ISLNK(mode) else
                "dir" if statmod.S_ISDIR(mode) else
                "file" if statmod.S_ISREG(mode) else "special")
        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except KeyError:
            owner = str(st.st_uid)
        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            group = str(st.st_gid)
        res["entries"].append({
            "name": n, "kind": kind, "size": st.st_size, "mtime": int(st.st_mtime),
            "perms": statmod.filemode(mode), "owner": owner, "group": group,
            "link": os.readlink(full) if kind == "link" else "",
            "exec": kind == "file" and bool(mode & 0o111),
        })
    return res


def listing(host, path):
    """List a directory on `host`, or locally when host is None."""
    if host is None:
        return _local_listing(path)
    rc, out, err = sshmgr.run_script(host, _list_script(path or "~"), timeout=45)
    res = parse_listing(out)
    if res["error"]:
        return res
    if rc != 0 and not res["entries"] and not res["path"]:
        res["error"] = (err or "listing failed").strip()[:300]
    return res


# ------------------------------------------------------------ operations

def _rpath(host, path):
    """Quote a path for whichever side it lives on."""
    return shlex.quote(os.path.expanduser(path)) if host is None else remote_target(path)


def _sh(host, cmd, timeout=60):
    if host is None:
        p = boundedproc.run(["/bin/sh", "-c", cmd], timeout=timeout,
                            stdout_limit=2 * 1024 * 1024, stderr_limit=256 * 1024)
        return p.returncode, p.stdout.decode(errors="replace"), p.stderr.decode(errors="replace")
    return sshmgr.run(host, cmd, timeout=timeout)


def mkdir(host, path):
    rc, _, err = _sh(host, "mkdir -p -- %s" % _rpath(host, path))
    return {"ok": rc == 0, "error": err.strip()}


def rename(host, src, dst):
    rc, _, err = _sh(host, "mv -n -- %s %s" % (_rpath(host, src), _rpath(host, dst)))
    return {"ok": rc == 0, "error": err.strip()}


def guard_delete(p):
    """Reject a path that is too dangerous to remove recursively.

    The first version of this checked `count("/") == 0` on an absolute path,
    which is never true -- so `/etc` and `/home` sailed through. The rule that
    actually matters is depth: a single-component absolute path is a system
    directory, never a thing you meant to select in a file browser.
    """
    p = (p or "").strip()
    if not p:
        return "empty path"
    if p in ("~", "~/", "/", "//", "."):
        return "refusing to delete %r" % p
    parts = [c for c in p.replace("~/", "", 1).split("/") if c and c != "."]
    if ".." in parts:
        return "refusing a path containing '..': %r" % p
    if p.startswith("/") and len([c for c in p.split("/") if c]) <= 1:
        return "refusing to delete the top-level directory %r" % p
    if not parts:
        return "refusing to delete %r" % p
    return None


def delete(host, paths):
    """Delete files or directories, recursively.

    Guards against an empty list becoming a bare `rm -rf`, and against any
    path shallow enough to be a system directory.
    """
    if not isinstance(paths, list) or len(paths) > 128:
        return {"ok": False, "error": "delete accepts at most 128 paths"}
    clean = []
    for p in paths or []:
        bad = guard_delete(p)
        if bad:
            return {"ok": False, "error": bad}
        clean.append(p.strip())
    if not clean:
        return {"ok": False, "error": "nothing selected"}
    rc, _, err = _sh(host, "rm -rf -- %s" % " ".join(_rpath(host, p) for p in clean),
                     timeout=300)
    return {"ok": rc == 0, "error": err.strip(), "deleted": len(clean)}


def chmod(host, path, mode):
    if not str(mode).isdigit():
        return {"ok": False, "error": "mode must be octal digits"}
    rc, _, err = _sh(host, "chmod %s -- %s" % (mode, _rpath(host, path)))
    return {"ok": rc == 0, "error": err.strip()}


def read_text(host, path, limit=TEXT_EDIT_LIMIT):
    """Read a file for the built-in editor, refusing binaries and huge files."""
    if host is None:
        try:
            if os.path.getsize(path) > limit:
                return {"ok": False, "error": "file is larger than %d bytes" % limit}
            with open(path, "rb") as fh:
                raw = fh.read(limit + 1)
        except OSError as e:
            return {"ok": False, "error": e.strerror or str(e)}
    else:
        rc, out, err = _sh(host, "head -c %d -- %s | base64" % (limit + 1, shlex.quote(path)),
                           timeout=90)
        if rc != 0:
            return {"ok": False, "error": err.strip() or "could not read file"}
        import base64
        try:
            raw = base64.b64decode(out)
        except Exception as e:
            return {"ok": False, "error": str(e)}
    if len(raw) > limit:
        return {"ok": False, "error": "file is larger than %d bytes" % limit}
    if b"\0" in raw[:8192]:
        return {"ok": False, "error": "looks like a binary file"}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return {"ok": True, "text": text, "bytes": len(raw)}


def write_text(host, path, text):
    """Write a file back, keeping a .bak of what was there before."""
    data = text.encode()
    if host is None:
        try:
            if os.path.exists(path):
                shutil.copy2(path, path + ".fleet.bak")
            with open(path, "wb") as fh:
                fh.write(data)
            return {"ok": True, "bytes": len(data)}
        except OSError as e:
            return {"ok": False, "error": e.strerror or str(e)}
    q = shlex.quote(path)
    argv = sshmgr.base_args(host) + [
        "--", "sh -c %s" % shlex.quote(
            "[ -f {p} ] && cp -p -- {p} {p}.fleet.bak; cat > {p}".format(p=q))]
    try:
        p = boundedproc.run(argv, input_data=data, timeout=180,
                            env=sshmgr.env_for(host), stdout_limit=65536,
                            stderr_limit=65536)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if p.returncode != 0:
        return {"ok": False, "error": p.stderr.decode(errors="replace").strip()}
    return {"ok": True, "bytes": len(data)}


# ------------------------------------------------------------- streaming

def stream_download(host, path, chunk=256 * 1024):
    """Yield a file's bytes without staging a temp copy on this machine."""
    if host is None:
        with open(path, "rb") as fh:
            while True:
                b = fh.read(chunk)
                if not b:
                    return
                yield b
    else:
        argv = sshmgr.base_args(host) + ["--", "cat -- %s" % shlex.quote(path)]
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             env=sshmgr.env_for(host))
        try:
            while True:
                b = p.stdout.read(chunk)
                if not b:
                    return
                yield b
        finally:
            try:
                p.stdout.close()
                p.terminate()
            except Exception:
                pass


def stream_download_dir(host, path, chunk=256 * 1024):
    """Stream a directory as a gzipped tar, so folders download in one click."""
    parent = os.path.dirname(path.rstrip("/")) or "/"
    base = os.path.basename(path.rstrip("/")) or "."
    cmd = "tar -czf - -C %s -- %s" % (shlex.quote(parent), shlex.quote(base))
    if host is None:
        p = subprocess.Popen(["/bin/sh", "-c", cmd], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL)
    else:
        p = subprocess.Popen(sshmgr.base_args(host) + ["--", cmd],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             env=sshmgr.env_for(host))
    try:
        while True:
            b = p.stdout.read(chunk)
            if not b:
                return
            yield b
    finally:
        try:
            p.stdout.close()
            p.terminate()
        except Exception:
            pass


def upload_stream(host, dest_path, reader, total=None):
    """Pipe an uploaded body straight to the destination file."""
    if host is None:
        try:
            with open(dest_path, "wb") as fh:
                n = 0
                while True:
                    b = reader(262144)
                    if not b:
                        break
                    fh.write(b)
                    n += len(b)
            return {"ok": True, "bytes": n}
        except OSError as e:
            return {"ok": False, "error": e.strerror or str(e)}
    argv = sshmgr.base_args(host) + ["--", "cat > %s" % shlex.quote(dest_path)]
    p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.PIPE, env=sshmgr.env_for(host))
    err_buf = bytearray()
    _drain(p.stderr, err_buf)
    n = 0
    try:
        while True:
            b = reader(262144)
            if not b:
                break
            p.stdin.write(b)
            n += len(b)
        p.stdin.close()
    except Exception as e:
        try:
            p.kill()
        except Exception:
            pass
        return {"ok": False, "error": str(e)}
    try:
        rc = p.wait(timeout=600)
    except subprocess.TimeoutExpired:
        p.kill()
        return {"ok": False, "error": "upload timed out"}
    if rc != 0:
        return {"ok": False,
                "error": bytes(err_buf).decode(errors="replace").strip() or "exit %d" % rc}
    return {"ok": True, "bytes": n}


# ------------------------------------------------------------- transfers

_home_cache = {}


def remote_home(host):
    if host is None:
        return os.path.expanduser("~")
    hid = host["id"]
    if hid not in _home_cache:
        rc, out, _ = _sh(host, 'printf %s "$HOME"', timeout=20)
        _home_cache[hid] = out.strip() if rc == 0 and out.strip() else "/root"
    return _home_cache[hid]


def abspath(host, path):
    """Resolve ~ to a real absolute path before any transfer touches it."""
    path = (path or "~").strip() or "~"
    if path == "~":
        return remote_home(host)
    if path.startswith("~/"):
        return remote_home(host).rstrip("/") + "/" + path[2:]
    return path


def total_size(host, paths):
    """Sum of the sources, so a progress bar has a denominator."""
    if not paths:
        return 0
    if host is None:
        n = 0
        for p in paths:
            if os.path.isdir(p):
                for root, _, fs in os.walk(p):
                    for f in fs:
                        try:
                            n += os.path.getsize(os.path.join(root, f))
                        except OSError:
                            pass
            else:
                try:
                    n += os.path.getsize(p)
                except OSError:
                    pass
        return n
    cmd = "du -sbc -- %s 2>/dev/null | tail -1 | cut -f1" % \
          " ".join(shlex.quote(p) for p in paths)
    rc, out, _ = _sh(host, cmd, timeout=120)
    try:
        return int(out.strip())
    except ValueError:
        return 0


class Job:
    def __init__(self, kind, label, total=0):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.label = label
        self.status = "running"        # running | done | error | cancelled
        self.total = total
        self.done = 0
        self.error = ""
        self.started = time.time()
        self.finished = None
        self.proc = []

    def info(self):
        el = (self.finished or time.time()) - self.started
        return {"id": self.id, "kind": self.kind, "label": self.label,
                "status": self.status, "total": self.total, "done": self.done,
                "error": self.error, "elapsed": round(el, 1),
                "rate": int(self.done / el) if el > 0.3 and self.done else 0,
                "pct": round(self.done / self.total * 100, 1) if self.total else None}

    def cancel(self):
        self.status = "cancelled"
        for p in self.proc:
            try:
                p.kill()
            except Exception:
                pass


_jobs = {}
_jobs_lock = threading.RLock()
_transfer_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fleet-transfer")
_on_progress = None          # set by the API layer to push over the websocket


def set_progress_hook(fn):
    global _on_progress
    _on_progress = fn


def get_job(jid):
    with _jobs_lock:
        return _jobs.get(jid)


def list_jobs():
    with _jobs_lock:
        js = sorted(_jobs.values(), key=lambda j: j.started, reverse=True)
    return [j.info() for j in js[:20]]


def _reap_jobs():
    with _jobs_lock:
        old = [i for i, j in _jobs.items()
               if j.finished and time.time() - j.finished > 600]
        for i in old:
            _jobs.pop(i, None)


def _drain(pipe, sink, cap=16384):
    """Consume a subprocess's stderr concurrently.

    Reading stderr only after pumping stdout deadlocks the moment the child
    writes more than one pipe buffer (~64KB) of warnings -- and `tar` is
    chatty about permissions and vanishing files. Draining it in parallel is
    the only safe shape.
    """
    def run():
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                if len(sink) < cap:
                    sink.extend(chunk[:cap - len(sink)])
        except Exception:
            pass
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _tar_producer(host, parent, names, job):
    cmd = "tar -cf - -C %s -- %s" % (shlex.quote(parent),
                                     " ".join(shlex.quote(n) for n in names))
    if host is None:
        p = subprocess.Popen(["/bin/sh", "-c", cmd], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(sshmgr.base_args(host) + ["--", cmd],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=sshmgr.env_for(host))
    job.proc.append(p)
    return p


def _tar_consumer(host, dest_dir, job):
    cmd = "mkdir -p -- {d} && tar -xf - -C {d}".format(d=shlex.quote(dest_dir))
    if host is None:
        p = subprocess.Popen(["/bin/sh", "-c", cmd], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        p = subprocess.Popen(sshmgr.base_args(host) + ["--", cmd],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=sshmgr.env_for(host))
    job.proc.append(p)
    return p


def transfer(src_host, src_paths, dst_host, dst_dir, move=False):
    """Copy paths from one location to another and return a Job.

    Everything goes through a single `tar` pipe pumped by this process, which
    is what lets one implementation cover local->remote, remote->local,
    remote->remote and local->local, preserve permissions and directory trees,
    and still report byte-accurate progress. `scp -3` would cover the remote
    pair but not the rest, and reports nothing.

    A same-host copy skips the pipe entirely and uses `cp -a`, which is an
    order of magnitude faster than a round trip through here.
    """
    if not isinstance(src_paths, list) or len(src_paths) > 128:
        raise ValueError("a transfer accepts at most 128 paths")
    src_paths = [abspath(src_host, p) for p in src_paths if p]
    dst_dir = abspath(dst_host, dst_dir)
    if not src_paths:
        raise ValueError("nothing to transfer")

    same_host = (src_host or {}).get("id") == (dst_host or {}).get("id") \
        if (src_host and dst_host) else (src_host is None and dst_host is None)

    label = "%s %d item%s -> %s" % ("Move" if move else "Copy", len(src_paths),
                                    "" if len(src_paths) == 1 else "s",
                                    (dst_host or {}).get("name", "this computer"))
    with _jobs_lock:
        active = sum(1 for item in _jobs.values() if not item.finished)
        if active >= 16:
            raise ValueError("too many active or queued transfers")
        job = Job("move" if move else "copy", label)
        _jobs[job.id] = job
    _reap_jobs()

    def emit():
        if _on_progress:
            try:
                _on_progress(job.info())
            except Exception:
                pass

    def finish(status, err=""):
        job.status = status
        job.error = err
        job.finished = time.time()
        emit()

    def work():
        try:
            # Same host: let the host do the copy itself.
            if same_host:
                op = "mv" if move else "cp -a"
                cmd = "mkdir -p -- {d} && {op} -- {s} {d}".format(
                    d=shlex.quote(dst_dir), op=op,
                    s=" ".join(shlex.quote(p) for p in src_paths))
                rc, _, err = _sh(src_host, cmd, timeout=3600)
                return finish("done" if rc == 0 else "error",
                              "" if rc == 0 else err.strip()[:400])

            job.total = total_size(src_host, src_paths)
            emit()

            # tar needs a common parent; group the sources by directory.
            groups = {}
            for p in src_paths:
                groups.setdefault(os.path.dirname(p.rstrip("/")) or "/", []).append(
                    os.path.basename(p.rstrip("/")))

            for parent, names in groups.items():
                if job.status == "cancelled":
                    return
                prod = _tar_producer(src_host, parent, names, job)
                cons = _tar_consumer(dst_host, dst_dir, job)
                perr_buf, cerr_buf = bytearray(), bytearray()
                dt = [_drain(prod.stderr, perr_buf), _drain(cons.stderr, cerr_buf)]
                try:
                    while True:
                        chunk = prod.stdout.read(262144)
                        if not chunk:
                            break
                        cons.stdin.write(chunk)
                        job.done += len(chunk)
                        if job.done % (2 * 1024 * 1024) < 262144:
                            emit()
                        if job.status == "cancelled":
                            prod.kill()
                            cons.kill()
                            return
                    cons.stdin.close()
                except BrokenPipeError:
                    pass
                prc, crc = prod.wait(), cons.wait()
                for t in dt:
                    t.join(2)
                perr = bytes(perr_buf).decode(errors="replace").strip()
                cerr = bytes(cerr_buf).decode(errors="replace").strip()
                # tar warns about a lot of harmless things; only a non-zero
                # exit on the receiving end is worth failing the whole job.
                if crc != 0:
                    return finish("error", (cerr or perr or "tar exit %d" % crc)[:400])
                if prc != 0 and not job.done:
                    return finish("error", (perr or "source read failed")[:400])

            if move:
                rc, _, err = _sh(src_host, "rm -rf -- %s" %
                                 " ".join(shlex.quote(p) for p in src_paths), timeout=600)
                if rc != 0:
                    return finish("error", "copied, but could not remove source: " + err[:200])
            finish("done")
        except Exception as e:
            finish("error", str(e)[:400])

    _transfer_pool.submit(work)
    return job
