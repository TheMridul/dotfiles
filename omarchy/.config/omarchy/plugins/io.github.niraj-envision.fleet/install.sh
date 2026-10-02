#!/usr/bin/bash
# Fleet installer. Every persistent change is one recoverable transaction.
set -euo pipefail

script_path=${BASH_SOURCE[0]}
[[ $script_path == /* ]] || script_path=$PWD/$script_path
repo_dir=$(cd -- "${script_path%/*}" && pwd -P)
helper="$repo_dir/scripts/install_transaction.py"

python_bin=/usr/bin/python3
ssh_bin=/usr/bin/ssh
ssh_keygen_bin=/usr/bin/ssh-keygen
secret_tool_bin=/usr/bin/secret-tool
hyprctl_bin=/usr/bin/hyprctl
omarchy_bin=/usr/share/omarchy/bin/omarchy
gtk_cache_bin=/usr/bin/gtk-update-icon-cache
desktop_db_bin=/usr/bin/update-desktop-database

data_home=${XDG_DATA_HOME:-$HOME/.local/share}
app="$data_home/fleet"
launcher="$HOME/.local/bin/fleet"
transaction=""
validated=false

c()    { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }

rollback_on_failure() {
  local status=$?
  if (( status != 0 )) && [[ -n $transaction && $validated == false ]]; then
    printf 'Fleet setup failed; restoring every changed file...\n' >&2
    "$python_bin" "$helper" rollback "$transaction" || \
      printf 'Automatic rollback failed. Recovery evidence: %s\n' "$transaction" >&2
    if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} && -x $hyprctl_bin ]]; then
      "$hyprctl_bin" reload >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap rollback_on_failure EXIT

[[ -x $python_bin ]] || { printf 'Missing required command: %s\n' "$python_bin" >&2; exit 1; }
[[ -r $helper ]] || { printf 'Missing installer helper: %s\n' "$helper" >&2; exit 1; }

# A killed installer leaves a complete write-ahead journal. Recover it before
# calculating a new plan so upgrades cannot layer over a partial old one.
"$python_bin" "$helper" recover

if [[ ${1:-} == --uninstall ]]; then
  c "Removing Fleet"
  printf '  This removes the application, launcher, desktop entry, icon, and Fleet-managed\n'
  printf '  Hyprland blocks. Hosts, state, credentials, and VPN profiles stay untouched.\n'
  if [[ ${2:-} != --yes && ${FLEET_ASSUME_YES:-} != 1 ]]; then
    read -rp '  Continue? [y/N] ' answer
    [[ ${answer:-N} =~ ^[Yy]$ ]] || { printf '  cancelled\n'; exit 0; }
  fi
  transaction=$("$python_bin" "$helper" uninstall --repo-dir "$repo_dir")
else
  c "Installing Fleet"
  printf '  target: %s\n' "$app"
  for command in "$ssh_bin" "$ssh_keygen_bin" "$secret_tool_bin"; do
    [[ -x $command ]] || { printf 'Missing required command: %s\n' "$command" >&2; exit 1; }
  done
  "$python_bin" - <<'PY' || { printf 'Fleet needs Python 3.9 or newer.\n' >&2; exit 1; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 9) else 1)
PY
  ok "fixed system Python, OpenSSH, and Secret Service tools found"
  [[ -x /usr/bin/openvpn || -x /usr/bin/wg-quick ]] || \
    warn "no VPN client found; install one only if your servers require it"

  with_hypr=false
  hypr_dir=${XDG_CONFIG_HOME:-$HOME/.config}/hypr
  if [[ -d $hypr_dir && -f $hypr_dir/bindings.lua ]]; then
    read -rp '  Add the SUPER+SHIFT+V keybinding and Fleet window rule? [Y/n] ' answer
    [[ ${answer:-Y} =~ ^[Yy]?$ ]] && with_hypr=true
  else
    warn "no Hyprland config found; see docs/hyprland.md for manual setup"
  fi

  args=(install --repo-dir "$repo_dir")
  [[ $with_hypr == true ]] && args+=(--with-hypr)
  transaction=$("$python_bin" "$helper" "${args[@]}")
fi

if [[ -n ${HYPRLAND_INSTANCE_SIGNATURE:-} && -x $hyprctl_bin ]]; then
  "$hyprctl_bin" reload >/dev/null
  errors=$("$hyprctl_bin" configerrors)
  if [[ -n $errors ]]; then
    printf 'Hyprland reported configuration errors:\n%s\n' "$errors" >&2
    exit 1
  fi
  ok "Hyprland reloaded with no configuration errors"
fi

validated=true
trap - EXIT

if [[ ${1:-} == --uninstall ]]; then
  [[ ! -x $gtk_cache_bin ]] || "$gtk_cache_bin" "$data_home/icons/hicolor" >/dev/null 2>&1 || true
  [[ ! -x $desktop_db_bin ]] || "$desktop_db_bin" "$data_home/applications" >/dev/null 2>&1 || true
  c "Fleet removed"
  ok "application payload and managed Hyprland blocks removed"
  warn "left alone: hosts, state, credentials, and VPN profiles"
else
  [[ ! -x $gtk_cache_bin ]] || "$gtk_cache_bin" "$data_home/icons/hicolor" >/dev/null 2>&1 || true
  [[ ! -x $desktop_db_bin ]] || "$desktop_db_bin" "$data_home/applications" >/dev/null 2>&1 || true
  [[ ! -x $omarchy_bin ]] || "$omarchy_bin" menu refresh >/dev/null 2>&1 || true
  c "Done"
  ok "installed to $app"
  ok "launcher at $launcher"
  printf '  Start it with: %s\n' "$launcher"
  printf '  Recovery evidence: %s\n' "$transaction"
fi
