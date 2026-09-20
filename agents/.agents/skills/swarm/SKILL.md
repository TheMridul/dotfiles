---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for /swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
---

# Swarm

Fan out N parallel workers. They may cover separate slices, race the same brief, or mix both. You wait, aggregate, and return one report.

## Start

Open a todolist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Set N from the user or derive it from the shape. N is total workers, not any concurrency limit your environment imposes.
4. Pick the worker setup. If you have access to more than one model or agent type, spread workers across them; diversity of perspective helps for exploration and races. Otherwise run N workers on whatever subagent you have. For a race across genuinely different perspectives, name each arm's model/agent up front.
5. Give each worker its own writable output when it writes. Use a worktree, branch, or a per-worker scratch subdirectory.

## Phase B: Fan out

Spawn all N workers in one message, each as a fresh, non-fork subagent (`subagent_type: general-purpose`), running in the background where your tooling supports it, with the setup chosen in Phase A.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.
