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

# Shared layer.
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
  .hooks //= {} |
  .hooks.SessionStart //= [] |
  .hooks.SubagentStart //= [] |
  .hooks.SessionStart |= if has_context_hook then . else . + [{"hooks": [{"type": "command", "command": $hook}]}] end |
  .hooks.SubagentStart |= if has_context_hook then . else . + [{"hooks": [{"type": "command", "command": $hook}]}] end
' "$settings_path" >"$temporary_settings"
chmod --reference="$settings_path" "$temporary_settings"
mv "$temporary_settings" "$settings_path"

printf 'Agent context wired: rules %s, skills %s/skills.\n' "$rules" "$shared"
printf 'Local facts in %s/memory and %s/MACHINE.md stay untracked.\n' "$shared" "$shared"
