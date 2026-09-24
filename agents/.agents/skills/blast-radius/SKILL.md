---
name: blast-radius
description: "Check what a specific code change might break beyond its diff. Use when asked for blast radius, downstream risk, or a focused safety review."
---

# Blast radius

Trace the changed behavior through callers, data formats, timing, and external contracts. Look beyond direct symbol references when the change affects serialized data, framework lifecycle, shared state, or a dependency.

Identify the safety assumption each material risk depends on. Check it against current code and the pinned dependency. Run a focused test or reproduction when it can settle a consequential uncertainty at reasonable cost; otherwise mark the assumption unproven. Do not create a test that only repeats the implementation.

Report confirmed risks, important cleared risks, and unresolved assumptions with file and line evidence. Give the likely impact and the cheapest useful check before shipping. Keep the report proportional to the diff.

Use **how** if the affected subsystem needs a walkthrough and **why** if an old decision constrains the change. For a wide change, independent review passes can help when different areas can be examined separately; do not require an arena for size alone.
