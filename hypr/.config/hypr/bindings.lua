-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- ---------------------------------------------------------------------------
-- Personal overrides
-- ---------------------------------------------------------------------------

-- Editor: VS Code on SUPER + C (replaces Omarchy's "Universal copy" default).
hl.unbind("SUPER + C")
o.bind("SUPER + C", "VS Code", { launch = "code", focus = "^([Cc]ode)$" })

-- AI: Claude on SUPER + A, Claude Code (CLI) in a terminal on SUPER + SHIFT + A
-- (replaces the default ChatGPT binding).
o.bind("SUPER + A", "Claude", { webapp = "https://claude.ai" })
hl.unbind("SUPER + SHIFT + A")
o.bind("SUPER + SHIFT + A", "Claude Code", { tui = "claude", focus = true })

-- Music: YouTube Music webapp on SUPER + SHIFT + M (replaces the default
-- Spotify bind, which just launches Spotify's installer since it isn't
-- installed here).
hl.unbind("SUPER + SHIFT + M")
o.bind("SUPER + SHIFT + M", "Music (YouTube Music)", { webapp = "https://music.youtube.com", focus = true })

-- Passwords: Bitwarden desktop on SUPER + SHIFT + SLASH (replaces 1Password default).
hl.unbind("SUPER + SHIFT + SLASH")
o.bind("SUPER + SHIFT + SLASH", "Passwords (Bitwarden)", { launch = "bitwarden-desktop", focus = "^([Bb]itwarden)$" })

-- System monitor: btop in a floating TUI on SUPER + SHIFT + ESCAPE
-- (SUPER + ESCAPE is Omarchy's default System menu bind — left alone).
o.bind("SUPER + SHIFT + ESCAPE", "System monitor (btop)", { tui = "btop", focus = true })

-- Network TUI (nmtui) on SUPER + SHIFT + H. The bar's network widget only
-- documents a right-click -> nmtui shortcut for hidden-SSID connections;
-- that interaction isn't actually wired up in the current omarchy-shell
-- code (upstream doc/implementation mismatch), so this is a direct path.
-- (SUPER + SHIFT + N is Omarchy's default Editor bind — left alone.)
o.bind("SUPER + SHIFT + H", "Network (nmtui)", { tui = "nmtui", focus = true })

-- Send VS Code to workspace 3.
o.window("[Cc]ode", { workspace = "3" })
