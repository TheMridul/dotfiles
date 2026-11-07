---
name: obsidian-notes
description: Produce study or reference notes as a linked set of Obsidian markdown files, for any subject. Use when the user asks for "Obsidian notes", "notes for my vault", "atomic notes", or "Zettelkasten notes", or asks to turn lecture material, a textbook chapter, a syllabus, a case, a paper, or a long document into linked notes with wikilinks. Also use when converting an existing single-file guide into a note set. Do NOT use for a single standalone document, a plain markdown report, or when the user just wants an inline answer in chat.
---

# Obsidian Notes

Produce a set of markdown files that drop straight into a vault. Deliver them as a zip of one folder, plus the index note presented separately.

Subject-agnostic. The same structure serves organic chemistry, constitutional law, macroeconomics, Mughal history, and machine learning — what changes is what counts as a worked example and what the relevance section is called.

## Two kinds of note — always produce both

A vault needs one document that **teaches** and many that **remind**. Producing only the terse notes leaves someone who has never met the material with nothing to learn from; producing only the long one leaves nothing to revise from.

| | From-scratch note | Concept notes |
|---|---|---|
| File | `01 <Topic> From Scratch.md` | one per concept |
| Count | exactly 1 | 5–12 |
| Length | 1500–2500 words | 60–120 words of prose each |
| Read | once, linearly, with a pen | repeatedly, in seconds |
| Assumes | no prior exposure | you have read it once |
| Voice | explains, motivates, derives | states, tabulates, exemplifies |

**The no-fluff rule below applies to concept notes only.** In the from-scratch note, intuition is the point: analogies, the motivating question a concept answers, why a rule is true and not just what it says, and derivations shown step by step all belong there. What stays banned everywhere is filler — reassurance, self-congratulation, and restating something already said precisely.

Structure of the from-scratch note:

1. One line on scope and how to use it, plus a link to the MOC.
2. A section-by-section time budget as a table.
3. Numbered sections in spine order, each teaching one concept: motivating question, definition, derivation or reasoning, worked example with real values.
4. A self-check section of 5–8 questions, with answers at the bottom.
5. `**Back to** [[00 <Topic> MOC]]`

It references other concepts as **plain text only**. Its sole wikilinks are to the MOC, so it costs the graph two edges.

If a from-scratch guide already exists in the conversation, adapt it rather than rewriting from nothing — strip frontmatter and H1, convert callouts to prose or tables, and add the self-check.

## Graph shape — the most important rule

**Default to hub-and-spine. Nothing else.**

- One index note (`00 <Topic> MOC.md`) links out to every other note, including the from-scratch note. That is the hub.
- Every other note links to **exactly one** note: the next one in the natural reading order. That is the spine.
- The final note in the chain links back to the MOC.

This yields about `n + 2` links for `n` notes and a graph view that reads as a wheel — legible at a glance.

**Do not** add "related concept" cross-links just because two notes mention each other. Inline conceptual references are written as **plain text**, not wikilinks. A note on the Hessian may say "the Jacobian of the gradient" without linking either word; a note on consideration may cite *Carlill* without linking it. Density kills the graph: 10 notes with incidental cross-linking produces ~40 edges and an unreadable hairball, which is the failure mode this rule exists to prevent.

Only add an off-spine link when the connection is genuinely load-bearing — the reader would be stuck without jumping. At most one or two across the whole set.

Reading order for the spine is whatever the subject dictates: dependency order for technical material, chronology for history, doctrinal development for law, pathway order for biology.

## Hard formatting rules

1. **Never put LaTeX inside a wikilink alias.** `[[Gradient|$\nabla f$ points uphill]]` renders as literal `$\nabla f$` — Obsidian does not process math in link text. Rewrite the sentence so the link text is plain words, or drop the link.
2. **No H1 heading.** Obsidian displays the filename as the title, so a leading `# Title` shows the name twice. Start the body at `##` or with content.
3. **No YAML frontmatter and no tags.** Start the file with content.
4. **No callouts** (`> [!note]`, `> [!tip]`, etc.). If something is important, state it as a numbered rule or a table row.
5. Also never put inside a wikilink alias: backticks, `|`, `#`, `^`, `[`, `]`.
6. Filenames are the note titles — human-readable, spaces allowed, no special characters. Prefix the index with `00 ` so it sorts first.

## No fluff

Notes contain definitions, statements, worked examples, tables, and the relevance section below. Nothing else. Cut on sight:

- analogies and "think of it as" framings
- motivational or reassuring asides ("this is the heart of it", "worth writing out yourself")
- restating something in words after already stating it precisely
- hedging, throat-clearing, and transitional sentences

