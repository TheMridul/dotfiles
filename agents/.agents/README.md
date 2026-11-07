# Shared agent resources

`~/AGENTS.md` holds the machine- and user-wide rules. This directory holds the
resources those rules point at.

- `skills/<name>/` is the canonical home for user-level skills across agents.
  Tool-specific discovery paths may symlink here; do not maintain separate copies.
  Related skills may live in subfolders, with discovery links at the skill root.
- `memory/<slug>.md` is one durable fact about this machine, this user, or work
  spanning projects. `memory/MEMORY.md` indexes them. Agent memories go here,
  never in a provider-private memory directory.
- `MACHINE.md` is a one-page card of this machine: hardware, OS, shell, tools
  and servers, each linked to the memory with the detail. Keep it short and
  current; it is what an agent reads instead of probing the system.

`memory/` and `MACHINE.md` are real local files and are not stowed from the
dotfiles repository. That repository is public, and they carry hostnames, key
fingerprints, account names, and hardware details. Back them up separately if
you want them to survive a reinstall.

Project-specific context belongs in the project root's `AGENTS.md`, and that
project's own resources, memories included, belong in its `.agents/` directory.
Keep provider-specific configuration in its own tool directory. Do not copy
project rules into `~/.agents/`.
