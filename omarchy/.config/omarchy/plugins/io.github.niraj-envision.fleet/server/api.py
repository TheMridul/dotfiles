"""REST + WebSocket API, and the background poller that keeps it live."""
import json
import logging
import os
import queue
import shlex
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import blueprint
import appmeta
import desktop
import files
import hosts as hostreg
import netspeed
import probes
import ptys
import secretsvc
import sshmgr
import store
import theme
import vpn
from httpd import Raw, Router

log = logging.getLogger("fleet.api")
_started = time.time()

router = Router()

_metrics = {}            # host_id -> last parsed metrics
_metrics_lock = threading.RLock()
_event_clients = set()
_event_lock = threading.RLock()
_background = ThreadPoolExecutor(max_workers=12, thread_name_prefix="fleet-bg")


class EventClient:
    """A websocket with its own outbound queue and writer thread.

    Broadcasting straight onto the socket meant one stalled reader could block
    the poller for every host. Each client now absorbs its own backpressure,
    and a client that falls too far behind drops its oldest frames rather than
    slowing anyone else down -- metrics are a stream of current state, so the
    newest frame is the one worth keeping.
    """

    def __init__(self, ws):
        self.ws = ws
        self.q = queue.Queue(maxsize=256)
        self.alive = True
        self.dropped = 0
        threading.Thread(target=self._writer, daemon=True,
                         name="ws-writer").start()

    def send(self, msg):
        if not self.alive:
            return
        try:
            self.q.put_nowait(msg)
        except queue.Full:
            try:
                self.q.get_nowait()
                self.q.put_nowait(msg)
                self.dropped += 1
            except queue.Empty:
                pass

    def _writer(self):
        while True:
            msg = self.q.get()
            if msg is None or not self.alive:
                break
            try:
                self.ws.send(msg)
            except Exception:
                self.alive = False
                break
        self.alive = False

    def close(self):
        self.alive = False
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass
_focus = {"host_id": None}


# ------------------------------------------------------------- broadcasting

def broadcast(kind, payload):
    try:
        msg = json.dumps({"type": kind, "data": payload})
    except (TypeError, ValueError):
        log.exception("broadcast payload not serialisable: %s", kind)
        return
    with _event_lock:
        clients = list(_event_clients)
    for c in clients:
        c.send(msg)
        if not c.alive:
            with _event_lock:
                _event_clients.discard(c)


def last_metrics(host_id):
    with _metrics_lock:
        m = _metrics.get(host_id)
        return dict(m) if m else None


# ------------------------------------------------------------------ poller

class Poller(threading.Thread):
    """Polls every host on a cadence, faster for whichever host you're looking at.

    Metrics ride the existing master connection, so a poll is a ~40ms exec
    rather than a handshake. A host that fails twice in a row is marked offline
    and backed off, so a dead VPS cannot stall the loop for the live ones.
    """
    daemon = True

    def __init__(self):
        super().__init__(name="poller")
        self.stop_flag = threading.Event()
        self._next = {}
        self._fails = {}
        self._inflight = set()
        self._gate = threading.BoundedSemaphore(12)

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("poller tick failed")
            self.stop_flag.wait(0.5)

    def tick(self):
        s = hostreg.settings()
        now = time.time()
        # Tunnels are sampled here rather than on a thread of their own: it is
        # two file reads per live tunnel, and it keeps every "what is the state
        # of the world" broadcast on one clock.
        for st in vpn.refresh():
            broadcast("vpnstate", st)
        # Nobody is looking: keep state warm, but stop paying for it every few
        # seconds. The UI reconnecting triggers an immediate refresh anyway.
        watched = bool(_event_clients)
        for h in hostreg.load()[:64]:
            if len(self._inflight) >= 12:
                break
            hid = h["id"]
            if hid in self._inflight or now < self._next.get(hid, 0):
                continue
            active = watched and (_focus["host_id"] == hid)
            base = (s["poll_active_ms"] if active else s["poll_idle_ms"]) / 1000.0
            if not watched:
                base = max(base, 60.0)
            backoff = min(120.0, base * (2 ** self._fails.get(hid, 0)))
            self._next[hid] = now + backoff
            self._inflight.add(hid)
            _background.submit(self._poll_guarded, h)

    def _poll_guarded(self, h):
        try:
            with self._gate:
                self.poll_one(h)
        except Exception:
            log.exception("poll failed for %s", h.get("name"))
        finally:
            self._inflight.discard(h["id"])

    def poll_one(self, h):
        hid = h["id"]
        st = sshmgr.get_state(hid)
        if st["status"] not in ("online", "connecting"):
            if st["status"] == "error":
                return
        rc, out, err = sshmgr.run_script(h, probes.METRICS_SH, timeout=20)
        if rc != 0 or "__FLEET_END__" not in out:
            self._fails[hid] = min(6, self._fails.get(hid, 0) + 1)
            if self._fails[hid] >= 2 and st["status"] == "online":
                sshmgr.set_state(hid, status="offline",
                                 error=(err or "probe failed").strip()[:200])
                store.event(hid, "warn", "%s went offline" % h["name"])
                broadcast("hoststate", {"host_id": hid, "state": sshmgr.get_state(hid)})
            return

        if self._fails.get(hid):
            self._fails[hid] = 0
        if st["status"] != "online":
            sshmgr.set_state(hid, status="online", error="")
            store.event(hid, "info", "%s is online" % h["name"])
            broadcast("hoststate", {"host_id": hid, "state": sshmgr.get_state(hid)})

        with _metrics_lock:
            prev = _metrics.get(hid)
            m = probes.parse_metrics(out, prev)
            _metrics[hid] = m
        # CPU% is a delta between two samples, so the first poll after a connect
        # has nothing to compare against. Take the second one straight away
        # rather than making the user stare at a dash for a whole poll interval.
        if prev is None:
            self._next[hid] = time.time() + 1.0
        store.add_metric(hid, m)
        broadcast("metrics", {"host_id": hid, "metrics": _public_metrics(m)})


