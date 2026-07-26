-- Personal environment overrides

-- gtk-3.0/settings.ini pointed at "Bibata-Modern-Ice", which was never
-- actually installed (AUR-only) -- apps were silently falling back to a
-- mismatched default cursor. Adwaita is already installed system-wide and
-- reads cleanly on the dark hushOS background.
hl.env("XCURSOR_THEME", "Adwaita")
