source /usr/share/cachyos-fish-config/cachyos-config.fish

# OMARCHY_PATH is no longer set here. Omarchy is a package now (omarchy-dev), so
# /etc/omarchy.conf resolves it to /usr/share/omarchy and /usr/bin/omarchy-* is
# already on PATH. Setting it here pinned interactive shells to the old
# ~/.local/share/omarchy checkout, which is frozen and no longer updated.

# overwrite greeting
# potentially disabling fastfetch
#function fish_greeting
#    # smth smth
#end

# Prompt (hushOS-themed, ~/.config/starship.toml)
if command -q starship
    starship init fish | source
end

# Set default for ani-cli as "dub"
set -gx ANI_CLI_MODE dub
# Syntax highlighting for common commands
if command -q bat
    alias cat='bat --paging=never'
end
alias diff='diff --color=auto'
alias ip='ip --color=auto'
