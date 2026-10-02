"""Internet speed test, run on the server itself.

What matters for a VPS is the link *the VPS* has, so the test runs remotely,
using nothing but `curl` -- installing speedtest-cli on someone's production
box to answer a dashboard question would be rude.

It does not trust a single endpoint. Measured on a real host, Cloudflare's
speed endpoint delivered 0.7 Mbps while Hetzner delivered 8 Mbps over the same
link, so a one-source test is worse than no test: it reports a confident wrong
number. Fleet probes several geographically spread sources with a small
sample, then runs the full measurement against whichever answered fastest --
which is what a real speed test does when it picks a server.
"""
import threading
import time

import store

# name -> (url, needs_range). Range-capable sources let one big file serve any
# sample size; Cloudflare takes a byte count in the query instead.
SOURCES = [
    ("cloudflare", "https://speed.cloudflare.com/__down?bytes=%(bytes)d", False),
    ("vultr-sgp",  "https://sgp-ping.vultr.com/vultr.com.100MB.bin", True),
    ("hetzner-fsn", "https://fsn1-speed.hetzner.com/100MB.bin", True),
    ("ovh-fr",     "https://proof.ovh.net/files/100Mb.dat", True),
]
UP_URL = "https://speed.cloudflare.com/__up"
HDR_URL = "https://speed.cloudflare.com/__down?bytes=0"

PRESETS = {"quick": (10, 5), "normal": (25, 10), "thorough": (100, 25)}   # MB down, MB up
PROBE_MB = 1


def script(down_mb, up_mb):
    cases = "\n".join(
        '    %s) url="%s"; extra=%s ;;' % (
            name,
            (url % {"bytes": 0}).replace("bytes=0", "bytes=$2") if not rng else url,
            '"--range 0-$(( $2 - 1 ))"' if rng else '""')
        for name, url, rng in SOURCES)
    names = " ".join(n for n, _, _ in SOURCES)
    return r"""
command -v curl >/dev/null 2>&1 || { printf 'ERR|curl is not installed\n'; exit 1; }

dl() {  # $1=source  $2=bytes  $3=max seconds
  url=""; extra=""
  case "$1" in
%(cases)s
  esac
  [ -n "$url" ] || return 1
  curl -sS -o /dev/null --max-time "$3" $extra \
       -w '%%{speed_download}|%%{size_download}|%%{time_total}|%%{http_code}' \
       "$url" 2>/dev/null
}

# Where this host actually is, from the edge's own view of the connection.
# Cloudflare's /meta endpoint 403s for non-browser clients, but the same facts
# come back as cf-meta-* response headers, which are not blocked.
hdrs=$(curl -sS -D - -o /dev/null --max-time 20 "%(hdr)s" 2>/dev/null)
printf '%%s\n' "$hdrs" | tr -d '\r' | while IFS=': ' read -r k v; do
  case "$(printf '%%s' "$k" | tr 'A-Z' 'a-z')" in
    cf-meta-ip)      printf 'IP|%%s\n' "$v" ;;
    cf-meta-colo)    printf 'COLO|%%s\n' "$v" ;;
    cf-meta-city)    printf 'CITY|%%s\n' "$v" ;;
    cf-meta-country) printf 'COUNTRY|%%s\n' "$v" ;;
    cf-meta-asn)     printf 'ASN|%%s\n' "$v" ;;
    cf-ray)          printf 'RAY|%%s\n' "$v" ;;
  esac
done

# Latency: best of three TCP connects, so one unlucky packet does not define it.
best=""
for i in 1 2 3; do
  t=$(curl -sS -o /dev/null --max-time 10 -w '%%{time_connect}' "%(hdr)s" 2>/dev/null)
  case "$t" in ''|*[!0-9.]*) continue ;; esac
  if [ -z "$best" ]; then best=$t
  else best=$(awk -v a="$best" -v b="$t" 'BEGIN{print (b<a)?b:a}'); fi
done
[ -n "$best" ] && printf 'PING|%%s\n' "$best"

# Sample each source briefly, keep the fastest.
bs=0; bn=""
for src in %(names)s; do
  r=$(dl "$src" %(probebytes)d 12)
  sp=${r%%%%|*}
  case "$sp" in ''|*[!0-9.]*) sp=0 ;; esac
  printf 'PROBE|%%s|%%s\n' "$src" "$sp"
  if awk -v a="$sp" -v b="$bs" 'BEGIN{exit !(a>b)}'; then bs=$sp; bn=$src; fi
done
[ -n "$bn" ] || { printf 'ERR|no download source was reachable\n'; exit 1; }
printf 'PICK|%%s\n' "$bn"

printf 'DOWN|%%s\n' "$(dl "$bn" %(downbytes)d 45)"

if [ %(upmb)d -gt 0 ]; then
  u=$(head -c %(upbytes)d /dev/zero | curl -sS -o /dev/null --max-time 45 \
        -w '%%{speed_upload}|%%{size_upload}|%%{time_total}|%%{http_code}' \
        -X POST -H 'Content-Type: application/octet-stream' \
        --data-binary @- "%(up)s" 2>/dev/null)
  printf 'UP|%%s\n' "$u"
fi
printf 'END|\n'
""" % {"cases": cases, "names": names, "hdr": HDR_URL, "up": UP_URL,
       "probebytes": PROBE_MB * 1000000,
       "downbytes": down_mb * 1000000, "upmb": up_mb, "upbytes": up_mb * 1000000}