def _public_metrics(m):
    out = {k: v for k, v in m.items() if k != "raw"}
    return out


poller = Poller()

files.set_progress_hook(lambda info: broadcast("filejob", info))
netspeed.set_hook(lambda info: broadcast("speedtest", info))
desktop.set_hook(lambda info: broadcast("desktop", info))
vpn.set_hook(lambda info: broadcast("vpnstate", info))


class ThemeWatcher(threading.Thread):
    """Repaints the app when Omarchy's theme changes underneath it."""
    daemon = True

    def run(self):
        last = theme.stamp()
        while True:
            time.sleep(2)
            s = theme.stamp()
            if s != last:
                last = s
                broadcast("theme", theme.palette())


# ------------------------------------------------------------------- helpers

def _host_or_404(hid):
    h = hostreg.get(hid)
    if not h:
        raise ValueError("no such host: %s" % hid)
    return h


def _bounded_int(value, default, low, high):
    try:
        return max(low, min(int(value), high))
    except (TypeError, ValueError):
        return default


def _host_public(h):
    d = dict(h)
    d["has_password"] = secretsvc.has_secret("pw:" + h["id"])
    d["has_passphrase"] = secretsvc.has_secret("ph:" + h["id"])
    d["state"] = sshmgr.get_state(h["id"])
    d["metrics"] = _public_metrics(last_metrics(h["id"]) or {}) or None
    d["counts"] = store.index_counts(h["id"])
    d["speed"] = store.last_speedtest(h["id"])
    d["speed_running"] = netspeed.is_running(h["id"])
    if h.get("vpn"):
        prof = vpn.get(h["vpn"])
        d["vpn_name"] = prof["name"] if prof else ""
        # Whether the tunnel is *carrying* this host, not merely running: the
        # routing table is the only thing that actually knows.
        d["vpn_routed"] = bool(prof) and \
            vpn.route_dev(h.get("hostname") or "") == vpn.iface_name(prof)
    return d


# --------------------------------------------------------------- core state

@router.route("GET", "state")
def api_state(h, a, b, q):
    hs = [_host_public(x) for x in hostreg.load()]
    return {"hosts": hs, "settings": hostreg.settings(), "theme": theme.palette(),
            "desktop": desktop.snapshot(),
            "sessions": ptys.list_sessions(), "icons": hostreg.ICONS,
            "secret_backend": secretsvc.backend_name(),
            "vpns": [_vpn_public(v) for v in vpn.load()],
            "vpn_tooling": vpn.tooling(),
            "events": store.recent_events(30)}


@router.route("GET", "theme")
def api_theme(h, a, b, q):
    return theme.palette()


@router.route("GET", "desktop")
def api_desktop(h, a, b, q):
    return desktop.snapshot()


@router.route("GET", "settings")
def api_get_settings(h, a, b, q):
    return hostreg.settings()


@router.route("POST", "settings")
def api_set_settings(h, a, b, q):
    return hostreg.save_settings(b)


@router.route("POST", "focus")
def api_focus(h, a, b, q):
    _focus["host_id"] = b.get("host_id")
    return {"ok": True}


# ------------------------------------------------------------------- hosts

_NAME_OK = __import__("re").compile(r"^[^\x00-\x1f]{1,60}$")


def validate_host(b, existing=None):
    """Check a host before it reaches ssh_config. Returns an error string.

    Values here become directives in a file ssh executes, so a rejection with
    a clear reason is far better than a silent fallback that produces a host
    which simply never connects.
    """
    name = (b.get("name") or "").strip()
    if name and not _NAME_OK.match(name):
        return "Name contains control characters"
    host = (b.get("hostname") or "").strip()
    if not host:
        return "Hostname or IP is required"
    if not sshmgr.cfg_value(host):
        return ("Hostname %r is not valid — it may only contain letters, digits "
                "and . : @ / _ - [ ]" % host[:60])
    user = (b.get("user") or "root").strip()
    if not sshmgr.cfg_value(user):
        return "User %r is not a valid username" % user[:40]
    try:
        port = int(b.get("port") or 22)
    except (TypeError, ValueError):
        return "Port must be a number"
    if not 1 <= port <= 65535:
        return "Port must be between 1 and 65535"
    auth = b.get("auth", "agent")
    if auth not in ("agent", "key", "password"):
        return "Unknown authentication mode %r" % auth
    if auth == "key":
        ident = (b.get("identity_file") or "").strip()
        if not ident:
            return "Choose a private key, or switch to agent authentication"
        if not sshmgr.cfg_value(ident, allow_spaces=True):
            return "Key path %r contains characters ssh_config cannot express" % ident[:60]
        if not os.path.isfile(os.path.expanduser(ident)):
            return "No such key file: %s" % ident
    if auth == "password":
        has = b.get("password") or (existing and
                                    secretsvc.has_secret("pw:" + existing["id"]))
        if not has:
            return "A password is required for password authentication"
    jump = (b.get("proxy_jump") or "").strip()
    if jump and not sshmgr.cfg_value(jump):
        return "Jump host %r is not valid" % jump[:60]
    tunnel = (b.get("vpn") or "").strip()
    if tunnel and not vpn.get(tunnel):
        return "That VPN profile no longer exists"
    return None

