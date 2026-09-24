---
name: interrogate
description: "Adversarially review a specified change with independent reviewers. Use for /interrogate, 'multi-model review', or an explicit request to challenge the change."
---

# Interrogate

Use independent reviewers to challenge a code change when the requested review benefits from separate perspectives. Give them the same intent, diff, and rubric. Different models may expose different blind spots, but agreement is a lead to verify, not proof; a lone finding can still be the most serious one.

The deliverable is a synthesized verdict. Do NOT auto-apply changes.

## Step 1, Determine Scope

Identify what to review from context:

- If the user points at specific files or a diff, use that
- If on a feature branch, run `git diff main...HEAD` (or the appropriate base branch) for the full changeset
- If the user's message references recent work, gather the relevant files

Package the diff (or file contents) plus any surrounding context files the reviewers need to understand the code.

## Step 2, State the Intent

Before spawning reviewers, state the intent explicitly. What is this code trying to accomplish? Derive this from:

- The user's message
- Commit messages
- PR description if one exists
- The code itself

Write one clear paragraph. Reviewers challenge whether the work achieves the intent well. If intent is unclear, state a reasonable assumption and continue; ask only when the answer would change what should be reviewed.

## Step 3, Spawn Reviewers

Choose the smallest useful set, usually two reviewers for a focused change and more only when the change has distinct risk areas. Use the agent mechanism and model choices available in the current environment. Separate context matters more than filling a fixed roster.

Give each reviewer read-only scope and tell it not to edit files.

Read [`reviewer-prompt.md`](reviewer-prompt.md) and fill in the template with:
1. The stated intent
2. The diff or file contents
3. The review rubric from [`rubric.md`](rubric.md)
4. The code-quality lens from [`code-quality-review.md`](code-quality-review.md)

The same filled template goes to all reviewers, so every reviewer applies the code-quality lens.

Each reviewer produces structured findings as described in the prompt template.

## Step 4, Synthesize

As results come back, build a unified picture:

1. **Parse all findings** from the reviewers
2. **Check repeated findings** against the actual code. Repetition can help prioritize investigation, but does not establish correctness.
3. **Check lone findings** on their merits, especially for security and correctness.
4. **Deduplicate**. Different reviewers may describe the same issue differently. Merge these and note which reviewers raised it.
5. **Note disagreements**. If one reviewer flags something and another explicitly says the opposite, that's useful context for the verdict.

## Step 5, Lead Judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral aggregator.

Read [`lead-judgment.md`](lead-judgment.md) for the full framework. Reviewers only see a slice of the codebase. You have the full context (the goal, the constraints, the timeline, which tradeoffs were already considered). Use that context aggressively.

Categorize every finding using these buckets:

- **Act on**. Real issues affecting correctness, security, or maintainability given the actual goals. These would block a real PR.
- **Consider**. Legitimate points, but you're not sure they outweigh the cost of addressing them right now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent, premature optimization, or low-impact given the current stage.
- **Dismissed**. Wrong, nitpicky, or missing context. Brief explanation why.

For each finding, include:
- Which reviewer(s) raised it
- The category (act on / consider / noted / dismissed)
- A one-line rationale for the categorization

## Output Format

Present the verdict in this structure:

### Intent
> [The stated intent paragraph from Step 2]

### Reviewers
- Reviewer [label]: [setup used], [N findings] (one bullet per reviewer)

### Act On
[Findings that should be addressed. For each: description, which reviewers raised it, why it matters.]

### Consider
[Findings worth thinking about. For each: description, which reviewers raised it, tradeoff involved.]

### Noted
[Valid but low-priority. Brief list.]

### Dismissed
[Rejected findings with brief rationale. This shows the user what was filtered out and why, so they can override your judgment if they disagree.]

### Agreement Map
[Where did reviewers agree, where did they diverge, and what does the pattern of agreement/disagreement tell us?]
