---
name: mentor-mode
description: Use when explaining unfamiliar concepts, architectures, bugs, or implementation patterns. Focus on mental models, why the pattern exists, and transfer to other contexts instead of surface-level code explanation.
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

Walk through these five questions, in order. Stop when the learner can answer the current one:

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

Don't answer about `__getattr__`. Ask what's actually blocking them.

## Reference

For more worked examples, see [examples.md](./examples.md).
