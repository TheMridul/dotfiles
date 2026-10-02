"""Full regression suite for Fleet.

Runs against the live server and your real configured hosts, because the
things most likely to break -- ssh quoting, transfer pipes, remote clocks,
distro differences -- do not show up against a mock.

    fleet test

Everything it creates goes under /tmp/fleet-regress-<timestamp> on the target
hosts and is removed at the end; the last checks assert that nothing is left
behind. It is safe to run against production, but it does execute commands and
write files, so read it before you believe that.
"""
import base64, hashlib, json, os, socket, struct, sys, time, urllib.error, urllib.request

try:
    RT = json.load(open(os.path.expanduser("~/.local/state/fleet/runtime.json")))
except OSError:
    sys.exit("Fleet is not running. Start it with `fleet` first.")
PORT, TOK = RT["port"], RT["token"]
TAG = "fleet-regress-%d" % int(time.time())
R = []

def ok(label, cond, extra=""):
    R.append(bool(cond))
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", label,
                           "  — %s" % extra if extra else ""))
    return cond

def api(p, body=None, method=None, raw=None, ctype=None, expect=None, timeout=300):
    url = "http://127.0.0.1:%d/api/%s%st=%s" % (PORT, p, "&" if "?" in p else "?", TOK)
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hdr = {"Content-Type": ctype or "application/json"} if data is not None else {}
    rq = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"),
                                headers=hdr)
    try:
        r = urllib.request.urlopen(rq, timeout=timeout)
        return json.loads(r.read()) if expect != "raw" else r
    except urllib.error.HTTPError as e:
        return {"_status": e.code, "_body": e.read().decode()[:300]}

print("═══ 1. core state ═══")
# A connection can become online just before the poller's first metrics sample.
# Wait for the state this section actually asserts instead of formatting None
# and crashing before `ok()` can report a useful failure.
for _ in range(40):
    st = api("state")
    hosts = st["hosts"]
    online = [h for h in hosts if h["state"]["status"] == "online"]
    if len(online) >= 2 and all((h.get("metrics") or {}).get("age") for h in online[:2]):
        break
    time.sleep(0.5)
ok("state loads", len(hosts) >= 2, "%d hosts, theme %s" % (len(hosts), st["theme"]["name"]))
ok("secret backend reported", st["secret_backend"] == "keyring", st["secret_backend"])
ok("hosts online", len(online) >= 2, [h["name"] for h in online])
A, B = online[0], online[1]
age = (A.get("metrics") or {}).get("age", 0)
ok("age present", age > 0, "%.1f days" % (age / 86400))
ok("speed result carried in state", A.get("speed") is not None,
   "%.1f Mbps" % ((A.get("speed") or {}).get("down_bps", 0) / 1e6))

print("\n═══ 2. input validation (new) ═══")
for body, why in [({"name": "x", "hostname": "a.com\n  ProxyCommand id"}, "newline injection"),
                  ({"name": "x", "hostname": ""}, "empty hostname"),
                  ({"name": "x", "hostname": "a.com", "port": 99999}, "bad port"),
                  ({"name": "x", "hostname": "a.com", "auth": "password"}, "missing password"),
                  ({"name": "x", "hostname": "a.com", "auth": "key",
                    "identity_file": "/nope"}, "missing key")]:
    r = api("hosts", body)
    ok("rejected: %s" % why, r.get("_status") == 400, (r.get("_body") or "")[:70])
ok("ssh_config has no injected directives",
   "ProxyCommand" not in open(os.path.expanduser("~/.local/state/fleet/ssh_config")).read())

print("\n═══ 3. inventory + search ═══")
inv = api("hosts/%s/inventory" % A["id"])
ok("inventory served", len(inv.get("packages", [])) > 100,
   "%d pkgs, %d svcs, %d ports" % (len(inv.get("packages", [])),
                                   len(inv.get("services", [])), len(inv.get("ports", []))))
s = api("search?q=openssh")
ok("cross-host search", len(s["results"]) > 0, "%d hits" % len(s["results"]))

