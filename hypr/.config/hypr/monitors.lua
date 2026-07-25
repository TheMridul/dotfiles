-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

-- Lenovo LOQ 15IRX9 internal panel (BOE): 1920x1080, up to 144Hz.
-- GDK_SCALE must be an integer (GTK doesn't support fractional values here);
-- keep it at 1 and let Wayland's fractional-scale protocol handle the 1.25x
-- panel scale below, so GTK apps stay crisp instead of being pre-scaled twice.
local omarchy_gdk_scale = 1
local omarchy_monitor_scale = "auto"

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))

-- 1080p @ 144Hz. Valid integer-pixel scales here: 1.0 (native), 1.25 (1536x864),
-- 1.5 (1280x720). 1.25 is the comfortable default for a 15.6" 1080p panel.
hl.monitor({ output = "eDP-1", mode = "1920x1080@144", position = "0x0", scale = 1.25 })

-- Fallback for any other/external monitor.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- Configure a specific external monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "auto", scale = 1 })
