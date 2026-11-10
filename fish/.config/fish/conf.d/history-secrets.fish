# Keep API tokens out of fish history. A Cloudflare token pasted into a curl
# command sat in the history for days before anyone noticed. Atuin has its
# own copy of these patterns in ~/.config/atuin/config.toml (history_filter).
#
# Defining this function replaces fish's default rule of skipping commands
# that start with a space, so that rule is kept here too.
function fish_should_add_to_history
    string match -qr '^\s' -- $argv; and return 1
    string match -qr -- '(cf[a-z]t_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|sk-(ant|proj)-[\w-]{20,}|\b(AKIA|ASIA)[0-9A-Z]{16}\b|xox[abpr]-[\w-]{10,}|AIza[\w-]{30,}|Bearer\s+[\w.~+/-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY)' $argv
    and return 1
    return 0
end
