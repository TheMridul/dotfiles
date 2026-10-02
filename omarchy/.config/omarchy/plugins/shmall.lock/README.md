# Media Lock Screen

A drop-in replacement lock screen for [Omarchy](https://omarchy.org/) that shows
the currently playing track (MPRIS), a large clock, and your user name — with
separate password and fingerprint PAM flows.

Built by forking Omarchy's built-in `omarchy.lock` service. It replaces the
built-in lock screen when enabled; removing it restores the original.

## Features

- Now-playing title and artist from MPRIS players (e.g. music apps in the tray)
- Large live clock
- User name display
- Password auth via `omarchy-lock-password` PAM service
- Fingerprint auth via `omarchy-lock-fingerprint` PAM service, only when a
  fingerprint is enrolled
- Blurred wallpaper background, Hyprland-driven corners, theme-aware colors
- Safe stranded-lock recovery, mirroring the built-in
- Display stays on while locked (no auto-blank)

## Install

```sh
omarchy plugin add https://github.com/shmall03/omarchy-shmall.lock-plugin.git --enable
```

The plugin is enabled with `clonedFrom: omarchy.lock`, so the shell
automatically disables the built-in lock screen. Lock with your normal keybind
or `omarchy system lock`.

## Requirements

- Omarchy (Quickshell shell)
- `/etc/pam.d/omarchy-lock-password` present (ships with Omarchy)
- Optionally `/etc/pam.d/omarchy-lock-fingerprint` for fingerprint unlock

## Remove

```sh
omarchy plugin remove shmall.lock
```

This restores the built-in Omarchy lock screen.

## Preview

`omarchy-shell lock preview` shows a full-screen preview of the lock screen;
`omarchy-shell lock hidePreview` hides it.

## License

[MIT](LICENSE). Derived from Omarchy's `omarchy.lock` plugin (MIT).
