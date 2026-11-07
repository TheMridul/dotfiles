---
name: explain-code
description: "Teach an unfamiliar code pattern so the user can understand and reconstruct it. Use for learning-focused code explanations; use how for a subsystem walkthrough and mentor-mode for guided learning during implementation."
---

# Explain code

Read the actual code and the relevant callers. Explain the unfamiliar concept, the problem it solves, and the non-obvious decision that shapes it. Skip syntax and concepts the user already understands.

For an interactive lesson, show a small example and ask the learner to predict its behavior. Wait for their answer, then explain the mechanism with a few meaningful conceptual steps and minimal code. Show a failure or boundary case when it helps. Finish with a teach-back or small transfer exercise that reveals understanding.

For a direct question or a requested complete explanation, answer the whole question without requiring a prediction first. Include an optional exercise at the end when useful. The teaching flow must not block a quick lookup or stop a requested full walkthrough partway through.

Distinguish behavior verified in the code from historical intent. Use a consistent analogy only when it clarifies the unfamiliar part. Cite the source locations needed to follow the explanation.

## Model quirks

Astra may turn an optional check question into a stopping point; complete a requested continuous explanation first. For Sonnet 5.5 and Haiku 5.5, make the lesson scope explicit. Show mathematical derivations, execution traces, and concise reasons as teaching content, without requesting the model's private internal reasoning. See [model quirks](../claude-collab/references/model-quirks.md).

## Interactive output in T3 Code

When an interactive visual would help, follow [T3 interactive output](../teach-me/t3-interactive.md). Preserve the lesson or plan scope and the learner checkpoints; use prose when controls add no value.
