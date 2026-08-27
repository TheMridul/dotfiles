#!/bin/bash
set -euo pipefail

input=$(cat)
cwd=$(jq -r '.cwd // empty' <<<"$input")
[[ -n $cwd && -d $cwd ]] || exit 0

dir=$(realpath "$cwd")
project_root=""
while :; do
  if [[ -f $dir/AGENTS.md ]]; then
    project_root=$dir
    break
  fi
  [[ $dir == / ]] && break
  dir=$(dirname "$dir")
done

[[ -n $project_root ]] || exit 0

event=$(jq -r '.hook_event_name // "SessionStart"' <<<"$input")
context=$(printf 'Shared project context is at %s/AGENTS.md. Read it before working. Shared agent resources are under %s/.agents/; read only files relevant to the task. Do not create or rely on provider-specific project instruction files.\n' "$project_root" "$project_root")

jq -n --arg event "$event" --arg context "$context" \
  '{hookSpecificOutput: {hookEventName: $event, additionalContext: $context}}'
