---
name: visual-plan
description: "Turn an existing multi-step plan into a readable visual document. Use when the user asks to see a plan visually or invokes /visual-plan."
---

# Visual plan

Use the current plan as the source. Preserve its decisions, order, dependencies, and uncertainty. If no plan exists, ask what should be visualized.

Choose the smallest useful format: a concise Markdown document for phases and checklists, a Mermaid diagram for meaningful branches or dependencies, or a richer artifact when the available tools support one and its interaction adds value. Avoid duplicating a simple plan in a decorative format.

Save a standalone file when the user wants something to keep or share, and link it in the response. If an Artifact or publishing tool is unavailable, give the visual directly in chat or as a local file. Do not assume a particular tool, scratchpad directory, or deployment flow exists.

Publishing to an external service is an outward action. Prepare the complete visual for review and follow the applicable authorization rules before publishing. Local rendering needs no extra approval.
