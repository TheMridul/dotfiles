-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

local omarchy_monitor_scale = 1.25
local omarchy_gdk_scale = 1

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))

-- Internal BOE panel. The connector is eDP-2, not eDP-1 -- confirmed against
-- `hyprctl monitors`, which also lists 1920x1080@144 among its modes. Without
-- this rule the panel only picks up a scale by accident, through the ""
-- fallback below, and runs at the preferred mode instead of 144Hz.
hl.monitor({ output = "eDP-2", mode = "1920x1080@144", position = "0x0", scale = omarchy_monitor_scale, vrr = 1 })

-- Fallback for any other/external monitor.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- Configure a specific external monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "auto", scale = 1 })
