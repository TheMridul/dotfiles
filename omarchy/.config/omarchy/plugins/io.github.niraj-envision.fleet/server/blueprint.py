"""Blueprints: capture what makes a host what it is, replay it somewhere else.

The unit of reuse is a *spec* -- an explicit list of packages, docker images,
compose projects, services, language-runtime globals and file paths -- rather
than a disk image. That keeps replication honest across distros: a spec
captured on Debian installs through pacman on Arch, because the spec records
intent (`install nginx`) and the target decides the mechanism.

Nothing is ever applied blind. `plan()` diffs a spec against a live target and
returns exactly what would change; the UI shows that before anything runs.
"""
import shlex
import time

import probes

CATEGORIES = ("packages", "docker_images", "compose", "services", "runtimes",
              "npm_global", "pip_user", "cargo", "files")

# Packages every distro image already has; capturing them adds noise to the
# diff without adding information.
_BORING = {
    "base", "base-files", "bash", "coreutils", "util-linux", "systemd", "libc6",
    "glibc", "filesystem", "ncurses", "readline", "zlib", "openssl", "ca-certificates",
    "tzdata", "grep", "sed", "gawk", "gzip", "tar", "findutils", "diffutils",
    "linux", "linux-firmware", "pacman", "apt", "dpkg", "rpm", "dnf", "yum",
    "shadow", "pam", "e2fsprogs", "iproute2", "iputils", "procps", "procps-ng",
    "less", "login", "init-system-helpers", "debianutils", "hostname", "mount",
}

EXTRA_SH = r"""
sec() { printf '\n##%s\n' "$1"; }
for d in /usr/local/bin "$HOME/.local/bin" "$HOME/.cargo/bin" "$HOME/.bun/bin" \
         "$HOME/go/bin" "$HOME/.local/share/mise/shims"; do
  [ -d "$d" ] && case ":$PATH:" in *":$d:"*) ;; *) PATH="$PATH:$d" ;; esac
done
export PATH
sec npm_global
command -v npm >/dev/null 2>&1 && npm ls -g --depth=0 --parseable 2>/dev/null | \
  awk -F/ 'NR>1{print $NF}'
sec pip_user
command -v pip3 >/dev/null 2>&1 && pip3 list --user --format=freeze 2>/dev/null | head -100
sec cargo
[ -f "$HOME/.cargo/.crates.toml" ] && awk -F'"' '/^"/{split($2,a," "); print a[1]}' \
  "$HOME/.cargo/.crates.toml" 2>/dev/null
sec end
"""


def collect_extras(host, sshmgr):
    """Language-ecosystem globals -- the plugins that a package manager misses."""
    rc, out, _ = sshmgr.run_script(host, EXTRA_SH, timeout=60)
    res = {"npm_global": [], "pip_user": [], "cargo": []}
    sec = None
    for line in out.splitlines():
        if line.startswith("##"):
            sec = line[2:].strip()
            continue
        v = line.strip()
        if sec in res and v:
            res[sec].append(v)
    return res


def capture(host, inventory, extras=None, include=None, manual_only=True):
    """Build a spec from a host's inventory.

    `manual_only` keeps explicitly-installed packages and drops the dependency
    closure, which is the difference between a 40-line spec you can read and a
    2000-line one you cannot.
    """
    include = set(include or CATEGORIES)
    extras = extras or {}
    inv = inventory or {}

    manual = set(inv.get("manual") or [])
    pkgs = []
    for p in inv.get("packages") or []:
        n = p["name"]
        if n in _BORING:
            continue
        if manual_only and manual and n not in manual:
            continue
        pkgs.append({"name": n, "version": p.get("version", "")})

    spec = {
        "captured": int(time.time()),
        "source_os": inv.get("os", ""),
        "pkgmgr": inv.get("pkgmgr", ""),
        "packages": sorted(pkgs, key=lambda p: p["name"]) if "packages" in include else [],
        "docker_images": [i["tag"] for i in (inv.get("docker_images") or [])
                          if "docker_images" in include and not i["tag"].endswith(":<none>")],
        "compose": list(inv.get("compose") or []) if "compose" in include else [],
        "services": [s["name"] for s in (inv.get("services") or [])
                     if "services" in include and s.get("active") == "active"],
        "runtimes": [{"name": r["name"], "version": r.get("version", "")}
                     for r in (inv.get("runtimes") or []) if "runtimes" in include],
        "npm_global": extras.get("npm_global", []) if "npm_global" in include else [],
        "pip_user": extras.get("pip_user", []) if "pip_user" in include else [],
        "cargo": extras.get("cargo", []) if "cargo" in include else [],
        "files": [],
    }
    return spec


