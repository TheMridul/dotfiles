"""Remote probes.

Each probe is a POSIX sh script piped to the remote `sh -s`. They assume
nothing beyond a shell, coreutils and /proc -- no `hostname`, no `ip`, no
`ss`, no bash -- because a Debian VPS, an Alpine container and a RHEL box all
disagree about which of those exist. Every probe emits TAB-separated records
so parsing stays trivial and a broken line never poisons the rest.
"""
import re
import shlex
import time

# --------------------------------------------------------------- metrics

METRICS_SH = r"""
p() { printf '%s\t%s\n' "$1" "$2"; }
p ts "$(date +%s 2>/dev/null)"
p host "$(cat /proc/sys/kernel/hostname 2>/dev/null || uname -n 2>/dev/null)"
if [ -r /etc/os-release ]; then
  . /etc/os-release 2>/dev/null
  p os "${PRETTY_NAME:-${NAME:-unknown}}"
  p osid "${ID:-}"
fi
p kernel "$(uname -r 2>/dev/null)"
p arch "$(uname -m 2>/dev/null)"
p uptime "$(cut -d' ' -f1 /proc/uptime 2>/dev/null)"
p loadavg "$(cat /proc/loadavg 2>/dev/null)"
p cpucount "$(grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo 1)"
cpumodel=$(awk -F': *' '/^(model name|Model|Hardware|cpu model)/{print $2; exit}' /proc/cpuinfo 2>/dev/null)
[ -z "$cpumodel" ] && [ -r /sys/firmware/devicetree/base/model ] && \
  cpumodel=$(tr -d '\0' < /sys/firmware/devicetree/base/model 2>/dev/null)
[ -z "$cpumodel" ] && command -v lscpu >/dev/null 2>&1 && \
  cpumodel=$(lscpu 2>/dev/null | awk -F': *' '/^Model name/{print $2; exit}')
p cpumodel "$cpumodel"
p procs "$(ls -1 /proc 2>/dev/null | grep -c '^[0-9]')"
p users "$(who 2>/dev/null | wc -l | tr -d ' ')"
p virt "$(systemd-detect-virt 2>/dev/null || echo unknown)"
awk '/^cpu /{print "cpu\t" $2" "$3" "$4" "$5" "$6" "$7" "$8" "$9}' /proc/stat 2>/dev/null
awk '/^(MemTotal|MemAvailable|MemFree|SwapTotal|SwapFree|Buffers|Cached):/ \
     {printf "mem\t%s\t%s\n", substr($1,1,length($1)-1), $2}' /proc/meminfo 2>/dev/null
df -P -k 2>/dev/null | awk 'NR>1 && $1 !~ /^(tmpfs|devtmpfs|overlay|shm|udev|none|efivarfs)$/ \
     && $6 !~ /^\/(proc|sys|dev|run)/ {printf "disk\t%s\t%s\t%s\t%s\t%s\n",$1,$2,$3,$4,$6}'
awk 'NR>2 {sub(/:$/,"",$1); if ($1 != "lo") printf "net\t%s\t%s\t%s\n", $1, $2, $10}' /proc/net/dev 2>/dev/null
if command -v ip >/dev/null 2>&1; then
  ip -o -4 addr show 2>/dev/null | awk '{print "ip4\t" $2 "\t" $4}'
  ip -o -6 addr show scope global 2>/dev/null | awk '{print "ip6\t" $2 "\t" $4}'
  ip route show default 2>/dev/null | awk '{print "gw\t" $3; exit}'
elif command -v ifconfig >/dev/null 2>&1; then
  ifconfig 2>/dev/null | awk '/^[a-z]/{i=$1; sub(/:$/,"",i)} /inet /{print "ip4\t" i "\t" $2}'
fi
for z in /sys/class/thermal/thermal_zone*/temp; do
  [ -r "$z" ] && printf 'temp\t%s\n' "$(cat "$z" 2>/dev/null)" && break
done
for c in "$(stat -c %W / 2>/dev/null)" "$(stat -c %Y /lost+found 2>/dev/null)" \
         "$(stat -c %W /etc/machine-id 2>/dev/null)"; do
  case "$c" in ''|*[!0-9]*) continue ;; esac
  [ "$c" -gt 946684800 ] || continue          # sanity: after 2000-01-01
  [ -z "${born:-}" ] && born="$c"
  [ "$c" -lt "$born" ] && born="$c"
done
[ -n "${born:-}" ] && p born "$born"
[ -f /var/run/reboot-required ] && p reboot_required 1
[ -f /run/reboot-required ] && p reboot_required 1
ps -eo pcpu,pmem,rss,comm,user 2>/dev/null | sort -rn -k1 | head -9 | \
  awk 'NR>0 {printf "proc\t%s\t%s\t%s\t%s\t%s\n",$1,$2,$3,$4,$5}'
echo '__FLEET_END__'
"""