@router.route("GET", "hosts")
def api_hosts(h, a, b, q):
    return [_host_public(x) for x in hostreg.load()]


@router.route("POST", "hosts")
def api_add_host(h, a, b, q):
    err = validate_host(b)
    if err:
        return (400, {"error": err})
    pw = b.pop("password", None)
    ph = b.pop("passphrase", None)
    host = hostreg.upsert(b)
    if pw:
        secretsvc.set_secret("pw:" + host["id"], pw)
    if ph:
        secretsvc.set_secret("ph:" + host["id"], ph)
    sshmgr.write_ssh_config()
    store.event(host["id"], "info", "Added host %s" % host["name"])
    _background.submit(sshmgr.connect, host)
    return _host_public(host)


@router.route("PUT", "hosts/:id")
def api_update_host(h, a, b, q):
    old = _host_or_404(a[0])
    err = validate_host(b, existing=old)
    if err:
        return (400, {"error": err})
    pw = b.pop("password", None)
    ph = b.pop("passphrase", None)
    b["id"] = a[0]
    host = hostreg.upsert(b)
    if pw is not None:
        secretsvc.set_secret("pw:" + host["id"], pw or None)
    if ph is not None:
        secretsvc.set_secret("ph:" + host["id"], ph or None)
    sshmgr.write_ssh_config()
    # Connection parameters changed -- the old master now points somewhere else.
    if any(old.get(k) != host.get(k) for k in
           ("hostname", "user", "port", "auth", "identity_file", "proxy_jump")):
        sshmgr.disconnect(old)
        _background.submit(sshmgr.connect, host)
    return _host_public(host)


@router.route("DELETE", "hosts/:id")
def api_delete_host(h, a, b, q):
    host = _host_or_404(a[0])
    ptys.close_for_host(host["id"])
    sshmgr.disconnect(host)
    secretsvc.set_secret("pw:" + host["id"], None)
    secretsvc.set_secret("ph:" + host["id"], None)
    hostreg.delete(host["id"])
    store.forget_host(host["id"])
    sshmgr.write_ssh_config()
    return {"ok": True}


@router.route("POST", "hosts/reorder")
def api_reorder(h, a, b, q):
    return hostreg.reorder(b.get("ids") or [])


@router.route("POST", "hosts/import")
def api_import(h, a, b, q):
    added = hostreg.import_ssh_config()
    sshmgr.write_ssh_config()
    for x in added[:64]:
        _background.submit(sshmgr.connect, x)
    return {"added": added}


@router.route("GET", "hosts/preview-import")
def api_preview_import(h, a, b, q):
    return {"hosts": hostreg.parse_ssh_config()}


@router.route("POST", "hosts/:id/connect")
def api_connect(h, a, b, q):
    host = _host_or_404(a[0])
    st = sshmgr.connect(host, force=bool(b.get("force")))
    broadcast("hoststate", {"host_id": host["id"], "state": st})
    return st


@router.route("POST", "hosts/:id/disconnect")
def api_disconnect(h, a, b, q):
    host = _host_or_404(a[0])
    ptys.close_for_host(host["id"])
    st = sshmgr.disconnect(host)
    broadcast("hoststate", {"host_id": host["id"], "state": st})
    return st


# ---------------------------------------------------------------- metrics

@router.route("GET", "hosts/:id/metrics")
def api_metrics(h, a, b, q):
    host = _host_or_404(a[0])
    m = last_metrics(host["id"])
    if not m:
        rc, out, err = sshmgr.run_script(host, probes.METRICS_SH, timeout=20)
        if rc == 0:
            m = probes.parse_metrics(out)
            with _metrics_lock:
                _metrics[host["id"]] = m
    return _public_metrics(m or {})


@router.route("GET", "hosts/:id/series")
def api_series(h, a, b, q):
    try:
        n = max(1, min(int(q.get("n", [120])[0]), 1000))
    except (TypeError, ValueError):
        return (400, {"error": "invalid series length"})
    return {"series": store.metric_series(a[0], n)}


# -------------------------------------------------------------- inventory