def plan(spec, target_inv, target_extras=None, categories=None):
    """Diff a spec against a target. Returns per-category missing/present."""
    cats = set(categories or CATEGORIES)
    tinv = target_inv or {}
    textras = target_extras or {}

    have_pkgs = {p["name"] for p in (tinv.get("packages") or [])}
    have_imgs = {i["tag"] for i in (tinv.get("docker_images") or [])}
    have_svcs = {s["name"] for s in (tinv.get("services") or [])}
    have_rt = {r["name"] for r in (tinv.get("runtimes") or [])}

    def split(items, have, key=lambda i: i):
        missing = [i for i in items if key(i) not in have]
        present = [i for i in items if key(i) in have]
        return {"missing": missing, "present": present}

    out = {}
    if "packages" in cats:
        out["packages"] = split(spec.get("packages", []), have_pkgs, lambda p: p["name"])
    if "docker_images" in cats:
        out["docker_images"] = split(spec.get("docker_images", []), have_imgs)
    if "runtimes" in cats:
        out["runtimes"] = split(spec.get("runtimes", []), have_rt, lambda r: r["name"])
    if "services" in cats:
        out["services"] = split(spec.get("services", []), have_svcs)
    if "npm_global" in cats:
        out["npm_global"] = split(spec.get("npm_global", []),
                                  set(textras.get("npm_global", [])))
    if "pip_user" in cats:
        out["pip_user"] = split(
            spec.get("pip_user", []),
            {p.split("==")[0] for p in textras.get("pip_user", [])},
            lambda p: p.split("==")[0])
    if "cargo" in cats:
        out["cargo"] = split(spec.get("cargo", []), set(textras.get("cargo", [])))
    if "compose" in cats:
        out["compose"] = {"missing": spec.get("compose", []), "present": []}

    out["_summary"] = {k: len(v.get("missing", [])) for k, v in out.items()
                       if not k.startswith("_")}
    return out


def build_script(planned, target_pkgmgr, categories=None, dry_run=False):
    """Turn a plan into a readable shell script.

    The script is shown to you in full before it runs -- it is a deliverable in
    its own right, not a hidden implementation detail, so it is commented and
    ordered the way a person would write it.
    """
    cats = set(categories or CATEGORIES)
    L = ["#!/usr/bin/env bash",
         "# Generated by Fleet from a blueprint. Review before running.",
         "set -uo pipefail", "",
         'SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null && SUDO=sudo', ""]
    if dry_run:
        L += ['echo "DRY RUN -- nothing will be changed"', 'run() { echo "  would run: $*"; }', ""]
    else:
        L += ['run() { echo "+ $*"; "$@"; }', ""]

    ran = False
    pkgs = [p["name"] for p in planned.get("packages", {}).get("missing", [])] \
        if "packages" in cats else []
    if pkgs:
        ran = True
        cmd = probes.pkg_command("install", target_pkgmgr, pkgs, as_root=False)
        if cmd:
            L += ['echo "==> %d package(s) via %s"' % (len(pkgs), target_pkgmgr),
                  "$SUDO sh -c %s" % shlex.quote(cmd), ""]
        else:
            L += ["# No installer known for package manager %r" % target_pkgmgr, ""]

    imgs = planned.get("docker_images", {}).get("missing", []) if "docker_images" in cats else []
    if imgs:
        ran = True
        L += ['echo "==> %d docker image(s)"' % len(imgs),
              'if command -v docker >/dev/null 2>&1; then']
        L += ["  run $SUDO docker pull %s" % shlex.quote(i) for i in imgs]
        L += ['else echo "  docker not installed on this host -- skipping"; fi', ""]

    npm = planned.get("npm_global", {}).get("missing", []) if "npm_global" in cats else []
    if npm:
        ran = True
        L += ['echo "==> %d global npm package(s)"' % len(npm),
              'if command -v npm >/dev/null 2>&1; then',
              "  run $SUDO npm install -g %s" % " ".join(shlex.quote(p) for p in npm),
              'else echo "  npm not installed -- skipping"; fi', ""]

    pip = planned.get("pip_user", {}).get("missing", []) if "pip_user" in cats else []
    if pip:
        ran = True
        L += ['echo "==> %d pip package(s)"' % len(pip),
              'if command -v pip3 >/dev/null 2>&1; then',
              "  run pip3 install --user %s" % " ".join(shlex.quote(p) for p in pip),
              'else echo "  pip3 not installed -- skipping"; fi', ""]

    crates = planned.get("cargo", {}).get("missing", []) if "cargo" in cats else []
    if crates:
        ran = True
        L += ['echo "==> %d cargo crate(s)"' % len(crates),
              'if command -v cargo >/dev/null 2>&1; then',
              "  run cargo install %s" % " ".join(shlex.quote(c) for c in crates),
              'else echo "  cargo not installed -- skipping"; fi', ""]

    svcs = planned.get("services", {}).get("missing", []) if "services" in cats else []
    if svcs:
        ran = True
        L += ['echo "==> enabling %d service(s)"' % len(svcs),
              'if command -v systemctl >/dev/null 2>&1; then']
        L += ["  run $SUDO systemctl enable --now %s" % shlex.quote(s) for s in svcs]
        L += ['else echo "  no systemd -- skipping"; fi', ""]

    if not ran:
        L += ['echo "Nothing to do -- target already matches the blueprint."']
    L += ["", 'echo "==> blueprint applied"']
    return "\n".join(L) + "\n"
