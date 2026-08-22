-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

-- Lenovo LOQ 15IRX9 internal panel (BOE): 1920x1080, up to 144Hz.
-- GDK_SCALE must be an integer (GTK doesn't support fractional values here);
-- keep it at 1 and let Wayland's fractional-scale protocol handle the 1.25x
-- panel scale below, so GTK apps stay crisp instead of being pre-scaled twice.
local omarchy_gdk_scale = 1.25

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))

-- 1080p @ 144Hz. omarchy-hyprland-monitor-scaling / the Quickshell monitor
-- panel step through presets 1, 1.25, 1.5, 2, 3, 4 (custom: ~/.local/bin
-- shadows the stock 1.6 preset with 1.5 for this panel size).
--
-- Scale MUST be a literal number here, not a variable reference. The stock
-- /usr/share/omarchy/bin/omarchy-hyprland-monitor-clamshell script (run on
-- every Hyprland startup via omarchy-hyprland-monitor-watch) text-parses this
-- exact line with a regex expecting a literal after `scale = `; a variable
-- name fails its numeric check and silently falls back to scale 2, which is
-- why the panel used to boot at 2x. Our own ~/.local/bin/omarchy-hyprland-
-- monitor-scaling (SUPER+/ shortcut) persists by rewriting this literal in
-- place, so it stays correct after both scripts touch it.
hl.monitor({ output = "eDP-1", mode = "1920x1080@144", position = "0x0", scale = omarchy_gdk_scale })

-- Fallback for any other/external monitor.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_gdk_scale })

-- Configure a specific external monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "auto", scale = 1 })