@router.route("GET", "hosts/:id/inventory")
def api_inventory(h, a, b, q):
    host = _host_or_404(a[0])
    ttl = hostreg.settings()["inventory_ttl_s"]
    age = store.inventory_age(host["id"])
    force = q.get("refresh", ["0"])[0] == "1"
    if force or age is None or age > ttl:
        rc, out, err = sshmgr.run_script(host, probes.INVENTORY_SH, timeout=180)
        if rc != 0 and not out.strip():
            return (502, {"error": err.strip() or "inventory probe failed"})
        inv = probes.parse_inventory(out)
        store.save_inventory(host["id"], inv)
        rc2, hout, _ = sshmgr.run_script(
            host, probes.HISTORY_SH % hostreg.settings()["history_mine_limit"], timeout=30)
        if rc2 == 0 and hout.strip():
            store.save_freq(host["id"], probes.parse_history(hout, 40))
        broadcast("inventory", {"host_id": host["id"],
                                "counts": store.index_counts(host["id"])})
    return store.get_inventory(host["id"]) or {}


@router.route("GET", "hosts/:id/commands")
def api_commands(h, a, b, q):
    return {"top": store.top_commands(a[0], 40),
            "runs": store.recent_runs(a[0], 30),
            "snippets": store.list_snippets()}


# ------------------------------------------------------------------- exec

@router.route("POST", "hosts/:id/run")
def api_run(h, a, b, q):
    host = _host_or_404(a[0])
    cmd = (b.get("command") or "").strip()
    if not cmd:
        return (400, {"error": "empty command"})
    t0 = time.time()
    try:
        timeout = max(1, min(int(b.get("timeout", 120)), 300))
    except (TypeError, ValueError):
        return (400, {"error": "invalid timeout"})
    rc, out, err = sshmgr.run(host, cmd, timeout=timeout)
    ms = int((time.time() - t0) * 1000)
    combined = (out + ("\n" + err if err else "")).strip()
    rid = store.add_run(host["id"], cmd, rc, ms, combined, b.get("label", ""))
    return {"id": rid, "rc": rc, "ms": ms, "stdout": out, "stderr": err}


@router.route("GET", "runs/:id")
def api_run_output(h, a, b, q):
    r = store.run_output(a[0])
    return r or (404, {"error": "no such run"})


@router.route("POST", "fanout")
def api_fanout(h, a, b, q):
    """Run one command across many hosts at once, in parallel."""
    cmd = (b.get("command") or "").strip()
    ids = list(dict.fromkeys(b.get("host_ids") or []))
    if not cmd or not ids:
        return (400, {"error": "command and host_ids required"})
    if len(ids) > 32 or not all(isinstance(i, str) and len(i) <= 128 for i in ids):
        return (400, {"error": "fanout accepts at most 32 valid host ids"})
    try:
        timeout = max(1, min(int(b.get("timeout", 120)), 300))
    except (TypeError, ValueError):
        return (400, {"error": "invalid timeout"})
    results, lock = {}, threading.Lock()

    def work(hid):
        try:
            host = _host_or_404(hid)
            t0 = time.time()
            rc, out, err = sshmgr.run(host, cmd, timeout=timeout)
            ms = int((time.time() - t0) * 1000)
            store.add_run(hid, cmd, rc, ms, (out + err)[:20000], "fanout")
            r = {"rc": rc, "ms": ms, "stdout": out, "stderr": err, "name": host["name"]}
        except Exception as e:
            r = {"rc": -1, "ms": 0, "stdout": "", "stderr": str(e), "name": hid}
        with lock:
            results[hid] = r

    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="fleet-fanout") as pool:
        list(pool.map(work, ids))
    return {"results": results, "command": cmd}


@router.route("POST", "hosts/:id/pkg")
def api_pkg(h, a, b, q):
    """Package actions run in a visible terminal, never silently in the background."""
    host = _host_or_404(a[0])
    inv = store.get_inventory(host["id"]) or {}
    mgr = b.get("pkgmgr") or inv.get("pkgmgr") or ""
    cmd = probes.pkg_command(b.get("action", "install"), mgr,
                             b.get("pkgs") or [], b.get("query"))
    if not cmd:
        return (400, {"error": "unknown package manager %r" % mgr})
    if b.get("dry_run"):
        return {"command": cmd}
    s = ptys.open_session(host, _bounded_int(b.get("cols"), 100, 20, 500),
                          _bounded_int(b.get("rows"), 30, 5, 200),
                          command=cmd, title="%s %s" % (b.get("action"),
                                                        " ".join(b.get("pkgs") or [])[:30]))
    store.event(host["id"], "info", "%s: %s" % (b.get("action"), " ".join(b.get("pkgs") or [])))
    return {"session": s.info(), "command": cmd}


@router.route("POST", "hosts/:id/service")
def api_service(h, a, b, q):
    host = _host_or_404(a[0])
    name, action = b.get("name", ""), b.get("action", "status")
    if action not in ("start", "stop", "restart", "status", "enable", "disable"):
        return (400, {"error": "bad action"})
    cmd = "systemctl %s %s" % (action, shlex.quote(name))
    if action != "status":
        cmd = "sudo -n %s || sudo %s" % (cmd, cmd)
    else:
        cmd = "systemctl status --no-pager -l %s | head -40" % shlex.quote(name)
    t0 = time.time()
    rc, out, err = sshmgr.run(host, cmd, timeout=45)
    return {"rc": rc, "stdout": out, "stderr": err,
            "ms": int((time.time() - t0) * 1000)}


