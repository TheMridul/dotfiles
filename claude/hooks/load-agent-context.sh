#!/bin/bash
set -euo pipefail

input=$(cat)
cwd=$(jq -r '.cwd // empty' <<<"$input")
[[ -n $cwd && -d $cwd ]] || exit 0

dir=$(realpath "$cwd")
home=$(realpath "$HOME")

# Nearest project root is the closest ancestor with an AGENTS.md, excluding
# $HOME itself — the file there is the user-wide layer, reported separately.
project_root=""
while :; do
  if [[ $dir != "$home" && -f $dir/AGENTS.md ]]; then
    project_root=$dir
    break
  fi
  [[ $dir == / ]] && break
  dir=$(dirname "$dir")
done

lines=()

if [[ -f $home/AGENTS.md ]]; then
  lines+=("Machine- and user-wide rules are at $home/AGENTS.md. Read it before working.")
fi

if [[ -d $home/.agents ]]; then
  lines+=("User-level agent resources are under $home/.agents/; machine-wide memories are in $home/.agents/memory/ (index: MEMORY.md).")
fi

if [[ -n $project_root ]]; then
  lines+=("Shared project context is at $project_root/AGENTS.md. It is canonical for this project and wins over the user-wide file. Shared agent resources are under $project_root/.agents/; read only files relevant to the task.")
  if [[ -d $project_root/.agents/memory ]]; then
    lines+=("This project's memories are in $project_root/.agents/memory/ (index: MEMORY.md). Record new durable project facts there, never in a provider-private memory directory.")
  else
    lines+=("Record new durable project facts in $project_root/.agents/memory/<slug>.md and index them in MEMORY.md, never in a provider-private memory directory.")
  fi
fi

lines+=("Do not create or rely on provider-specific project instruction files.")

((${#lines[@]})) || exit 0

context=$(printf '%s\n' "${lines[@]}")
event=$(jq -r '.hook_event_name // "SessionStart"' <<<"$input")

jq -n --arg event "$event" --arg context "$context" \
  '{hookSpecificOutput: {hookEventName: $event, additionalContext: $context}}'
