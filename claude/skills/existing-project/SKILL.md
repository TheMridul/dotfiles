---
name: existing-project
description: Use when adding shared project context and rules to an existing codebase that has no AGENTS.md
---

# Existing Project Setup

Audits an existing codebase and scaffolds AGENTS.md, .agents/, and docs/plan.md.

## Process

### Step 1: Audit

Read the codebase before writing anything:
- What frameworks, libraries, tools are in use (check package.json, config files)
- What commands exist (check scripts in package.json)
- What file organization exists (ls the directory tree)
- What testing is set up (test config, existing test files)
- What patterns are already used (naming, state management, styling)
- What's broken or missing (failing tests, TODO comments, missing configs)

### Step 2: Ask

Confirm with the user:
1. Is the audit accurate? Anything I missed?
2. Any working rules they want enforced?
3. Any design preferences?

### Step 3: Create Files

#### AGENTS.md (project root)

The canonical project context and conventions, based on patterns found in the codebase. Keep under 100 lines.

Must include:
- Working rules (explain first, one logical unit per response, commit after each feature, answer questions, DRY)
- Code style (from existing patterns — don't invent new conventions)
- Testing approach (from what's already set up)
- File organization (map what actually exists)
- Git conventions (from commit history patterns)
- Anti-patterns and preferences

#### .agents/README.md

Create a short index for shared agent skills, references, and templates. Do not
create `CLAUDE.md`, `codex.md`, or provider-specific duplicate instructions.

#### docs/plan.md

- What's broken (from audit)
- What's missing (from audit)
- Phased plan with checkboxes

## Rules

- Audit first, write second. Never guess.
- AGENTS.md is the single source of project context and rules for every agent.
- Use `.agents/` only for reusable shared resources.
- Respect existing conventions — don't force new patterns on an established codebase
- No fluff
