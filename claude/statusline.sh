#!/usr/bin/env bash
# Claude Code status line
# stdin: the Status hook JSON payload (schema as of claude-code 2.1.220)
# Renders 2 lines (narrow-terminal friendly):
#   1: model+effort · user@host · cwd · branch
#   2: permission mode · context window usage bar · 5h rate-limit usage bar + reset countdown

input=$(cat)

HAVE_JQ=0
command -v jq >/dev/null 2>&1 && HAVE_JQ=1

# ---------- palette ----------
# A small curated set of saturated hues (blue/orange/purple/green/pink/gold)
# so segments pop against a dark terminal; separators/labels stay dim so
# they still recede behind the bright segments.
R=$'\033[0m'; B=$'\033[1m'
C_MODEL=$'\033[38;5;39m'
C_EFFORT=$'\033[38;5;215m'
C_HOST=$'\033[38;5;141m'
C_DIR=$'\033[38;5;83m'
C_BRANCH=$'\033[38;5;213m'
C_DIRTY=$'\033[38;5;196m'
C_PERM=$'\033[38;5;227m'
C_LABEL=$'\033[38;5;103m'
C_WARN=$'\033[38;5;214m'
C_CRIT=$'\033[38;5;196m'
C_GOOD=$'\033[38;5;83m'
SEP=" ${C_LABEL}·${R} "

line1=(); line2=()
add() { local ln="$1" text="$2"; [ -n "$text" ] && eval "${ln}+=(\"\$text\")"; }

# jq wrapper that returns empty on any error/missing binary instead of
# leaking "null"/error text into the status line.
jqi() {
  [ "$HAVE_JQ" = 1 ] || return 1
  jq -r "$1" <<<"$input" 2>/dev/null
}
jqf() {
  [ "$HAVE_JQ" = 1 ] || return 1
  jq -r "$1" "$2" 2>/dev/null
}
is_set() { [ -n "$1" ] && [ "$1" != "null" ] && [ "$1" != "-" ]; }

