---
name: arena
description: "Compare independent candidates for the same substantial artifact, then synthesize and verify the best result. Use for /arena or an explicit request for competing approaches."
---

# Arena

Fan out N parallel attempts at the same task. Read every candidate end to end. Pick the strongest as the base. Graft the best ideas from the others into it. Verify the synthesized result.

## Start

Track phases when the task is long enough to need it.

1. Frame
2. Fan out
3. Cross-judge
4. Pick
5. Graft
6. Verify

## Phase A: Frame

The N candidates will receive the same prompt, so the prompt is the contract. Get it right before spawning anything.

1. State the artifact each candidate is producing.
2. Derive the rubric. State what success looks like for *this* task, then turn it into 3-6 concrete gradeable criteria. Concrete: `Adds a --dry-run flag that skips writes`. Vague: `code is correct`. The rubric is the picker's tool in Phase D; candidates only see the task.
3. Pick the runners. If more than one model or agent type is available to you, spread candidates across them; different perspectives catch different problems. Otherwise run N candidates on the same subagent with independent context. Spawn more runners when the arena covers multiple design directions. Same setup N times is fine when the work is generation-bound rather than judgment-sensitive.
4. Assign output paths. Each candidate writes to its own location (a git worktree where possible, otherwise a per-candidate scratch subdirectory). N candidates writing to the same path is shared mutable state and will corrupt each other's output.

## Phase B: Fan out

Launch independent workers with the agent mechanism available in the current environment. Give each the task, shared grounding, its own output path, and instructions to produce the artifact and a short rationale. Keep concurrent writes isolated.

The rationale is mandatory. Without it, you cannot tell whether a candidate's structure is principled or accidental, which makes Phase E grafting unreliable. Each rationale names the alternatives the candidate considered and what it rejected.

If a candidate fails to produce output, proceed with N-1 and note the dropout in the synthesis record.

## Phase C: Cross-judge

After all candidates complete, use an independent judge when the choice is consequential or close. Give it the rubric and complete candidates, and ask it to recommend a base with reasons. Do not judge partial outputs.

## Phase D: Pick a base

Read every candidate end to end before picking. Skimming N candidates surfaces only the candidate whose surface looks most familiar.

Score each candidate against the rubric criterion by criterion. If an independent judge disagrees, inspect the evidence and decide; agreement alone does not prove correctness.

Pick the base on which candidate a future maintainer can extend most easily without breaking invariants. Prefer the cleaner boundary or smaller surface area when two feel tied.

Record the pick and the reason in a short synthesis note alongside the artifact, including any judge's verdict.

## Phase E: Graft

Walk each losing candidate once more and identify what is worth porting into the base. The signal is usually one or two things per candidate, not most of it.

Fold each graft in by hand, redesigning the affected piece rather than pasting mechanically. The result has to remain coherent under one mental model.

Record what was grafted, from which candidate, and what was rejected and why. The rejection notes are the highest-signal part of the record. Future readers learn from what you considered and dropped, not just what you kept.

When N candidates converge on the same shape, that is a strong agreement signal. Note the convergence in the record and ship the consensus shape. No graft is needed. When N candidates wildly diverge, Phase A was under-specified. Reframe and re-run rather than averaging the divergence.

## Phase F: Verify

The synthesized artifact has to hold up under the same scrutiny as any other output. Actually run it, test it, or otherwise prove it works; the arena does not earn you a pass.

If verification surfaces a problem the arena did not catch, either Phase A was wrong (re-frame and re-run) or one candidate caught it and you missed the graft (go back to Phase E). Don't paper over.

## Outputs

One synthesized artifact. One short synthesis note alongside, naming the base, the grafts (with source candidate), the rejections, the dropouts if any, and the verification result.
