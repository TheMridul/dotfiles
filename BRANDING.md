# hushOS branding

Custom personal branding (name: **hushOS**), built on the **Hackerman**
Omarchy theme's palette (`background = #0B0C16`, `accent = #82FB9C`).
Wordmark treatment: `> hushos_` — bold `JetBrainsMono Nerd Font Mono`,
matrix green.

## Assets

- `omarchy/.config/omarchy/branding/hushos-logo.png` — 800×188 transparent
  PNG, used as the Plymouth boot-splash and SDDM login logo.
- `omarchy/.config/omarchy/branding/about.txt` — ASCII-art box logo shown by
  `fastfetch` (referenced from `fastfetch/.config/fastfetch/config.jsonc`).

## Boot splash + login screen (Plymouth + SDDM)

Applied via Omarchy's own tooling — recolors Plymouth's assets, installs the
logo, rebuilds the initramfs, and syncs SDDM's login theme (colors, logo,
failed-state assets) in one command:

```bash
omarchy plymouth set '#0B0C16' '#82FB9C' ~/.config/omarchy/branding/hushos-logo.png
```

Needs sudo. Re-run this any time `omarchy plymouth reset` / `omarchy refresh
sddm` is used (those revert to stock Omarchy assets — this repo's copy of
the logo is the source of truth to restore from). Doesn't touch
`metadata.desktop`, so it's independent of and won't undo the `QtVersion=6`
SDDM fix documented in `TROUBLESHOOTING.md`.

To preview a change before committing (no sudo, doesn't touch anything
live):

```bash
omarchy plymouth preview '#0B0C16' '#82FB9C' <path-to-logo.png> /tmp/preview.png
```

## Terminal banner (fastfetch)

`fastfetch/.config/fastfetch/config.jsonc` is Omarchy's own template
(`~/.local/share/omarchy/etc/fastfetch/config.jsonc`) — on the official ISO
this gets installed to `/etc/fastfetch/config.jsonc` automatically; on this
manual install that step never ran, so fastfetch was silently falling back
to a generic default. Installed to `~/.config/fastfetch/config.jsonc`
instead (user-scoped, no sudo needed, and fastfetch checks that path first).

## Lock screen — NOT branded, and why

Omarchy's plugin system hard-blocks reskinning the lock screen via the
supported `omarchy plugin clone` path: in
`~/.local/share/omarchy/shell/services/PluginRegistry.qml`, first-party
plugin ids (`omarchy.*`, including `omarchy.lock`) are always treated as
enabled regardless of any `disable` call, and third-party plugins can never
shadow a first-party id — "the whole `omarchy.*` namespace is reserved for
first-party plugins," by design, so a broken or malicious third-party
plugin can never hijack the password-entry screen. A clone
(`omarchy plugin clone omarchy.lock local.lock --replace`) loads *alongside*
the built-in rather than replacing it; both register the same `lock` IPC
target and the built-in always wins.

The only way to actually change the live lock screen's look is to hand-edit
the vendor file directly
(`~/.local/share/omarchy/shell/plugins/lock/LockView.qml`), which gets
overwritten by every `omarchy update` — deliberately not done here, since
that file also owns real auth/session-lock logic and the upside (a text
label) wasn't worth the risk/maintenance burden. The lock screen still
picks up Hackerman's matrix-green palette automatically (it reads live
theme tokens, not hardcoded colors) — it just has no `hushos` wordmark.
