# Dotfiles — OMARCHY Setup

My personal dotfiles, designed around [OMARCHY](https://omarchy.org).

Based on [sheikhlimon/dotfiles](https://github.com/sheikhlimon/dotfiles), an
excellent Omarchy dotfiles template — per its own philosophy: *"Take anything
and make it your own."* This repo's history starts with a single squashed
import of that base, with my own changes on top.

> 💡 **OMARCHY Philosophy**: Take anything and make it your own. These configs are a starting point - feel free to take, modify, and customize to fit your workflow.

## Features

- 🖥️ Hyprland window manager (native Lua config, Omarchy 4.0 "Quattro")
- 🐚 Omarchy shell: bar layout, custom branding, and a cloned monitor panel
- ⚡ Neovim via the official [`omarchy-nvim`](https://github.com/LazyVim/LazyVim) package (package-managed, theme-synced automatically; run `omarchy update` then `omarchy-nvim-refresh` to update)
- 🐟 Fish shell config with Starship setup and personal aliases
- ✨ Starship prompt
- 📊 btop and fastfetch
- 📦 Lazygit config
- 🔎 Ripgrep config
- 🔤 Fontconfig (JetBrainsMono Nerd Font)
- 🛠️ Tmux configuration with plugins and custom keybindings
- 📋 Git configuration
- 💻 VS Code settings and keybindings
- 🔊 `read-aloud`, speaks the current selection with piper-tts
- 🚀 Automated scripts for app installation and database setup
- 🤖 Shared AI-agent context with `AGENTS.md` and `.agents/`

The terminal is [foot](https://codeberg.org/dnkl/foot), configured through
Omarchy rather than tracked here.

## Installation

**Clone the repository:**

```bash
git clone https://github.com/TheMridul/dotfiles ~/.dotfiles
cd ~/.dotfiles
```

**Install specific configs (example):**

```bash
stow --no-folding hypr
stow --no-folding fish
stow --no-folding starship
```

Install packages selectively. Do not stow `claude` or `scripts`, and merge the
`hypr` and `omarchy` packages against the current Omarchy defaults before
stowing them.

The `bin` package installs `read-aloud`, bound to `SUPER + ALT + R` in the
`hypr` package. It needs `piper-tts-bin` from the AUR plus a voice model, which
is too large to track here:

```bash
yay -S piper-tts-bin
mkdir -p ~/.local/share/piper-voices && cd ~/.local/share/piper-voices
B=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high
curl -fsSLO "$B/en_US-lessac-high.onnx" -O "$B/en_US-lessac-high.onnx.json"
```

> Make sure to remove or back up existing config files before stowing.

**Always pass `--no-folding`.** Without it, stow replaces a whole config
directory with one symlink pointing into this repo. Any file the program then
writes — fish's `fish_variables`, btop's runtime `btop.conf`, Omarchy's
downloaded themes and installed plugins — lands *inside* the repository and
shows up as untracked noise. `--no-folding` keeps the real directories in place
and symlinks only the tracked files.

## Shared agent context

One agent-neutral layout, in two layers:

- `~/AGENTS.md` (symlinked from `agents/AGENTS.md` here) holds machine- and
  user-wide rules. `~/.agents/skills` points at the shared skills tracked here,
  while `~/.agents/memory` is the local machine-wide memory store.
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

The script links the hook, the statusline and all six skills into `~/.claude`,
adds the required hook entries without replacing other Claude settings, links
`~/AGENTS.md`, `~/.agents/README.md`, and `~/.agents/skills`, points
`~/.codex/AGENTS.md` at the same rules file, and creates an empty
`~/.agents/memory/`. It requires `jq` and stops if a target file already exists
rather than overwriting it.

Use the `new-project`, `existing-project`, or `just-rules` Claude skills to
create the same `AGENTS.md` and `.agents/` layout in future repositories. No
project-level `CLAUDE.md`, `.cursorrules`, or `.cursor/rules` is needed. The
remaining skills — `collaborator-tone`, `explain-code`, `mentor-mode` — shape
how an agent writes and explains rather than what it scaffolds.

## Troubleshooting

`TROUBLESHOOTING.md` is retained as history for the retired CachyOS-based
installation. Do not apply its repository, kernel, SDDM, or boot fixes to a
standard Omarchy install.
