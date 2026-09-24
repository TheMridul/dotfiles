---
name: swarm
description: "Coordinate independent workers on explicit parallel coverage, then return one report. Use for /swarm or 'swarm this'. Use arena for competing candidates."
---

# Swarm

Fan out workers across independent slices, then aggregate one report. Use **arena** when workers should solve the same task and their artifacts need comparison or synthesis.

## Start

Track phases when the task is long enough to need it.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Partition the task into independent slices with minimal overlap.
3. Set N from the user or derive it from the shape. N is total workers, not any concurrency limit your environment imposes.
4. Pick the worker setup that fits each slice. Use different models only when their strengths match different parts of the task.
5. Give each worker its own writable output when it writes. Use a worktree, branch, or a per-worker scratch subdirectory.

## Phase B: Fan out

Launch workers with the agent mechanism available in the current environment, up to its concurrency limit. Keep briefs independent and writes isolated.

Every brief stands alone. Include the goal, scope, exact slice, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Every required slice needs a result. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, and gaps or dropouts.
