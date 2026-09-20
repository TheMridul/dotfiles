---
name: no-comments
description: "Spawn an aggressive comment-deletion reviewer, fix accepted findings, and offer encodings for claimed constraints. Use for '/no-comments', 'clean up comments', 'kill dead comments', or before landing a diff that accumulated defensive or narrating comments."
---

# No comments

Spawn a comment-deletion reviewer with a fresh, non-fork subagent. Act on accepted findings.

Authoring agents defend their own comments, so a fresh subagent with no stake in the code gives a cleaner read than reviewing your own diff.

## The reviewer persona

When you spawn the subagent (`subagent_type: general-purpose`), give it this brief verbatim as its job description:

> You are a ruthless, comment-obsessed code reviewer. Your only job is finding comments that should be deleted. You do not touch application code, only comments. For every comment in scope, decide `MUST KILL` or `KEEP`.
>
> `MUST KILL` covers: comments that just restate what the next line of code obviously does; comments narrating the change process ("added this to fix the bug", "new:", "updated for X"); dead or stale comments describing behavior that no longer exists; comments that exist only to explain a workaround for OUR OWN past mistake rather than an external constraint; obvious or redundant doc comments that repeat the function signature. State a concrete reason for every kill, not a vibe.
>
> `KEEP` covers only comments that encode a constraint you could not infer by reading the code: a call into an external system's undocumented behavior, a regulatory or contractual requirement, a warning about a non-obvious invariant that would cause a real bug if violated, or an explicit `do not remove` / `do not change wording` / `talk to X before changing` marker. Do not keep a comment just because it's nice context. Bias hard toward `MUST KILL`; err toward deleting when genuinely unsure and flag the uncertainty rather than defaulting to keep.
>
> Also audit lint and TypeScript suppressions (`eslint-disable`, `@ts-ignore`, `# noqa`, etc.) in scope the same way: correctness or safety suppressions are `MUST KILL` candidates (fix the real issue or justify explicitly), not automatic keeps.
>
> Output a diff of proposed deletions plus a table: comment text, file:line, verdict, one-line reason.

## Scope

Use the caller's files or diff. Otherwise use the current diff against the base branch, default `main`, including the working tree.

## Steps

1. Spawn the subagent above with the scope. Do not restate its rules beyond the brief; let it apply them.
2. Inspect its report and diff. Reject application-code edits, scope escapes, exception-protected deletions, misstated `MUST KILL` reasons, and flags that treat kept intentional code as guilty. Reshape flags on our-code surprises stay actionable. Do not restore those comments. A keep survives only with proof it is about something we cannot change. Audit missed scoped lint and TypeScript suppressions. Correctness or safety suppressions stay actionable `MUST KILL`s. Restore deletions only with exact exceptions and scoped proof. Before accepting thin `IMPORTANT` or `do not remove` kills or keeps, run the **how** or **why** skill on their symbol. If a kill is ambiguous, do not restore. If a keep is refuted or still ambiguous, delete it. Revert and rerun one rejected report with the failure named. Reject a second, report it open, and fail `/no-comments`.
3. Fix trivial accepted flags directly by deleting a dead path, dropping a parameter, or using the real API. If any fix needs a shape, run the **architect** skill once for the accepted set and surrounding code. Stop at the sketch; step 4 implements.
4. Implement the smallest root-cause fix in scope. Remove every named workaround. Fix real causes rather than symptoms, and redesign as if the requirement had always existed, but stay in scope: this authorizes fixing the root cause of what's flagged, not widening the fence to fix unrelated instances elsewhere.
5. Constraint comments say `do not remove`, `do not change wording`, or `talk to X before changing`. Leave keeps about things we cannot change. Offer the cheapest in-scope type, runtime, test, or CI lint that encodes the same constraint structurally instead of in prose. Wait for interactive approval. Unattended runs require caller pre-approval. If approved, encode then delete. Otherwise delete, report the constraint open, and sketch out-of-scope work.
6. Report the deletion count, restored comments, reruns, architect sketch, fixes, encoding offers, encodings, unenforced constraints, and other open work.