# ----------------------------------------------------------------- search

@router.route("GET", "search")
def api_search(h, a, b, q):
    term = str(q.get("q", [""])[0])[:256]
    kinds = [str(kind)[:32] for kind in (q.get("kind") or [])[:16]]
    limit = _bounded_int(q.get("limit", [80])[0], 80, 1, 200)
    rows = store.search(term, kinds=kinds, limit=limit)
    names = {x["id"]: x for x in hostreg.load()}
    for r in rows:
        hh = names.get(r["host_id"])
        r["host_name"] = hh["name"] if hh else r["host_id"]
        r["host_icon"] = hh["icon"] if hh else "?"
        r["host_color"] = hh["color"] if hh else "blue"
    return {"results": rows, "query": term}


# --------------------------------------------------------------- snippets

@router.route("GET", "snippets")
def api_snippets(h, a, b, q):
    return {"snippets": store.list_snippets()}


@router.route("POST", "snippets")
def api_save_snippet(h, a, b, q):
    return {"id": store.save_snippet(b)}


@router.route("DELETE", "snippets/:id")
def api_del_snippet(h, a, b, q):
    store.delete_snippet(a[0])
    return {"ok": True}


# ------------------------------------------------------------- blueprints

@router.route("GET", "blueprints")
def api_blueprints(h, a, b, q):
    return {"blueprints": store.list_blueprints()}


@router.route("POST", "blueprints/capture")
def api_capture(h, a, b, q):
    host = _host_or_404(b.get("host_id"))
    inv = store.get_inventory(host["id"])
    if not inv:
        rc, out, _ = sshmgr.run_script(host, probes.INVENTORY_SH, timeout=180)
        inv = probes.parse_inventory(out)
        store.save_inventory(host["id"], inv)
    extras = blueprint.collect_extras(host, sshmgr)
    spec = blueprint.capture(host, inv, extras,
                             include=b.get("categories"),
                             manual_only=b.get("manual_only", True))
    bid = store.save_blueprint({"name": b.get("name") or ("%s blueprint" % host["name"]),
                                "source_host": host["id"], "source_name": host["name"],
                                "spec": spec, "notes": b.get("notes", "")})
    store.event(host["id"], "info", "Captured blueprint from %s" % host["name"])
    return store.get_blueprint(bid)


@router.route("DELETE", "blueprints/:id")
def api_del_blueprint(h, a, b, q):
    store.delete_blueprint(a[0])
    return {"ok": True}


@router.route("POST", "blueprints/:id/plan")
def api_plan(h, a, b, q):
    bp = store.get_blueprint(a[0])
    if not bp:
        return (404, {"error": "no such blueprint"})
    target = _host_or_404(b.get("target"))
    inv = store.get_inventory(target["id"])
    if not inv:
        rc, out, _ = sshmgr.run_script(target, probes.INVENTORY_SH, timeout=180)
        inv = probes.parse_inventory(out)
        store.save_inventory(target["id"], inv)
    extras = blueprint.collect_extras(target, sshmgr)
    cats = b.get("categories")
    planned = blueprint.plan(bp["spec"], inv, extras, cats)
    script = blueprint.build_script(planned, inv.get("pkgmgr", ""), cats,
                                    dry_run=bool(b.get("dry_run")))
    return {"plan": planned, "script": script, "target": target["name"],
            "target_pkgmgr": inv.get("pkgmgr", ""), "target_os": inv.get("os", "")}


@router.route("POST", "blueprints/:id/apply")
def api_apply(h, a, b, q):
    """Apply runs in a real terminal so you watch it happen and can Ctrl-C it."""
    target = _host_or_404(b.get("target"))
    script = b.get("script")
    if not script:
        return (400, {"error": "script required -- plan first"})
    remote = "/tmp/fleet-blueprint-%d.sh" % int(time.time())
    rc, out, err = sshmgr.run(
        target, "cat > %s && chmod +x %s" % (remote, remote),
        timeout=60, input_data=script)
    if rc != 0:
        return (502, {"error": err or "could not upload script"})
    s = ptys.open_session(target, _bounded_int(b.get("cols"), 100, 20, 500),
                          _bounded_int(b.get("rows"), 30, 5, 200),
                          command="bash %s; rc=$?; rm -f %s; exit $rc" % (remote, remote),
                          title="blueprint → %s" % target["name"])
    store.event(target["id"], "info", "Applying blueprint to %s" % target["name"])
    return {"session": s.info()}


# ------------------------------------------------------------- speed test

@router.route("POST", "hosts/:id/speedtest")
def api_speedtest(h, a, b, q):
    host = _host_or_404(a[0])
    preset = b.get("preset", "normal")
    if preset not in netspeed.PRESETS:
        return (400, {"error": "unknown preset %r" % preset})
    return netspeed.run(host, sshmgr, preset)


@router.route("GET", "hosts/:id/speedtest")
def api_speedtest_last(h, a, b, q):
    return {"last": store.last_speedtest(a[0]),
            "history": store.speedtest_history(a[0], 12),
            "running": netspeed.is_running(a[0]),
            "presets": {k: {"down_mb": v[0] + netspeed.PROBE_MB * len(netspeed.SOURCES),
                            "up_mb": v[1]}
                        for k, v in netspeed.PRESETS.items()}}