These are recall notes for someone who has already met the material once. Prose is the exception, not the default — most lines should be a definition, a formula, a table row, a numbered rule, or a cited instance.

## Preserve relevance — this is not fluff

Cutting fluff must not cut *why the thing exists*. Almost everyone studying a topic is studying it **for** something — an exam, a clinical setting, a proof technique, a legal argument, an application area — and stripping that out makes notes harder to learn from, not leaner.

Give every concept note a short relevance section immediately before the `**Next:**` link, named for the actual domain:

| Subject | Heading |
|---|---|
| Maths for ML | `## In ML` |
| Anatomy, pharmacology | `## Clinically` |
| Law | `## In practice` |
| History, literature | `## Why it matters` |
| Pure theory | `## What it's used for` |

Rules for it:

1. **Two or three sentences, hard cap.** If it runs longer it has become fluff.
2. **Concrete and falsifiable.** Name the algorithm, the failure mode, the case, the drug, the exam question type, the design decision that depends on this.
3. **Answer "what breaks without this?"** not "isn't this interesting".
4. Forward references belong here and only here, and only when they name a specific downstream use.

Good: *"Curvature sets the largest stable learning rate. Definiteness separates minima from saddle points, which are the dominant stationary points in high-dimensional networks."*

Good: *"Decides whether a promise is enforceable at all, so it is the first question in any contract dispute. Past consideration fails this test, which is why pre-existing duty cases recur in exams."*

Bad: *"The Hessian is one of the most important tools in the field and you'll see it again later in the course."* — no mechanism, no consequence.

Carry the same idea into the index note: give its summary table a final column for what each item is used for.

## Note anatomy

```markdown
The central statement — a formula, definition, rule, or holding.

Supporting line only if the statement needs it.

## Worked

A fully carried-through instance.

## <relevance heading>

Two or three concrete sentences.

**Next:** [[Next Note]]
```

- **One concept per note.** If a note needs two `##` sections that don't depend on each other, split it.
- **Target 60–120 words of prose per note**, excluding formulas, tables, and quoted sources.
- Prefer a table to a bulleted list wherever the content has parallel structure — classification schemes, comparisons, drills, timelines, and case lists all read better as tables.

### What "worked example" means by subject

| Subject type | The example is |
|---|---|
| Maths, physics, engineering | a derivation with real numbers carried to an answer |
| Chemistry, biology | a specific reaction, pathway, or organism |
| Law | a named case with facts, holding, and ratio in one line each |
| Economics, statistics | a numeric scenario or a labelled diagram description |
| History, politics | a dated event that instantiates the concept |
| Languages, literature | a sentence or passage plus its analysis |

Every concept note gets at least one. A note with no instance is a definition, not a note.

## Math and notation

Use `$inline$` and `$$block$$` (MathJax) where the subject uses maths. For non-quantitative subjects, don't manufacture notation — cite sources, dates, and names precisely instead, and let tables carry the structure.

## The index note

A one-line scope statement, a pointer to the from-scratch note for anyone new to the material, the flat list of concept links, and one summary table if the material supports it. Nothing else.

## Delivery

1. Write files into a single folder named for the topic.
2. `zip -qr <topic>.zip <folder>` and copy the loose `.md` files to the outputs directory too.
3. Present the zip, from-scratch note, and index note with the available artifact tool or local file links. Do not assume `present_files` exists.
4. Tell the user to unzip the folder into their vault and start from the index. For an existing set, inspect and update it without discarding user edits. Do not delete an older set without authorization.

## Before presenting, verify

```bash
grep -n '\[\[[^]]*\$' *.md          # LaTeX in a wikilink alias — must be empty
grep -c '^# ' *.md                   # duplicate H1 — must be 0 for every file
grep -c '^---$' *.md                 # frontmatter — must be 0 for every file
grep -c '\[!' *.md                   # callouts — must be 0 for every file
grep -o '\[\[[^]]*\]\]' *.md | wc -l # total links — should be about (number of notes + 2)
```

Then check by hand that a from-scratch note exists, that it covers every concept note, and that every concept note has a worked instance and a relevance section. If the link count is far above `n + 2`, prune back to the spine before delivering.

## Model quirks

For Astra, the requested guide and concept set define the completion scope; do not stop after producing only the first note. For Sonnet 5.5, preserve the requested graph shape without adding extra notes. For Haiku 5.5, verify the files and links before claiming the set is complete. Derivations in the notes are teaching content, not requests for private internal reasoning. See [model quirks](../claude-collab/references/model-quirks.md) when adapting the task.
