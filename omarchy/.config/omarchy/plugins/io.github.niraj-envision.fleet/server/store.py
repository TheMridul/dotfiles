"""Local persistence: inventory cache, cross-host search index, run history,
saved commands, blueprints and a metrics ring buffer.

One SQLite file behind a single lock. The workload is a handful of writes per
second from the poller and interactive reads from the UI, so a connection pool
would be ceremony; WAL plus a mutex is the honest fit.
"""
import json
import os
import sqlite3
import threading
import time
import uuid

from paths import DB_FILE

_lock = threading.RLock()
_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS inventory (
  host_id TEXT PRIMARY KEY, json TEXT NOT NULL, collected INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS idx (
  host_id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
  detail TEXT DEFAULT '', extra TEXT DEFAULT '', sort REAL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_name ON idx(name);
CREATE INDEX IF NOT EXISTS idx_host ON idx(host_id);
CREATE INDEX IF NOT EXISTS idx_kind ON idx(kind);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, host_id TEXT, command TEXT, rc INTEGER,
  started INTEGER, duration_ms INTEGER, output TEXT, label TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS runs_started ON runs(started DESC);

CREATE TABLE IF NOT EXISTS snippets (
  id TEXT PRIMARY KEY, name TEXT, command TEXT, tags TEXT DEFAULT '',
  created INTEGER, uses INTEGER DEFAULT 0, last_used INTEGER DEFAULT 0,
  needs_root INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS freq (
  host_id TEXT NOT NULL, cmd TEXT NOT NULL, count INTEGER DEFAULT 1,
  source TEXT DEFAULT 'history', updated INTEGER,
  PRIMARY KEY (host_id, cmd));

CREATE TABLE IF NOT EXISTS blueprints (
  id TEXT PRIMARY KEY, name TEXT, source_host TEXT, source_name TEXT,
  created INTEGER, json TEXT NOT NULL, notes TEXT DEFAULT '');

CREATE TABLE IF NOT EXISTS metrics (
  host_id TEXT NOT NULL, ts INTEGER NOT NULL, cpu REAL, mem REAL,
  disk REAL, rx INTEGER, tx INTEGER, load1 REAL);
CREATE INDEX IF NOT EXISTS metrics_host_ts ON metrics(host_id, ts DESC);

CREATE TABLE IF NOT EXISTS speedtests (
  host_id TEXT NOT NULL, ts INTEGER NOT NULL, json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS speed_host_ts ON speedtests(host_id, ts DESC);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, host_id TEXT,
  level TEXT, message TEXT);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts DESC);
"""


def init():
    global _conn
    with _lock:
        if _conn:
            return _conn
        _conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        try:
            os.chmod(DB_FILE, 0o600)
        except OSError:
            pass
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.commit()
        return _conn


def q(sql, args=()):
    with _lock:
        return [dict(r) for r in init().execute(sql, args).fetchall()]


def x(sql, args=()):
    with _lock:
        c = init().execute(sql, args)
        init().commit()
        return c


def nid():
    return uuid.uuid4().hex[:12]


# ------------------------------------------------------------- inventory

_INDEXERS = (
    # (inventory key, index kind, name field, detail field, extra field)
    ("packages", "package", "name", "version", "desc"),
    ("services", "service", "name", "active", "desc"),
    ("docker", "container", "name", "status", "image"),
    ("docker_images", "image", "tag", "size", "id"),
    ("runtimes", "runtime", "name", "version", "path"),
    ("users", "user", "name", "uid", "shell"),
)


def save_inventory(host_id, inv):
    """Cache an inventory and rebuild this host's slice of the search index."""
    with _lock:
        x("INSERT INTO inventory(host_id,json,collected) VALUES(?,?,?) "
          "ON CONFLICT(host_id) DO UPDATE SET json=excluded.json, collected=excluded.collected",
          (host_id, json.dumps(inv), inv.get("collected", int(time.time()))))
        x("DELETE FROM idx WHERE host_id=?", (host_id,))
        rows = []
        for key, kind, nf, df, ef in _INDEXERS:
            for i, item in enumerate(inv.get(key) or []):
                if not item.get(nf):
                    continue
                rows.append((host_id, kind, item[nf], str(item.get(df, "")),
                             str(item.get(ef, "")), float(i)))
        for p in inv.get("ports") or []:
            label = "%s/%s" % (p.get("port", ""), p.get("proto", ""))
            rows.append((host_id, "port", label,
                         p.get("proc", "") or p.get("addr", ""), p.get("addr", ""), 0.0))
        for c in inv.get("compose") or []:
            rows.append((host_id, "compose", c.rsplit("/", 1)[-1], c, "", 0.0))
        init().executemany(
            "INSERT INTO idx(host_id,kind,name,detail,extra,sort) VALUES(?,?,?,?,?,?)", rows)
        init().commit()
        return len(rows)


def get_inventory(host_id):
    r = q("SELECT json, collected FROM inventory WHERE host_id=?", (host_id,))
    if not r:
        return None
    inv = json.loads(r[0]["json"])
    inv["collected"] = r[0]["collected"]
    return inv


def inventory_age(host_id):
    r = q("SELECT collected FROM inventory WHERE host_id=?", (host_id,))
    return int(time.time()) - r[0]["collected"] if r else None


def forget_host(host_id):
    for t in ("inventory", "idx", "metrics", "freq"):
        x("DELETE FROM %s WHERE host_id=?" % t, (host_id,))


# ---------------------------------------------------------------- search

def search(term, kinds=None, host_ids=None, limit=60):
    """Substring search across every indexed object on every host.

    Ranked so an exact name wins, then a prefix, then any substring -- which is
    what makes typing `ngin` surface the nginx package before a service whose
    description merely mentions it.
    """
    term = (term or "").strip()
    if not term:
        return []
    like = "%" + term.replace("%", "").replace("_", "") + "%"
    sql = ["SELECT host_id, kind, name, detail, extra,",
           "  CASE WHEN lower(name)=lower(?) THEN 0",
           "       WHEN lower(name) LIKE lower(?) THEN 1",
           "       WHEN lower(name) LIKE lower(?) THEN 2 ELSE 3 END AS rank",
           "FROM idx WHERE (name LIKE ? COLLATE NOCASE OR detail LIKE ? COLLATE NOCASE",
           "  OR extra LIKE ? COLLATE NOCASE)"]
    args = [term, term + "%", like, like, like, like]
    if kinds:
        sql.append("AND kind IN (%s)" % ",".join("?" * len(kinds)))
        args += list(kinds)
    if host_ids:
        sql.append("AND host_id IN (%s)" % ",".join("?" * len(host_ids)))
        args += list(host_ids)
    sql.append("ORDER BY rank, kind, length(name), name LIMIT ?")
    args.append(limit)
    return q(" ".join(sql), tuple(args))


def hosts_with(kind, name):
    return [r["host_id"] for r in
            q("SELECT DISTINCT host_id FROM idx WHERE kind=? AND name=? COLLATE NOCASE",
              (kind, name))]


def index_counts(host_id):
    return {r["kind"]: r["n"] for r in
            q("SELECT kind, COUNT(*) n FROM idx WHERE host_id=? GROUP BY kind", (host_id,))}


# ------------------------------------------------------------------ runs

def add_run(host_id, command, rc, duration_ms, output, label=""):
    rid = nid()
    x("INSERT INTO runs(id,host_id,command,rc,started,duration_ms,output,label) "
      "VALUES(?,?,?,?,?,?,?,?)",
      (rid, host_id, command, rc, int(time.time()), duration_ms, output[:20000], label))
    x("INSERT INTO freq(host_id,cmd,count,source,updated) VALUES(?,?,1,'fleet',?) "
      "ON CONFLICT(host_id,cmd) DO UPDATE SET count=count+1, updated=excluded.updated",
      (host_id, command.strip(), int(time.time())))
    x("DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY started DESC LIMIT 500)")
    return rid


def recent_runs(host_id=None, limit=50):
    if host_id:
        return q("SELECT id,host_id,command,rc,started,duration_ms,label FROM runs "
                 "WHERE host_id=? ORDER BY started DESC LIMIT ?", (host_id, limit))
    return q("SELECT id,host_id,command,rc,started,duration_ms,label FROM runs "
             "ORDER BY started DESC LIMIT ?", (limit,))


def run_output(run_id):
    r = q("SELECT * FROM runs WHERE id=?", (run_id,))
    return r[0] if r else None


# ------------------------------------------------- frequent commands & snippets

def save_freq(host_id, entries):
    now = int(time.time())
    with _lock:
        x("DELETE FROM freq WHERE host_id=? AND source='history'", (host_id,))
        init().executemany(
            "INSERT INTO freq(host_id,cmd,count,source,updated) VALUES(?,?,?,'history',?) "
            "ON CONFLICT(host_id,cmd) DO UPDATE SET count=max(count,excluded.count)",
            [(host_id, e["cmd"], e["count"], now) for e in entries])
        init().commit()


def top_commands(host_id, limit=30):
    return q("SELECT cmd, count, source FROM freq WHERE host_id=? "
             "ORDER BY (CASE source WHEN 'fleet' THEN 1000 ELSE 0 END) + count DESC, cmd "
             "LIMIT ?", (host_id, limit))


def list_snippets():
    return q("SELECT * FROM snippets ORDER BY uses DESC, name")


def save_snippet(s):
    sid = s.get("id") or nid()
    x("INSERT INTO snippets(id,name,command,tags,created,needs_root) VALUES(?,?,?,?,?,?) "
      "ON CONFLICT(id) DO UPDATE SET name=excluded.name, command=excluded.command, "
      "tags=excluded.tags, needs_root=excluded.needs_root",
      (sid, s.get("name", ""), s.get("command", ""), s.get("tags", ""),
       int(time.time()), 1 if s.get("needs_root") else 0))
    return sid


def touch_snippet(sid):
    x("UPDATE snippets SET uses=uses+1, last_used=? WHERE id=?", (int(time.time()), sid))


def delete_snippet(sid):
    x("DELETE FROM snippets WHERE id=?", (sid,))


# ----------------------------------------------------------- blueprints

def save_blueprint(bp):
    bid = bp.get("id") or nid()
    x("INSERT INTO blueprints(id,name,source_host,source_name,created,json,notes) "
      "VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, "
      "json=excluded.json, notes=excluded.notes",
      (bid, bp.get("name", ""), bp.get("source_host", ""), bp.get("source_name", ""),
       int(time.time()), json.dumps(bp.get("spec") or {}), bp.get("notes", "")))
    return bid


def list_blueprints():
    out = []
    for r in q("SELECT * FROM blueprints ORDER BY created DESC"):
        r["spec"] = json.loads(r.pop("json"))
        out.append(r)
    return out


def get_blueprint(bid):
    r = q("SELECT * FROM blueprints WHERE id=?", (bid,))
    if not r:
        return None
    b = r[0]
    b["spec"] = json.loads(b.pop("json"))
    return b


def delete_blueprint(bid):
    x("DELETE FROM blueprints WHERE id=?", (bid,))


# -------------------------------------------------------------- metrics

def add_metric(host_id, m):
    net = m.get("nets") or []
    x("INSERT INTO metrics(host_id,ts,cpu,mem,disk,rx,tx,load1) VALUES(?,?,?,?,?,?,?,?)",
      (host_id, int(time.time()), m.get("cpu_pct"), (m.get("mem") or {}).get("pct"),
       m.get("disk_worst"), sum(n.get("rx_bps", 0) for n in net),
       sum(n.get("tx_bps", 0) for n in net), (m.get("load") or [0])[0]))
    # Keep roughly an hour of 3s samples per host; the sparklines never look
    # further back than that and unbounded growth is the classic agent bug.
    x("DELETE FROM metrics WHERE host_id=? AND ts < ?",
      (host_id, int(time.time()) - 3600))


def metric_series(host_id, points=120):
    rows = q("SELECT ts,cpu,mem,disk,rx,tx,load1 FROM metrics WHERE host_id=? "
             "ORDER BY ts DESC LIMIT ?", (host_id, points))
    return list(reversed(rows))


# ------------------------------------------------------------ speed tests

def save_speedtest(host_id, res):
    x("INSERT INTO speedtests(host_id, ts, json) VALUES(?,?,?)",
      (host_id, res.get("ts") or int(time.time()), json.dumps(res)))
    x("DELETE FROM speedtests WHERE host_id=? AND ts NOT IN "
      "(SELECT ts FROM speedtests WHERE host_id=? ORDER BY ts DESC LIMIT 20)",
      (host_id, host_id))


def last_speedtest(host_id):
    r = q("SELECT json FROM speedtests WHERE host_id=? ORDER BY ts DESC LIMIT 1", (host_id,))
    return json.loads(r[0]["json"]) if r else None


def speedtest_history(host_id, limit=12):
    return [json.loads(r["json"]) for r in
            q("SELECT json FROM speedtests WHERE host_id=? ORDER BY ts DESC LIMIT ?",
              (host_id, limit))]


# --------------------------------------------------------------- events

def event(host_id, level, message):
    x("INSERT INTO events(ts,host_id,level,message) VALUES(?,?,?,?)",
      (int(time.time()), host_id or "", level, message[:1000]))
    x("DELETE FROM events WHERE id NOT IN "
      "(SELECT id FROM events ORDER BY ts DESC LIMIT 300)")


def recent_events(limit=80):
    return q("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))
