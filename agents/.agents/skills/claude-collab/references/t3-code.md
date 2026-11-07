# T3 Code execution

Use this route when running inside T3 Code. Outside T3, retain the skill's native or CLI workflow. Host instructions take precedence over these defaults.

- Use native subagents for same-provider work with inherited settings. Use T3 `delegate_task` for cross-provider workers, explicitly selected settings, background work, or a separate checkout. Discover tools if needed and call `orchestrator_capabilities` once before the first delegation. Use its actual provider instance IDs and supported models/options; personal and work accounts are distinct instances. Never silently switch accounts or providers.
- Give each worker a self-contained brief with intent, scope, source instruction paths, evidence, checks, and completion criteria. Children do the assigned work themselves unless explicitly authorized to delegate.
- For writers, request `isolation: "worktree"`. Never create their checkouts in the shell or ask workers to create them. Worktrees start from the parent commit; relevant uncommitted edits are not included. With a dirty baseline, prefer read-only analysis and integrate in the parent unless another baseline is explicitly agreed.
- For read-only reviewers, forbid edits in the brief and use any available tool restrictions. A prompt restriction is not equivalent to the CLI's enforced read-only tool allowlist; do not claim otherwise or treat Plan mode as an enforcement boundary.
- Keep task IDs and returned links. Follow the tool's `next` instruction: when completion wakes the parent, end the turn instead of polling, sleeping, or adding a watcher. Use `task_cancel` for work no longer needed.
- Every new review or re-check is a fresh `delegate_task`, with findings and objections in the brief. Do not send a new review through an existing child thread. Create top-level threads only when the user asks for one.
- Inspect each returned diff and verify the integrated result. Do not assume isolated edits were merged automatically. Preserve the skill's rubric, synthesis, and verification requirements.
- If a requested provider or setting is unavailable, report it. Do not bypass T3 using a shell CLI or another provider. Use returned thread links verbatim when referring to delegated threads.
