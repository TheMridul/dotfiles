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
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- Personal application bindings.
hl.unbind("SUPER + C")
o.bind("SUPER + C", "VS Code", { launch = "code", focus = "^([Cc]ode)$" })

o.bind("SUPER + A", "Claude", { webapp = "https://claude.ai" })
hl.unbind("SUPER + SHIFT + A")
o.bind("SUPER + SHIFT + A", "Claude Code", { tui = "claude", focus = true })

hl.unbind("SUPER + SHIFT + M")
o.bind("SUPER + SHIFT + M", "Music (YouTube Music)", { webapp = "https://music.youtube.com", focus = true })

hl.unbind("SUPER + SHIFT + SLASH")
o.bind("SUPER + SHIFT + SLASH", "Passwords (Bitwarden)", { launch = "bitwarden-desktop", focus = "^([Bb]itwarden)$" })

o.bind("SUPER + SHIFT + ESCAPE", "System monitor (btop)", { tui = "btop", focus = true })
o.bind("SUPER + SHIFT + H", "Network (nmtui)", { tui = "nmtui", focus = true })

-- Google Maps webapp removed; free its bind.
hl.unbind("SUPER + SHIFT + S")

-- Drop Omarchy's HEY binds; email goes to Gmail instead.
hl.unbind("SUPER + SHIFT + C")
hl.unbind("SUPER + SHIFT + ALT + E")
hl.unbind("SUPER + SHIFT + E")
o.bind("SUPER + SHIFT + E", "Email (Gmail)", { webapp = "https://mail.google.com", focus = true })

o.bind("SUPER + SHIFT + V", "Fleet (VPS manager)", os.getenv("HOME") .. "/.local/bin/fleet")
o.bind("SUPER + SHIFT + ALT + RETURN", "Browser (private)", { omarchy = "browser --private" })

-- Read the selection aloud (piper-tts). Reads PRIMARY via wl-paste rather than
-- faking Ctrl+C, so it works in native Wayland windows. Press again to stop.
o.bind("SUPER + ALT + R", "Read aloud", os.getenv("HOME") .. "/.local/bin/read-aloud")

hl.unbind("SUPER + SHIFT + F")
o.bind("SUPER + SHIFT + F", "File manager", { launch = "nemo" })
hl.unbind("SUPER + ALT + SHIFT + F")
o.bind("SUPER + ALT + SHIFT + F", "File manager (cwd)", [[setsid uwsm-app -- nemo "$(omarchy-cmd-terminal-cwd)"]])

-- Super+` drops T3 Code down as a popup instead of Omarchy's agent console.
-- T3 is single-instance, so the bind pulls the one existing window into its own
-- special workspace (wherever it was opened) and toggles that, launching T3
-- straight into it when it is not running.
local T3_CLASS = "com.t3tools.T3Code"
local T3_APP = os.getenv("HOME") .. "/.local/share/t3code/T3-Code.AppImage"

local function t3_popup()
  for _, window in ipairs(hl.get_windows()) do
    if window.class == T3_CLASS then
      if not (window.workspace and window.workspace.name == "special:t3") then
        hl.dispatch(hl.dsp.window.move({ workspace = "special:t3", follow = false, window = "address:" .. window.address }))
      end
      hl.dispatch(hl.dsp.workspace.toggle_special("t3"))
      return
    end
  end
  hl.exec_cmd(o.launch(T3_APP), { workspace = "special:t3" })
end

hl.unbind("SUPER + grave")
o.bind("SUPER + grave", "T3 Code popup", t3_popup)
