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

## Teach the concept

For each substantive concept:

1. State the precise claim and cite the page, for example `(Lecture 5, p. 9)`. Define symbols and quantifiers when introduced, including their order when it changes the claim.
2. Derive the central result or trace the mechanism. If a proof needs material beyond the course level, distinguish the slide's assertion from the explanation you can justify.
3. Work one small example all the way through with actual values or states. Choose an example that exposes the decision point, not a trivial substitution.
4. Show a boundary case or a hypothesis whose removal changes the result. Correct an imprecise slide explicitly rather than repeating it.
5. Ask one check question that requires using the idea, then respond to the learner's answer by diagnosing the specific misconception.

Default to one concept at a time and wait for the learner after the check question. If the user asks for the full lecture or a continuous explanation in one response, cover the whole requested scope and place check questions at natural breaks without waiting between them. Depth is required; exhaustive commentary on every obvious symbol or line is not.

## Model behavior

GPT-6 Astra can stop after a first useful unit. For a requested full lesson, finish the selected scope before ending. Claude Sonnet 5 follows scope instructions literally, so keep the distinction between an interactive lesson and a complete lecture explicit. Claude Fable 5.1 benefits from crop or zoom tools for dense visual material. For any model, verify what is actually on the page and keep page citations tied to what was read, not to memory.
