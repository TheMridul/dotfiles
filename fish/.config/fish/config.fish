function fish_greeting
end

# Prompt (~/.config/starship.toml)
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

# Catppuccin accents for syntax and completion menus.
if status is-interactive
    set -g fish_color_normal cdd6f4
    set -g fish_color_command 89b4fa --bold
    set -g fish_color_keyword cba6f7 --bold
    set -g fish_color_param f5c2e7
    set -g fish_color_option fab387
    set -g fish_color_quote a6e3a1
    set -g fish_color_redirection 74c7ec --bold
    set -g fish_color_end cba6f7
    set -g fish_color_error f38ba8 --bold
    set -g fish_color_escape f2cdcd
    set -g fish_color_operator 94e2d5
    set -g fish_color_comment 7f849c --italics
    set -g fish_color_autosuggestion 7f849c
    set -g fish_color_search_match --background=45475a f9e2af --bold
    set -g fish_color_selection --background=585b70 cdd6f4 --bold
    set -g fish_color_valid_path --underline
    set -g fish_color_cancel f38ba8 --reverse
    set -g fish_pager_color_progress cba6f7 --bold
    set -g fish_pager_color_prefix 89b4fa --bold
    set -g fish_pager_color_completion cdd6f4
    set -g fish_pager_color_description a6adc8
    set -g fish_pager_color_selected_background --background=45475a
    set -g fish_pager_color_selected_prefix f9e2af --bold
    set -g fish_pager_color_selected_completion f5c2e7 --bold
    set -g fish_pager_color_selected_description cdd6f4
end