# ------------------------------------------------------------------ files

def _loc(host_id):
    """Resolve a browser location id to a host dict, or None for this machine."""
    if not host_id or host_id in ("local", "this-computer"):
        return None
    return _host_or_404(host_id)


@router.route("GET", "files/list")
def api_files_list(h, a, b, q):
    host = _loc(q.get("host", [""])[0])
    return files.listing(host, q.get("path", ["~"])[0])


@router.route("POST", "files/mkdir")
def api_files_mkdir(h, a, b, q):
    return files.mkdir(_loc(b.get("host")), b.get("path", ""))


@router.route("POST", "files/rename")
def api_files_rename(h, a, b, q):
    return files.rename(_loc(b.get("host")), b.get("src", ""), b.get("dst", ""))


@router.route("POST", "files/delete")
def api_files_delete(h, a, b, q):
    host = _loc(b.get("host"))
    res = files.delete(host, b.get("paths") or [])
    if res.get("ok"):
        store.event(b.get("host", ""), "warn",
                    "Deleted %d item(s) on %s" % (res.get("deleted", 0),
                                                  (host or {}).get("name", "this computer")))
    return res


@router.route("POST", "files/chmod")
def api_files_chmod(h, a, b, q):
    return files.chmod(_loc(b.get("host")), b.get("path", ""), b.get("mode", ""))


@router.route("GET", "files/read")
def api_files_read(h, a, b, q):
    return files.read_text(_loc(q.get("host", [""])[0]), q.get("path", [""])[0])


@router.route("POST", "files/write")
def api_files_write(h, a, b, q):
    return files.write_text(_loc(b.get("host")), b.get("path", ""), b.get("text", ""))


@router.route("GET", "files/download")
def api_files_download(h, a, b, q):
    """Stream a file -- or a directory as a tar.gz -- to the browser."""
    host = _loc(q.get("host", [""])[0])
    path = q.get("path", [""])[0]
    if not path:
        return (400, {"error": "path required"})
    name = os.path.basename(path.rstrip("/")) or "download"
    if q.get("dir", ["0"])[0] == "1":
        return Raw(files.stream_download_dir(host, path),
                   "application/gzip", name + ".tar.gz")
    size = None
    try:
        candidate = int(q.get("size", [""])[0])
        size = candidate if 0 <= candidate <= 10 * 1024 * 1024 * 1024 else None
    except (ValueError, IndexError):
        pass
    return Raw(files.stream_download(host, path),
               "application/octet-stream", name, length=size)


@router.route("POST", "files/upload")
def api_files_upload(h, a, b, q):
    """Pipe a raw request body straight into a file on the target."""
    host = _loc(q.get("host", [""])[0])
    dest = q.get("path", [""])[0]
    if not dest:
        return (400, {"error": "path required"})
    remaining = [int(b.get("_length") or 0)]

    def reader(n):
        if remaining[0] <= 0:
            return b""
        chunk = h.rfile.read(min(n, remaining[0]))
        remaining[0] -= len(chunk)
        return chunk

    res = files.upload_stream(host, files.abspath(host, dest), reader)
    if remaining[0] != 0:
        return (400, {"error": "request body ended before Content-Length"})
    if res.get("ok"):
        store.event(q.get("host", [""])[0], "info",
                    "Uploaded %s (%d bytes)" % (os.path.basename(dest), res["bytes"]))
    return res


@router.route("POST", "files/transfer")
def api_files_transfer(h, a, b, q):
    """Paste: copy or move paths between any two locations."""
    src = _loc(b.get("src_host"))
    dst = _loc(b.get("dst_host"))
    try:
        job = files.transfer(src, b.get("paths") or [], dst,
                             b.get("dst_dir", "~"), move=bool(b.get("move")))
    except ValueError as e:
        return (400, {"error": str(e)})
    return job.info()


@router.route("GET", "files/jobs")
def api_files_jobs(h, a, b, q):
    return {"jobs": files.list_jobs()}


@router.route("POST", "files/jobs/:id/cancel")
def api_files_cancel(h, a, b, q):
    job = files.get_job(a[0])
    if not job:
        return (404, {"error": "no such job"})
    job.cancel()
    return job.info()


# ---------------------------------------------------------------- sessions

@router.route("GET", "sessions")
def api_sessions(h, a, b, q):
    return {"sessions": ptys.list_sessions()}


@router.route("POST", "sessions")
def api_new_session(h, a, b, q):
    local = bool(b.get("local"))
    host = {"id": "local", "name": "local"} if local else _host_or_404(b.get("host_id"))
    s = ptys.open_session(host, _bounded_int(b.get("cols"), 100, 20, 500),
                          _bounded_int(b.get("rows"), 30, 5, 200),
                          command=b.get("command"), title=b.get("title"), local=local)
    return s.info()


@router.route("DELETE", "sessions/:id")
def api_close_session(h, a, b, q):
    return {"closed": ptys.close_session(a[0])}


# -------------------------------------------------------------- keys/auth

@router.route("GET", "keys")
def api_keys(h, a, b, q):
    return {"keys": sshmgr.list_local_keys()}


