---
name: how
description: "Explain how a codebase subsystem works, including its runtime flow and ownership. Use when the user asks for a walkthrough or where a responsibility belongs."
---

# How

Trace the relevant code from entry point to effect, including the data passed between components. Explain only the concepts and files needed to answer the question. Cite current files and line numbers for claims about behavior.

For a narrow question, read and explain directly. For a broad subsystem, split independent areas among agents only when separate exploration will save time or isolate substantial context. Synthesize their findings yourself and resolve conflicts against the code. Do not require an agent just to write the explanation.

Use [explorer-prompt.md](explorer-prompt.md) for a large delegated trace and [explainer-prompt.md](explainer-prompt.md) when its format helps. Neither is a required preflight.

Lead with the answer. Then show the path through the code, the relevant owners or modules, and any non-obvious constraints. Adapt detail to the user's question; a single function does not need a subsystem map.

## Architecture critique

When the user asks for architectural problems or placement advice, trace the current behavior first. Identify concrete problems, affected callers, and a feasible improvement. Use [critique-rubric.md](critique-rubric.md) to check a broad critique. Independent reviewers can help when several plausible boundaries need comparison; they are not a default step.

Distinguish observed behavior from a proposed change. Use **why** only when historical motivation matters to the recommendation.
