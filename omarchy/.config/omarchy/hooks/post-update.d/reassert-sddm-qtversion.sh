#!/bin/bash

# Re-assert the QtVersion=6 SDDM greeter fix after Omarchy package updates.
#
# `omarchy update` runs pacman with --overwrite '/usr/share/sddm/themes/omarchy/*',
# so whenever the omarchy pacman package ships a new version, this whole
# directory (including metadata.desktop) gets reinstalled from the package
# and silently drops the QtVersion=6 fix, which caused a full SDDM outage
# once already. This hook makes that fix self-healing after every update.
#
# See TROUBLESHOOTING.md in the dotfiles repo for the full story.

set -euo pipefail

META=/usr/share/sddm/themes/omarchy/metadata.desktop

if [[ -f $META ]] && ! grep -q '^QtVersion=6$' "$META"; then
  echo "[post-update hook] QtVersion=6 missing from $META — re-applying"
  echo "QtVersion=6" | sudo tee -a "$META" >/dev/null
fi
