"""Omarchy's semantic palette, exposed to Fleet's browser UI.

The contract here is ``omarchy-theme-color --all`` rather than the layout of
one theme. Omarchy's resolver handles current semantic colors, legacy ANSI
themes, light/dark mode, aliases and derived shades; Fleet only validates and
forwards that resolved output. This keeps a new Omarchy theme usable without a
Fleet release.
"""
import os
import re
import subprocess

OMARCHY_CURRENT = os.path.expanduser("~/.local/state/omarchy/current")
THEME_NAME = os.path.join(OMARCHY_CURRENT, "theme.name")
COLORS_FILE = os.path.join(OMARCHY_CURRENT, "theme", "colors.toml")

FALLBACK = {
    "background": "#1a1b26", "foreground": "#c0caf5", "muted": "#565f89",
    "red": "#f7768e", "green": "#9ece6a", "yellow": "#e0af68", "blue": "#7aa2f7",
    "magenta": "#bb9af7", "cyan": "#7dcfff", "bright_foreground": "#ffffff",
    "dark_background": "#16161e", "darker_background": "#101014",
    "lighter_background": "#24283b", "selection": "#283457", "mode": "dark",
}

# Only these reach the browser. A theme file is user-editable, so keys and CSS
# color values are allow-listed rather than splatted into a stylesheet.
KEYS = ("accent", "background", "foreground", "muted", "red", "green",
        "yellow", "blue", "magenta", "purple", "cyan", "orange", "brown",
        "bright_red", "bright_green", "bright_yellow", "bright_blue",
        "bright_magenta", "bright_purple", "bright_cyan", "bright_foreground",
        "light_foreground", "dark_background", "darker_background",
        "lighter_background", "dark_foreground", "cursor", "selection",
        "selection_background", "selection_foreground", "mode",
        *("color%d" % i for i in range(16)))

_CSS_COLOR = re.compile(
    r"^(?:#[0-9a-fA-F]{3,8}|(?:rgb|rgba|hsl|hsla)\([0-9.,%+\- /]+\))$")


def _safe(v):
    v = (v or "").strip()
    if v in ("dark", "light"):
        return v
    if _CSS_COLOR.fullmatch(v):
        return v
    return None


def _theme_color_tool():
    """Use Omarchy's fixed, package-owned semantic-color resolver."""
    return "/usr/share/omarchy/bin/omarchy-theme-color"


def current_name():
    try:
        with open(THEME_NAME) as fh:
            return fh.read().strip()
    except OSError:
        return "unknown"


def palette(colors_file=None, name=None):
    """Return a complete, browser-safe semantic palette.

    ``colors_file`` and ``name`` are optional so the test matrix can resolve
    every installed Omarchy theme without changing the user's active theme.
    """
    colors = dict(FALLBACK)
    tool = _theme_color_tool()
    if os.path.isfile(tool):
        try:
            argv = [tool]
            if colors_file:
                argv += ["--file", colors_file]
            argv.append("--all")
            p = subprocess.run(argv, capture_output=True, text=True, timeout=8)
            if p.returncode == 0:
                for line in p.stdout.splitlines():
                    if "\t" not in line:
                        continue
                    k, v = line.split("\t", 1)
                    if k in KEYS and _safe(v):
                        colors[k] = _safe(v)
        except Exception:
            pass
    # Stable UI semantics even for an old ANSI-only theme. The Omarchy
    # resolver normally supplies these; these aliases are the last safety net.
    colors["accent"] = colors.get("accent") or colors["blue"]
    colors["selection_background"] = (colors.get("selection_background") or
                                      colors["selection"])
    colors["selection_foreground"] = (colors.get("selection_foreground") or
                                      colors["bright_foreground"])
    colors["name"] = name if name is not None else current_name()
    return colors


def css_vars(colors=None):
    c = colors or palette()
    lines = ["  --%s: %s;" % (k.replace("_", "-"), v)
             for k, v in c.items() if k != "name" and k != "mode"]
    return ":root {\n" + "\n".join(lines) + "\n}\n"


def stamp():
    """Cheap change-detector for an atomic theme switch or palette edit."""
    def one(path):
        try:
            st = os.stat(path)
            return (st.st_ino, st.st_size, st.st_mtime_ns)
        except OSError:
            return (0, 0, 0)
    return (one(THEME_NAME), one(COLORS_FILE))
