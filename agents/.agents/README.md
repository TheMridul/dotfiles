# Shared agent resources

`~/AGENTS.md` holds the machine- and user-wide rules. This directory holds the
resources those rules point at.

- `skills/<name>/` is a user-level skill that is useful across projects.
- `memory/<slug>.md` is one durable fact about this machine, this user, or work
  spanning projects. `memory/MEMORY.md` indexes them. Agent memories go here,
  never in a provider-private memory directory.

`memory/` is a real local directory and is not stowed from the dotfiles
repository. That repository is public, and memories carry hostnames, key
fingerprints, account names, and hardware details. Back the directory up
separately if you want it to survive a reinstall.

Project-specific context belongs in the project root's `AGENTS.md`, and that
project's own resources, memories included, belong in its `.agents/` directory.
Keep provider-specific configuration in its own tool directory. Do not copy
project rules into `~/.agents/`.