def _rate(field):
    """curl's speed fields are bytes/sec, and some locales use a comma."""
    sp, size, tt, code = (field.split("|") + ["0", "0", "0", "0"])[:4]
    return (int(float(sp.replace(",", ".")) * 8), int(float(size or 0)),
            float(tt.replace(",", ".") or 0), code)


def parse(out):
    r = {"down_bps": 0, "up_bps": 0, "latency_ms": None, "bytes_down": 0,
         "bytes_up": 0, "colo": "", "city": "", "country": "", "ip": "",
         "asn": "", "source": "", "probes": [], "error": "", "partial": False}
    for line in out.splitlines():
        if "|" not in line:
            continue
        k, v = line.split("|", 1)
        try:
            if k == "ERR":
                r["error"] = v
            elif k == "IP":
                r["ip"] = v.strip()
            elif k == "COLO":
                r["colo"] = v.strip()
            elif k == "CITY":
                r["city"] = v.strip()
            elif k == "COUNTRY":
                r["country"] = v.strip()
            elif k == "ASN":
                r["asn"] = v.strip()
            elif k == "RAY":
                # Only cf-meta-ip reliably comes back; the edge airport code is
                # the suffix of CF-RAY, which is always present.
                tail = v.strip().rsplit("-", 1)
                if len(tail) == 2 and tail[1].isalpha():
                    r["colo"] = r["colo"] or tail[1].upper()
            elif k == "PING":
                r["latency_ms"] = round(float(v) * 1000, 1)
            elif k == "PICK":
                r["source"] = v.strip()
            elif k == "PROBE":
                name, sp = v.split("|", 1)
                r["probes"].append({"source": name,
                                    "bps": int(float(sp.replace(",", ".") or 0) * 8)})
            elif k == "DOWN":
                bps, size, tt, code = _rate(v)
                r["down_bps"], r["bytes_down"] = bps, size
                r["down_seconds"] = tt
                r["partial"] = tt >= 44.0
            elif k == "UP":
                bps, size, tt, code = _rate(v)
                r["up_bps"], r["bytes_up"] = bps, size
        except (ValueError, IndexError):
            continue
    if not r["down_bps"] and not r["error"]:
        r["error"] = "no throughput measured (egress blocked, or no route out?)"
    return r


# ------------------------------------------------------------------ runner

_running = {}
_lock = threading.RLock()
_on_update = None


def set_hook(fn):
    global _on_update
    _on_update = fn


def is_running(host_id):
    with _lock:
        return host_id in _running


def running_hosts():
    with _lock:
        return list(_running)


def _emit(payload):
    if _on_update:
        try:
            _on_update(payload)
        except Exception:
            pass


def estimate_mb(preset):
    down_mb, up_mb = PRESETS.get(preset, PRESETS["normal"])
    return down_mb + PROBE_MB * len(SOURCES), up_mb


def run(host, sshmgr, preset="normal"):
    """Kick off a test in the background. Returns immediately."""
    hid = host["id"]
    with _lock:
        if hid in _running:
            return {"running": True, "already": True}
        _running[hid] = time.time()
    down_mb, up_mb = PRESETS.get(preset, PRESETS["normal"])

    def work():
        started = time.time()
        _emit({"host_id": hid, "status": "running", "preset": preset})
        try:
            rc, out, err = sshmgr.run_script(host, script(down_mb, up_mb), timeout=300)
            res = parse(out)
            if rc != 0 and not res["down_bps"]:
                res["error"] = res["error"] or (err or "speed test failed").strip()[:200]
            res["preset"] = preset
            res["elapsed"] = round(time.time() - started, 1)
            res["ts"] = int(time.time())
            store.save_speedtest(hid, res)
            store.event(hid, "warn" if res["error"] else "info",
                        "Speed test: " + (res["error"] or
                                          "%.1f down / %.1f Mbps up via %s" %
                                          (res["down_bps"] / 1e6, res["up_bps"] / 1e6,
                                           res["source"] or "?")))
            _emit({"host_id": hid, "status": "done", "result": res})
        except Exception as e:
            _emit({"host_id": hid, "status": "error", "result": {"error": str(e)[:200]}})
        finally:
            with _lock:
                _running.pop(hid, None)

    threading.Thread(target=work, daemon=True).start()
    return {"running": True, "preset": preset}
