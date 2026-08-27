---
name: new-project
description: Use when starting a brand new project from scratch and needing project structure, rules, and documentation files generated
---

# New Project Setup

Scaffolds AGENTS.md, .agents/, docs/design.md, and docs/plan.md for a new project.

## Required Inputs

Ask the user for:
1. **Project description** — what it does in 1-2 sentences
2. **Tech stack** — frameworks, libraries, tools
3. **Package manager** — default to pnpm if unspecified

## Files to Create

### 1. AGENTS.md (project root)

The canonical context for every coding agent. Keep under 100 lines.

Must include:
- Working rules (explain first, one logical unit per response, commit after each feature, answer questions, DRY)
- Code style (TypeScript, comments explain WHY not WHAT, no JSDoc unless public API, CSS variables, cn())
- Testing approach (adapt to user's stack — Vitest, Jest, etc.)
- File organization (generate from tech stack)
- Git conventions (conventional commits, one change per commit)
- Anti-patterns (generic blue/indigo, same radius everywhere, gradients, template nav)
- Preferences (asymmetric layouts, mixed radii, dark mode, micro-interactions)
- A statement that `.agents/` holds shared reusable resources

### 2. .agents/README.md

Create a short index for shared agent resources:

- `skills/<name>/SKILL.md` for reusable workflows
- `references/` for task-specific supporting material
- `templates/` for reusable output assets

Only create additional resources when the project needs them. Do not create
`CLAUDE.md`, `codex.md`, or provider-specific duplicate instructions.

### 3. docs/design.md

Ask user about design vision, then document:
- Layout architecture
- Color scheme (CSS variables, light/dark)
- Typography scale
- Component inventory
- Interaction states (hover, active, focus, disabled, loading)

### 4. docs/plan.md

Phased implementation with checkboxes. Commit sequence: one commit per checkbox.

## Rules

- AGENTS.md is the single source of project context and rules for every agent.
- `.agents/` contains optional shared resources; do not duplicate them in agent-specific directories.
- Adapt testing, file org, and commands to the actual tech stack — don't assume React/Express
- No fluff, no filler paragraphs
- Keep both files concise
