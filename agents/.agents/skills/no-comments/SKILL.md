---
name: no-comments
description: "Review comments in a specified diff or files and remove stale or redundant ones. Use for /no-comments or an explicit comment cleanup request."
---

# No comments

Review comments in the requested files or diff. Keep comments that explain a non-obvious invariant, external constraint, surprising behavior, or public contract. Remove comments that merely narrate nearby code, record obsolete history, or repeat a signature.

Inspect lint and type suppressions separately. A suppression may encode a real limitation; verify its reason before changing it. If a comment points to a code defect, fix the defect only when it is within the user's requested scope. Otherwise report the issue and leave the code intact.

A direct review is enough for an ordinary diff. Use an independent reviewer when the comment set is large or the author needs a separate judgment. Judge each suggestion against current code rather than accepting an aggressive deletion verdict by default.

Run the relevant checks after code changes. Report the meaningful deletions, comments kept for a reason, and any open constraint that could be encoded in code or tests. Do not require a separate approval for local, reversible fixes already covered by the user's request.