def _rows(out):
    for line in out.splitlines():
        if line == "__FLEET_END__":
            break
        if line:
            yield line.split("\t")


def parse_metrics(out, prev=None):
    """Turn probe output into a metrics dict.

    CPU percentage needs two samples, so the caller threads the previous raw
    jiffie counters back in through `prev`; the first poll after a connect
    reports cpu_pct None rather than a bogus 0.
    """
    m = {"disks": [], "nets": [], "ip4": [], "ip6": [], "top": [], "raw": {}}
    mem = {}
    for r in _rows(out):
        k = r[0]
        try:
            if k == "cpu":
                m["raw"]["cpu"] = [int(x) for x in r[1].split()]
            elif k == "mem" and len(r) > 2:
                mem[r[1]] = int(r[2])
            elif k == "disk" and len(r) > 5:
                total, used, avail = int(r[2]) * 1024, int(r[3]) * 1024, int(r[4]) * 1024
                m["disks"].append({"dev": r[1], "total": total, "used": used,
                                   "avail": avail, "mount": r[5],
                                   "pct": round(used / total * 100, 1) if total else 0})
            elif k == "net" and len(r) > 3:
                m["nets"].append({"iface": r[1], "rx": int(r[2]), "tx": int(r[3])})
            elif k == "ip4" and len(r) > 2:
                m["ip4"].append({"iface": r[1], "addr": r[2]})
            elif k == "ip6" and len(r) > 2:
                m["ip6"].append({"iface": r[1], "addr": r[2]})
            elif k == "proc" and len(r) > 5:
                m["top"].append({"cpu": float(r[1]), "mem": float(r[2]),
                                 "rss": int(r[3]) * 1024, "cmd": r[4], "user": r[5]})
            elif k == "temp":
                v = int(r[1])
                m["temp_c"] = round(v / 1000.0, 1) if v > 1000 else float(v)
            elif len(r) > 1:
                m[k] = r[1]
        except (ValueError, IndexError, ZeroDivisionError):
            continue

    for f in ("uptime", "cpucount", "procs", "users", "ts", "born"):
        if m.get(f):
            try:
                m[f] = float(m[f]) if f == "uptime" else int(float(m[f]))
            except ValueError:
                pass

    if m.get("loadavg"):
        parts = str(m["loadavg"]).split()
        m["load"] = [float(x) for x in parts[:3]] if len(parts) >= 3 else [0, 0, 0]

    total = mem.get("MemTotal", 0) * 1024
    avail = mem.get("MemAvailable", mem.get("MemFree", 0)) * 1024
    m["mem"] = {"total": total, "avail": avail, "used": total - avail,
                "pct": round((total - avail) / total * 100, 1) if total else 0,
                "swap_total": mem.get("SwapTotal", 0) * 1024,
                "swap_used": (mem.get("SwapTotal", 0) - mem.get("SwapFree", 0)) * 1024}

    m["cpu_pct"] = None
    cur = m["raw"].get("cpu")
    old = (prev or {}).get("raw", {}).get("cpu")
    if cur and old and len(cur) == len(old):
        dt = sum(cur) - sum(old)
        idle = (cur[3] + cur[4]) - (old[3] + old[4])   # idle + iowait
        if dt > 0:
            m["cpu_pct"] = round(max(0.0, min(100.0, (dt - idle) / dt * 100)), 1)

    # Interface throughput, derived the same way as CPU.
    pnets = {n["iface"]: n for n in (prev or {}).get("nets", [])}
    pts = (prev or {}).get("ts")
    span = (m.get("ts", 0) - pts) if pts else 0
    for n in m["nets"]:
        o = pnets.get(n["iface"])
        if o and span > 0:
            n["rx_bps"] = max(0, int((n["rx"] - o["rx"]) / span))
            n["tx_bps"] = max(0, int((n["tx"] - o["tx"]) / span))
    m["primary_ip"] = next((a["addr"].split("/")[0] for a in m["ip4"]
                            if not a["addr"].startswith("127.")), "")
    m["disk_worst"] = max((d["pct"] for d in m["disks"]), default=0)
    # Age of the machine itself, measured on the host's own clock so a server
    # whose time differs from ours does not report a negative age.
    if m.get("born") and m.get("ts"):
        m["age"] = max(0, int(m["ts"]) - int(m["born"]))
    return m


