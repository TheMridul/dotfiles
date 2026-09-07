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
- 🐟 Fish shell config (CachyOS fish preset + Omarchy `OMARCHY_PATH`/starship setup) — daily-driver shell
- 📝 Kitty & Ghostty terminal configurations
- 🗂️ Yazi with custom theme
- 📦 Lazygit and Lazydocker configs
- 🔤 Fontconfig (Victor Mono Nerd Font)
- 🛠️ Tmux configuration with plugins and custom keybindings
- 📋 Git configuration
- 🚀 Automated scripts for app installation and database setup
- 🤖 Shared AI-agent context with `AGENTS.md` and `.agents/`

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

## Shared agent context

One agent-neutral layout, in two layers:

- `~/AGENTS.md` (symlinked from `agents/AGENTS.md` here) holds machine- and
  user-wide rules. `~/.agents/` holds user-level skills and the machine-wide
  memory store.
- `AGENTS.md` at a project root holds that project's context and rules, and
  wins wherever it disagrees with the user-wide file. `.agents/` holds that
  project's skills, references, templates, and memories.
- Cursor reads `AGENTS.md` directly. Codex reads `~/.codex/AGENTS.md`, which is
  a symlink to `~/AGENTS.md` rather than a second copy. Claude Code uses a small
  local hook that points its main session and subagents at both layers.

**Memories are not stored in an agent's private directory.** A project fact goes
in that project's `.agents/memory/`; a machine or user fact goes in
`~/.agents/memory/`. Both are plain Markdown with a `MEMORY.md` index, so every
tool can read them. `~/.agents/memory/` is deliberately **not** tracked here —
this repository is public and memories carry hostnames, key fingerprints, and
hardware details. Back it up separately.

After cloning this dotfiles repository on a new machine, install the bridge:

```bash
./scripts/install-agent-context.sh
```

The script links the hook and project-scaffolding skills into `~/.claude`,
adds the required hook entries without replacing other Claude settings, links
`~/AGENTS.md` and the shared `~/.agents/README.md`, points `~/.codex/AGENTS.md`
at the same file, and creates an empty `~/.agents/memory/`. It requires `jq` and
stops if a target file already exists rather than overwriting it.

Use the `new-project`, `existing-project`, or `just-rules` Claude skills to
create the same `AGENTS.md` and `.agents/` layout in future repositories. No
project-level `CLAUDE.md`, `.cursorrules`, or `.cursor/rules` is needed.

## Troubleshooting

CachyOS-specific gotchas (SDDM theme Qt5/Qt6 crash, `omarchy update` wiping
pacman repos, locale/btop, keybind conflicts) are written up in
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Branding

Custom "hushOS" branding (boot splash, login screen, terminal banner) built
on the Hackerman theme's palette — see [BRANDING.md](BRANDING.md) for the
assets, the commands to reapply it, and why the lock screen is deliberately
left unbranded.
