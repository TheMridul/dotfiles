# Hyprland integration

`install.sh` offers to add these. They are listed here so you can apply them by
hand, or adapt them.

## Keybinding — `~/.config/hypr/bindings.lua`

```lua
-- BEGIN io.github.niraj-envision.fleet binding
-- Fleet starts the server on first run and focuses its existing window later.
o.bind("SUPER + SHIFT + V", "Fleet (VPS manager)", os.getenv("HOME") .. "/.local/bin/fleet")
-- END io.github.niraj-envision.fleet binding
```

## Window rule — `~/.config/hypr/hyprland.lua`

```lua
-- BEGIN io.github.niraj-envision.fleet window rule
-- Fleet's SSH terminals must remain fully opaque inside its Chromium webapp.
local FLEET = { class = "^chrome-.*$", title = "^Fleet$" }
o.window(FLEET, { tag = "-chromium-based-browser" })
o.window(FLEET, { tag = "-default-opacity" })
o.window(FLEET, { opacity = "1.0 1.0" })
-- END io.github.niraj-envision.fleet window rule
```

Validate with `hyprctl reload && hyprctl configerrors`.