# shorten a path: collapse $HOME to ~, and if it still has more than 4
# components keep the first and last two, ellipsizing the middle.
shorten_path() {
  local p="$1" prefix="" clean=() part
  case "$p" in
    "$HOME") p="~" ;;
    "$HOME"/*) p="~${p#"$HOME"}" ;;
  esac
  [ "${p:0:1}" = "/" ] && prefix="/"
  IFS='/' read -ra parts <<<"$p"
  for part in "${parts[@]}"; do [ -n "$part" ] && clean+=("$part"); done
  local n=${#clean[@]}
  if [ "$n" -gt 4 ]; then
    printf '%s%s/…/%s/%s' "$prefix" "${clean[0]}" "${clean[$((n-2))]}" "${clean[$((n-1))]}"
  else
    printf '%s' "$p"
  fi
}

# cap a string at N chars with an ellipsis
truncate_str() {
  local s="$1" max="${2:-24}"
  if [ "${#s}" -gt "$max" ]; then
    printf '%s…' "${s:0:$((max-1))}"
  else
    printf '%s' "$s"
  fi
}

threshold_fg() {
  local p="$1"
  if   [ "$p" -ge 80 ]; then printf '%s' "$C_CRIT"
  elif [ "$p" -ge 50 ]; then printf '%s' "$C_WARN"
  else                       printf '%s' "$C_GOOD"; fi
}

# solid color-filled progress bar, built from background-colored spaces
# rather than glyphs — renders identically in any font/terminal.
usage_bar() {
  local pct="$1" width="${2:-14}" filled empty fillbg emptybg fill_sp empty_sp
  filled=$(( pct * width / 100 ))
  [ "$filled" -gt "$width" ] && filled=$width
  [ "$filled" -lt 0 ] && filled=0
  empty=$(( width - filled ))
  if   [ "$pct" -ge 80 ]; then fillbg=$'\033[48;5;196m'
  elif [ "$pct" -ge 50 ]; then fillbg=$'\033[48;5;214m'
  else                         fillbg=$'\033[48;5;83m'; fi
  emptybg=$'\033[48;5;237m'
  printf -v fill_sp '%*s' "$filled" ''
  printf -v empty_sp '%*s' "$empty" ''
  printf '%s%s%s%s%s' "$fillbg" "$fill_sp" "$emptybg" "$empty_sp" "$R"
}

# ---------- line 1: model+effort · user@host · cwd · branch ----------
model=$(jqi '.model.display_name // .model.id // empty')
effort=$(jqi '.effort.level // empty')
fast=$(jqi 'if .fast_mode then "fast" else empty end')
if is_set "$model"; then
  m="${B}${C_MODEL}${model}${R}"
  is_set "$effort" && m+=" ${C_EFFORT}${effort}${R}"
  [ "$fast" = "fast" ] && m+=" ${C_EFFORT}fast${R}"
  add line1 "$m"
fi

uh_user=$(whoami 2>/dev/null)
uh_host=$(hostname -s 2>/dev/null)
[ -n "$uh_user" ] && [ -n "$uh_host" ] && add line1 "${C_HOST}${uh_user}@${uh_host}${R}"

acct_file="${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json"
acct=$(jqf '.oauthAccount | (.emailAddress // .displayName // empty)' "$acct_file")
is_set "$acct" || acct=""
add line1 "${acct:+${C_HOST}${acct}${R}}"

dir=$(jqi '.workspace.current_dir // .cwd // empty')
is_set "$dir" || dir="$PWD"
add line1 "${C_DIR}$(shorten_path "$dir")${R}"

if root=$(git -C "$dir" --no-optional-locks rev-parse --show-toplevel 2>/dev/null); then
  branch=$(git -C "$dir" --no-optional-locks symbolic-ref --short -q HEAD 2>/dev/null) \
    || branch=$(git -C "$dir" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
  dirty=""
  [ -n "$(git -C "$dir" --no-optional-locks status --porcelain 2>/dev/null | head -c1)" ] && dirty="*"
  branch_name=$(truncate_str "${branch:-detached}" 24)
  if [ "$(basename "$root")" = "$(basename "$dir")" ]; then
    g="${C_BRANCH}${branch_name}${R}"
  else
    repo_name=$(truncate_str "$(basename "$root")" 24)
    g="${C_BRANCH}${repo_name}:${branch_name}${R}"
  fi
  [ -n "$dirty" ] && g+="${C_DIRTY}*${R}"
  add line1 "$g"
fi

# ---------- line 2: permission mode · usage bars ----------
# permission mode (only shown when not the plain default)
perm=$(jqi '.permission_mode // .permissionMode // empty')
if is_set "$perm" && [ "$perm" != "default" ]; then
  add line2 "${C_PERM}${perm}${R}"
fi

if [ "$HAVE_JQ" = 1 ]; then
  ctx_used=$(jqi '.context_window.used_percentage // empty')
else
  ctx_used=""
fi

if is_set "$ctx_used"; then
  cp=$(printf '%.0f' "$ctx_used" 2>/dev/null) || cp=0
  cc=$(threshold_fg "$cp")
  add line2 "${C_LABEL}ctx${R} $(usage_bar "$cp") ${cc}${cp}%${R}"
fi

# 5h rate-limit usage bar + reset countdown
pct="" resets=""
if [ "$HAVE_JQ" = 1 ]; then
  IFS=$'\t' read -r pct resets <<<"$(jqi '[
      (.rate_limits.five_hour.used_percentage // empty),
      (.rate_limits.five_hour.resets_at // empty)] | @tsv')"

  # fall back to the cached utilization Claude Code persists between refreshes
  if ! is_set "$pct" || ! is_set "$resets"; then
    IFS=$'\t' read -r pct resets <<<"$(jqf '
        (.cachedUsageUtilization.utilization.limits // [])
        | map(select(.kind == "session")) | first
        | if . then [(.percent // empty), (.resets_at // empty)] else [] end
        | @tsv' "$HOME/.claude.json")"
  fi
fi

if is_set "$pct"; then
  p=$(printf '%.0f' "$pct" 2>/dev/null) || p=0
  c=$(threshold_fg "$p")
  u="${C_LABEL}5h${R} $(usage_bar "$p") ${c}${p}%${R}"

  end=""
  if is_set "$resets"; then
    case "$resets" in
      *[!0-9.]*) end=$(date -d "$resets" +%s 2>/dev/null) ;;
      *)         end=$(date -d "@${resets%%.*}" +%s 2>/dev/null) ;;
    esac
  fi
  if is_set "$end"; then
    left=$(( end - $(date +%s) ))
    if [ "$left" -le 0 ]; then t="now"
    else t="$((left/3600))h$(printf '%02d' $(( (left%3600)/60 )))m"; fi
    u+=" ${C_LABEL}(resets ${t})${R}"
  fi
  add line2 "$u"
fi

# ---------- render ----------
render_line() {
  local -n arr="$1"
  local out=""
  for s in "${arr[@]}"; do
    [ -n "$out" ] && out+="$SEP"
    out+="$s"
  done
  printf '%s' "$out"
}

out=""
for ln in line1 line2; do
  eval "n=\${#${ln}[@]}"
  [ "$n" -gt 0 ] || continue
  [ -n "$out" ] && out+=$'\n'
  out+="$(render_line "$ln")"
done
printf '%s' "$out"
