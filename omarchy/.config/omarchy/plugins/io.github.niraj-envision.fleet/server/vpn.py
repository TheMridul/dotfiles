"""VPN tunnels, for a fleet that is only reachable from inside one.

A VPS behind a company concentrator, a WireGuard mesh, a management network
fronted by OpenVPN: in all three cases ssh cannot reach the box until the
tunnel is up. Fleet therefore treats the tunnel as part of connecting to a
host rather than as something you are expected to arrange elsewhere first --
a host names a profile, and opening its connection brings that profile up.

Two backends, each driven through its own tooling:

  openvpn    started with a management socket, so connection state, throughput
             and the credential prompts all arrive on a channel we own. The
             username and password are answered over that socket -- never
             written to a file, never on a command line, never in `ps` -- the
             same shape as the SSH_ASKPASS path the rest of Fleet uses.

  wireguard  wg-quick up/down. Status is read from /sys and `ip`, neither of
             which needs privilege, so watching a live tunnel costs nothing.

Privilege is the honest part. A tunnel means a tun device and a routing table
edit, which is root, and Fleet does not have root: every up and down runs
through pkexec (a desktop prompt) or, when you have already configured one,
`sudo -n`. Nothing here installs a rule to make that automatic, because a
.ovpn `up` script and a WireGuard `PostUp` both run as root -- a NOPASSWD rule
for either is a NOPASSWD rule for anything.
"""
import collections
import getpass
import json
import logging
import os
import re
import secrets as pysecrets
import socket
import subprocess
import threading
import time

import secretsvc
from paths import CONFIG_DIR, STATE_DIR

log = logging.getLogger("fleet.vpn")

VPN_DIR = os.path.join(CONFIG_DIR, "vpn")
VPNS_FILE = os.path.join(CONFIG_DIR, "vpns.json")


def _run_dir():
    """Where the management sockets live.

    A unix socket path is capped at about 108 bytes by the kernel -- the same
    limit that keeps ssh's ControlPath short in paths.py -- and an XDG state
    directory nested under a long HOME can exceed it on its own. The runtime
    directory is short, already 0700, and is exactly what it is for; the state
    directory is only the fallback for a session that has none.
    """
    xrd = os.environ.get("XDG_RUNTIME_DIR")
    if xrd and os.path.isdir(xrd):
        return os.path.join(xrd, "fleet-vpn")
    return os.path.join(STATE_DIR, "vpn")


RUN_DIR = _run_dir()

OPENVPN = "/usr/bin/openvpn" if os.access("/usr/bin/openvpn", os.X_OK) else None
WG_QUICK = "/usr/bin/wg-quick" if os.access("/usr/bin/wg-quick", os.X_OK) else None
PKEXEC = "/usr/bin/pkexec" if os.access("/usr/bin/pkexec", os.X_OK) else None
SUDO = "/usr/bin/sudo" if os.access("/usr/bin/sudo", os.X_OK) else None
IP = "/usr/bin/ip"
KILL = "/usr/bin/kill"

KINDS = ("openvpn", "wireguard")
MAX_PROFILES = 32
MAX_CONFIG_BYTES = 2 * 1024 * 1024

_lock = threading.RLock()
_hook = None


def set_hook(fn):
    """Called with a status dict whenever a tunnel changes state."""
    global _hook
    _hook = fn


def _emit(st):
    if _hook:
        try:
            _hook(st)
        except Exception:
            log.exception("vpn hook failed")


def ensure_dirs():
    for d in (VPN_DIR, RUN_DIR):
        os.makedirs(d, exist_ok=True)
        os.chmod(d, 0o700)


# --------------------------------------------------------------- registry

def _new_id():
    return pysecrets.token_hex(8)


def iface_name(v):
    """Interface (and config file) name for a profile.

    wg-quick takes the interface name from the config file's basename and the
    kernel caps that at 15 characters, so both backends use the same short,
    collision-free stem rather than anything derived from a name the user can
    type.
    """
    return "fv" + v["id"][:8]


def config_path(v):
    ext = ".conf" if v["kind"] == "wireguard" else ".ovpn"
    return os.path.join(VPN_DIR, iface_name(v) + ext)


def _blank():
    return {
        "id": _new_id(),
        "name": "",
        "kind": "openvpn",
        "auto": False,          # bring up when Fleet starts
        "notes": "",
        "source_dir": "",       # where an imported config's siblings live
        "override": {},         # send this profile at a different server
        "summary": {},          # what analyse() found, for the UI
        "order": 0,
        "created": int(time.time()),
    }


def normalize(v):
    base = _blank()
    base.update({k: val for k, val in (v or {}).items() if k in base})
    base["id"] = str((v or {}).get("id") or base["id"])[:128]
    if base["kind"] not in KINDS:
        base["kind"] = "openvpn"
    base["auto"] = bool(base["auto"])
    ov = base.get("override") if isinstance(base.get("override"), dict) else {}
    base["override"] = {k: str(ov.get(k) or "").strip()[:255]
                        for k in ("host", "port", "proto")}
    base["name"] = str(base.get("name") or "")[:80]
    base["notes"] = str(base.get("notes") or "")[:4096]
    base["source_dir"] = str(base.get("source_dir") or "")[:4096]
    base["summary"] = base.get("summary") if isinstance(base.get("summary"), dict) else {}
    if len(base["summary"]) > 32:
        base["summary"] = {}
    try:
        base["order"] = max(0, min(int(base.get("order") or 0), MAX_PROFILES))
        base["created"] = max(0, int(base.get("created") or 0))
    except (TypeError, ValueError):
        base["order"], base["created"] = 0, int(time.time())
    if not base["name"]:
        base["name"] = base["kind"]
    return base


