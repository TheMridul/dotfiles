---
name: existing-project
description: "Inspect an existing codebase and add missing shared project instructions when the user requests project setup or AGENTS.md. Preserve existing conventions and instructions."
---

# Existing project setup

Inspect the applicable AGENTS.md files, package manifests, scripts, configuration, callers, and recent Git history. Identify the actual stack, working commands, testing approach, file layout, and conventions before writing project instructions.

Create or update the root AGENTS.md with the non-obvious rules an agent needs. Keep commands verifiable and distinguish observed conventions from user preferences. Ask only about missing requirements that would change the setup; an audit does not need a separate approval before authorized local edits.

Use .agents/ for project resources. Add a short index only when there are resources to explain. Add docs/plan.md only when a plan is requested or the setup needs one, and describe the current scope rather than inventing features. Do not create provider-specific copies of project rules.

Describe a commit convention only when the user or project establishes it. Do not introduce automatic commits, one-response-per-feature limits, forced approval checkpoints, a new framework, or unrelated design preferences.

Check documented commands against the manifests and report what was created and what could not be verified. Finish the requested setup in the current task.

## Model quirks

Astra is sensitive to inherited instructions, so remove conflicting workflow rules rather than adding another approval gate. Sonnet 5.5 can add supporting files beyond the requested change; create only the setup artifacts needed here. See [model quirks](../claude-collab/references/model-quirks.md) when adapting a worker brief.