@router.route("POST", "keys/generate")
def api_genkey(h, a, b, q):
    return sshmgr.generate_key(b.get("name") or "id_ed25519_fleet", b.get("comment"))


@router.route("POST", "hosts/:id/install-key")
def api_installkey(h, a, b, q):
    host = _host_or_404(a[0])
    res = sshmgr.install_key(host, b.get("key_path"))
    if res.get("ok"):
        store.event(host["id"], "info", "Installed key on %s" % host["name"])
    return res


# -------------------------------------------------------------------- vpn

def _vpn_or_404(vid):
    v = vpn.get(vid)
    if not v:
        raise ValueError("no such VPN: %s" % vid)
    return v


def _vpn_public(v):
    d = dict(v)
    d["status"] = vpn.status(v["id"]) or {}
    # The username is not a secret and the editor needs it to round-trip; the
    # password and passphrase are reported only as "present".
    d["username"] = secretsvc.get_secret("vpnuser:" + v["id"]) or ""
    d["has_password"] = secretsvc.has_secret("vpnpass:" + v["id"])
    d["has_passphrase"] = secretsvc.has_secret("vpnkey:" + v["id"])
    d["hosts"] = [h["name"] for h in hostreg.load() if h.get("vpn") == v["id"]]
    # Where it will actually connect: the card shows this rather than the
    # config's own `remote`, because with an override they differ.
    d["effective_remotes"] = vpn.effective_remotes(v)
    d["overridden"] = vpn.has_override(v)
    return d


def _vpn_creds(vpn_id, b):
    """Move credentials out of the request body and into the keyring."""
    for field, key in (("username", "vpnuser:"), ("password", "vpnpass:"),
                       ("passphrase", "vpnkey:")):
        val = b.pop(field, None)
        if val is not None:
            secretsvc.set_secret(key + vpn_id, val or None)


@router.route("GET", "vpn")
def api_vpns(h, a, b, q):
    return {"vpns": [_vpn_public(v) for v in vpn.load()],
            "tooling": vpn.tooling()}


@router.route("POST", "vpn/analyse")
def api_vpn_analyse(h, a, b, q):
    """Read a config without saving it, so the import dialog can say what the
    file will do -- including which directives run a program as root."""
    kind = b.get("kind") or "openvpn"
    text = b.get("config") or ""
    problem = vpn.validate(text, kind)
    ov = b.get("override") or {}
    ov_problem = vpn.validate_override(ov, kind)
    changes, effective = [], []
    if not problem and not ov_problem and vpn.has_override({"override": ov}):
        rewritten, changes = vpn.apply_override(text, kind, ov)
        effective = vpn.analyse(rewritten, kind).get("remotes", [])
    return {"problem": problem or ov_problem,
            "summary": {} if problem else vpn.analyse(text, kind),
            "override_changes": changes, "effective_remotes": effective}


@router.route("POST", "vpn")
def api_add_vpn(h, a, b, q):
    kind = b.get("kind") or "openvpn"
    text = b.get("config")
    if not text:
        return (400, {"error": "A configuration file is required"})
    err = vpn.validate(text, kind) or vpn.validate_override(b.get("override"), kind)
    if err:
        return (400, {"error": err})
    prof = vpn.upsert({"name": (b.get("name") or "").strip(), "kind": kind,
                       "auto": bool(b.get("auto")), "notes": b.get("notes") or "",
                       "source_dir": (b.get("source_dir") or "").strip(),
                       "override": b.get("override") or {}},
                      config_text=text)
    _vpn_creds(prof["id"], b)
    store.event("", "info", "Added VPN %s" % prof["name"])
    return _vpn_public(prof)


@router.route("PUT", "vpn/:id")
def api_update_vpn(h, a, b, q):
    old = _vpn_or_404(a[0])
    kind = b.get("kind") or old["kind"]
    text = b.get("config")
    if text is not None:
        err = vpn.validate(text, kind)
        if err:
            return (400, {"error": err})
    if b.get("override") is not None:
        err = vpn.validate_override(b["override"], kind)
        if err:
            return (400, {"error": err})
    prof = dict(old)
    if b.get("override") is not None:
        prof["override"] = b["override"]
    for k in ("name", "notes", "source_dir"):
        if b.get(k) is not None:
            prof[k] = str(b[k]).strip() if k != "notes" else b[k]
    if b.get("auto") is not None:
        prof["auto"] = bool(b["auto"])
    if b.get("kind"):
        prof["kind"] = b["kind"]
    prof = vpn.upsert(prof, config_text=text)
    _vpn_creds(prof["id"], b)
    out = _vpn_public(prof)
    if vpn.status(prof["id"])["status"] in ("up", "connecting", "auth"):
        out["restart_needed"] = True
    return out


@router.route("DELETE", "vpn/:id")
def api_delete_vpn(h, a, b, q):
    v = _vpn_or_404(a[0])
    using = [x for x in hostreg.load() if x.get("vpn") == v["id"]]
    if using and not b.get("force"):
        return (400, {"error": "%s still uses this tunnel: %s"
                      % ("A host" if len(using) == 1 else "%d hosts" % len(using),
                         ", ".join(x["name"] for x in using))})
    for x in using:
        x["vpn"] = ""
        hostreg.upsert(x)
    vpn.delete(v["id"])
    sshmgr.write_ssh_config()
    store.event("", "info", "Removed VPN %s" % v["name"])
    return {"ok": True}


