function fish_greeting
    if command -q fastfetch
        fastfetch
    end
end

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
