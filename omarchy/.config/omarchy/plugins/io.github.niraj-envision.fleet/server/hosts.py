"""Host registry: a human-editable JSON file plus ~/.ssh/config import."""
import json
import os
import re
import secrets as pysecrets
import threading
import time

from paths import HOSTS_FILE, SETTINGS_FILE, CONFIG_DIR

_lock = threading.RLock()
MAX_HOSTS = 64

# Sidebar glyphs. Kept to a set that renders in the terminal font too, so the
# same identity carries over if a host is ever shown outside the web UI.
ICONS = ["⬢", "◆", "▲", "●", "⬟", "✦", "■",
         "⬜", "♥", "⚡", "☁", "⚙", "⚑", "◐"]

DEFAULT_SETTINGS = {
    "poll_active_ms": 3000,
    "poll_idle_ms": 20000,
    "inventory_ttl_s": 900,
    "connect_on_start": True,
    "font_size": 13,
    "public_ip_lookup": True,
    "history_mine_limit": 4000,
    # How much room a fullscreen window leaves at the bar's edge.
    #   auto  a little breathing room, so the header is not flush against the
    #         screen edge -- right when the compositor lets the window cover
    #         the bar, which is what Hyprland does
    #   bar   the bar's full height, for compositors that paint their bar over
    #         a fullscreen window and would otherwise hide the header
    #   none  no inset at all
    "fullscreen_inset": "auto",
}


def _new_id():
    return pysecrets.token_hex(8)


def _blank():
    return {
        "id": _new_id(),
        "name": "",
        "icon": ICONS[0],
        "color": "blue",
        "group": "",
        "tags": [],
        "hostname": "",
        "user": os.environ.get("USER", "root"),
        "port": 22,
        "auth": "agent",          # agent | key | password
        "identity_file": "",
        "proxy_jump": "",
        "vpn": "",                # VPN profile to bring up before connecting
        "options": {},            # extra ssh -o key/values
        "notes": "",
        "shell": "",              # override login shell for terminals
        "order": 0,
        "created": int(time.time()),
    }


def normalize(h):
    base = _blank()
    base.update({k: v for k, v in (h or {}).items() if k in base})
    base["id"] = str((h or {}).get("id") or base["id"])[:128]
    try:
        base["port"] = max(1, min(int(base["port"] or 22), 65535))
    except (TypeError, ValueError):
        base["port"] = 22
    tags = base["tags"] if isinstance(base["tags"], list) else []
    base["tags"] = [str(t)[:64] for t in tags[:32] if t]
    for key, limit in (("name", 60), ("hostname", 255), ("user", 128),
                       ("group", 80), ("identity_file", 4096),
                       ("proxy_jump", 255), ("vpn", 128), ("notes", 4096),
                       ("shell", 4096)):
        base[key] = str(base.get(key) or "")[:limit]
    base["color"] = str(base.get("color") or "blue")[:32]
    base["icon"] = str(base.get("icon") or ICONS[0])[:8]
    try:
        base["order"] = max(0, min(int(base.get("order") or 0), MAX_HOSTS))
        base["created"] = max(0, int(base.get("created") or 0))
    except (TypeError, ValueError):
        base["order"], base["created"] = 0, int(time.time())
    base["auth"] = str(base.get("auth") or "agent")
    if not isinstance(base.get("options"), dict) or len(base["options"]) > 32:
        base["options"] = {}
    if base["auth"] not in ("agent", "key", "password"):
        base["auth"] = "agent"
    if not base["name"]:
        base["name"] = base["hostname"] or "unnamed"
    if base["icon"] not in ICONS:
        base["icon"] = ICONS[sum(map(ord, base["name"])) % len(ICONS)]
    return base


def load():
    with _lock:
        try:
            with open(HOSTS_FILE) as fh:
                raw = json.load(fh)
        except Exception:
            raw = []
        if not isinstance(raw, list):
            raw = []
        hosts = [normalize(h) for h in raw[:MAX_HOSTS] if isinstance(h, dict)]
        hosts.sort(key=lambda h: (h.get("order", 0), h["name"].lower()))
        return hosts


def save(hosts):
    with _lock:
        if not isinstance(hosts, list) or len(hosts) > MAX_HOSTS:
            raise ValueError("Fleet supports at most %d hosts" % MAX_HOSTS)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        for i, h in enumerate(hosts):
            h["order"] = i
        tmp = HOSTS_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(hosts, fh, indent=2)
        os.replace(tmp, HOSTS_FILE)
        return hosts


def get(host_id):
    for h in load():
        if h["id"] == host_id:
            return h
    return None


def upsert(host):
    hosts = load()
    host = normalize(host)
    for i, h in enumerate(hosts):
        if h["id"] == host["id"]:
            host["created"] = h.get("created", host["created"])
            hosts[i] = host
            break
    else:
        host["order"] = len(hosts)
        hosts.append(host)
    save(hosts)
    return host