print("\n═══ 4. exec ═══")
r = api("hosts/%s/run" % A["id"], {"command": "echo regress-ok"})
ok("run", r.get("rc") == 0 and "regress-ok" in r.get("stdout", ""))
f = api("fanout", {"command": "id -un", "host_ids": [A["id"], B["id"]]})
ok("fanout across both hosts", all(v["rc"] == 0 for v in f["results"].values()),
   {v["name"]: v["stdout"].strip() for v in f["results"].values()})

print("\n═══ 5. files ═══")
ok("mkdir", api("files/mkdir", {"host": A["id"], "path": "/tmp/%s" % TAG}).get("ok"))
blob = os.urandom(120_000); want = hashlib.sha256(blob).hexdigest()
u = api("files/upload?host=%s&path=/tmp/%s/b.bin" % (A["id"], TAG),
        raw=blob, ctype="application/octet-stream")
ok("upload", u.get("ok") and u["bytes"] == len(blob))
got = api("files/download?host=%s&path=/tmp/%s/b.bin&size=%d" % (A["id"], TAG, len(blob)),
          expect="raw").read()
ok("download round-trips", hashlib.sha256(got).hexdigest() == want)
api("files/write", {"host": A["id"], "path": "/tmp/%s/n.conf" % TAG, "text": "a=1\n"})
ok("read back edit", api("files/read?host=%s&path=/tmp/%s/n.conf" % (A["id"], TAG)).get("text") == "a=1\n")
lst = api("files/list?host=%s&path=/tmp/%s" % (A["id"], TAG))
ok("listing reports host clock", lst.get("now", 0) > 1_700_000_000)
ok("listing reports truncation flag", "truncated" in lst)

job = api("files/transfer", {"src_host": A["id"], "paths": ["/tmp/%s" % TAG],
                             "dst_host": B["id"], "dst_dir": "/tmp"})
for _ in range(120):
    time.sleep(0.4)
    j = [x for x in api("files/jobs")["jobs"] if x["id"] == job["id"]]
    if j and j[0]["status"] != "running": job = j[0]; break
ok("VPS→VPS transfer", job["status"] == "done", "%s bytes in %ss" % (job["done"], job["elapsed"]))
ok("arrived intact", any(e["name"] == "b.bin" for e in
   api("files/list?host=%s&path=/tmp/%s" % (B["id"], TAG)).get("entries", [])))

print("\n═══ 6. delete guards (were broken) ═══")
for p, why in [("/", "root"), ("/etc", "top-level"), ("/home", "top-level"),
               ("~", "home"), ("/a/../..", "dot-dot")]:
    r = api("files/delete", {"host": A["id"], "paths": [p]})
    ok("refuses %s (%s)" % (p, why), not r.get("ok"), (r.get("error") or "")[:50])

print("\n═══ 7. terminal ═══")
sess = api("sessions", {"host_id": A["id"], "cols": 80, "rows": 24})
ok("session opens", sess.get("alive"), sess.get("id"))
api("sessions/%s" % sess["id"], method="DELETE")

print("\n═══ 8. vpn ═══")
tool = api("vpn")["tooling"]
ok("vpn tooling reports the whole path to root",
   all(k in tool for k in ("openvpn", "pkexec", "polkit_agent", "sudoers")),
   "polkit agent running: %s" % tool.get("polkit_agent"))
ok("vpn tooling reported", "openvpn" in tool and "pkexec" in tool,
   "openvpn=%s wg-quick=%s elevation=%s" % (tool["openvpn"] or "-",
   tool["wireguard"] or "-", tool["openvpn_elevation"] or tool["wireguard_elevation"] or "pkexec"))

# OpenVPN often ends with a generic "fatal error" after printing the useful
# reason. Fleet must keep the actionable line for the card and fleet.log.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "server"))
import vpn as vpn_unit
ok("sudo policy parser rejects password-protected allow rules",
   not vpn_unit._sudo_listing_is_nopasswd(
       "Sudoers entry: /etc/sudoers.d/user\n    Commands:\n        ALL\n"))
