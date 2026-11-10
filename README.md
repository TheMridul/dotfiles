# Dotfiles — OMARCHY Setup

My personal dotfiles, designed around [OMARCHY](https://omarchy.org).

Based on [sheikhlimon/dotfiles](https://github.com/sheikhlimon/dotfiles), an
excellent Omarchy dotfiles template — per its own philosophy: *"Take anything
and make it your own."* This repo's history starts with a single squashed
import of that base, with my own changes on top.

> 💡 **OMARCHY Philosophy**: Take anything and make it your own. These configs are a starting point - feel free to take, modify, and customize to fit your workflow.

## Features

- 🖥️ Hyprland window manager (native Lua config, Omarchy 4.5)
- 🐚 Omarchy shell: bar layout, custom branding, and a cloned monitor panel
- ⚡ Neovim via the official [`omarchy-nvim`](https://github.com/LazyVim/LazyVim) package (package-managed, theme-synced automatically; run `omarchy update` then `omarchy-nvim-refresh` to update)
- 🐟 Fish shell config with Starship setup and personal aliases
- ✨ Starship prompt
- 📊 btop and fastfetch
- 📦 Lazygit config
- 🔎 Ripgrep config
- 🔤 Fontconfig (Iosevka Nerd Font for monospace)
- 🛠️ Tmux configuration with plugins and custom keybindings
- 📋 Git configuration
- 💻 VS Code settings and keybindings
- 🔊 `read-aloud`, speaks the current selection with Kokoro-82M on CPU
- 🤖 Shared AI-agent rules and skills for Claude Code, Codex, opencode, Copilot
  CLI and Antigravity, through `AGENTS.md` and `.agents/`

The terminal is [foot](https://codeberg.org/dnkl/foot), the only one installed.
Its configuration is tracked in the `foot` package and includes the active
Omarchy theme at runtime.

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
`hypr` package. It speaks whatever is in the primary selection. The models are
far too large to track here, so set them up once:

```bash
# Kokoro-82M, the default engine. Use the fp32 model: the int8 one is 4.6x
# slower on CPU (RTF 0.99 vs 0.21) because ConvInteger has no fast kernel.
mkdir -p ~/.local/share/kokoro && cd ~/.local/share/kokoro
python3 -m venv venv
venv/bin/pip install --ignore-requires-python kokoro-onnx
K=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
curl -fsSLO "$K/kokoro-v1.0.onnx" -O "$K/voices-v1.0.bin"

# piper, the fallback, used when the venv is missing or READ_ALOUD_ENGINE=piper
yay -S piper-tts-bin
mkdir -p ~/.local/share/piper-voices && cd ~/.local/share/piper-voices
B=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high
curl -fsSLO "$B/en_US-lessac-high.onnx" -O "$B/en_US-lessac-high.onnx.json"
```

`--ignore-requires-python` is needed because `kokoro-onnx` caps at Python
`<3.14` while both of its dependencies are `py3-none-any`, so the cap is an
untested upper bound rather than a real incompatibility.

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
  and `~/.agents/README.md` at `agents/.agents/README.md`.
- `AGENTS.md` at a project root holds that project's context and rules, and
  wins wherever it disagrees with the user-wide file. `.agents/` holds that
  project's skills, references, templates, and memories.
- Every harness reads the same rules file through a symlink at its own path:
  `~/.codex/AGENTS.md`, `~/.config/opencode/AGENTS.md`,
  `~/.copilot/copilot-instructions.md` and `~/.gemini/AGENTS.md`. Claude Code
  uses a small hook, `claude/hooks/load-agent-context.sh`, that points its main
  session and subagents at both layers.
- Codex, opencode and Copilot read `~/.agents/skills` natively. Antigravity
  gets one link to it, and Claude Code gets one link per skill in
  `~/.claude/skills`, because Claude also keeps its synced claude.ai skills in
  that folder.

**Memories are not stored in an agent's private directory.** A project fact goes
in that project's `.agents/memory/`; a machine or user fact goes in
`~/.agents/memory/`. Both are plain Markdown with a `MEMORY.md` index, so every
tool can read them. `~/.agents/memory/`, `~/.agents/plans/` and
`~/.agents/MACHINE.md` are deliberately **not** tracked here, because this
repository is public and they carry hostnames, key fingerprints, and hardware
details. `~/.agents` is a private Git repository of its own instead, and
`agents-private-sync.timer` in the `systemd` package commits and pushes it
daily, with a desktop notification if the push fails.

After cloning this dotfiles repository on a new machine, install the bridge:

```bash
./scripts/install-agent-context.sh
```

The script:

- clones the private `~/.agents` repository when `gh` is signed in;
- links `~/AGENTS.md`, `~/.agents/README.md` and `~/.agents/skills`, and the
  rules file into each installed harness;
- links every skill, the hook and the statusline into `~/.claude`, and merges
  the hook entries and a few settings (auto memory and attribution off, Claude
  in Chrome on) into `~/.claude/settings.json` without replacing the rest;
- links the Claude in Chrome and Codex browser native hosts into Brave Origin's
  profile;
- turns off Copilot's memory and co-author trailer;
- enables the private sync timer once the `systemd` package is stowed.

It requires `jq`, is safe to re-run, and refuses to replace a file or symlink
it did not create. Re-run it after adding or removing a skill.

Use the `new-project`, `existing-project`, or `just-rules` skills to create the
same `AGENTS.md` and `.agents/` layout in future repositories. No project-level
`CLAUDE.md`, `.cursorrules`, or `.cursor/rules` is needed. The other skills in
`agents/.agents/skills/` cover writing style, explanation, review, research,
and AWS and Cloudflare work; each one's `SKILL.md` says when it applies.

## Config recovery copies

The desktop configuration was first copied from the live Omarchy setup on
2026-10-03, before testing a Ryoku conversion, and last refreshed on
2026-11-10. Added packages cover:

- `foot`: terminal settings. The default Alacritty, Kitty, and Neovim
  configs are not included.
- `desktop`: environment overrides, screenshot directory, GTK bookmarks,
  file associations, browser flags, user directories, and volume preferences.
- `systemd` and `wireplumber`: custom user services and Bluetooth audio rules.
- `apps`: selected settings for Fcitx5, imv, mpv, mise, micro, OpenCode, Herdr,
  Sunshine, and OBS. Credentials and application runtime state are excluded.
- `omarchy`: the current shell and menu settings, active hooks, installed
  plugin sources, downloaded themes, and personal backgrounds. Sources are
  retained so local plugin edits survive removal or upstream changes.

The root Git ignore file and the active XDG Git and tmux configs are also
included. The older `~/.tmux.conf` remains available alongside the active
`~/.config/tmux/tmux.conf`; choose the applicable config when restoring.

These additions are copies of the live files; existing live files have not
been replaced with symlinks. Refresh the copies before relying on this repo
for a later migration. GitHub contains them only after committing and pushing.
When restoring, compare against the installed Omarchy version and stow only
selected packages with `--no-folding`. Preserve existing files before resolving
stow conflicts. Do not apply Omarchy services or hooks to a Ryoku session.

Restore custom service activation separately when needed:

```fish
systemctl --user enable slay50-battery.service
systemctl --user enable sunshine.service
systemctl --user enable --now agents-private-sync.timer
systemctl --user enable --now aws-session.timer
```

The `bin` package includes the installed `slay50-battery` executable required
by its user service. The other Omarchy/PipeWire service activation links are
managed by their packages and are not copied here. Browser profiles, API keys,
Sunshine credentials and AI-agent private settings remain outside this public
repository, and shared agent memories live in the private `~/.agents`
repository.
