---
name: why
description: "Investigate why a code or product decision was made, using history and relevant records. Use for design rationale, regressions, postmortems, or unexplained thresholds. Use how for runtime behavior."
---

# Why

Find evidence for the motivation behind a decision. Start with the code and history that introduced or changed it. Follow linked PRs, issues, documents, incidents, or conversations when they are available and relevant. A source's existence does not make it relevant to every question.

Separate direct evidence from inference. Code shows what happens; it rarely proves why its author chose that behavior. Cite a commit, PR, issue, document, comment, or other specific record for a claim about intent. If the record does not say, state the best-supported inference and the uncertainty.

## Investigation

1. Identify the current code, date range, and decision being explained. Trace the relevant commits or PRs. Check whether a later change superseded the original rationale.
2. Search additional sources according to the question and leads found. Tickets and design documents help with product or architecture choices; incidents and observability help with runtime failures; analytics can support numerical thresholds. Search chat when a linked discussion or missing written rationale makes it likely to help.
3. Stop when the answer has enough direct support, or when the remaining sources are unlikely to change it. Do not launch one investigator per available tool or search every category by default. Use independent agents only when several substantial evidence paths can run in parallel.
4. Spot-check citations and report meaningful gaps. A search that found nothing is a gap, not proof that no rationale existed.

## Answer

Lead with the most supported explanation and cite it. Then distinguish what the record explicitly says, what you infer, and what remains unknown. Include competing explanations only when the evidence really supports more than one. For a change request, turn discovered constraints into a short list of what the implementation must preserve.