ok("sudo policy parser accepts explicit NOPASSWD rules",
   vpn_unit._sudo_listing_is_nopasswd(
       "Sudoers entry: /etc/sudoers.d/fleet\n"
       "    Options: !authenticate\n    Commands:\n        /usr/bin/openvpn\n"))
diag = vpn_unit.OpenVPNConn({"id": "regression-diagnostic", "name": TAG,
                             "kind": "openvpn"})
diag.note("Options error: unsupported option in profile")
diag.note("Exiting due to fatal error")
ok("openvpn failure keeps the actionable diagnostic",
   diag._last_error() == "Options error: unsupported option in profile",
   diag._last_error())

# A pasted config that is not one must be refused before it reaches a root
# process, and the reason has to name what was missing.
for cfg, kind, why in [("hello world", "openvpn", "not a config"),
                       ("client\ndev tun\n", "openvpn", "no remote"),
                       ("remote a.com 1194\n", "openvpn", "no certificates"),
                       ("[Peer]\nEndpoint = a:1", "wireguard", "no [Interface]")]:
    r = api("vpn", {"name": TAG, "kind": kind, "config": cfg})
    ok("rejected: %s" % why, r.get("_status") == 400, (r.get("_body") or "")[:60])

RISKY = ("client\ndev tun\nremote vpn.example.com 1194\nca ca.crt\n"
         "up /etc/openvpn/update-resolv-conf\nscript-security 2\n")
an = api("vpn/analyse", {"kind": "openvpn", "config": RISKY})
ok("analyse finds the remote", an["summary"]["remotes"] == ["vpn.example.com 1194"])
ok("analyse flags what runs as root", len(an["summary"]["risky"]) == 2, an["summary"]["risky"])
ok("analyse flags files that must travel with it",
   an["summary"]["external"] == ["ca.crt"], an["summary"]["external"])

WG = ("[Interface]\nPrivateKey = QF7T1zXcYQ1sYy1lFQ1qkP0hV0m3sYzT2eEr9nA0dWs=\n"
      "Address = 10.99.0.2/24\n\n[Peer]\nPublicKey = mR4kEwT7uYc0pLq2XvZaB3nH8jK1sD9fG6hJ4lO2wQs=\n"
      "Endpoint = %s.example.net:51820\nAllowedIPs = 10.99.0.0/24\n" % TAG)
v = api("vpn", {"name": TAG, "kind": "wireguard", "config": WG})
ok("wireguard profile created", v.get("id") and v["status"]["status"] == "down",
   "iface %s" % v["status"]["iface"])
ok("interface name fits the kernel limit", len(v["status"]["iface"]) <= 15,
   v["status"]["iface"])
ok("config stored verbatim", api("vpn/%s/config" % v["id"])["config"].strip() == WG.strip())
CFGDIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or
                      os.path.expanduser("~/.config"), "fleet")
ok("config file is not world-readable",
   oct(os.stat(os.path.join(CFGDIR, "vpn", "%s.conf" % v["status"]["iface"]))
       .st_mode & 0o777) == "0o600")

# Binding a host to a tunnel, and the guard that stops the tunnel vanishing
# out from under it.
hv = api("hosts", {"name": TAG, "hostname": "10.99.0.9", "user": "root",
                   "auth": "agent", "vpn": v["id"]})
ok("host binds to a tunnel", hv.get("vpn") == v["id"], hv.get("vpn_name"))
ok("host reports whether the route really goes there", "vpn_routed" in hv,
   hv.get("vpn_routed"))
d = api("vpn/%s" % v["id"], method="DELETE")
ok("refuses to delete a tunnel a host uses", d.get("_status") == 400,
   (d.get("_body") or "")[:70])
bad = api("hosts", {"name": TAG + "2", "hostname": "10.99.0.10", "vpn": "nope"})
ok("rejects a host pointing at no tunnel", bad.get("_status") == 400,
   (bad.get("_body") or "")[:60])
ok("route lookup answers", api("vpn/route?addr=127.0.0.1").get("dev") == "lo",
   api("vpn/route?addr=127.0.0.1").get("dev"))

