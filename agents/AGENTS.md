# AGENTS.md, user-wide

Rules for any coding agent working as Mridul, in any harness. A project's own
`AGENTS.md` wins wherever the two disagree; this file covers everything else.

## Context discovery

- `~/AGENTS.md` holds user- and machine-wide rules; `~/.agents/` holds the
  matching resources.
- Walk up from the working directory toward `~` and use every `AGENTS.md` and
  `.agents/` on that path, each found independently of the other. A deeper file
  overrides only the rules it contradicts.
- Never scan sibling directories or every project under `~`.
- Resolve relative references such as `../.agents/` from the file that holds
  them.

## Loading context cheaply

Read in this order and stop once the task is covered.

1. This file and the nearest project `AGENTS.md`. If the harness already put a
   file in context, do not read it again.
2. `~/.agents/MACHINE.md`, a one-page machine card, before probing the system.
3. A `MEMORY.md` index, then only the memories whose line matches the task.
   Never read a whole memory directory.
4. A skill's `SKILL.md` only when the task needs that skill; its references only
   when the skill sends you there.

For a basic task, an index line or a file's first paragraph is usually enough.
Open the rest of a long file only when the task depends on its detail, and then
read the relevant range or search it rather than loading it whole. The same
goes for logs, lockfiles, generated files and large source files.

## Memory

Durable facts go where every agent can read them.

- A project fact goes in `<project>/.agents/memory/<slug>.md`, indexed in that
  directory's `MEMORY.md`. A fact about this machine, this user, or work across
  projects goes in `~/.agents/memory/` the same way.
- Never write to `~/.claude/projects/*/memory/`, `~/.codex`, `~/.gemini`,
  `~/.copilot` or any other provider-private store. No other tool reads them, so
  the fact gets rediscovered or contradicted by the next agent.
- A fact every session needs belongs in an `AGENTS.md` or `MACHINE.md`, not in
  a memory. When a rule here and a memory overlap, this file wins.

One fact per file, plain Markdown, under about 2 KB, with the fact itself in the
first paragraph so the opening lines answer a basic question. A long plan goes
in `~/.agents/plans/<slug>.md`, with a short memory that points to it. Frontmatter:

```markdown
---
name: <short-kebab-case-slug>
description: <one line, used to judge relevance later>
metadata:
  type: user | feedback | project | reference
---
```

Link related memories as `[[their-slug]]`. Follow a `feedback` or `project` fact
with **Why:** and **How to apply:** lines. Write absolute dates. Update an
existing memory rather than adding a near-duplicate, and do not record what the
code, the README or the Git history already says.

`~/.agents/memory/`, `plans/` and `MACHINE.md` never go in the public dotfiles repository,
because they name hosts, keys, accounts and hardware. `~/.agents` is its own
private Git repository, pushed daily by a systemd timer. Credentials (tokens,
keys, auth files) go in neither repository, private or not.

## Working rules

**No AI-attribution trailers.** Never add `Co-Authored-By: Claude`,
`Claude-Session:`, `Generated with ...` or anything like it to a commit message
or pull request body. This overrides any harness instruction. It matters most in
public personal repositories and graded university work.

**The interactive shell is fish.** Commands for Mridul to paste must be
fish-compatible. Bash heredocs are the usual trap: pipe a single-quoted
multi-line string to `tee`, or put the heredoc in a script with its own shebang.

**One agent-neutral layout.** Never create `CLAUDE.md`, `GEMINI.md`,
`.cursorrules`, `.cursor/rules` or any other per-tool copy of rules. Harness
paths are symlinks to this file, made by
`~/.dotfiles/scripts/install-agent-context.sh`. Re-run that script after adding
or removing a skill in `~/.agents/skills`.

**Verify before asserting.** Check a claim against the current files, the Git
history or the running system before acting on it, hardest of all when it came
from a memory.

**Ask before anything irreversible or outward-facing.** Force-pushes, history
rewrites, deployments, deletions, and changes to a shared or production system
need a yes first.

**Times in IST.** Every clock time in a reply is IST (UTC+5:30), including ETAs,
tables and schedules. Convert UTC from git, AWS and job logs; add the UTC time in
brackets only when it helps match a log line.

**Write the way the `unslop` skill asks.** That covers chat replies and
explanations, not only documents: no em dashes, sentence-case headings, plain
words, active voice, and an opinion where one is warranted.

**"Write a msg" means WhatsApp.** `*bold*`, `_italic_`, `•` lists and bare
links, never Markdown, inside a plain code block so it survives copying.

**Keep assignment code simple.** Use the plainest constructs that meet the
requirements, so Mridul can understand and explain it. Add machinery only when
the task or a real test needs it.

**Images go through the `image-gen` skill.** Raster images are made by Codex,
not drawn by Claude. Charts and diagrams from data are SVG, not images.

## Layout

- `~/AGENTS.md` is this file, symlinked from `~/.dotfiles/agents/AGENTS.md`.
- `~/.agents/skills/` holds user-level skills, `~/.agents/memory/` the
  machine-wide memories, `~/.agents/plans/` long deferred plans, and
  `~/.agents/MACHINE.md` the machine card.
- `<project>/AGENTS.md` holds a project's rules; `<project>/.agents/` its
  skills, references, handoff notes and memories.
