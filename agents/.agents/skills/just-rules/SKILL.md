---
name: just-rules
description: "Create or update concise AGENTS.md project rules without design documents or implementation plans. Use when the user requests minimal shared project instructions."
---

# Just rules

Read the applicable instructions and inspect the actual stack, commands, layout, and conventions. Create or update a concise root AGENTS.md with only the context that changes how an agent should work in this project.

Include verified development and validation commands, non-obvious code conventions, and the user's stated preferences. Use .agents/ for shared project resources; add .agents/README.md only when there is something to index. User-wide skills and non-project memories belong in ~/.agents/skills and ~/.agents/memory respectively. Do not generate design documents, plans, or provider-specific rule files.

Do not copy a sample stack into the rules, invent design bans, force a question before each edit, limit implementation to one unit per response, or require automatic commits. Follow existing Git conventions and authorization boundaries. Briefly explain the rules added and any command that could not be verified.

## Model quirks

Astra follows instruction files closely, so keep actual requirements distinct from examples and suggestions. For Sonnet 5.5, make the requested file scope explicit to avoid extra scaffolding. See [model quirks](../claude-collab/references/model-quirks.md) when tuning these instructions.