@router.route("GET", "vpn/:id/config")
def api_vpn_config(h, a, b, q):
    v = _vpn_or_404(a[0])
    return {"config": vpn.read_config(v["id"]), "kind": v["kind"]}


@router.route("POST", "vpn/:id/up")
def api_vpn_up(h, a, b, q):
    """Start the tunnel.

    Asynchronous by default: bringing one up means a polkit dialog and a
    handshake, which is far longer than a request should be held open, and
    every state change is broadcast anyway. `?wait=1` blocks for a caller --
    the regression suite, or an ssh connect -- that needs the verdict.
    """
    v = _vpn_or_404(a[0])
    if q.get("wait", ["0"])[0] == "1":
        err = vpn.up(v["id"])
        if err:
            return (400, {"error": err, "status": vpn.status(v["id"])})
        return {"ok": True, "status": vpn.status(v["id"])}

    def work():
        err = vpn.up(v["id"])
        store.event("", "warn" if err else "info",
                    "VPN %s: %s" % (v["name"], err) if err
                    else "VPN %s is up" % v["name"])
    _background.submit(work)
    return {"ok": True, "status": vpn.status(v["id"])}


@router.route("POST", "vpn/:id/down")
def api_vpn_down(h, a, b, q):
    v = _vpn_or_404(a[0])
    err = vpn.down(v["id"])
    if err:
        return (400, {"error": err})
    store.event("", "info", "VPN %s is down" % v["name"])
    return {"ok": True, "status": vpn.status(v["id"])}


@router.route("GET", "vpn/:id/log")
def api_vpn_log(h, a, b, q):
    v = _vpn_or_404(a[0])
    return {"lines": vpn.tail(v["id"], _bounded_int(q.get("n", [200])[0], 200, 1, 1000)),
            "status": vpn.status(v["id"])}


@router.route("GET", "vpn/route")
def api_vpn_route(h, a, b, q):
    """Which interface the kernel would use to reach an address."""
    addr = q.get("addr", [""])[0]
    return {"addr": addr, "dev": vpn.route_dev(addr)}


@router.route("POST", "clientlog")
def api_clientlog(h, a, b, q):
    """Record a browser-side error in the server log.

    The UI runs in a detached window with no console anyone will look at, so a
    frontend exception would otherwise vanish. Rate-limiting lives on the
    client, which reports each distinct message once.
    """
    log.warning("client %s: %s", str(b.get("kind"))[:40], str(b.get("message"))[:2000])
    return {"ok": True}


@router.route("GET", "health")
def api_health(h, a, b, q):
    hs = hostreg.load()
    states = sshmgr.all_states()
    return {"ok": True, "version": appmeta.VERSION,
            "uptime_s": int(time.time() - _started),
            "hosts": len(hs),
            "online": sum(1 for x in hs
                          if states.get(x["id"], {}).get("status") == "online"),
            "sessions": len(ptys.list_sessions()),
            "event_clients": len(_event_clients),
            "transfers": len([j for j in files.list_jobs() if j["status"] == "running"])}


@router.route("GET", "events")
def api_events(h, a, b, q):
    return {"events": store.recent_events(
        _bounded_int(q.get("n", [60])[0], 60, 1, 300))}


# -------------------------------------------------------------- websockets

@router.ws("/ws/events")
def ws_events(ws, args, qs):
    client = EventClient(ws)
    with _event_lock:
        _event_clients.add(client)
    try:
        ws.send(json.dumps({"type": "hello", "data": {
            "hosts": [_host_public(x) for x in hostreg.load()],
            "theme": theme.palette()}}))
        while True:
            msg = ws.recv()
            if msg is None:
                break
            op, payload = msg
            try:
                m = json.loads(payload)
            except ValueError:
                continue
            if m.get("type") == "focus":
                _focus["host_id"] = m.get("host_id")
            elif m.get("type") == "ping":
                ws.send(json.dumps({"type": "pong", "data": {}}))
    finally:
        client.close()
        with _event_lock:
            _event_clients.discard(client)


@router.ws("/ws/term/:sid")
def ws_term(ws, args, qs):
    s = ptys.get(args[0])
    if not s:
        ws.send(json.dumps({"type": "error", "data": "no such session"}))
        return
    from httpd import OP_BIN

    def push(chunk):
        ws.send(chunk, OP_BIN)

    s.subscribe(push, replay=qs.get("replay", ["1"])[0] == "1")
    try:
        while True:
            msg = ws.recv()
            if msg is None:
                break
            op, payload = msg
            if op == 0x2:                       # binary frame == keystrokes
                s.write(payload)
            else:
                try:
                    m = json.loads(payload)
                except ValueError:
                    s.write(payload)
                    continue
                if m.get("t") == "in":
                    s.write(m.get("d", ""))
                elif m.get("t") == "size":
                    s.resize(m.get("cols", 100), m.get("rows", 30))
    finally:
        s.unsubscribe(push)
