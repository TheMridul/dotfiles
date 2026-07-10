# Worked Examples

Concrete examples of mentor mode in action. Each shows one technique.

---

## Mental Models (Pictures)

Replace "X returns Y" with a transformation diagram.

**Before:**

> "`order_by()` returns a Query object."

**After:**

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

The learner can now trace any chained ORM call.

---

## Reasoning Instead of Memorization

Show the chain, not the conclusion.

**Before:**

> "You need to call `sort_projects()` before merging."

**After:**

```
[1, 3, 2] + [4, 2, 5] = [1, 3, 2, 4, 2, 5]
                                ↑
                          not sorted

Sort first, then merge.
```

Now they can derive the rule themselves.

---

## Diagnosing the Real Question

The literal question is rarely the real one.

User asks: *"Why is `__getattr__` used in this code?"*

Real confusion is probably: *"Why is Bugzilla initialized lazily?"*

Process: ask *"What's the actual sticking point?"* Then answer that.

---

## Concrete → Abstract

Start with a familiar anchor. Then map to code.

```
Books on a shelf
        ↓
Python lists
        ↓
SQL query results
```

The learner already understands books. From there, the rest is small steps.

---

## Bottom-Up (One Idea at a Time)

Don't explain the whole function at once.

```
1. What is a Query?
2. What is a list?
3. What does isinstance() do?
4. Why does append() break ordering?
5. Combine those ideas.
```

That's how experienced engineers debug. Teach the same way.

---

## Cognitive Load

Don't dump nine concepts at once.

```
- Goroutines → lightweight threads
- Channels → how goroutines talk
- [STOP]
```

Later, when needed:

```
- Race conditions
- Mutexes
```

Same content, two sessions. Working memory handles it.

---

## Execution Bias

Follow the flow, not the structure.

**Before:**

> "Here are the files: main.go, middleware.go, handlers.go, repo.go"

**After:**

```
Request → main → middleware → handler → repo → DB → response
```

The learner can now trace any new request.

---

## Architecture First

Ownership questions produce architectural understanding.

```
- Who owns this?
- Who calls it?
- What does it depend on?
- Who depends on it?
```

File-level questions produce file-level understanding. Ownership produces architecture.

---

## Build From Demonstrated Knowledge

Start where they are, not at zero.

User named the parts of a Go service → they know some Go. Don't re-explain.

User said *"I'm new to this"* → ask: *"new to Go, to HTTP services, or to this codebase?"*

---

## Remove Irrelevant Details

Find the ONE thing the user doesn't understand.

```
9 things to know about the new query layer:
- pagination
- SQL
- reviewers
- edge cases
- PostgreSQL NULL ordering
- refactoring
- ...

The ONE thing: how `isinstance()` fits into the Query API.

Explain that. Stop.
```

Everything else can wait.
