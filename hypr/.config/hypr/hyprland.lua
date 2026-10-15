-- Learn how to configure Hyprland: https://wiki.hypr.land/Configuring/Start/

-- Omarchy's bootstrap keeps path setup out of this user config.
dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")

-- Disable all Omarchy default bindings. Add your own in hypr/bindings.lua.
-- omarchy_default_bindings = false
--
-- Or disable only bindings for Omarchy's preinstalled apps/web apps while
-- keeping core window-manager bindings:
-- omarchy_preinstalled_bindings = false

-- Load Omarchy defaults.
require("default.hypr.omarchy")

-- Put your personal overrides in these files. They're loaded after Omarchy's
-- defaults so package updates can improve the defaults without rewriting your
-- ~/.config/hypr files.
require("hypr.monitors")
require("hypr.input")
require("hypr.bindings")
require("hypr.looknfeel")
require("hypr.autostart")

-- Toggle config flags dynamically.
require("default.hypr.toggles")

-- Add any other personal Hyprland configuration below.
-- o.window("qemu", { workspace = "5" })

-- VA-API decodes on the Intel iGPU, not the dGPU. Omarchy's nvidia.lua sets
-- LIBVA_DRIVER_NAME=nvidia whenever a GSP-capable card is present, but the
-- panel hangs off 00:02.0, so the compositor and every GPU process render on
-- Intel. Chromium then loads nvidia_drv_video.so against /dev/dri/renderD129
-- (Intel), which hangs instead of failing cleanly: garbled frames, black video
-- with sound, and a CPU-decode fallback. Reproduced with ffmpeg on both nodes.
-- Revisit if an external display ever moves the compositor onto the dGPU.
hl.env("LIBVA_DRIVER_NAME", "iHD")

-- Fleet's SSH terminals remain opaque inside its Chromium webapp.
local FLEET = { class = "^chrome-.*$", title = "^Fleet$" }
o.window(FLEET, { tag = "-chromium-based-browser" })
o.window(FLEET, { tag = "-default-opacity" })
o.window(FLEET, { opacity = "1.0 1.0" })

-- Brave (class brave-origin) is not matched by Omarchy's browser regex, so it fell
-- through to the 0.985/0.96 default opacity. Keep it fully opaque.
local BRAVE = { class = "^brave-origin$" }
o.window(BRAVE, { tag = "-default-opacity" })
o.window(BRAVE, { opacity = "1.0 1.0" })


-- Preserve Foot translucency when Hyprland enters fullscreen.
local FROSTED_TERMINAL = { class = "^(foot|footclient)$" }
o.window(FROSTED_TERMINAL, { opacity = "1.0 override 1.0 override 0.8 override" })


-- Keep utility windows readable while revealing the blurred backdrop.
local FROSTED_UTILITIES = { class = "^(org\\.pulseaudio\\.pavucontrol|[Pp]avucontrol)$" }
o.window(FROSTED_UTILITIES, { tag = "-default-opacity" })
o.window(FROSTED_UTILITIES, { opacity = "0.92 override 0.88 override 1.0 override" })

hl.layer_rule({
  match = { namespace = "^(omarchy-menu|omarchy-emojis|omarchy-clipboard|omarchy-keyboard-panel|omarchy-notifications|omarchy-osd|omarchy-reminders|omarchy-network-qr)$" },
  blur = true,
  blur_popups = true,
  ignore_alpha = 0.55,
})


local FROSTED_CODE = { class = "^([Cc]ode|[Cc]ode - [Ii]nsiders|com[.]microsoft[.]VSCode)$" }
o.window(FROSTED_CODE, { tag = "-default-opacity" })
o.window(FROSTED_CODE, {
  opacity = "0.80 override 0.80 override 1.0 override",
  no_blur = false,
})


hl.layer_rule({
  match = { namespace = "^omarchy-bar$" },
  blur = true,
  blur_popups = true,
  ignore_alpha = 0.55,
})

local FROSTED_NEMO = { class = "^([Nn]emo)$" }
o.window(FROSTED_NEMO, { tag = "-default-opacity" })
o.window(FROSTED_NEMO, {
  opacity = "0.80 override 0.80 override 0.80 override",
  no_blur = false,
})