# ------------------------------------------------------------- inventory

INVENTORY_SH = r"""
# A non-login shell misses everything a version manager puts on PATH, so pull
# in the usual suspects before scanning for runtimes.
for d in /usr/local/bin /usr/local/sbin /usr/sbin /sbin /snap/bin \
         "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.bun/bin" "$HOME/go/bin" \
         "$HOME/.local/share/mise/shims" "$HOME/.nvm/versions/node"/*/bin \
         "$HOME/.rbenv/shims" "$HOME/.pyenv/shims" /opt/homebrew/bin; do
  [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$PATH:$d" ;; esac
done
export PATH

sec() { printf '\n##%s\n' "$1"; }

sec pkgmgr
for m in apt-get dnf yum pacman apk zypper; do
  command -v $m >/dev/null 2>&1 && echo "$m" && break
done

sec packages
if command -v dpkg-query >/dev/null 2>&1; then
  dpkg-query -W -f='${Package}\t${Version}\t${binary:Summary}\n' 2>/dev/null
elif command -v rpm >/dev/null 2>&1; then
  rpm -qa --qf '%{NAME}\t%{VERSION}-%{RELEASE}\t%{SUMMARY}\n' 2>/dev/null
elif command -v pacman >/dev/null 2>&1; then
  pacman -Q 2>/dev/null | awk '{print $1"\t"$2"\t"}'
elif command -v apk >/dev/null 2>&1; then
  apk info -v 2>/dev/null | awk '{n=$0; sub(/-[^-]*-[^-]*$/,"",n); print n"\t"$0"\t"}'
fi

sec manual
if command -v apt-mark >/dev/null 2>&1; then apt-mark showmanual 2>/dev/null
elif command -v pacman >/dev/null 2>&1; then pacman -Qqe 2>/dev/null
elif command -v dnf >/dev/null 2>&1; then dnf repoquery --userinstalled --qf '%{name}' 2>/dev/null
fi

sec updates
if command -v apt-get >/dev/null 2>&1; then
  apt-get -s -o Debug::NoLocking=true upgrade 2>/dev/null | grep -c '^Inst '
elif command -v dnf >/dev/null 2>&1; then dnf -q check-update 2>/dev/null | grep -c '^[a-zA-Z0-9]'
elif command -v pacman >/dev/null 2>&1; then pacman -Quq 2>/dev/null | wc -l
elif command -v apk >/dev/null 2>&1; then apk version -l '<' 2>/dev/null | tail -n +2 | wc -l
fi

sec services
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --type=service --all --no-legend --no-pager --plain 2>/dev/null | \
    awk '{unit=$1; act=$3; st=$4; $1=$2=$3=$4=""; gsub(/^ +| +$/,"");
          printf "%s\t%s\t%s\t%s\n", unit, act, st, $0}'
elif command -v rc-status >/dev/null 2>&1; then
  rc-status -a 2>/dev/null | awk '/\[/{gsub(/[][]/,""); printf "%s\t%s\t%s\t\n",$1,$3,$3}'
elif command -v service >/dev/null 2>&1; then
  service --status-all 2>/dev/null | awk '{printf "%s\tunknown\tunknown\t\n",$NF}'
fi

sec ports
if command -v ss >/dev/null 2>&1; then
  ss -H -tulnp 2>/dev/null | awk '{printf "%s\t%s\t%s\t%s\n",$1,$5,$2,$7}'
elif command -v netstat >/dev/null 2>&1; then
  netstat -tulnp 2>/dev/null | awk 'NR>2{printf "%s\t%s\t%s\t%s\n",$1,$4,$6,$7}'
fi

sec docker
if command -v docker >/dev/null 2>&1; then
  docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.ID}}' 2>/dev/null
fi

sec docker_images
if command -v docker >/dev/null 2>&1; then
  docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.ID}}' 2>/dev/null
fi

sec compose
for d in /opt /srv /home /root /var/www; do
  [ -d "$d" ] && find "$d" -maxdepth 4 -name 'docker-compose.y*ml' -o -maxdepth 4 -name 'compose.y*ml' 2>/dev/null
done | head -40

sec runtimes
for c in node npm pnpm yarn bun deno python3 pip3 ruby gem go rustc cargo java php composer \
         psql mysql redis-cli mongod nginx apache2 httpd caddy docker podman kubectl helm \
         git tmux vim nvim zsh fish ufw firewall-cmd fail2ban-client certbot systemctl; do
  if command -v $c >/dev/null 2>&1; then
    v=$($c --version 2>/dev/null | head -1 | tr -d '\r')
    [ -z "$v" ] && v=$($c -v 2>/dev/null | head -1 | tr -d '\r')
    printf '%s\t%s\t%s\n' "$c" "$(command -v $c)" "$v"
  fi
done

sec users
awk -F: '$3>=1000 && $3<65534 {printf "%s\t%s\t%s\n",$1,$3,$7}' /etc/passwd 2>/dev/null

sec cron
for f in /etc/crontab /etc/cron.d/*; do
  [ -f "$f" ] && awk -v F="$f" '!/^#/ && NF>5 {print F"\t"$0}' "$f" 2>/dev/null
done | head -40
crontab -l 2>/dev/null | awk '!/^#/ && NF>5 {print "user\t"$0}' | head -40

sec firewall
if command -v ufw >/dev/null 2>&1; then ufw status 2>/dev/null | head -20
elif command -v firewall-cmd >/dev/null 2>&1; then firewall-cmd --list-all 2>/dev/null | head -20
fi

sec disk_big
du -shx /var /home /opt /srv /usr /root 2>/dev/null | sort -rh | head -10

sec end
"""


