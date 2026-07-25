-- Omarchy theme integration.
--
-- Omarchy ships a LazyVim plugin spec for the *currently active* theme at
-- ~/.local/state/omarchy/current/theme/neovim.lua (a path whose target changes
-- when the user runs `omarchy-theme-set`). Loading it here as a plugin spec
-- keeps Neovim's colorscheme in sync with the rest of the Omarchy desktop, and
-- it is re-read on each future theme change (restart Neovim to pick it up).
local theme = vim.fn.expand("~/.local/state/omarchy/current/theme/neovim.lua")

if vim.uv.fs_stat(theme) then
  return dofile(theme)
end

-- Fallback if Omarchy's theme spec is missing: keep LazyVim on a sane default.
return {}
