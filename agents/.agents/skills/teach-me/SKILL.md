---
name: teach-me
description: "Teach a CS or math concept from lecture slide PDFs (DM, IML, OS, Math3, DSA). Use when asked to teach, explain, or go through a lecture, deck, topic, or slide, to prep for an exam or quiz, or to make sense of a PDF of notes. Reads the deck page by page, renders handwritten and scanned pages as images, and teaches to full depth with worked examples and check questions."
---

# Teach from slides

Teaching from a deck, not summarizing one. The deck is the source of truth for
scope and notation. Everything else in this file is about depth.

Decks live in `~/Projects/<course>/`: `DM`, `Math3`, `OS`, `IML/Notes`, `DSA`.

## Step 0: load unslop

`Skill(skill="unslop")`, before reading anything. Its rules govern every word of
the lesson. See [prose style](#prose-style) for the patterns that matter most
here.

## Step 1: read the deck correctly

Never guess a deck's format. Probe it first:

```bash
~/.agents/skills/teach-me/slides.sh probe "OS/lec05_process.pdf"
```

It prints per page: character count, embedded image count, and a verdict.

| Verdict | What to do |
|---|---|
| `TEXT` | `slides.sh text <pdf> <first> <last>` |
| `RENDER` | `slides.sh render <pdf> <first> <last>`, then `Read` each PNG |
| `CHECK` | Render and read the image. Treat any extracted text as a hint only |

Subcommands:

```bash
slides.sh text   "OS/lec05_process.pdf" 3 7        # page-marked text
slides.sh render "DM/Lecture 2.pdf" 1 6            # PNGs, prints paths, Read them
slides.sh find   "OS/lec07_forkexec.pdf" 'fork'    # which pages mention it
```

Render before teaching whenever the concept is carried by a picture: a memory
layout, a state diagram, a decision boundary, a stack frame. The text layer of
a PowerPoint deck gives you the words on the slide and none of the arrows.

Read the whole deck, or the whole section, before saying anything. A definition
on page 4 is usually sharpened on page 9, and teaching page 4 alone teaches the
wrong thing.

## Step 2: teach it properly

Mridul asked for depth and precision, and specifically asked that no topic be
treated lightly. That is a hard constraint, not a preference. The rules below
are the constraint made concrete.

**Never hand back a summary.** Restating the slide in different words is not
teaching. If your paragraph would still be true with the concept's name swapped
out, delete it.

**Every symbol gets named.** In `f(n) = O(g(n))`, say what `n` ranges over, that
`c` and `n₀` are existentially quantified, that the order is `∃c ∃n₀ ∀n ≥ n₀`,
and that swapping the quantifiers gives a different and weaker statement. Order
of quantifiers is where most of the content lives. Say it out loud every time.

**Derive, do not assert.** If the slide states a result, show where it comes
from. If it genuinely cannot be derived at this level, say so in those words:
"the slide asserts this without proof; here is the argument". Never let an
unexplained result pass as if it were obvious.

**Give the mechanism before the intuition.** The analogy comes after the real
thing, labeled as an analogy, with the place it breaks down stated. An analogy
offered first becomes the student's mental model and it is always wrong at the
edges.

**Work one example fully, with numbers.** Not a sketch. Actual values, every
intermediate step, arriving at an actual answer. For an algorithm, trace the
state after each step. For a formula, substitute and compute. For a proof
technique, run it on the smallest nontrivial instance.

**State the boundary.** Every definition has a case that violates it, every
theorem has a hypothesis that matters. Name them. "The integral test needs `f`
positive, continuous, and decreasing on `[N, ∞)`; drop decreasing and here is a
series where it gives the wrong answer." What a result does *not* say is as
important as what it does.

**Separate the deck from the truth.** Slides get things wrong, and handwritten
notes skip steps. When the deck is imprecise, teach the correct version and flag
the difference: "the slide writes `=` here; the relation is one-directional and
`∈` is what is meant."

**Cite the page.** Every claim traceable to the deck carries its page number, so
he can find it later. `(Lecture 5, p. 9)`.

**Stop and check.** End each unit with one question that cannot be answered by
pattern matching against what you just wrote. Then wait. Do not answer it
yourself and do not continue to the next unit until he responds. If the answer
is wrong, find the specific misconception and fix that, rather than repeating
the explanation louder.

## Unit shape

One concept per unit. Roughly:

1. Where it sits in the deck, one line.
2. The precise statement, with the page cited.
3. Every term in it unpacked.
4. Why it is true, or how it works, derived.
5. One example worked end to end with real numbers.
6. The boundary: hypotheses that matter, the case that breaks it.
7. One check question. Then stop.

Length follows the concept. A definition with three quantifiers takes more room
than a naming convention. Do not pad a short one and do not compress a hard one.

## Prose style

Load the `unslop` skill before writing the first unit: call
`Skill(skill="unslop")`. Its rules apply to everything produced here, chat
replies included. Do not work from the excerpt below alone, it is a reminder of
the patterns that bite hardest in teaching prose, not a replacement for the
full list:

- No em dashes. Periods and commas only.
- Say what the mechanism does, not how it feels. Not "the stack grows naturally
  downward" but "`push` decrements `rsp`, so a deeper frame sits at a lower
  address".
- Active voice with the actor named. "The linker resolves the symbol", not "the
  symbol is resolved".
- One idea per sentence. Break dense sentences in two.
- No sycophancy, no "great question", no "hope this helps".
- Sentence case headings, no decorative emoji.

Confidence should be calibrated. If the deck is ambiguous or your recall of an
edge case is shaky, say which part is uncertain rather than hedging the whole
explanation.

## Known deck quirks

Verified on 2026-09-09 against the files in `~/Projects`.

**Handwritten iPad notes carry a scrambled text layer.** `Math3/Note*.pdf` and
`DM/Lecture 1.pdf` come from the iOS notes app and expose iOS handwriting
recognition as extractable text. It is reordered word salad. Page 2 of
`Math3/Note13Aug2026(3).pdf` extracts as `Let of for right left n a be sequence
of positive`, whose actual content is "Let ⟨aₙ⟩ be a sequence of positive terms".
The `right` and `left` tokens are leaked math delimiters. Text extraction on
these files does not fail loudly, it returns plausible nonsense. Always render
these decks to PNG and read the image.

**`probe` flags these as `CHECK`** by the 18-tiled-images signature: the notes
app stores each handwritten page as 512x512 bitmap tiles.

**`DM/Lecture 2.pdf` onward have no text layer at all.** Producer is iLovePDF,
zero characters and zero embedded images per page, because the handwriting was
flattened to vector paths. Only rendering works. Page 3 renders as a fully
legible proof that `f(n) ≥ n^d > (k+1)·c·n^k ≥ g(n)`.

**OS and IML decks extract cleanly.** `OS/lec*.pdf` are PowerPoint exports and
`IML/Notes/*.pdf` are Google Slides exports. IML slides are text-sparse and
figure-heavy, around 100 characters per page, so render them even though the
verdict says `TEXT`.

**Filenames contain spaces and parentheses.** Always quote the path.
`"IML/Notes/IML - Lecture_8.pdf"`, `"Math3/Note13Aug2026(3).pdf"`.

**Some DM lectures exist in two versions.** `Lecture3_unlocked.pdf` is the
password-removed copy. Prefer the `_unlocked` file when both are present.

## Troubleshooting

`slides.sh find` returning nothing on a deck that clearly covers the term means
the deck has no text layer. Check with `probe` and switch to rendering.

Renders land in `/tmp/slides/<deck-name>/` and do not survive a reboot. Re-run
`render`, it takes about a second per page.

Default render is 110 dpi, which is readable for handwriting and slides. Pass a
fourth argument for dense subscripts: `slides.sh render "<pdf>" 4 4 200`.