def parse_inventory(out):
    inv = {"pkgmgr": "", "packages": [], "manual": [], "updates": 0, "services": [],
           "ports": [], "docker": [], "docker_images": [], "compose": [],
           "runtimes": [], "users": [], "cron": [], "firewall": "", "disk_big": []}
    section = None
    fw, dbig = [], []
    for line in out.splitlines():
        if line.startswith("##"):
            section = line[2:].strip()
            continue
        if not line.strip() or section in (None, "end"):
            continue
        f = line.split("\t")
        try:
            if section == "pkgmgr":
                inv["pkgmgr"] = line.strip()
            elif section == "packages" and f[0]:
                inv["packages"].append({"name": f[0],
                                        "version": f[1] if len(f) > 1 else "",
                                        "desc": f[2] if len(f) > 2 else ""})
            elif section == "manual":
                inv["manual"].append(line.strip())
            elif section == "updates":
                inv["updates"] = int(line.strip() or 0)
            elif section == "services" and f[0]:
                inv["services"].append({"name": f[0].replace(".service", ""),
                                        "active": f[1] if len(f) > 1 else "",
                                        "sub": f[2] if len(f) > 2 else "",
                                        "desc": f[3].strip() if len(f) > 3 else ""})
            elif section == "ports" and len(f) >= 2:
                addr = f[1]
                port = addr.rsplit(":", 1)[-1]
                proc = ""
                mm = re.search(r'"([^"]+)"', f[3] if len(f) > 3 else "")
                if mm:
                    proc = mm.group(1)
                elif len(f) > 3 and "/" in f[3]:
                    proc = f[3].split("/")[-1].strip()
                inv["ports"].append({"proto": f[0], "addr": addr, "port": port,
                                     "state": f[2] if len(f) > 2 else "", "proc": proc})
            elif section == "docker" and f[0]:
                inv["docker"].append({"name": f[0], "image": f[1] if len(f) > 1 else "",
                                      "status": f[2] if len(f) > 2 else "",
                                      "ports": f[3] if len(f) > 3 else "",
                                      "id": f[4] if len(f) > 4 else ""})
            elif section == "docker_images" and f[0]:
                inv["docker_images"].append({"tag": f[0], "size": f[1] if len(f) > 1 else "",
                                             "id": f[2] if len(f) > 2 else ""})
            elif section == "compose":
                inv["compose"].append(line.strip())
            elif section == "runtimes" and f[0]:
                inv["runtimes"].append({"name": f[0], "path": f[1] if len(f) > 1 else "",
                                        "version": f[2] if len(f) > 2 else ""})
            elif section == "users" and f[0]:
                inv["users"].append({"name": f[0], "uid": f[1] if len(f) > 1 else "",
                                     "shell": f[2] if len(f) > 2 else ""})
            elif section == "cron":
                inv["cron"].append(line.strip())
            elif section == "firewall":
                fw.append(line)
            elif section == "disk_big" and len(f) >= 1:
                dbig.append(line.strip())
        except (ValueError, IndexError):
            continue
    inv["firewall"] = "\n".join(fw).strip()
    inv["disk_big"] = dbig
    inv["collected"] = int(time.time())
    return inv


