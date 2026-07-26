# Troubleshooting

Caveats specific to this **manual** Omarchy install (git-cloned to
`~/.local/share/omarchy`, not the official ISO) on **CachyOS**. These bugs
mostly don't show up on a stock Omarchy ISO install because that image
controls exactly which packages (Qt5 vs Qt6, pacman repos, etc.) are present.
On a CachyOS base, assumptions Omarchy makes can be wrong.

## SDDM login theme crashes / blank or unresponsive greeter

**Symptom:** greeter flashes and shows nothing, or renders but keyboard/mouse
input does nothing.

**Cause:** SDDM runs a theme under the legacy Qt5 `sddm-greeter` binary
*unless* the theme's `metadata.desktop` explicitly sets `QtVersion=6`. Omarchy's
shipped theme (`default/sddm/omarchy/metadata.desktop`) doesn't set this,
because the official ISO only ever installs Qt6 anyway so it never mattered.
This CachyOS system only has Qt6 libraries installed — no `libQt5Quick.so.5` —
so the greeter fails to even launch. Confirm via:

```bash
journalctl -u sddm --no-pager -n 50 | grep -i "shared librar\|greeter"
```

**Fix (already applied, kept for reference / if it regresses):**

```bash
echo QtVersion=6 | sudo tee -a /usr/share/sddm/themes/omarchy/metadata.desktop
sudo systemctl restart sddm.service
```

Also patched at the source so `omarchy refresh sddm` / `omarchy plymouth reset`
carry the fix forward automatically:
`~/.local/share/omarchy/default/sddm/omarchy/metadata.desktop` now includes
`QtVersion=6`, `MainScript=Main.qml`, `ConfigFile=theme.conf`. Since
`OMARCHY_PATH` is a git clone, an `omarchy update` that touches this exact
upstream file could produce a merge conflict here — if so, keep those three
lines when resolving.

**Do NOT** set `DisplayServer=wayland` in `/etc/sddm.conf.d/10-wayland.conf`
on this system — it routes through a different SDDM code path that (separately
from the Qt5/6 issue) failed to hand off to the Hyprland greeter compositor
correctly and crash-looped. Stick to the X11 greeter path (i.e. don't create
`10-wayland.conf`); only `/etc/sddm.conf.d/10-theme.conf` (`Current=omarchy`)
is needed for the modern login screen.

## `omarchy update` silently wiped CachyOS pacman repos

**Symptom:** `pacman -Sl` stops listing `cachyos`, `cachyos-v3`,
`cachyos-extra-v3`, `cachyos-core-v3`; `[omarchy]` repo switches from `stable`
to `edge`.

**Cause:** an Omarchy migration overwrote `/etc/pacman.conf` wholesale instead
of appending to it, since it assumes a plain Arch base, not CachyOS's
multi-repo setup.

**Fix:** keep a backup (`/etc/pacman.conf.bak-preomarchy` on this machine) and
after any `omarchy update`, sanity-check with:

```bash
grep '^\[' /etc/pacman.conf
```

Expect to see all of: `cachyos-v3`, `cachyos-extra-v3`, `cachyos-core-v3`,
`cachyos`, `core`, `extra`, `multilib`, `omarchy`. If the CachyOS repos are
missing, restore from backup and re-append the `[omarchy]` block
(`SigLevel = Optional TrustAll`, `Server = https://pkgs.omarchy.org/stable/$arch`).

## btop requires `--force-utf8`

**Cause:** `/etc/locale.conf` had `LANG=en_IN` (and all `LC_*`) missing the
`.UTF-8` suffix, even though `en_IN.utf8` was properly generated
(`locale -a` showed it). Fix is to make sure every `LANG=`/`LC_*=` line in
`/etc/locale.conf` ends in `.UTF-8`, not just the bare locale name.

## Keybind conflicts when adding personal Hyprland binds

Omarchy ships a lot of default binds that aren't visible in
`~/.config/hypr/bindings.lua` — they live under
`~/.local/share/omarchy/default/hypr/bindings/*.lua`. Before adding a new
`o.bind(...)`, grep that whole directory (not just the top-level files) for
the key combo, and cross-check with `hyprctl binds` for accidental duplicate
registrations. Two bitten-us-before examples:

- `SUPER + ESCAPE` is already "System menu" (`utilities.lua`) — don't reuse it.
- `SUPER + SHIFT + N` is already "Editor" / nvim (`applications.lua`) — don't
  reuse it.

## Quickshell bar is what people mean by "waybar" here

This install runs Omarchy's Quickshell-based shell, not waybar — `pgrep -a`
confirms no waybar process exists, only
`quickshell -n -p $OMARCHY_PATH/shell`. Bar layout lives in
`~/.config/omarchy/shell.json` (**not** `shell.toml`, which is unused/stale —
the shell only ever reads the `.json` file). Manage widgets live, no reload
needed:

```bash
omarchy bar plugin add/move/remove/set <id> [placement]
```

Useful debug commands:

```bash
qs -p $OMARCHY_PATH/shell ipc call shell listShellConfig   # effective merged config
qs -p $OMARCHY_PATH/shell ipc call shell debugBarGeometry  # live widget positions/sizes
quickshell log -t <N> -p $OMARCHY_PATH/shell                # runtime QML warnings/errors
```
