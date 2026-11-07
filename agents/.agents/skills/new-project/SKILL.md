---
name: new-project
description: "Set up shared project instructions and the requested initial structure for a new project. Use when the user asks for new-project scaffolding, AGENTS.md, or initial design and planning documents."
---

# New project setup

Use the project description, stack, package manager, and constraints already provided. Ask for a missing choice only when it materially changes the scaffold and cannot reasonably be inferred. Avoid imposing a framework or package manager from an example.

Create a concise root AGENTS.md with the actual development commands, code conventions, validation approach, and project layout. Include user preferences only when established. Do not add automatic commits, per-response work limits, or mandatory approval pauses.

Keep shared resources in the project's .agents/. Create its index and supporting files only when useful. User-wide skills belong in ~/.agents/skills and non-project memories in ~/.agents/memory. Project memories belong in the project's .agents/memory. Do not create provider-specific instruction files.

When the user requests design or planning documents, write docs/design.md and docs/plan.md at the depth the project needs. Derive design choices from the brief and existing assets. Keep the plan actionable, with completion checks; a checkbox does not authorize a commit or deployment.

Carry the authorized scaffold through to a reviewable result. Run the relevant generated command, build, or configuration check where available and report any real limitation. Ask before outward actions under the applicable AGENTS.md rules.

## Model quirks

For Astra, treat a request to set up the project as authorization to prepare the local scaffold. For Sonnet 5.5, stop after the requested scaffold and its checks instead of adding related features. For Haiku 5.5, give the scaffold a concrete done condition and verification command. See [model quirks](../claude-collab/references/model-quirks.md).
