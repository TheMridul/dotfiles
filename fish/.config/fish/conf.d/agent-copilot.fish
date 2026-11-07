# Copilot CLI only reads files under the working directory and any --add-dir.
# Give it the shared agent context (machine card, memory, skills) everywhere.
function copilot --wraps copilot
    command copilot --add-dir ~/.agents --add-dir ~/.dotfiles/agents $argv
end
