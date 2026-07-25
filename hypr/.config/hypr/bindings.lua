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
-- Personal overrides (mridul)
-- ---------------------------------------------------------------------------

-- Editor: VS Code on SUPER + C (replaces Omarchy's "Universal copy" default).
hl.unbind("SUPER + C")
o.bind("SUPER + C", "VS Code", { launch = "code", focus = "^([Cc]ode)$" })

-- AI: Claude on SUPER + A, Claude Code (CLI) in a terminal on SUPER + SHIFT + A
-- (replaces the default ChatGPT binding).
o.bind("SUPER + A", "Claude", { webapp = "https://claude.ai" })
hl.unbind("SUPER + SHIFT + A")
o.bind("SUPER + SHIFT + A", "Claude Code", { tui = "claude", focus = true })

-- Passwords: Bitwarden desktop on SUPER + SHIFT + SLASH (replaces 1Password default).
hl.unbind("SUPER + SHIFT + SLASH")
o.bind("SUPER + SHIFT + SLASH", "Passwords (Bitwarden)", { launch = "bitwarden-desktop", focus = "^([Bb]itwarden)$" })

-- Send VS Code to workspace 3.
o.window("[Cc]ode", { workspace = "3" })
