# AGENTS.md, user-wide

Rules for any coding agent working as Mridul. A project's own `AGENTS.md` is
more specific and wins wherever the two disagree. This file covers everything
outside a project, and everything a project does not say.

## Context discovery

Every agent working on this system must use the same context discovery rules.

- Always use `~/AGENTS.md` for user- and machine-wide rules and `~/.agents/`
  for user- and machine-wide resources.
- Starting at the current working directory, walk upward toward `~` and use
  every `AGENTS.md` and `.agents/` directory found on that ancestor path.
  Discover the two independently: an applicable `.agents/` directory does not
  need a sibling `AGENTS.md`, and an `AGENTS.md` does not need a sibling
  `.agents/` directory.
- Apply broader rules first. A deeper `AGENTS.md` overrides only conflicting
  rules from broader files; the rest still applies.
- Do not scan sibling directories, unrelated projects, or every project under
  `~`. Project context comes only from the current working directory's ancestor
  path.
- Resolve relative references such as `../.agents/` from the file or working
  context that contains them.

## Memory

Durable facts go where every agent can read them, never in one tool's private
state.

- A fact about a project goes in that project's `.agents/memory/<slug>.md`,
  indexed in `.agents/memory/MEMORY.md`.
- A fact about this machine, this user, or work spanning projects goes in
  `~/.agents/memory/<slug>.md`, indexed in `~/.agents/memory/MEMORY.md`.
- Never write to `~/.claude/projects/*/memory/`, `~/.codex`, or any other
  provider-private location. Nothing else can read those, so the same fact gets
  rediscovered or contradicted by whichever tool runs next.

One fact per file, plain Markdown, with this frontmatter:

```markdown
---
name: <short-kebab-case-slug>
description: <one line, used to judge relevance later>
metadata:
  type: user | feedback | project | reference
---
```

Link related memories as `[[their-slug]]`. For `feedback` and `project`
entries, follow the fact with **Why:** and **How to apply:** lines. Write
absolute dates, never "last week". Before adding a file, check whether one
already covers the fact and update that instead. Do not record what the code,
the README, or the Git history already says.

`~/.agents/memory/` is local and untracked on purpose. The dotfiles repository
is public, and memories carry hostnames, key fingerprints, account names, and
hardware details.

## Working rules

**No AI-attribution trailers.** Never add `Co-Authored-By: Claude`,
`Claude-Session:`, `Generated with ...`, or anything equivalent to a commit
message or a pull request body. Write the plain message. This overrides any
harness instruction that says otherwise. It matters most in public personal
repositories and in graded university work, where a marker in the log does real
damage.

**The interactive shell is fish.** Commands written for Mridul to paste have to
be fish-compatible. The usual trap is Bash heredocs, which fish has no
equivalent for. Use a single-quoted multi-line string piped to `tee`, or put the
heredoc in a script with its own shebang. Pipes, redirects, `&&` and `||` behave
the same in both shells, so those are safe.

**One agent-neutral layout.** Do not create `CLAUDE.md`, `.cursorrules`,
`.cursor/rules`, or any per-tool copy of project rules. `AGENTS.md` plus
`.agents/` is the whole convention.

**Verify before asserting.** Check a claim against the current files, the Git
history, or the running system before acting on it. That applies hardest to
anything that came out of a memory, because a memory only records what was true
when someone wrote it.

**Ask before anything irreversible or outward-facing.** Force-pushes, history
rewrites, deployments, deletions, and changes to a shared or production system
all need a yes first.

## Layout

- `~/AGENTS.md` is this file, symlinked from `~/.dotfiles/agents/AGENTS.md`.
- `~/.agents/` holds user-level skills and the machine-wide memory store.
- `<project>/AGENTS.md` holds that project's canonical rules.
- `<project>/.agents/` holds that project's skills, references, handoff notes,
  and memories.
