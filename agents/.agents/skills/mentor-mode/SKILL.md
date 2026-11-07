---
name: mentor-mode
description: Teach unfamiliar concepts or implementation patterns when the user wants guided learning. Use for mentor-mode or learning during implementation; answer quick lookups directly.
---

# Mentor Mode

Teach for reconstruction, not memorization.

After your explanation the learner should be able to:

- explain **why** the concept exists
- recognize it elsewhere
- rebuild it from first principles
- reason about tradeoffs

## Reference Mode vs Mentor Mode

These are different goals:

- **Reference mode** answers your current question.
- **Mentor mode** reduces the number of future questions you'll have.

**Trade-off:** Mentor mode optimizes for understanding, not lookup. If the learner just needs a quick answer to a specific question ("What does `async_get_batch()` return on a partial cache miss?"), reference mode is faster. Mentor mode is for building the mental model that lets them answer those questions themselves by navigating unfamiliar code.

When to switch into mentor mode: you're no longer blocked by syntax, you're blocked by understanding. Common signals — rereading the same file without new insight, asking "why does this exist?" rather than "what does this line do?", can follow the code but not the architecture.

## The Progression

Use these questions to find the missing concept. In an interactive lesson, pause for the learner at a useful exercise. For a requested complete explanation, cover the selected scope in one response:

1. **What is this?** Identify the object using a familiar anchor. *Books on a shelf, not "an array."*
2. **What does it do?** Behavior, not implementation.
3. **Why is it written this way?** The intent behind the design.
4. **What problem does it solve?** The pain that motivated it.
5. **How does that relate to your situation?** Connect to their actual code or bug.

## Mentor Mode in Action

### Mental Models as Pictures

Instead of saying "`order_by()` returns a Query object":

```
Query
  ↓
order_by()
  ↓
Query
  ↓
all()
  ↓
List
```

Each arrow is a transformation. The learner now has a model they can reuse in any ORM.

### Reasoning Instead of Memorization

Instead of "you need to call `sort_projects()`":

```
[1, 3, 2]
+
[4, 2, 5]
=
[1, 3, 2, 4, 2, 5]
        ↑
    not sorted

Sort first, then merge.
```

Once they see the derivation, they don't need the rule.

### Diagnosing the Real Question

The literal question is rarely the real one.

User asks: *"Why is `__getattr__` used here?"*

Real confusion is probably: *"Why is Bugzilla initialized lazily?"*

Explain how `__getattr__` supports lazy initialization in this code. Ask about the learning goal only if the answer would change the explanation; do not substitute a guessed question for the one asked.

## Reference

For more worked examples, see [examples.md](./examples.md).

## Model quirks

For Astra, keep interactive checkpoints from cutting short a requested full explanation. For Claude 5.5, ask for a worked example, derivation, or concise rationale as teaching content rather than private internal reasoning. Use [model quirks](../claude-collab/references/model-quirks.md) only when adapting the prompt.

## Interactive output in T3 Code

When an interactive visual would help, follow [T3 interactive output](../teach-me/t3-interactive.md). Preserve the lesson or plan scope and the learner checkpoints; use prose when controls add no value.
