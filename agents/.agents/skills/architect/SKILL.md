---
name: architect
description: "Design a substantial change's interfaces and module boundaries before implementation. Use for /architect, 'architect this', or an explicit design request."
---

# Architect

Sketch the public types, signatures, caller usage, and module boundaries before implementing a substantial change. Use the sketch to expose awkward dependencies early; revise it when implementation provides contrary evidence.

## Start

Track phases when the work is long enough to need it. Keep the design proportional to the change; a small interface may need only a few signatures in the discussion.

## Phase A: Ground the problem

Read the callers, contracts, and adjacent implementation that constrain the design. Use **how** when a subsystem needs a full walkthrough. Use **why** when a historical decision affects a proposed boundary. Do not invoke either just to satisfy this phase.

## Phase B: Sketch

Write the caller's usage first, then the smallest type and module sketch that makes it work. Compare a second structural approach when ownership, state, or compatibility could reasonably go either way. Use **arena** only when independent candidates would change the choice; compare simple alternatives in one pass.

When the design adds an abstraction or changes ownership, check for shallow modules, information leakage, temporal decomposition, and pass-through methods.

Compare viable candidates on interface depth. Prefer the design that hides more complexity behind a smaller, simpler public surface. A rich interface can keep call chains short by concentrating capability instead of scattering it across layers.

Record the chosen shape and the reason for any meaningful tradeoff. A separate rationale file is useful for a large design; it is not required for a small edit.

## Phase C: Agree (opt-in)

Default: proceed directly to implementation with the chosen design. No human checkpoint.

Opt in to a checkpoint when the invoker explicitly asks: "/architect with checkpoint," "stop and show me before implementing," or similar. Then surface the design and pause for sign-off.

Use **interrogate** only when the user asks for adversarial review or the design has a concrete unresolved risk.

If the human pushes back on the shape (in a checkpoint or after the fact), treat that as new evidence. Re-ground and revise the sketch before writing more code.

## Phase D: Implement against the sketch

Implement the chosen design. The sketch is a working hypothesis, not a binding contract.

When code needs a different shape, check whether the sketch missed a constraint and update it. Tell the user about deviations that change the public contract or tradeoff.

## Phase E: Scrap when the architecture is wrong

If implementation repeatedly needs the same workaround, revisit the boundary rather than accumulating exceptions.

The signal is a *pattern*, not single instances. Tells:

- The same shape of workaround appearing repeatedly across unrelated code.
- Multiple unrelated edge cases that all need special-case branches.
- Types that need escape hatches (`any`, casts, optional fields always set in practice) to compile.
- The "we need a lock" reflex when the sketch said the state wasn't shared.
- Callers having to know the abstraction's internal rules to use it.
- Two or more independent Phase D deviations of the same shape across the implementation. Surfacing deviations is Phase D's job; a repeated pattern of them is Phase E's trigger.

Use judgment. A few edge cases don't condemn an architecture. Some problems are legitimately complex; complexity in the data is not complexity in the design. The rewrite signal is repeated friction of the same shape, not single hard cases.

When revising, use what the implementation taught you, simplify the sketch, and test the revised interface against its callers. Run another arena only if independent designs would resolve the remaining uncertainty.

## Outputs

Show caller usage and the resulting interface. For larger work, include a module map, the decision that mattered, and how implementation validated or changed the sketch.