# Server override: same certificates, a different endpoint. The import must
# stay untouched and the value must never be able to smuggle in a directive.
OV = ("client\ndev tun\nproto udp\nremote vpn.example.com 1194\nca ca.crt\n"
      "data-ciphers AES-256-GCM:AES-128-GCM:AES-256-CBC\n"
      "data-ciphers-fallback AES-256-CBC\n")
pre = api("vpn/analyse", {"kind": "openvpn", "config": OV,
                          "override": {"host": "sg1.example.com", "port": "443", "proto": "tcp"}})
ok("override preview shows the rewritten lines", len(pre["override_changes"]) == 2,
   pre["override_changes"])
ok("override preview resolves the endpoint",
   pre["effective_remotes"] == ["sg1.example.com 443 tcp"], pre["effective_remotes"])
for bad, why in [({"host": "a.com\nup /bin/sh"}, "newline in host"),
                 ({"host": "a b"}, "space in host"),
                 ({"port": "70000"}, "port out of range"),
                 ({"proto": "sctp"}, "unknown protocol")]:
    r = api("vpn", {"name": TAG + "ov", "kind": "openvpn", "config": OV, "override": bad})
    ok("override rejected: %s" % why, r.get("_status") == 400, (r.get("_body") or "")[:56])

ov = api("vpn", {"name": TAG + "ov", "kind": "openvpn", "config": OV,
                 "override": {"host": "sg1.example.com", "port": "443", "proto": "tcp"}})
ok("override saved", ov.get("overridden") and
   ov["effective_remotes"] == ["sg1.example.com 443 tcp"], ov.get("effective_remotes"))
ok("the imported config is left alone",
   ov["summary"]["remotes"] == ["vpn.example.com 1194"], ov["summary"]["remotes"])
ok("the imported file on disk is untouched",
   "vpn.example.com" in open(os.path.join(CFGDIR, "vpn", "%s.ovpn" % ov["status"]["iface"])).read())
EFF = os.path.join(CFGDIR, "vpn", "effective", "%s.ovpn" % ov["status"]["iface"])
ok("the config Fleet would run carries the override",
   "remote sg1.example.com 443 tcp" in open(EFF).read())
effective_text = open(EFF).read()
ok("override preserves modern OpenVPN cipher directives",
   "data-ciphers AES-256-GCM:AES-128-GCM:AES-256-CBC" in effective_text and
   "data-ciphers-fallback AES-256-CBC" in effective_text)
ok("the generated config is not world-readable",
   oct(os.stat(EFF).st_mode & 0o777) == "0o600")
ok("clearing the override goes back to the import",
   not api("vpn/%s" % ov["id"], {"override": {"host": "", "port": "", "proto": ""}},
           method="PUT")["overridden"])
ok("clearing the override removes the generated config", not os.path.exists(EFF))
ok("removing the profile removes the generated config",
   api("vpn/%s?force=1" % ov["id"], {"force": True}, method="DELETE").get("ok")
   and not os.path.exists(EFF))
ok("forced delete detaches the host",
   api("vpn/%s?force=1" % v["id"], {"force": True}, method="DELETE").get("ok"))
ok("host went back to a direct connection",
   [h for h in api("hosts") if h["name"] == TAG][0]["vpn"] == "")
api("hosts/%s" % hv["id"], method="DELETE")
ok("no tunnel left behind", not [x for x in api("vpn")["vpns"] if x["name"] == TAG])

print("\n═══ 9. cleanup ═══")
for h in (A, B):
    d = api("files/delete", {"host": h["id"], "paths": ["/tmp/%s" % TAG]})
    ok("cleaned %s" % h["name"], d.get("ok"))
    left = [e["name"] for e in api("files/list?host=%s&path=/tmp" % h["id"])["entries"]
            if "regress" in e["name"]]
    ok("nothing left on %s" % h["name"], not left, left)

print("\n%s\n  %d/%d passed\n%s" % ("=" * 46, sum(R), len(R), "=" * 46))
sys.exit(0 if all(R) else 1)
