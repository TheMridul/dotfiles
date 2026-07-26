# Dotfiles — OMARCHY Setup

My personal dotfiles, designed around [OMARCHY](https://omarchy.org).

Based on [sheikhlimon/dotfiles](https://github.com/sheikhlimon/dotfiles), an
excellent Omarchy dotfiles template — per its own philosophy: *"Take anything
and make it your own."* This repo's history starts with a single squashed
import of that base, with my own changes on top.

> 💡 **OMARCHY Philosophy**: Take anything and make it your own. These configs are a starting point - feel free to take, modify, and customize to fit your workflow.

## Features

- 🖥️ Hyprland window manager (native Lua config, Omarchy 4.0 "Quattro")
- 🍭 Waybar themed to match OMARCHY
- ⚡ Neovim via the official [`omarchy-nvim`](https://github.com/LazyVim/LazyVim) package (pacman-managed, theme-synced automatically — not tracked here; run `sudo pacman -Syu` then `omarchy-nvim-refresh` to update)
- 🧩 Zsh + Starship prompt with Oh My Zsh plugins
- 📝 Kitty & Ghostty terminal configurations
- 🗂️ Yazi with custom theme
- 📦 Lazygit and Lazydocker configs
- 🔤 Fontconfig (Victor Mono Nerd Font)
- 🛠️ Tmux configuration with plugins and custom keybindings
- 📋 Git configuration
- 🚀 Automated scripts for app installation and database setup

## Installation

**Clone the repository:**

```bash
git clone https://github.com/TheMridul/dotfiles ~/.dotfiles
cd ~/.dotfiles
```

**Install specific configs (example):**

```bash
stow hypr
stow zsh
stow kitty
```

**Install everything:**

```bash
stow */
```

> Make sure to remove or back up existing config files before stowing.

## Troubleshooting

CachyOS-specific gotchas (SDDM theme Qt5/Qt6 crash, `omarchy update` wiping
pacman repos, locale/btop, keybind conflicts) are written up in
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).
