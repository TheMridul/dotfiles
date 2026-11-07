---
name: teach-me
description: "Teach a CS or math lecture from a PDF in Mridul's coursework. Read the relevant pages, explain the reasoning in depth, work an example, and check understanding."
---

# Teach from slides

Teach the requested concept or lecture, using the deck for scope, notation, and page references. Mridul wants the reasoning, not a paraphrase of slides. Apply the unslop writing guidance when that skill is available; otherwise use plain, direct prose. No particular skill invocation tool is required.

## Find and read the deck

In a local workspace, find the actual PDF under the named course in `~/Projects`. Paths and filenames change; do not rely on remembered examples. Quote paths containing spaces or parentheses. In Claude on the web, use the PDF attached to the conversation or available through an authorized file connection. If the deck is unavailable there, ask for it; a remembered lecture is not a substitute.

When the local helper is available, use `~/.agents/skills/teach-me/slides.sh probe "<pdf>"` to inspect page text and images. For `TEXT` pages, use `slides.sh text`. For `RENDER` and `CHECK` pages, render and inspect the page image. In a web session without the helper, use the available PDF page viewer or file tools. Inspect pages visually when a diagram, graph, handwritten proof, or spatial layout carries the idea even if extracted text looks usable. If symbols or arrows are too small, render at higher DPI or crop and enlarge the relevant region with an available image tool. Never infer a diagram from its extracted words.

Read the whole requested section before teaching its first concept. If the user requests a whole lecture, survey the deck first so a later page cannot silently change an earlier definition. Do not read unrelated lectures merely because they are nearby.

Useful commands, from `~/Projects`:

```text
~/.agents/skills/teach-me/slides.sh probe "OS/Notes/lec05_process.pdf"
~/.agents/skills/teach-me/slides.sh text "OS/Notes/lec05_process.pdf" 3 7
~/.agents/skills/teach-me/slides.sh render "Math3/Note13Aug2026(3).pdf" 4 4 200
```

The helper prints page-marked text or paths to rendered images. `find` searches a real text layer; an empty result on handwriting does not mean the topic is absent.

PowerPoint-exported decks, the OS ones included, can carry text from hidden animation builds in a page's text layer. In OS `lec09_semaphores.pdf`, p. 7 extracts with `sem_wait` and `sem_post`, which appear only on p. 19. Treat `CHECK` as mandatory and read the rendered page before teaching code from it.

## Teach the concept

For each substantive concept:

1. State the precise claim and cite the page, for example `(Lecture 5, p. 9)`. Define symbols and quantifiers when introduced, including their order when it changes the claim.
2. Derive the central result or trace the mechanism. If a proof needs material beyond the course level, distinguish the slide's assertion from the explanation you can justify.
3. Work one small example all the way through with actual values or states. Choose an example that exposes the decision point, not a trivial substitution.
4. Show a boundary case or a hypothesis whose removal changes the result. Correct an imprecise slide explicitly rather than repeating it.
5. Ask one check question that requires using the idea, then respond to the learner's answer by diagnosing the specific misconception.

Default to one concept at a time and wait for the learner after the check question. If the user asks for the full lecture or a continuous explanation in one response, cover the whole requested scope and place check questions at natural breaks without waiting between them. Depth is required; exhaustive commentary on every obvious symbol or line is not.

Stay anchored to the deck: cover every slide, and cut what no slide raises, such as beyond-course derivations, modern-hardware asides and speculative gotchas. Mridul often revises against the rendered slides right before a quiz, so padding costs him time and off-deck claims get caught.

## Model quirks

For Astra, finish a requested full lesson before ending at a check question. For Sonnet 5.5 and Opus 5.5, use crop or zoom tools when dense charts or drawings need them. For Haiku 5.5, keep the selected page scope and completion condition explicit. Mathematical derivations and execution traces are teaching content; do not request private internal reasoning. Verify each page claim against the deck. See [model quirks](../claude-collab/references/model-quirks.md) when adapting the lesson.

## Interactive output in T3 Code

When an interactive visual would help, follow [T3 interactive output](t3-interactive.md). Preserve the lesson or plan scope and the learner checkpoints; use prose when controls add no value.
