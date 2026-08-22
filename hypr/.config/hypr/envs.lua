-- Personal environment overrides

-- gtk-3.0/settings.ini pointed at "Bibata-Modern-Ice", which was never
-- actually installed (AUR-only) -- apps were silently falling back to a
-- mismatched default cursor. Adwaita is already installed system-wide and
-- reads cleanly on the dark hushOS background.
hl.env("XCURSOR_THEME", "Adwaita")

-- default/hypr/nvidia.lua always forces VA-API/GLX onto the NVIDIA GPU, but
-- the internal panel (eDP) is wired to the Intel iGPU.
--
-- VA-API (video decode) always goes to Intel, never NVIDIA, regardless of
-- power state: nvidia-vaapi-driver's dmabuf zero-copy decode path is flaky
-- under Wayland+WebRTC -- it caused visible flicker while decoding, and
-- separately made remote participants' video render as solid black tiles in
-- Meet/WhatsApp calls (own camera preview was fine since that's raw capture,
-- no decode involved).
--
-- GLX (3D rendering, e.g. games) still prefers the dGPU on AC for
-- performance, and falls back to Intel on battery to save power. This runs
-- after nvidia.lua (envs.lua is required last in hyprland.lua), so it
-- overrides those defaults.
local function on_ac_power()
  local f = io.open("/sys/class/power_supply/ACAD/online", "r")
  if not f then
    return true -- no battery/AC info (e.g. desktop) -- default to the dGPU
  end
  local value = f:read("*l")
  f:close()
  return value == "1"
end

hl.env("LIBVA_DRIVER_NAME", "iHD")

if on_ac_power() then
  hl.env("NVD_BACKEND", "direct")
  hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
else
  hl.env("__GLX_VENDOR_LIBRARY_NAME", "mesa")
end
