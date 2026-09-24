---
name: claude-collab
description: Orchestrate Claude Code agents from Codex to divide substantial work, explore independent approaches, review one another's results, and synthesize the strongest verified outcome. Use when the user asks Codex and Claude to collaborate, requests Claude agents, or wants parallel multi-model implementation or review. Skip for small tasks where coordination would cost more than doing the work directly.
---

# Claude Collaboration

Codex owns the task and final result. Use fresh Claude Code sessions as independent workers, then inspect and integrate their useful output. Do not return a pile of agent transcripts as the answer.

Read [references/claude-cli.md](references/claude-cli.md) before launching workers. It defines the tested command shapes, prompt-file handling, session resumption, and isolation rules.

## Frame the collaboration

Before launching agents:

1. Read the applicable user and project `AGENTS.md` files and inspect the current worktree.
2. State a concrete done condition and split the work into independent slices. If several solutions are plausible, assign competing approaches instead.
3. Choose the smallest useful team, usually two or three workers. Use the installed Claude Code CLI with its existing Claude.ai subscription login, and account for latency and subscription quota. Do not switch to API-key billing unless the user explicitly requests it.
4. Check the installed CLI and current official model guidance before overriding a model. Use the session default when the task does not need a deliberate split. A fast model can handle bounded extraction or routine edits; reserve a stronger available model for difficult reasoning or judgment when it can change the result. Do not hard-code a Sonnet/Opus ratio or assume an alias names a particular version forever.
5. Tell the user the team size, role split, and model assignment in a commentary update before launch. Ask first only when the run would consume substantially more quota than a normal invocation.
6. Give every agent a self-contained brief with the goal, its exact scope, allowed paths, forbidden scope, relevant user and project rules, required evidence, and the report format. Tell the worker to read the source `AGENTS.md` files as well, when accessible; the brief still carries the rules because Claude sessions do not inherit Codex context.

Use Codex or an independent Claude judge when candidate selection involves meaningful judgment and the lead cannot settle it from the artifacts and checks.

## Choose an isolation mode

### Read-only specialists

Use this for investigation, architecture, planning, review, test analysis, or tasks where Codex will implement the synthesis. Run independent `claude -p` calls concurrently through the shell tool. Enforce read-only operation with `--permission-mode plan --tools Read,Glob,Grep --strict-mcp-config`; do not include Bash, Edit, Write, NotebookEdit, WebFetch, inherited MCP servers, or other mutating or external tools. Request structured, concise findings with file and line evidence.

Agents may read the same workspace concurrently. They must not edit it in this mode.

### Isolated implementers

Use this when agents should implement competing solutions or independent components. Give each writer a separate git worktree or a separate scratch copy. Never let parallel agents edit the same checkout.

Writing agents require a clean Git baseline. If relevant user changes are uncommitted, switch to read-only specialists and let Codex implement in the primary checkout. Do not stash, discard, or silently omit those changes.

On a clean baseline, create one explicit temporary git worktree and branch per writer. Tell each agent which directory it owns, which paths are in scope, which paths are forbidden, what checks to run, and that it must not modify another worker's output. Agents do not commit. Codex inspects each worktree's diff and manually applies the selected changes to the primary checkout; this is the integration method and keeps candidate history out of the project.

Use `--permission-mode acceptEdits` only inside an isolated writable workspace and only when edits are already authorized by the user's task. Do not use `--dangerously-skip-permissions` or `bypassPermissions`.

## Launch and drain

Run independent agents concurrently using separate shell-tool calls rather than shell job-control syntax. Use JSON noninteractive output so Codex captures both the result and session ID. Give sessions descriptive names. Pass `--model` only when a model choice is intentional, and record the selected model for reproducibility. Match effort to the role instead of defaulting every worker to maximum effort.

Declare a task-appropriate deadline before launch and monitor long-running calls. Stop a worker that passes the deadline. If an agent needs a follow-up, resume that session with its captured session ID rather than starting over. Wait for all useful workers before synthesis. A failed or timed-out worker is a dropout; continue when the remaining coverage is sufficient, otherwise retry once with a narrower brief.

Never expose secrets in prompts or command output. Do not give Claude broader filesystem, network, or mutation access than the task requires.

## Evaluate and synthesize

Read every result and inspect every changed file. Judge candidates against the done condition using concrete evidence:

- correctness and completeness;
- fit with the repository's architecture and conventions;
- maintainability and size of the change;
- meaningful test or runtime evidence;
- risks the candidate identified or missed.

Pick the strongest base. Manually graft compatible improvements from other candidates so the result has one coherent design. Do not combine code mechanically or preserve mutually inconsistent approaches. Resolve disagreements by checking the repository and running code, not by majority vote.

Codex remains responsible for the integrated edits, conflict resolution, and final verification in the primary workspace. Treat worker-reported checks as claims until Codex reruns them. Preserve unrelated user changes.

## Finish

Run the checks appropriate to the synthesized change. Report the completed result, the main contribution taken from each useful agent, verification performed, and any real remaining limitation. Keep raw transcripts and temporary coordination artifacts out of the project unless the user asks for them.

Report temporary worktree paths after integration. Removing worktrees, branches, prompt files, or other temporary artifacts is a deletion; obtain any approval required by the applicable `AGENTS.md` before cleanup.
