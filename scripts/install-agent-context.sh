#!/bin/bash
# Wire every installed coding agent to the same rules and skills.
#
# One source of truth: ~/AGENTS.md for rules, ~/.agents/skills for skills,
# ~/.agents/memory and ~/.agents/MACHINE.md for local facts. Each harness gets
# a symlink at the path it reads, never a copy, so nothing can fall behind.
# Safe to re-run; run it again after adding or removing a skill.
set -euo pipefail

dotfiles_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
claude_home=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
shared="$HOME/.agents"
rules="$HOME/AGENTS.md"
hook_source="$dotfiles_root/claude/hooks/load-agent-context.sh"

link_if_missing() {
  local source=$1 target=$2
  if [[ -L $target ]]; then
    [[ $(readlink -f "$target") == "$(readlink -f "$source")" ]] && return
    printf 'Refusing to replace existing symlink: %s\n' "$target" >&2
    return 1
  fi
  if [[ -e $target ]]; then
    printf 'Refusing to replace existing file: %s\n' "$target" >&2
    return 1
  fi
  mkdir -p "$(dirname "$target")"
  ln -s "$source" "$target"
}

# Shared layer. ~/.agents is a private repo holding memory/ and MACHINE.md;
# on a fresh machine, check it out before linking the public parts in.
private_repo=${AGENTS_PRIVATE_REPO:-TheMridul/agents-private}
if [[ ! -d $shared/.git ]] && command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  mkdir -p "$shared"
  git -C "$shared" init -q -b main
  git -C "$shared" remote add origin "https://github.com/$private_repo.git"
  if git -C "$shared" fetch -q origin main; then
    git -C "$shared" checkout -q -t origin/main ||
      printf 'Local files block checking out %s; merge them by hand\n' "$private_repo" >&2
  fi
fi
mkdir -p "$shared/memory"
link_if_missing "$dotfiles_root/agents/AGENTS.md" "$rules"
link_if_missing "$dotfiles_root/agents/.agents/README.md" "$shared/README.md"
link_if_missing "$dotfiles_root/agents/.agents/skills" "$shared/skills"

# Global rules: each harness's own path points at ~/AGENTS.md. Only for
# harnesses that are installed (their config directory exists).
declare -A rule_paths=(
  ["$HOME/.codex"]="$HOME/.codex/AGENTS.md"
  ["$HOME/.config/opencode"]="$HOME/.config/opencode/AGENTS.md"
  ["$HOME/.copilot"]="$HOME/.copilot/copilot-instructions.md"
  ["$HOME/.gemini"]="$HOME/.gemini/AGENTS.md"
)
# Copilot only reads files under --add-dir paths; fish/conf.d/agent-copilot.fish
# adds ~/.agents for every run.
for dir in "${!rule_paths[@]}"; do
  [[ -d $dir ]] && link_if_missing "$rules" "${rule_paths[$dir]}" || true
done

# Skills live only in ~/.agents/skills.
# - Codex, opencode and Copilot read it natively.
# - Antigravity's skills folder is one link to it.
# - Claude Code has no setting for another skills folder, and it writes its own
#   claude.ai skills into ~/.claude/skills/synced (19 MB, private), so that
#   folder cannot be a link into the public repo. It gets one link per skill.
[[ -d $HOME/.gemini ]] && link_if_missing "$shared/skills" "$HOME/.gemini/config/skills"

mkdir -p "$claude_home/skills"
for skill in "$shared"/skills/*/; do
  skill=${skill%/}
  [[ -f $skill/SKILL.md ]] || continue
  link_if_missing "$shared/skills/${skill##*/}" "$claude_home/skills/${skill##*/}" || true
done
find "$claude_home/skills" -maxdepth 1 -xtype l -print -delete

# Omarchy migrations add skill links to ~/.codex/skills, which Codex would list
# a second time next to ~/.agents/skills. Drop those duplicate links.
if [[ -d $HOME/.codex/skills ]]; then
  for link in "$HOME"/.codex/skills/*; do
    [[ -L $link && -e $shared/skills/${link##*/} ]] || continue
    rm "$link"
    printf 'Removed duplicate Codex skill link: %s\n' "${link##*/}"
  done
fi

# Claude: context hook, and no provider-private auto memory.
chmod +x "$hook_source" "$dotfiles_root/claude/statusline.sh"
link_if_missing "$hook_source" "$claude_home/hooks/load-agent-context.sh"
link_if_missing "$dotfiles_root/claude/statusline.sh" "$claude_home/statusline.sh"

settings_path="$claude_home/settings.json"
[[ -e $settings_path ]] || printf '{}\n' >"$settings_path"
jq empty "$settings_path"
temporary_settings=$(mktemp "$settings_path.XXXXXX")
jq --arg hook '$HOME/.claude/hooks/load-agent-context.sh' '
  def has_context_hook:
    any(.[]?; any(.hooks[]?; .type == "command" and .command == $hook));
  .autoMemoryEnabled = false |
  .includeCoAuthoredBy = false |
  .attribution = {"commit": "", "pr": ""} |
  .hooks //= {} |
  .hooks.SessionStart //= [] |
  .hooks.SubagentStart //= [] |
  .hooks.SessionStart |= if has_context_hook then . else . + [{"hooks": [{"type": "command", "command": $hook}]}] end |
  .hooks.SubagentStart |= if has_context_hook then . else . + [{"hooks": [{"type": "command", "command": $hook}]}] end
' "$settings_path" >"$temporary_settings"
chmod --reference="$settings_path" "$temporary_settings"
mv "$temporary_settings" "$settings_path"

printf 'Agent context wired: rules %s, skills %s/skills.\n' "$rules" "$shared"
# Claude in Chrome: Claude Code registers its native host for Chrome and
# regular Brave but not Brave Origin (Omarchy's browser since 2026-11). Link
# Brave Origin's registration to the one Claude Code maintains.
claude_host="$HOME/.config/google-chrome/NativeMessagingHosts/com.anthropic.claude_code_browser_extension.json"
if [[ -f $claude_host ]]; then
  for profile in "$HOME"/.config/BraveSoftware/Brave-Origin*/; do
    mkdir -p "$profile/NativeMessagingHosts"
    ln -sfn "$claude_host" "$profile/NativeMessagingHosts/${claude_host##*/}"
  done
fi

# Copilot: no private memory, no Co-authored-by trailer (its default is on).
if command -v copilot >/dev/null; then
  copilot config memory false >/dev/null
  copilot config includeCoAuthoredBy false >/dev/null
fi

if systemctl --user cat agents-private-sync.timer >/dev/null 2>&1; then
  systemctl --user enable --now agents-private-sync.timer >/dev/null 2>&1 || true
fi
printf 'Private memory and machine card: %s (repo %s, daily push).\n' "$shared" "$private_repo"
