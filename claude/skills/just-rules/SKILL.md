---
name: just-rules
description: Use when wanting minimal shared project rules without design docs or implementation plans
---

# Just Rules

Creates AGENTS.md and .agents/README.md only. No docs/, no plans, no design specs.

## Files to Create

### 1. AGENTS.md (project root)

The canonical context and rules for every coding agent. Keep under 80 lines.

Must include:

```markdown
# AGENTS.md

## Working Rules
- EXPLAIN FIRST — explain WHAT and WHY before writing code
- ONE LOGICAL UNIT — one unit of work per response, one commit per unit
- COMMIT AFTER EACH FEATURE
- ANSWER QUESTIONS — pause and explain when asked
- DRY — extract shared logic

## Code Style
- Comments explain WHY not WHAT, no JSDoc unless public API
- Use CSS variables/tokens, no arbitrary colors
- Use cn() for conditional class merging
- No inline styles, use Tailwind classes

## Git
- Format: feat: one liner description
- One logical change per commit

## Anti-Patterns (Avoid)
- Generic blue/indigo everywhere
- Same border radius on everything
- Gradient backgrounds
- Template nav bars
- Bland "Welcome to..." headings
- Default shadows on all cards

## Prefer Instead
- Asymmetric layouts, mixed border radii
- Dark mode support
- Micro-interactions, skeleton loaders
- Personality over templates
```

### 2. .agents/README.md

Create a short index for optional shared `skills/`, `references/`, and
`templates/`. Do not create `CLAUDE.md`, `codex.md`, or provider-specific
duplicate instructions.

## Rules

- AGENTS.md is the single source of project context and rules for every agent.
- `.agents/` holds reusable shared resources.
- Adapt to user's actual stack — don't assume anything
- No fluff
