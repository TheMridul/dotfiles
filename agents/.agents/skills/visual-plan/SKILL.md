---
name: visual-plan
description: >
  Render the current plan (from Plan Mode, or any multi-step plan just discussed)
  as a visually formatted, published Artifact instead of plain terminal text.
  Use when the user says "visual-plan", "show me the plan visually", "make this
  plan visual", "I want to see the plan", or asks for the plan in MDX/a nicer
  format for easy visibility. Triggers right after a plan is drafted in Plan
  Mode, before or after ExitPlanMode approval.
---

# visual-plan

Turn a plan into a published, readable Artifact — a real visual document
(headers, checklists, step ordering, risk callouts, optionally a dependency
diagram) instead of a wall of terminal markdown.

This does not change what Plan Mode itself shows for approval — `ExitPlanMode`
still needs the plain-text plan for the approval flow. This skill runs
alongside it: same plan content, rendered a second way for visibility.

## When to run this

- The user explicitly invokes `/visual-plan`.
- The user asks to see a plan "visually," "as MDX," "nicer," or similar,
  right after a plan was drafted (in Plan Mode or otherwise).
- Proactively offer it once a plan mode plan is ready, if the plan is long
  or has many steps/phases — but don't publish without the user asking or
  agreeing, since publishing is an outward action.

## Steps

1. **Load `artifact-design`** (required before writing any artifact — do
   this first, it calibrates how much visual structure this plan warrants).
2. **Take the plan content as-is.** Don't invent steps or re-plan — this is
   a rendering pass over the plan you (or the user) already have, not a new
   planning pass. If no plan exists yet in the conversation, ask what to
   visualize instead of fabricating one.
3. **Structure it for visual scanning**, not just reflowed prose:
   - A short title + one-line scope statement at the top.
   - Numbered phases/steps as real sections, not one long list, when the
     plan has distinct phases.
   - Checkboxes (`- [ ]`) for concrete action items.
   - Callouts for risks, open questions, or things needing the user's
     decision — visually distinct from the steps themselves (blockquote or
     a styled aside if using HTML).
   - If steps have real dependencies or a non-linear flow, add a Mermaid
     diagram (`artifact-diagramming` skill) showing the sequence/branches —
     only if it earns its place, not by default for a simple linear list.
4. **Write the file** to the scratchpad directory as `plan.md` (Markdown is
   almost always the right call here — plans are structured prose, not an
   interactive app; only reach for HTML if the plan genuinely needs custom
   layout artifact-design would call for).
5. **Publish via the `Artifact` tool** — pick a specific, short title (the
   plan's actual subject, e.g. "Auth Middleware Rollout," not "Project Plan"),
   a one-sentence `description`, and a favicon emoji that fits the subject.
   Artifacts start private — that's fine, no need to ask permission to
   publish your own draft plan.
6. **Hand back the link** with a one-line summary of what's in it. Don't
   restate the whole plan in chat text — the artifact is the point.

## Updating

If the plan changes (user requests edits, new steps), re-render and call
`Artifact` again on the **same `file_path`** to redeploy to the same URL
rather than creating a new one, unless the user is asking for a visualization
of a materially different plan.

## Notes

- This skill has no opinion on *whether* to enter or exit Plan Mode — that's
  governed by the harness's own Plan Mode flow. It only affects how the plan
  is presented once it exists.
- Keep the rendered plan honest: if a step is uncertain or a risk is real,
  say so in the artifact rather than smoothing it into confident prose.
