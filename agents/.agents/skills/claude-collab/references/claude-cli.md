# Claude CLI patterns

Use prompt files so multi-line briefs do not depend on shell quoting or Bash heredocs. Create them with the file-editing tool under a task-specific `/tmp` directory. Do not put secrets in a brief.

## Read-only worker

Run from the project root or the directory the worker should inspect:

```text
claude -p --name <unique-name> --permission-mode plan --tools Read,Glob,Grep --strict-mcp-config --output-format json < /tmp/<task>/brief.md
```

The tool allowlist is an enforcement boundary. `--strict-mcp-config` prevents inherited MCP servers from reopening external or mutating capabilities. Adding Bash or a write-capable tool changes this from read-only mode.

## Isolated writer

Codex first verifies that the relevant baseline is clean and creates a dedicated branch and worktree under a task-specific `/tmp` directory. Run the worker with that worktree as its working directory:

```text
claude -p --name <unique-name> --permission-mode acceptEdits --tools Read,Glob,Grep,Edit,Write,Bash --output-format json < /tmp/<task>/brief.md
```

The brief must forbid edits outside the assigned paths. Bash is permitted only because the worker is isolated; never add permission bypass flags. Ask the worker to leave an uncommitted diff and a concise report containing files changed, checks run, and known limitations.

## Resume

Parse and retain `session_id` from the JSON result. Put the follow-up in another prompt file and resume with the same permission and tool boundary:

```text
claude -p --resume <session-id> --permission-mode <original-mode> --tools <original-tools> --output-format json < /tmp/<task>/follow-up.md
```

Do not weaken permissions on resume.

These commands intentionally use the normal installed Claude Code session and its existing Claude.ai subscription authentication. Do not set `ANTHROPIC_API_KEY`, use `--bare`, or otherwise switch to API-key billing unless the user asked for that billing path. JSON output may contain an API-equivalent `total_cost_usd` telemetry field even when the authenticated account is using a Claude subscription; treat it as usage telemetry rather than proof of a separate charge.

## Model mix

Use the session's configured model by default. If a deliberate split helps, check the installed CLI and current official Claude Code model guidance, then pass `--model <supported-alias-or-id>` for that worker. Prefer a faster available model for bounded extraction and a stronger one for genuinely difficult synthesis or judgment. Model names, defaults, and account availability change; the skill should not freeze a roster. Keep effort proportional to the task.

When choosing a specific current model, adjust the worker brief only for a behavior that matters to this task:

- [Claude Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5) already uses tools and verifies more readily. Skip boilerplate that forces repeated self-checks or status updates; specify the actual completion check instead. Raise effort for hard reasoning before adding elaborate thinking prompts.
- [Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5) defaults to medium effort. Do not carry a high-effort default from an older Opus model into every worker; increase it only where the role justifies the extra latency.
- [Claude Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1) can underuse search at low effort. For evidence-heavy work, use an effort level or an explicit source-verification instruction that reliably gets the needed retrieval. Give long-running workers a clear done condition so they do not stop after a first pass.

Recheck these pages when changing the model roster. They describe current behavior, not permanent rules for every Claude model.

## Parallel execution and deadlines

Launch independent workers as concurrent shell-tool calls. Do not combine them with `&`, `wait`, heredocs, or generated shell scripts. Track each process or session separately so one timeout can be stopped without killing the others.

Choose a deadline from the task size before launch. Poll long-running calls often enough to keep the user informed. On deadline, stop the process, mark it as a dropout, and continue only if the remaining workers cover the done condition.

## Integration

For every writer, inspect the full diff and its untracked files. Compare candidates against the declared rubric. Apply the selected changes manually in the primary checkout, then rerun verification there. Do not cherry-pick opaque worker commits or trust a worker's test summary without checking it.
