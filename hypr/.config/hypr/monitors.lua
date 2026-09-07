-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

-- Lenovo LOQ 15IRX9 internal panel (BOE): 1920x1080, up to 144Hz.
--
-- omarchy_monitor_scale is the panel scale; omarchy_gdk_scale is GDK_SCALE.
-- GDK_SCALE must be an integer (GTK can't do fractional here) -- keep it at 1
-- and let Wayland's fractional-scale protocol handle the 1.25x panel scale, so
-- GTK apps stay crisp instead of being pre-scaled twice.
--
-- Both are stock Omarchy knobs. omarchy-hyprland-monitor-scaling (SUPER+/) and
-- the Quickshell monitor panel rewrite these two `local` lines in place to
-- persist a scale change across reboots; omarchy-hyprland-monitor-clamshell
-- resolves the variable when it reads a rule below. Presets step 1, 1.25, 1.6,
-- 2, 3, 4 -- set a fractional value like 1.5 with `omarchy-hyprland-monitor-
-- scaling 1.5` directly.
local omarchy_monitor_scale = 1.25
local omarchy_gdk_scale = 1

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))

-- vrr = 1 enables adaptive sync on this panel (144Hz, confirmed VRR-capable
-- via `hyprctl monitors`) to cut tearing/stutter during animations.
--
-- Connector is eDP-2, not eDP-1 (confirmed via `hyprctl monitors -j` ->
-- "name"). An eDP-1 rule never matched anything -- scale was only applied by
-- accident via the "" fallback rule below. This rule makes vrr (and any future
-- eDP-specific tweak) actually take effect.
hl.monitor({ output = "eDP-2", mode = "1920x1080@144", position = "0x0", scale = omarchy_monitor_scale, vrr = 1 })

-- Fallback for any other/external monitor.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- Configure a specific external monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "auto", scale = 1 })
