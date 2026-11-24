---
name: assignment-code
description: "Write, fix, or finish university assignment code in the plainest constructs that meet the brief, so Mridul can understand, explain, and defend it. Use for coursework, labs, homework, problem sets, autograded submissions, or any graded programming work, including when a brief, starter code, or course PDF is attached."
---

# Assignment code

Assignment code is graded twice: once by the tests and once when Mridul explains it to a TA or in a viva. Code Mridul cannot explain line by line has failed even if every test passes. The target is correct, plain, and readable on the first pass, at the level the course has reached.

## Start from the brief

- Read the whole brief and any starter code before writing. List the required names, signatures, file names, input and output formats, and any required or banned constructs.
- Keep starter code's structure, naming style, and signatures. Fill the gaps; do not reorganise it.
- If the brief is ambiguous on something that changes the output, ask. Do not guess and build around the guess.
- Match the course level. If the course has not covered classes, recursion, generics, or a library, do not use them. When unsure, take the more basic option.

## Write it plainly

- Use direct variables, ordinary `if`/`else`, and plain `for`/`while` loops.
- One function per step, named for that step, in the order they are called.
- Name variables for what they hold: `total_marks`, not `t` or `acc`.
- Avoid lambdas, logic packed into comprehensions or streams, chained one-liners, nested ternaries, decorators, operator tricks, and design patterns unless the brief asks for them.
- No new dependencies, extra files, or helper modules unless the brief expects them.
- Comments only where a step is not obvious, written the way a student would write them.

Plain versus clever, for the same task:

```python
# Plain: what this skill wants
count = 0
for mark in marks:
    if mark >= 40:
        count = count + 1

# Clever: avoid unless the course teaches it
count = sum(1 for m in marks if m >= 40)
```

## Meet the requirements exactly

- Match required names, signatures, and output formats character for character, including spacing, capitalisation, and trailing newlines.
- Handle the cases the brief states. Do not add validation, error handling, or edge cases nobody asked for.
- Do not engineer around guessed hidden tests. Add machinery only when a real test or stated requirement fails without it, and say in the handback what was added and why.

## When fixing Mridul's code

- Make the smallest change that fixes the bug, in Mridul's style. Leave working parts alone.
- Point to the exact line that was wrong and say why, so the mistake is easier to spot next time.

## Hand it back

- Run the code on the brief's examples or the provided tests and report the actual output. If it could not be run, say so.
- Give a short plain walkthrough: what each function does and how data flows through it, short enough to repeat in a viva.
- Flag anything a TA is likely to ask about.
- Shell commands for Mridul to paste must work in fish.
- Never add AI-attribution trailers to commits or PRs for graded work.

## Per-model checks

Read only the section for the model running this skill. These are known tendencies to correct for, not extra rules.

### Claude Opus 5.5

Not in the provider notes, but seen in practice: it can over-deliver on a clear task, adding helpers, defensive checks, or a test file nobody asked for. Before handing back, delete anything the brief did not require. In unattended runs, a text-only update is not completion; check the done condition above (code runs, output reported, walkthrough written).

### Claude Sonnet 5.5

At higher effort it can add supporting files or extra review rounds beyond the task; stay inside the brief and stop after the run on the examples. At low effort it can skip verification, so the run on the brief's examples is mandatory, not optional.

### Claude Fable 5.2

No checked provider notes yet in `claude-collab/references/model-quirks.md`. Apply the Opus checks: strip unrequested extras and confirm the code was actually run.

### GPT-6.1 Sol and GPT-6.2 Sol

Validate the Astra tendencies below rather than assuming them. Watch most for heavy formatting in the walkthrough: keep it to short plain paragraphs or a flat list. 6.2 has no checked notes yet; treat it like 6.1.

### GPT-6 Astra

Can ask for approval before finishing useful work: once the brief is clear, write, run, and hand back without stopping to check in. Can follow this skill too literally where rules seem to clash; the brief wins over this skill, and this skill wins over general style habits. Formats answers heavily: keep the walkthrough plain. Can test a small fix too broadly: run the brief's examples, not a whole new test suite.

Source for the tendencies: [model quirks](../claude-collab/references/model-quirks.md). Recheck it when a model is added or updated.
