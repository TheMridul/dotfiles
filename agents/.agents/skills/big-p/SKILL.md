---
name: big-p
description: "Research a recommendation, comparison, plan, or factual question when current evidence or missing context could change the answer. Use for /big-p. Skip routine coding, stable facts, and requests already answered by the supplied material."
---

# Big preparation

Resolve the context that matters, verify claims that need evidence, and answer the actual question. Preserve the user's requested scope and level of detail.

## Context

Use information already supplied and inspect available sources before asking. Ask only for missing information that would materially change the result, such as a purchase budget, travel dates, or jurisdiction. Bundle related questions and continue independent research while waiting. When a reasonable assumption is sufficient, state it and proceed. Do not impose a minimum question count or require an approval of the research plan.

## Evidence

Search current primary sources for changing facts such as prices, versions, rules, schedules, and availability. Read the supporting page before citing it. Stable facts and facts established by supplied material do not need a web search merely to satisfy this skill. If search is unavailable, distinguish what the supplied sources establish from what remains unverified.

Compare options against the user's constraints. Use code or a calculator for consequential arithmetic and keep units, dates, and currencies explicit. Separate sourced claims, assumptions, and recommendations. Do not claim that an unsuccessful search proves something does not exist.

## Finish

Give the answer or recommendation first, followed by the evidence and tradeoffs that affect the decision. Cite the sources near the claims they support. Complete the requested research and stop; publication, purchases, or messages require their own authorization.

## Model quirks

For Haiku 5.5, include the current date and explicitly request retrieval for changing facts, especially with a long prompt or low effort. Sonnet 5.5 can also answer changing questions from training knowledge; check the relevant source. For Astra, avoid turning optional context questions into a reason to stop useful work. Apply only the relevant note in [model quirks](../claude-collab/references/model-quirks.md).
