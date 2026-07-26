source /usr/share/cachyos-fish-config/cachyos-config.fish

# Omarchy (manual install) — expose OMARCHY_PATH and its bin dir to interactive shells
set -gx OMARCHY_PATH $HOME/.local/share/omarchy
if test -d $OMARCHY_PATH/bin
    fish_add_path --path $OMARCHY_PATH/bin
end

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
