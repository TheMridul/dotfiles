if status is-interactive
    if command -q zoxide
        zoxide init fish | source
    end

    if command -q fzf
        fzf --fish | source
    end

    # Initialize after fzf so Atuin owns Ctrl+R; keep fish's Up arrow.
    if command -q atuin
        atuin init fish --disable-up-arrow --disable-ai | source
    end
end
