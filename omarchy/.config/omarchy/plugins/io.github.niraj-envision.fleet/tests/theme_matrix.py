#!/usr/bin/env python3
"""Resolve every installed Omarchy theme without changing the active one."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

import theme

REQUIRED = ("background", "foreground", "accent", "muted", "red", "green",
            "yellow", "blue", "magenta", "cyan", "dark_background",
            "darker_background", "lighter_background", "selection_background",
            "selection_foreground", *("color%d" % i for i in range(16)))


def main():
    roots = ["/usr/share/omarchy/themes",
             os.path.expanduser("~/.config/omarchy/themes")]
    found = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            colors = os.path.join(root, name, "colors.toml")
            if os.path.isfile(colors):
                # A user overlay with the same slug intentionally wins.
                found[name] = colors
    if not found:
        print("No Omarchy themes with colors.toml found", file=sys.stderr)
        return 1

    failures = []
    modes = set()
    for name, path in sorted(found.items()):
        p = theme.palette(path, name)
        missing = [key for key in REQUIRED if not theme._safe(p.get(key))]
        if p.get("mode") not in ("dark", "light"):
            missing.append("mode")
        if missing:
            failures.append("%s: missing/unsafe %s" % (name, ", ".join(missing)))
            print("  [FAIL] %-22s %s" % (name, ", ".join(missing)))
        else:
            modes.add(p["mode"])
            print("  [PASS] %-22s %-5s %s / %s / %s" %
                  (name, p["mode"], p["background"], p["foreground"], p["accent"]))

    if modes != {"dark", "light"}:
        failures.append("matrix did not cover both light and dark modes")
    if failures:
        print("\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print("\n%d themes resolved; dark and light modes covered" % len(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