def load():
    with _lock:
        try:
            with open(VPNS_FILE) as fh:
                raw = json.load(fh)
        except Exception:
            raw = []
        if not isinstance(raw, list):
            raw = []
        out = [normalize(v) for v in raw[:MAX_PROFILES] if isinstance(v, dict)]
        out.sort(key=lambda v: (v.get("order", 0), v["name"].lower()))
        return out


def save(profiles):
    with _lock:
        if not isinstance(profiles, list) or len(profiles) > MAX_PROFILES:
            raise ValueError("Fleet supports at most %d VPN profiles" % MAX_PROFILES)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        for i, v in enumerate(profiles):
            v["order"] = i
        tmp = VPNS_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(profiles, fh, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, VPNS_FILE)
        return profiles


def get(vpn_id):
    for v in load():
        if v["id"] == vpn_id:
            return v
    return None


def upsert(profile, config_text=None):
    """Add or update a profile, writing its config file when text is given."""
    ensure_dirs()
    profiles = load()
    profile = normalize(profile)
    if config_text is not None:
        if not isinstance(config_text, str):
            raise ValueError("VPN configuration must be text")
        if len(config_text.encode("utf-8")) > MAX_CONFIG_BYTES:
            raise ValueError("VPN configuration exceeds 2 MiB")
    for i, v in enumerate(profiles):
        if v["id"] == profile["id"]:
            profile["created"] = v.get("created", profile["created"])
            # Keep the stored config when the editor did not resend it.
            if config_text is None and v["kind"] != profile["kind"]:
                raise ValueError("changing the tunnel type needs a new config file")
            profiles[i] = profile
            break
    else:
        if len(profiles) >= MAX_PROFILES:
            raise ValueError("Fleet supports at most %d VPN profiles" % MAX_PROFILES)
        profile["order"] = len(profiles)
        profiles.append(profile)
    if config_text is not None:
        profile["summary"] = analyse(config_text, profile["kind"])
        path = config_path(profile)
        with open(path, "w") as fh:
            fh.write(config_text if config_text.endswith("\n") else config_text + "\n")
        os.chmod(path, 0o600)
    sync_effective(profile)
    save(profiles)
    return profile


def delete(vpn_id):
    v = get(vpn_id)
    if not v:
        return
    try:
        down(vpn_id)
    except Exception:
        pass
    for key in ("vpnuser:", "vpnpass:", "vpnkey:"):
        secretsvc.set_secret(key + vpn_id, None)
    for path in (config_path(v),
                 os.path.join(EFFECTIVE_DIR, os.path.basename(config_path(v)))):
        try:
            os.unlink(path)
        except OSError:
            pass
    save([x for x in load() if x["id"] != vpn_id])
    with _conn_lock:
        _conns.pop(vpn_id, None)


def read_config(vpn_id):
    v = get(vpn_id)
    if not v:
        raise ValueError("no such VPN: %s" % vpn_id)
    try:
        with open(config_path(v)) as fh:
            return fh.read()
    except OSError:
        return ""


# ---------------------------------------------------------------- analysis

# Directives that run a program as root when the tunnel comes up. They are
# perfectly legitimate -- a provider's config often needs one to set DNS --
# but the user should see them before Fleet hands the file to a root process.
_OVPN_RISKY = ("up", "down", "route-up", "route-pre-down", "ipchange",
               "client-connect", "client-disconnect", "learn-address",
               "tls-verify", "auth-user-pass-verify", "plugin", "script-security")
# Directives whose argument is a path to another file that must travel with
# the config. An inline <ca>...</ca> block needs nothing alongside it.
_OVPN_FILES = ("ca", "cert", "key", "tls-auth", "tls-crypt", "tls-crypt-v2",
               "pkcs12", "crl-verify", "secret", "askpass", "auth-user-pass")
_WG_RISKY = ("preup", "postup", "predown", "postdown")


def analyse(text, kind):
    """Summarise a config for the UI: where it goes, what it needs, what it runs."""
    if kind == "wireguard":
        return _analyse_wg(text)
    return _analyse_ovpn(text)


def _analyse_ovpn(text):
    remotes, risky, external, inline = [], [], [], []
    needs_auth = False
    proto = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        m = re.match(r"^<(\w[\w-]*)>$", line)
        if m:
            inline.append(m.group(1))
            continue
        parts = line.split()
        key = parts[0].lower()
        args = parts[1:]
        if key == "remote" and args:
            remotes.append(" ".join(args[:3]))
        elif key == "proto" and args:
            proto = args[0]
        elif key == "auth-user-pass":
            # With a file argument the credentials come from that file; with
            # none, OpenVPN asks -- which is the case Fleet can answer.
            needs_auth = not args
            if args:
                external.append(args[0])
        elif key in _OVPN_FILES and args and args[0] != "[inline]":
            external.append(args[0])
        if key in _OVPN_RISKY:
            risky.append(line[:120])
    external = [f for f in external if f.split("/")[-1].split(".")[0] not in inline]
    return {"remotes": remotes, "proto": proto, "needs_auth": needs_auth,
            "inline": sorted(set(inline)), "external": sorted(set(external)),
            "risky": risky}