def delete(host_id):
    hosts = [h for h in load() if h["id"] != host_id]
    save(hosts)


def reorder(ids):
    hosts = load()
    by_id = {h["id"]: h for h in hosts}
    ordered = [by_id[i] for i in ids if i in by_id]
    ordered += [h for h in hosts if h["id"] not in set(ids)]
    save(ordered)
    return ordered


# ----------------------------------------------------------------- settings

def _validated(raw):
    """Coerce a settings dict to something the UI can trust.

    Applied on both read and write, so a hand-edited settings.json cannot put
    a value into the app that its callers never check for.
    """
    out = dict(DEFAULT_SETTINGS)
    out.update({k: v for k, v in (raw or {}).items() if k in DEFAULT_SETTINGS})
    if out.get("fullscreen_inset") not in ("auto", "bar", "none"):
        out["fullscreen_inset"] = DEFAULT_SETTINGS["fullscreen_inset"]
    for k in ("poll_active_ms", "poll_idle_ms", "inventory_ttl_s",
              "font_size", "history_mine_limit"):
        try:
            out[k] = int(out[k])
        except (TypeError, ValueError):
            out[k] = DEFAULT_SETTINGS[k]
    out["poll_active_ms"] = max(500, min(600000, out["poll_active_ms"]))
    out["poll_idle_ms"] = max(1000, min(600000, out["poll_idle_ms"]))
    out["inventory_ttl_s"] = max(30, min(604800, out["inventory_ttl_s"]))
    out["font_size"] = max(8, min(32, out["font_size"]))
    out["history_mine_limit"] = max(0, min(10000, out["history_mine_limit"]))
    out["connect_on_start"] = bool(out["connect_on_start"])
    out["public_ip_lookup"] = bool(out["public_ip_lookup"])
    return out


def settings():
    try:
        with open(SETTINGS_FILE) as fh:
            s = json.load(fh)
    except Exception:
        s = {}
    return _validated(s)


def save_settings(patch):
    s = dict(settings())
    s.update({k: v for k, v in (patch or {}).items() if k in DEFAULT_SETTINGS})
    s = _validated(s)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as fh:
        json.dump(s, fh, indent=2)
    return s


# ------------------------------------------------------- ~/.ssh/config import

def parse_ssh_config(path=None):
    """Flatten ~/.ssh/config into concrete host entries.

    Wildcard blocks (Host *) contribute defaults rather than becoming hosts of
    their own, and Include directives are followed one level deep -- enough for
    the common `Include ~/.ssh/config.d/*` layout.
    """
    path = path or os.path.expanduser("~/.ssh/config")
    blocks, defaults = [], {}
    cur = None

    def feed(fpath, depth=0):
        nonlocal cur
        try:
            with open(fpath) as fh:
                lines = fh.readlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"[\s=]+", line, maxsplit=1)
            if len(parts) != 2:
                continue
            key, val = parts[0].lower(), parts[1].strip()
            if key == "include" and depth < 2:
                import glob
                for inc in glob.glob(os.path.expanduser(val)):
                    feed(inc, depth + 1)
                continue
            if key == "host":
                names = val.split()
                cur = {"_names": names, "_opts": {}}
                blocks.append(cur)
            elif cur is not None:
                cur["_opts"][key] = val
            else:
                defaults[key] = val

    feed(path)

    out = []
    wildcard = dict(defaults)
    for b in blocks:
        if any("*" in n or "?" in n for n in b["_names"]):
            wildcard.update(b["_opts"])
    for b in blocks:
        for name in b["_names"]:
            if "*" in name or "?" in name or "!" in name:
                continue
            o = dict(wildcard)
            o.update(b["_opts"])
            h = _blank()
            h["name"] = name
            h["hostname"] = o.get("hostname", name)
            h["user"] = o.get("user") or os.environ.get("USER", "root")
            h["port"] = int(o.get("port", 22) or 22)
            h["proxy_jump"] = o.get("proxyjump", "")
            if o.get("identityfile"):
                h["identity_file"] = os.path.expanduser(o["identityfile"].strip('"'))
                h["auth"] = "key"
            h["icon"] = ICONS[sum(map(ord, name)) % len(ICONS)]
            h["notes"] = "Imported from ~/.ssh/config"
            out.append(h)
    return out


def import_ssh_config():
    """Add hosts from ~/.ssh/config that are not already registered."""
    existing = load()
    known = {(h["hostname"], h["user"], h["port"]) for h in existing}
    known_names = {h["name"].lower() for h in existing}
    added = []
    for h in parse_ssh_config():
        if (h["hostname"], h["user"], h["port"]) in known or h["name"].lower() in known_names:
            continue
        h["order"] = len(existing) + len(added)
        added.append(h)
    if added:
        save(existing + added)
    return added
