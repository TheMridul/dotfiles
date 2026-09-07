# ripgrep reads no configuration file at all unless this variable points at one.
# There is no implicit ~/.config/ripgrep/ripgreprc lookup.
set -l rg_config $HOME/.config/ripgrep/ripgreprc
if test -f $rg_config
    set -gx RIPGREP_CONFIG_PATH $rg_config
end