def _analyse_wg(text):
    remotes, risky, addrs, allowed = [], [], [], []
    has_key = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;[":
            continue
        if "=" not in line:
            continue
        key, val = [p.strip() for p in line.split("=", 1)]
        k = key.lower()
        if k == "endpoint":
            remotes.append(val)
        elif k == "address":
            addrs.append(val)
        elif k == "allowedips":
            allowed.append(val)
        elif k == "privatekey":
            has_key = bool(val)
        elif k in _WG_RISKY:
            risky.append("%s = %s" % (key, val[:100]))
    return {"remotes": remotes, "proto": "udp", "needs_auth": False,
            "addresses": addrs, "allowed_ips": allowed,
            "has_key": has_key, "inline": [], "external": [], "risky": risky}


def validate(text, kind):
    """Return an error string, or None. Cheap checks that catch a wrong paste."""
    if not (text or "").strip():
        return "The configuration is empty"
    low = text.lower()
    if kind == "wireguard":
        if "[interface]" not in low:
            return "That does not look like a WireGuard config — no [Interface] section"
        if "privatekey" not in low:
            return "The WireGuard config has no PrivateKey"
        if "[peer]" not in low:
            return "The WireGuard config has no [Peer] section"
        return None
    a = _analyse_ovpn(text)
    if not a["remotes"]:
        return "That does not look like an OpenVPN client config — no `remote` line"
    if not (a["inline"] or a["external"]):
        return "No certificates or keys are referenced — is this the whole file?"
    return None


# ---------------------------------------------------------------- override

# One provider, one .ovpn, and a web page listing thirty servers you are
# allowed to use: overriding the endpoint is the normal case, not an escape
# hatch. Rather than ask you to hand-edit a file full of inline certificates,
# Fleet keeps the import pristine and writes an *effective* config at connect
# time with the remote rewritten. What actually ran is always a file you can
# read, and clearing the override goes straight back to the original.

EFFECTIVE_DIR = os.path.join(VPN_DIR, "effective")

# An override value is written into a file that openvpn executes directives
# from, so a newline in it is a directive -- the same class of hole that
# ssh_config generation guards against in sshmgr. Nothing but the characters a
# host name or address can contain gets through.
_OV_HOST = re.compile(r"^[A-Za-z0-9._:\[\]-]{1,253}$")
_PROTOS = ("udp", "tcp")


def has_override(prof):
    ov = (prof or {}).get("override") or {}
    return any(str(ov.get(k) or "").strip() for k in ("host", "port", "proto"))


def validate_override(ov, kind="openvpn"):
    """Return an error string, or None."""
    ov = ov or {}
    host = str(ov.get("host") or "").strip()
    port = str(ov.get("port") or "").strip()
    proto = str(ov.get("proto") or "").strip().lower()
    if host and not _OV_HOST.match(host):
        return ("Server %r is not a valid host name or address — it may only "
                "contain letters, digits and . : - _ [ ]" % host[:60])
    if port:
        try:
            n = int(port)
        except ValueError:
            return "Server port must be a number"
        if not 1 <= n <= 65535:
            return "Server port must be between 1 and 65535"
    if proto:
        if kind == "wireguard":
            return "WireGuard is always UDP — leave the protocol alone"
        if proto not in _PROTOS:
            return "Protocol must be udp or tcp"
    return None


def apply_override(text, kind, ov):
    """Rewrite a config's endpoint. Returns (text, [human-readable changes])."""
    ov = ov or {}
    host = str(ov.get("host") or "").strip()
    port = str(ov.get("port") or "").strip()
    proto = str(ov.get("proto") or "").strip().lower()
    if not (host or port or proto):
        return text, []
    if kind == "wireguard":
        return _override_wg(text, host, port)
    return _override_ovpn(text, host, port, proto)


def _override_ovpn(text, host, port, proto):
    lines = text.splitlines(True)
    changes = []
    # `remote host [port] [proto]` is positional, so setting a protocol on a
    # bare `remote host` needs a port to put in front of it. The config's own
    # `port` directive is the right answer; OpenVPN's default is the fallback.
    cfg_port = ""
    for raw in lines:
        f = raw.strip().split()
        if len(f) >= 2 and f[0].lower() == "port":
            cfg_port = f[1]
    out = []
    for raw in lines:
        stripped = raw.strip()
        indent = raw[:len(raw) - len(raw.lstrip())]
        eol = "\n" if raw.endswith("\n") else ""
        f = stripped.split()
        key = f[0].lower() if f else ""
        if key == "remote" and len(f) >= 2:
            new_port = port or (f[2] if len(f) > 2 else "")
            new_proto = proto or (f[3] if len(f) > 3 else "")
            if new_proto and not new_port:
                new_port = cfg_port or "1194"
            parts = ["remote", host or f[1]]
            if new_port:
                parts.append(new_port)
            if new_proto:
                parts.append(new_proto)
            line = " ".join(parts)
            if line != stripped:
                changes.append("%s  →  %s" % (stripped, line))
            out.append(indent + line + eol)
        elif key == "proto" and proto and len(f) >= 2:
            # The standalone directive spells TCP differently from the third
            # field of a `remote` line, and openvpn rejects the wrong spelling.
            line = "proto " + ("tcp-client" if proto == "tcp" else "udp")
            if line != stripped:
                changes.append("%s  →  %s" % (stripped, line))
            out.append(indent + line + eol)
        elif key == "port" and port and len(f) >= 2:
            line = "port " + port
            if line != stripped:
                changes.append("%s  →  %s" % (stripped, line))
            out.append(indent + line + eol)
        else:
            out.append(raw)
    return "".join(out), changes


def _split_endpoint(value):
    """host:port, with IPv6 in brackets kept intact."""
    v = value.strip()
    if v.startswith("["):
        end = v.find("]")
        if end > 0:
            rest = v[end + 1:]
            return v[:end + 1], rest[1:] if rest.startswith(":") else ""
    if v.count(":") == 1:
        h, _, p = v.partition(":")
        return h, p
    return v, ""


def _override_wg(text, host, port):
    out, changes = [], []
    for raw in text.splitlines(True):
        stripped = raw.strip()
        if "=" in stripped and stripped.split("=", 1)[0].strip().lower() == "endpoint":
            key = stripped.split("=", 1)[0].rstrip()
            oh, op = _split_endpoint(stripped.split("=", 1)[1])
            nh, np = host or oh, port or op
            line = "%s = %s" % (key, "%s:%s" % (nh, np) if np else nh)
            if line != stripped:
                changes.append("%s  →  %s" % (stripped, line))
            indent = raw[:len(raw) - len(raw.lstrip())]
            out.append(indent + line + ("\n" if raw.endswith("\n") else ""))
        else:
            out.append(raw)
    return "".join(out), changes


def effective_config(prof):
    """The config file that will actually be handed to the client.

    Without an override this is the import itself; with one it is a generated
    file whose basename is unchanged, because wg-quick takes the interface
    name from it.
    """
    pristine = config_path(prof)
    if not has_override(prof):
        return pristine
    try:
        with open(pristine) as fh:
            text = fh.read()
    except OSError:
        return pristine
    new, _ = apply_override(text, prof["kind"], prof.get("override"))
    os.makedirs(EFFECTIVE_DIR, exist_ok=True)
    os.chmod(EFFECTIVE_DIR, 0o700)
    path = os.path.join(EFFECTIVE_DIR, os.path.basename(pristine))
    header = ("# Generated by Fleet from %s -- edits are overwritten.\n"
              "# The server override on this profile is applied below.\n"
              % os.path.basename(pristine))
    with open(path, "w") as fh:
        fh.write(header + new)
    os.chmod(path, 0o600)
    return path


def sync_effective(prof):
    """Keep the generated config in step with the profile.

    Written on save rather than only at connect time, because the promise the
    editor makes -- the file Fleet will run is one you can read -- should not
    wait for a handshake. Clearing the override deletes it again; it holds the
    same key material as the import and has no business outliving its reason.
    """
    path = os.path.join(EFFECTIVE_DIR, os.path.basename(config_path(prof)))
    if has_override(prof) and os.path.isfile(config_path(prof)):
        return effective_config(prof)
    try:
        os.unlink(path)
    except OSError:
        pass
    return config_path(prof)


def effective_remotes(prof):
    """Where this profile will actually connect, override included."""
    try:
        with open(config_path(prof)) as fh:
            text = fh.read()
    except OSError:
        return []
    if has_override(prof):
        text, _ = apply_override(text, prof["kind"], prof.get("override"))
    return analyse(text, prof["kind"]).get("remotes", [])


# -------------------------------------------------------------- privilege

def _sudo_listing_is_nopasswd(text):
    """Whether ``sudo -ll <command>`` matched a passwordless rule.

    ``sudo -n -l <command>`` only answers whether the command is allowed; it
    can return success for an ordinary password-protected ``ALL`` rule. In the
    verbose listing sudo represents NOPASSWD as ``Options: !authenticate``.
    """
    return any("!authenticate" in line for line in (text or "").splitlines()
               if line.strip().startswith("Options:"))


def _sudo_nopasswd(binpath):
    if not (SUDO and binpath):
        return False
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    try:
        p = subprocess.run([SUDO, "-n", "-ll", binpath],
                           capture_output=True, text=True, env=env, timeout=5)
        return p.returncode == 0 and _sudo_listing_is_nopasswd(p.stdout)
    except Exception:
        return False


def elevation(binpath):
    """How to run `binpath` as root, as an argv prefix, or None if we cannot.

    `sudo -n` is preferred only when a rule already exists: it is silent and
    survives a session with no polkit agent. Otherwise pkexec, which asks.
    """
    if os.geteuid() == 0:
        return []
    if _sudo_nopasswd(binpath):
        return [SUDO, "-n", "--"]
    if PKEXEC and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        return [PKEXEC]
    return None


# Agents whose name does not contain "agent".
_KNOWN_AGENTS = ("xfce-polkit", "pantheon-polkit", "polkit-dumb-agent")

_agent_cache = [0.0, False]


def polkit_agent_running():
    """Is there an authentication agent for pkexec to ask?

    polkitd being up is not enough: without a *session* agent, pkexec has
    nowhere to put a password prompt, and Fleet's children have no terminal to
    fall back to. The failure that produces is obscure enough ("Not
    authorized") that it is worth detecting before rather than explaining
    after. Scanned from /proc because polkit exposes no way to ask.
    """
    now = time.time()
    if now - _agent_cache[0] < 5.0:
        return _agent_cache[1]
    found = False
    me = str(os.getpid())
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit() or pid == me:
                continue
            try:
                with open("/proc/%s/cmdline" % pid, "rb") as fh:
                    argv0 = fh.read().split(b"\0", 1)[0]
            except OSError:
                continue
            # The program's own name, not its whole command line: a shell
            # running a command that merely mentions polkit is not an agent,
            # and matching the full line makes this function find itself.
            name = os.path.basename(argv0.decode(errors="replace")).lower()
            if not name or name == "polkitd":
                continue
            if (("polkit" in name or "policykit" in name)
                    and ("agent" in name or name in _KNOWN_AGENTS)):
                found = True
                break
    except OSError:
        pass
    _agent_cache[0], _agent_cache[1] = now, found
    return found


def elevation_problem(binpath):
    """Why elevation would fail, in words the person can act on, or None."""
    elev = elevation(binpath)
    if elev is None:
        return ("Fleet has no way to become root: install a polkit agent, or add "
                "a sudo rule for %s" % binpath)
    if elev and elev[0] == PKEXEC and not polkit_agent_running():
        return ("pkexec has no authentication agent to ask for your password. "
                "Install and start one — on Hyprland: sudo pacman -S hyprpolkitagent "
                "then systemctl --user enable --now hyprpolkitagent — or add a "
                "sudo rule for %s" % os.path.basename(binpath))
    return None


def _elev_name(prefix):
    if prefix == []:
        return "root"
    if prefix and prefix[0] == SUDO:
        return "sudo"
    if prefix and prefix[0] == PKEXEC:
        return "pkexec"
    return None


def sudoers_line():
    bins = [b for b in (OPENVPN, WG_QUICK) if b]
    if not bins:
        return ""
    return "%s ALL=(root) NOPASSWD: %s" % (getpass.getuser(), ", ".join(bins))


def tooling():
    """What is installed and how Fleet would elevate — the UI explains this."""
    ov = elevation(OPENVPN) if OPENVPN else None
    wg = elevation(WG_QUICK) if WG_QUICK else None
    return {
        "openvpn": OPENVPN or "",
        "wireguard": WG_QUICK or "",
        "openvpn_elevation": _elev_name(ov),
        "wireguard_elevation": _elev_name(wg),
        "pkexec": bool(PKEXEC),
        "polkit_agent": polkit_agent_running(),
        "openvpn_problem": elevation_problem(OPENVPN) if OPENVPN else "",
        "wireguard_problem": elevation_problem(WG_QUICK) if WG_QUICK else "",
        "sudoers": sudoers_line(),
        "user": getpass.getuser(),
    }


# ------------------------------------------------------------ connections

_conns = {}
_conn_lock = threading.RLock()

_OPENVPN_STATES = {
    "CONNECTING": "connecting", "WAIT": "connecting", "AUTH": "auth",
    "GET_CONFIG": "connecting", "ASSIGN_IP": "connecting",
    "ADD_ROUTES": "connecting", "CONNECTED": "up",
    "RECONNECTING": "connecting", "TCP_CONNECT": "connecting",
    "RESOLVE": "connecting", "EXITING": "down",
}


class Conn:
    """One tunnel's live state. Subclasses supply start/stop and counters."""

    def __init__(self, prof):
        self.prof = prof
        self.id = prof["id"]
        self.iface = iface_name(prof)
        self.lock = threading.RLock()
        self.log = collections.deque(maxlen=400)
        self._prev = None
        self.st = {"id": self.id, "name": prof["name"], "kind": prof["kind"],
                   "status": "down", "error": "", "detail": "", "since": 0,
                   "iface": self.iface, "ip": "", "server": "",
                   "rx": 0, "tx": 0, "rx_rate": 0.0, "tx_rate": 0.0}

    # -- state -------------------------------------------------------------
    def state(self):
        with self.lock:
            return dict(self.st)

    def set(self, emit=True, **kw):
        with self.lock:
            changed = any(self.st.get(k) != v for k, v in kw.items())
            self.st.update(kw)
            snap = dict(self.st)
        if changed and emit:
            _emit(snap)
        return snap

    def note(self, line):
        line = line.rstrip()
        if line:
            self.log.append("%s %s" % (time.strftime("%H:%M:%S"), line[:400]))

    def tail(self, n=200):
        return list(self.log)[-n:]

    # -- counters ----------------------------------------------------------
    def _counters(self):
        return None

    def sample(self):
        """Refresh throughput. Returns True when the visible state changed."""
        c = self._counters()
        now = time.time()
        if c is None:
            self._prev = None
            return False
        rx, tx = c
        rates = {}
        if self._prev:
            dt = now - self._prev[0]
            if dt > 0.4:
                rates = {"rx_rate": max(0.0, (rx - self._prev[1]) / dt),
                         "tx_rate": max(0.0, (tx - self._prev[2]) / dt)}
                self._prev = (now, rx, tx)
        else:
            self._prev = (now, rx, tx)
        with self.lock:
            before = (self.st["rx"], self.st["tx"])
            self.st["rx"], self.st["tx"] = rx, tx
            self.st.update(rates)
        return before != (rx, tx)


# ------------------------------------------------------------- openvpn

class OpenVPNConn(Conn):
    """OpenVPN driven through its management interface.

    The interface is a unix socket in Fleet's own 0700 state directory, so the
    only accounts that can reach it are this user and root; `openvpn` is also
    told to accept nobody else. Everything interactive -- the username, the
    password, a private key passphrase -- is answered there, which is why none
    of it reaches the filesystem or a command line.
    """

    def __init__(self, prof):
        super().__init__(prof)
        self.proc = None
        self.sock = None
        self.sock_path = os.path.join(RUN_DIR, self.iface + ".sock")
        self.pid_path = os.path.join(RUN_DIR, self.iface + ".pid")
        self._auth_fails = 0
        self._stopping = False
        self._drain_done = threading.Event()

    # -- lifecycle ---------------------------------------------------------
    def start(self, timeout=75):
        if not OPENVPN:
            return "openvpn is not installed"
        if not os.path.isfile(config_path(self.prof)):
            return "the configuration file for this profile is missing"
        cfg = effective_config(self.prof)
        problem = elevation_problem(OPENVPN)
        if problem:
            return problem
        elev = elevation(OPENVPN)
        ensure_dirs()
        if len(self.sock_path.encode()) > 100:
            return ("The management socket path is too long for a unix socket "
                    "(%s). Set XDG_RUNTIME_DIR." % self.sock_path)
        for p in (self.sock_path, self.pid_path):
            try:
                os.unlink(p)
            except OSError:
                pass

        self._stopping = False
        self._auth_fails = 0
        self._drain_done.clear()
        self.set(status="connecting", error="", detail="starting openvpn",
                 since=int(time.time()), ip="", rx=0, tx=0)
        argv = elev + [
            OPENVPN,
            "--config", cfg,
            # Provider profiles commonly say only `dev tun`, which lets
            # OpenVPN allocate tun0/tun1. Fleet's route checks, counters and
            # host badges use the stable per-profile interface name, so pin
            # the actual kernel device to that same name. Command-line options
            # follow the config and therefore override its generic `dev`.
            "--dev-type", "tun",
            "--dev", self.iface,
            "--cd", self.prof.get("source_dir") or VPN_DIR,
            "--management", self.sock_path, "unix",
            "--management-client-user", getpass.getuser(),
            "--management-query-passwords",
            "--management-hold",
            "--writepid", self.pid_path,
            "--auth-nocache",
            "--verb", "3",
        ]
        try:
            self.proc = subprocess.Popen(
                argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
        except Exception as e:
            self.set(status="error", error=str(e))
            return str(e)
        threading.Thread(target=self._drain, daemon=True,
                         name="ovpn-log-" + self.iface).start()

        if not self._attach(deadline=time.time() + 25):
            # The log-drain thread owns the useful exit reason. Give it a
            # moment to finish before replacing that reason with a generic
            # "did not open its management socket" error.
            self._drain_done.wait(2)
            self._reap()
            err = self.state()["error"] or "openvpn did not open its management socket"
            self.set(status="error", error=err)
            return err

        # Wait for the tunnel to actually come up, so the caller -- which may
        # be an ssh connect that needs the route -- learns the real outcome
        # rather than "we started a process".
        end = time.time() + timeout
        while time.time() < end:
            s = self.state()
            if s["status"] == "up":
                return None
            if s["status"] in ("error", "down"):
                err = s["error"]
                self._reap()
                return err or "openvpn exited"
            if self.proc.poll() is not None:
                self._drain_done.wait(2)
                self._reap()
                return self.state()["error"] or "openvpn exited"
            time.sleep(0.25)
        self.stop()
        self.set(status="error", error="timed out after %ds" % timeout)
        return "timed out after %ds" % timeout

    def _attach(self, deadline):
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return False
            if os.path.exists(self.sock_path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(self.sock_path)
                    self.sock = s
                    threading.Thread(target=self._mgmt_loop, daemon=True,
                                     name="ovpn-mgmt-" + self.iface).start()
                    self._send("state on")
                    self._send("bytecount 3")
                    self._send("hold release")
                    return True
                except OSError:
                    pass
            time.sleep(0.15)
        return False

    def _send(self, line):
        s = self.sock
        if not s:
            return
        try:
            s.sendall((line + "\n").encode())
        except OSError:
            pass

    @staticmethod
    def _mq(value):
        """Quote a credential for the management protocol."""
        return '"%s"' % str(value or "").replace("\\", "\\\\").replace('"', '\\"')

    def _drain(self):
        """openvpn's own log, straight from the process."""
        try:
            for raw in self.proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                self.note(line)
                low = line.lower()
                if "auth_failed" in low or "authenticate/decrypt" in low:
                    self.set(status="error", error=line[:200])
                elif "cannot allocate tun" in low or "operation not permitted" in low:
                    self.set(status="error", error=line[:200])
        except Exception:
            pass
        finally:
            rc = self.proc.wait() if self.proc else 0
            if not self._stopping:
                s = self.state()
                if s["status"] != "error":
                    self.set(status="error", error=self._last_error() or
                             "openvpn exited (%s)" % rc)
                if rc:
                    tail = [line.split(" ", 1)[-1] for line in list(self.log)[-20:]]
                    log.warning("openvpn %s exited (%s); last output:\n%s",
                                self.prof["name"], rc,
                                "\n".join(tail) if tail else "(no output)")
            else:
                # A deliberate stop, but not necessarily a clean one: if we
                # already know why this tunnel is going away -- rejected
                # credentials, a missing password -- that reason outlives the
                # process and is what the UI should keep showing.
                self._settle()
            self._drain_done.set()

    def _last_error(self):
        generic = ("exiting due to fatal error", "process exiting")
        for line in reversed(self.log):
            low = line.lower()
            if any(g in low for g in generic):
                continue
            if any(w in low for w in
                   ("options error", "auth_failed", "tls error", "error",
                    "fatal", "failed", "cannot", "denied", "unsupported")):
                return line.split(" ", 1)[-1][:200]
        return ""

    def _mgmt_loop(self):
        try:
            fh = self.sock.makefile("rb")
            for raw in fh:
                self._on_mgmt(raw.decode(errors="replace").strip())
        except Exception:
            pass

    def _on_mgmt(self, line):
        if not line:
            return
        if line.startswith(">BYTECOUNT:"):
            try:
                rx, tx = line[11:].split(",")[:2]
                with self.lock:
                    self.st["rx"], self.st["tx"] = int(rx), int(tx)
            except ValueError:
                pass
            return
        if line.startswith(">STATE:"):
            f = line[7:].split(",")
            name = f[1] if len(f) > 1 else ""
            status = _OPENVPN_STATES.get(name, "connecting")
            kw = {"detail": name.replace("_", " ").lower()}
            if name == "CONNECTED":
                kw["ip"] = f[3] if len(f) > 3 else ""
                kw["server"] = f[4] if len(f) > 4 else ""
                kw["error"] = ""
                kw["since"] = int(time.time())
            if status == "down" and self._stopping:
                return
            self.set(status=status if status != "down" else "connecting", **kw)
            return
        if line.startswith(">PASSWORD:"):
            self._on_password(line[10:])
            return
        if line.startswith(">LOG:"):
            parts = line[5:].split(",", 2)
            if len(parts) == 3:
                self.note(parts[2])
            return
        if line.startswith(">FATAL:") or line.startswith("ERROR:"):
            self.set(status="error", error=line.split(":", 1)[1].strip()[:200])
            self.note(line)

    def _on_password(self, body):
        if body.startswith("Verification Failed"):
            self._auth_fails += 1
            self.set(status="error",
                     error="VPN credentials were rejected" if self._auth_fails < 2
                     else "VPN credentials were rejected twice — stopping")
            if self._auth_fails >= 2:
                threading.Thread(target=self.stop, daemon=True).start()
            return
        m = re.match(r"Need '([^']+)' (username/password|password)", body)
        if not m:
            return
        realm, want = m.group(1), m.group(2)
        if want == "username/password":
            user = secretsvc.get_secret("vpnuser:" + self.id) or ""
            pw = secretsvc.get_secret("vpnpass:" + self.id) or ""
            if not (user or pw):
                self.set(status="error",
                         error="This tunnel needs a username and password — add them to the profile")
                threading.Thread(target=self.stop, daemon=True).start()
                return
            self.set(status="auth", detail="authenticating")
            self._send("username %s %s" % (self._mq(realm), self._mq(user)))
            self._send("password %s %s" % (self._mq(realm), self._mq(pw)))
        else:
            pp = secretsvc.get_secret("vpnkey:" + self.id) or ""
            if not pp:
                self.set(status="error",
                         error="The private key in this config is encrypted — add its passphrase")
                threading.Thread(target=self.stop, daemon=True).start()
                return
            self._send("password %s %s" % (self._mq(realm), self._mq(pp)))

    # -- teardown ----------------------------------------------------------
    def _settle(self):
        """Come to rest: down, or error when there is a reason on record."""
        err = self.state()["error"]
        self.set(status="error" if err else "down", ip="", detail="",
                 rx_rate=0.0, tx_rate=0.0)

    def stop(self):
        self._stopping = True
        self.set(status="down", detail="stopping")
        # The process is root's, so we cannot signal it directly. Asking it to
        # exit over the management socket is both cleaner and prompt-free --
        # a pkexec teardown would pop a second password dialog.
        self._send("signal SIGTERM")
        end = time.time() + 10
        while self.proc and self.proc.poll() is None and time.time() < end:
            time.sleep(0.2)
        if self.proc and self.proc.poll() is None:
            self._kill_by_pidfile()
        self._reap()
        self._settle()
        return None

    def _kill_by_pidfile(self):
        try:
            pid = int(open(self.pid_path).read().strip())
        except (OSError, ValueError):
            return
        elev = elevation(KILL)
        if elev is None:
            return
        try:
            subprocess.run(elev + [KILL, "-TERM", str(pid)],
                           capture_output=True, timeout=20)
        except Exception:
            pass

    def _reap(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None
        for p in (self.sock_path, self.pid_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    def _counters(self):
        s = self.state()
        if s["status"] != "up":
            return None
        return (s["rx"], s["tx"])

    def alive(self):
        return bool(self.proc and self.proc.poll() is None)


# ------------------------------------------------------------ wireguard

class WireGuardConn(Conn):
    """wg-quick, with status read from the kernel rather than from `wg`.

    `wg show` needs CAP_NET_ADMIN, so polling it would mean an authentication
    prompt every few seconds. The interface's byte counters in /sys and its
    address from `ip` are world-readable and say the same thing.
    """

    def start(self, timeout=60):
        if not WG_QUICK:
            return "wg-quick is not installed (package: wireguard-tools)"
        if not os.path.isfile(config_path(self.prof)):
            return "the configuration file for this profile is missing"
        cfg = effective_config(self.prof)
        if self._up_already():
            self.set(status="up", error="", since=int(time.time()))
            return None
        problem = elevation_problem(WG_QUICK)
        if problem:
            return problem
        elev = elevation(WG_QUICK)
        self.set(status="connecting", error="", detail="wg-quick up",
                 since=int(time.time()), rx=0, tx=0)
        try:
            p = subprocess.run(elev + [WG_QUICK, "up", cfg],
                               capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            self.set(status="error", error="wg-quick timed out")
            return "wg-quick timed out"
        except Exception as e:
            self.set(status="error", error=str(e))
            return str(e)
        for line in (p.stdout + p.stderr).decode(errors="replace").splitlines():
            self.note(line)
        if p.returncode != 0 or not self._up_already():
            err = self._last_line() or "wg-quick exited %d" % p.returncode
            self.set(status="error", error=err[:200])
            return err
        self.set(status="up", error="", detail="", ip=iface_ip(self.iface),
                 server=", ".join((self.prof.get("summary") or {}).get("remotes", [])),
                 since=int(time.time()))
        return None

    def stop(self):
        cfg = effective_config(self.prof)
        if not self._up_already():
            self.set(status="down", error="", ip="", rx_rate=0.0, tx_rate=0.0)
            return None
        elev = elevation(WG_QUICK)
        if elev is None:
            return "No way to get root to bring the tunnel down"
        self.set(status="connecting", detail="wg-quick down")
        try:
            p = subprocess.run(elev + [WG_QUICK, "down", cfg],
                               capture_output=True, timeout=45)
            for line in (p.stdout + p.stderr).decode(errors="replace").splitlines():
                self.note(line)
        except Exception as e:
            self.set(status="error", error=str(e))
            return str(e)
        self.set(status="down", error="", ip="", detail="", rx_rate=0.0, tx_rate=0.0)
        return None

    def _last_line(self):
        return self.log[-1].split(" ", 1)[-1] if self.log else ""

    def _up_already(self):
        return os.path.isdir("/sys/class/net/%s" % self.iface)

    def alive(self):
        return self._up_already()

    def _counters(self):
        return iface_counters(self.iface)


# ----------------------------------------------------------- host helpers

def iface_counters(iface):
    base = "/sys/class/net/%s/statistics/" % iface
    try:
        with open(base + "rx_bytes") as fh:
            rx = int(fh.read().strip())
        with open(base + "tx_bytes") as fh:
            tx = int(fh.read().strip())
        return (rx, tx)
    except (OSError, ValueError):
        return None


def iface_ip(iface):
    try:
        p = subprocess.run([IP, "-j", "-4", "addr", "show", "dev", iface],
                           capture_output=True, timeout=5)
        if p.returncode != 0:
            return ""
        for entry in json.loads(p.stdout or b"[]"):
            for a in entry.get("addr_info", []):
                if a.get("family") == "inet":
                    return a.get("local", "")
    except Exception:
        pass
    return ""


def routes(iface):
    """Networks currently routed through the tunnel, for the UI to show."""
    try:
        p = subprocess.run([IP, "-j", "route", "show", "dev", iface],
                           capture_output=True, timeout=5)
        if p.returncode != 0:
            return []
        return [r.get("dst", "") for r in json.loads(p.stdout or b"[]") if r.get("dst")]
    except Exception:
        return []


def route_dev(addr):
    """Which interface the kernel would use to reach `addr`.

    This is what makes the VPN panel able to say something true rather than
    something hopeful: a host is reachable *through* a tunnel only if the
    routing table agrees.
    """
    if not addr:
        return ""
    try:
        p = subprocess.run([IP, "-j", "route", "get", addr],
                           capture_output=True, timeout=5)
        if p.returncode != 0:
            return ""
        rows = json.loads(p.stdout or b"[]")
        return rows[0].get("dev", "") if rows else ""
    except Exception:
        return ""


# --------------------------------------------------------------- control

def _conn_for(prof):
    with _conn_lock:
        c = _conns.get(prof["id"])
        if c is None or c.prof.get("kind") != prof["kind"]:
            c = (WireGuardConn if prof["kind"] == "wireguard" else OpenVPNConn)(prof)
            _conns[prof["id"]] = c
        else:
            c.prof = prof
            c.st["name"] = prof["name"]
        return c


def up(vpn_id, timeout=75):
    prof = get(vpn_id)
    if not prof:
        return "no such VPN: %s" % vpn_id
    c = _conn_for(prof)
    with c.lock:
        if c.st["status"] in ("connecting", "auth"):
            return "already connecting"
    if c.alive() and c.state()["status"] == "up":
        return None
    log.info("bringing up %s (%s)", prof["name"], prof["kind"])
    err = c.start(timeout=timeout)
    if err:
        log.warning("vpn %s failed: %s", prof["name"], err)
        # Some failures -- a missing client binary, a config that vanished --
        # are decided before the connection has any state to speak of. Record
        # them anyway: `up` is normally called asynchronously, and a return
        # value nobody is waiting on is a failure the UI never hears about.
        if c.state()["status"] != "error":
            c.set(status="error", error=str(err))
    return err


def down(vpn_id):
    prof = get(vpn_id)
    if not prof:
        return "no such VPN: %s" % vpn_id
    c = _conn_for(prof)
    return c.stop()


def ensure_up(vpn_id, timeout=75):
    """Bring a tunnel up if it is not already. Returns an error string or None."""
    prof = get(vpn_id)
    if not prof:
        return "no such VPN: %s" % vpn_id
    c = _conn_for(prof)
    s = c.state()
    if s["status"] == "up" and c.alive():
        return None
    # Another connect may already be racing us -- wait for its outcome rather
    # than starting a second openvpn against the same tun device.
    if s["status"] in ("connecting", "auth"):
        end = time.time() + timeout
        while time.time() < end:
            s = c.state()
            if s["status"] == "up":
                return None
            if s["status"] in ("down", "error"):
                return s["error"] or "the tunnel did not come up"
            time.sleep(0.3)
        return "timed out waiting for %s" % prof["name"]
    return up(vpn_id, timeout=timeout)


def status(vpn_id):
    prof = get(vpn_id)
    if not prof:
        return None
    c = _conn_for(prof)
    s = c.state()
    live = c.alive()
    # Fleet is not the only thing that can raise a tunnel: `wg-quick up` in a
    # terminal, or a systemd unit, leaves an interface the kernel will happily
    # tell us about. Reconciling here means the panel reports the machine's
    # actual state rather than only the part Fleet caused -- including after a
    # failed attempt of our own, whose error must not outlive the facts.
    if prof["kind"] == "wireguard":
        if live and s["status"] not in ("up", "connecting"):
            s = c.set(status="up", error="", ip=iface_ip(c.iface))
        elif not live and s["status"] == "up":
            s = c.set(status="down", ip="")
        elif live and s["status"] == "up" and not s["ip"]:
            s = c.set(ip=iface_ip(c.iface))
    elif not live and s["status"] in ("up", "auth"):
        s = c.set(status="down", ip="")
    s["routes"] = routes(c.iface) if s["status"] == "up" else []
    return s


def all_status():
    return [status(v["id"]) for v in load()]


def tail(vpn_id, n=200):
    prof = get(vpn_id)
    if not prof:
        return []
    return _conn_for(prof).tail(n)


_last_sample = [0.0]


def refresh(interval=2.0):
    """Sample throughput for live tunnels. Returns the states that changed."""
    now = time.time()
    if now - _last_sample[0] < interval:
        return []
    _last_sample[0] = now
    changed = []
    for prof in load():
        c = _conn_for(prof)
        before = c.state()
        if c.sample() or before["status"] != c.state()["status"]:
            changed.append(status(prof["id"]))
    return changed


def autostart():
    """Bring up every profile marked `auto` — called once at startup."""
    for prof in load():
        if prof.get("auto"):
            threading.Thread(target=up, args=(prof["id"],), daemon=True,
                             name="vpn-auto-" + prof["id"][:8]).start()


def shutdown(stop_tunnels=False):
    """Tunnels are deliberately left up unless asked otherwise: a route you
    are using should not vanish because you closed a window."""
    if not stop_tunnels:
        return
    for prof in load():
        try:
            down(prof["id"])
        except Exception:
            pass