# ------------------------------------------------- frequently used commands

HISTORY_SH = r"""
for f in "$HOME/.bash_history" "$HOME/.zsh_history" "$HOME/.local/share/fish/fish_history" \
         /root/.bash_history /root/.zsh_history; do
  [ -r "$f" ] || continue
  case "$f" in
    *zsh_history) sed 's/^: [0-9]*:[0-9]*;//' "$f" 2>/dev/null ;;
    *fish_history) grep '^- cmd: ' "$f" 2>/dev/null | sed 's/^- cmd: //' ;;
    *) cat "$f" 2>/dev/null ;;
  esac
done | tail -n %d
"""

_NOISE = re.compile(r"^(ls|ll|cd|pwd|clear|exit|c|l|la|top|htop|history|q|vi|vim|nano)\b\s*$")
_SECRETY = re.compile(r"(password|passwd|token|secret|api[-_]?key|BEGIN [A-Z ]*PRIVATE)", re.I)


def parse_history(out, limit=25):
    """Rank a host's shell history into its genuinely frequent commands.

    Bare navigation is dropped, near-duplicates collapse on their normalized
    form, and anything that looks like it carries a credential is skipped
    outright so a secret typed at a prompt never lands in the UI or the index.
    """
    counts, first_seen, recency = {}, {}, {}
    for i, raw in enumerate(out.splitlines()):
        cmd = raw.strip()
        if not cmd or len(cmd) < 3 or len(cmd) > 400:
            continue
        if _NOISE.match(cmd) or _SECRETY.search(cmd):
            continue
        key = re.sub(r"\s+", " ", cmd)
        counts[key] = counts.get(key, 0) + 1
        first_seen.setdefault(key, i)
        recency[key] = i
    n = max(1, len(out.splitlines()))
    ranked = sorted(counts.items(),
                    key=lambda kv: (-kv[1], -(recency[kv[0]] / n)))
    return [{"cmd": c, "count": n_, "last_rank": recency[c]}
            for c, n_ in ranked[:limit]]


# ----------------------------------------------------------- package tools

PKG_INSTALL = {
    "apt-get": "DEBIAN_FRONTEND=noninteractive apt-get install -y {pkgs}",
    "dnf": "dnf install -y {pkgs}",
    "yum": "yum install -y {pkgs}",
    "pacman": "pacman -S --noconfirm --needed {pkgs}",
    "apk": "apk add --no-cache {pkgs}",
    "zypper": "zypper --non-interactive install {pkgs}",
}
PKG_REMOVE = {
    "apt-get": "DEBIAN_FRONTEND=noninteractive apt-get remove -y {pkgs}",
    "dnf": "dnf remove -y {pkgs}",
    "yum": "yum remove -y {pkgs}",
    "pacman": "pacman -Rns --noconfirm {pkgs}",
    "apk": "apk del {pkgs}",
    "zypper": "zypper --non-interactive remove {pkgs}",
}
PKG_UPDATE = {
    "apt-get": "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
    "dnf": "dnf upgrade -y",
    "yum": "yum update -y",
    "pacman": "pacman -Syu --noconfirm",
    "apk": "apk update && apk upgrade",
    "zypper": "zypper --non-interactive update",
}
PKG_SEARCH = {
    "apt-get": "apt-cache search {q} | head -40",
    "dnf": "dnf search {q} 2>/dev/null | head -40",
    "yum": "yum search {q} 2>/dev/null | head -40",
    "pacman": "pacman -Ss {q} | head -60",
    "apk": "apk search -v {q} | head -40",
    "zypper": "zypper search {q} | head -40",
}


def pkg_command(kind, pkgmgr, pkgs=None, query=None, as_root=True):
    table = {"install": PKG_INSTALL, "remove": PKG_REMOVE,
             "update": PKG_UPDATE, "search": PKG_SEARCH}[kind]
    tpl = table.get(pkgmgr)
    if not tpl:
        return None
    cmd = tpl.format(pkgs=" ".join(shlex.quote(p) for p in (pkgs or [])),
                     q=shlex.quote(query or ""))
    if as_root and kind != "search":
        cmd = "if [ \"$(id -u)\" -ne 0 ]; then sudo -n sh -c %s || sudo sh -c %s; else sh -c %s; fi" % (
            shlex.quote(cmd), shlex.quote(cmd), shlex.quote(cmd))
    return cmd
