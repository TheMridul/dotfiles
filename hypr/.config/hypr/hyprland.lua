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
