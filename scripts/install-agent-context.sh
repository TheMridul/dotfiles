#!/bin/bash
set -euo pipefail

dotfiles_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
claude_home=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
shared_agents_home="$HOME/.agents"
hook_source="$dotfiles_root/claude/hooks/load-agent-context.sh"
hook_target="$claude_home/hooks/load-agent-context.sh"

link_if_missing() {
  local source=$1
  local target=$2

  if [[ -L $target ]]; then
    [[ $(readlink -f "$target") == "$source" ]] && return
    printf 'Refusing to replace existing symlink: %s\n' "$target" >&2
    exit 1
  fi

  if [[ -e $target ]]; then
    printf 'Refusing to replace existing file: %s\n' "$target" >&2
    exit 1
  fi

  ln -s "$source" "$target"
}

mkdir -p "$claude_home/hooks" "$claude_home/skills" "$shared_agents_home"
mkdir -p "$shared_agents_home/memory"
chmod +x "$hook_source"
chmod +x "$dotfiles_root/claude/statusline.sh"

link_if_missing "$hook_source" "$hook_target"
link_if_missing "$dotfiles_root/claude/statusline.sh" "$claude_home/statusline.sh"
link_if_missing "$dotfiles_root/claude/skills/new-project" "$claude_home/skills/new-project"
link_if_missing "$dotfiles_root/claude/skills/existing-project" "$claude_home/skills/existing-project"
link_if_missing "$dotfiles_root/claude/skills/just-rules" "$claude_home/skills/just-rules"
link_if_missing "$dotfiles_root/claude/skills/collaborator-tone" "$claude_home/skills/collaborator-tone"
link_if_missing "$dotfiles_root/claude/skills/explain-code" "$claude_home/skills/explain-code"
link_if_missing "$dotfiles_root/claude/skills/mentor-mode" "$claude_home/skills/mentor-mode"
link_if_missing "$dotfiles_root/agents/.agents/README.md" "$shared_agents_home/README.md"
link_if_missing "$dotfiles_root/agents/.agents/skills" "$shared_agents_home/skills"
link_if_missing "$dotfiles_root/agents/AGENTS.md" "$HOME/AGENTS.md"

# Codex reads ~/.codex/AGENTS.md as its global instructions. Point it at the
# same file rather than keeping a second copy of the rules.
if [[ -d $HOME/.codex ]]; then
  link_if_missing "$HOME/AGENTS.md" "$HOME/.codex/AGENTS.md"
fi

settings_path="$claude_home/settings.json"
if [[ -e $settings_path ]]; then
  jq empty "$settings_path"
else
  printf '{}\n' >"$settings_path"
fi

temporary_settings=$(mktemp "$settings_path.XXXXXX")
jq --arg hook '$HOME/.claude/hooks/load-agent-context.sh' '
  def has_context_hook:
    any(.[]?; any(.hooks[]?; .type == "command" and .command == $hook));

  .hooks //= {} |
  .hooks.SessionStart //= [] |
  .hooks.SubagentStart //= [] |
  .hooks.SessionStart |= if has_context_hook then . else . + [{"hooks": [{"type": "command", "command": $hook}]}] end |
  .hooks.SubagentStart |= if has_context_hook then . else . + [{"hooks": [{"type": "command", "command": $hook}]}] end
' "$settings_path" >"$temporary_settings"
mv "$temporary_settings" "$settings_path"

printf 'Shared agent context installed. Projects use AGENTS.md and .agents/.\n'
printf 'Machine-wide memories live in %s/memory/ and are deliberately untracked.\n' "$shared_agents_home"
