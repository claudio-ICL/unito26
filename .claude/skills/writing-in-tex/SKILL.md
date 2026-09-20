---
name: writing-in-tex
description: How TeX is written for this course. Load before creating or editing any .tex file in unito26 — lecture notes, slides, beamer frames, class files, notation macros, or the bibliography. Covers the house style (semantic line breaking, labels, notation macros, British English), the layout of documentation/tex/, and how to compile.
---

# Writing in TeX for `unito26`

The house style is Claudio's thesis: `~/Documents/thesis/tex` (the book) and
`~/Documents/thesis/viva/tex` (the beamer deck). Read from it when a case is not
covered here. The worked example inside this repo is the limit-order-book chapter at
`documentation/tex/notes/microstructure/`.

## The rules that matter most

**1. Semantic line breaking.** One sentence, or one clause, per source line. Break at
commas, at conjunctions, at relative pronouns. Never wrap to a column width, and never
run a paragraph onto a single long line.

```tex
The two sides never overlap.
If a buy limit order arrives priced at or above $\bestAskPrice_t$,
it does not rest in the book:
it is matched immediately against the resting sell orders,
exactly as a market order would be.
```

This is the most visible signature of the style, and the reason diffs stay readable.

**2. Sectioning lives in the parent file.** A chapter file is a table of contents:
`\section`, `\label`, `\input` on three consecutive lines, and nothing else. The
`\input`ed file opens straight into prose and contains no sectioning command of its own
(except `\subsection` nested inside it).

```tex
\section{The limit order book}
\label{sec.theBook}
\input{the_book}
```

**3. The class file owns the entire preamble.** Every `\usepackage`, `\newtheorem`,
length and path is in `unito26notes.cls` or `unito26slides.cls`. Content files carry
zero preamble. Paths are declared once via `\input@path` and `\graphicspath`, so
`\input{filename}` and `\includegraphics{name}` never carry a directory.

**4. Every symbol is a macro.** They live in `documentation/tex/include/notation.tex`,
shared by the notes and the slides. Never hardcode a symbol that has a macro, and never
define a macro locally in a content file. See `references/notation.md`.

**5. Labels are `type.camelCaseDescription`, all lowercase.** `eq.` `sec.` `chap.`
`prop.` `def.` `lemma.` `thm.` `corol.` `remark.` `example.` `exercise.` `assumption.`
`assignment.` `algo.` `fig.` `tab.` `listing.` `item.` The description names the subject, never a
position: `chap.lob`, not `chap.lec01`.

**6. Names are topics, not numbers.** Files and directories are `lob.tex`, `sabr.tex`.
Order is carried solely by the sequence of `\include` lines in `main.tex`, so inserting
or reordering a lecture renames nothing and breaks no cross-reference.

**7. British English.** `-ise`/`-isation`, `behaviour`, `modelled`, `analysed`. First
person plural. `\emph{}` for emphasis and for the first use of a defined term — never
`\textit` or `\textbf`.

**8. The notes reference nothing outside themselves.** No notebook, no markdown document, no
module, no file path. The notes are self-contained and independent: it is the notebooks and the
documentation that cite the notes, not the other way round. A fact worth having in the notes is
worth writing in the notes.

An external address is not such a reference. The notes name the exchanges of `sec.orderDrivenMarkets`,
LOBSTER in `sec.messageFiles` and the course repository in `sec.assignments`, each as a `\url`.
What the rule forbids is a path *into this repository*.

**9. Every paragraph earns its place.** A free-standing paragraph must introduce a symbol,
state a hypothesis, or draw a consequence. One that does none of the three exists only to
comment on the paragraph beside it, and is deleted.

This is the rule that drifts, and a blocklist of phrases does not hold it: the offence is a
role, not a vocabulary. `The half-open interval of integration is what makes $\intensity$
predictable` is the same construction as `Reconstruction is an ordinary part of a trading
system`, and only the second is the offence. So the trigger is structural. Run

```bash
python3 .claude/skills/writing-in-tex/scripts/loose_paragraphs.py documentation/tex/notes
```

which lists free-standing paragraphs carrying no `$`, no `\ref`/`\eqref`, no `\cite` and no
`\emph`. It is a list to **justify**, not a list to forbid: most hits are lead-ins to a
display, and its false positives cost nothing. Read it before reporting `.tex` work done.

The phrase gate is kept, cut to the arms that do not fire on correct mathematics, and it
skips comment lines so that it does not flag the author's own notes to you:

```bash
cd documentation/tex
grep -rnE "worth (stating|noting|restating|having|being|a (line|comment))|deserves? comment|\
and nothing else|not an afterthought|it is tempting|an honest statement|\
matters more than it looks|turns out that|the key (insight|point|idea)|\
this section (says|tells|shows|will)|as we (shall|will) see|\
(^|[.;] )(Importantly|Crucially|Interestingly|Remarkably|Strikingly|Notably)|\
a reader should|the reader should|one should be careful|[Nn]ote that |\
rather than (a |an )?(convenience|formality|nicety)|is not innocuous|\
than one (expects|might|would)|\bnot merely\b|is a statement about|\
\bwe (state|write|place|put) (it|this|the [a-z]+) here\b" --include=*.tex . \
  | grep -v ':[0-9]*:%'
```

`Note that` is on the list because the house word is `Notice that`. No exclamation marks and
no rhetorical questions. An environment that exists to answer a question someone asked in a
conversation does not belong: write for a stranger meeting the file in a year.

**How to say it instead.** Two shapes recur, and neither is catchable by pattern. The
*reversed cleft* — `What $\branchingRatio<1$ supplies is Lemma iv.`, `A single $\decay$ buys
a state of dimension $\numEventTypes$`, `The mechanism the kernel has to carry is
replenishment` — is written forwards: `The kernel carries the mechanism of replenishment`.
The *defensive negative* — `a genuine restriction and not a formality`, `hypotheses rather
than conveniences`, `constant column sums are not needed` — states the condition and stops:
`$(\branchingMatrix,\stationaryIntensity)$ should be chosen so that $\baseIntensity$ has
non-negative components`.

Sentences whose only job is to rate another sentence go without replacement: `and its sign is
a statement about the state alone`, `We state the assumption here, where it is used, because
it is not innocuous`, `Less fails without it than one expects`, `The right-hand side is a
product of two factors, and the following lemma says what that means`.

Full details, with the remaining conventions on equations, theorems, figures, code,
algorithms and citations, are in `references/style.md`.

## Where things go

```
documentation/tex/
├── bibliography.bib          shared
├── include/                  shared: notation, listings style, hyperref
├── notes/                    the book — unito26notes.cls, main.tex, one dir per chapter
└── slides/                   the deck — unito26slides.cls, main.tex, sections/<topic>.tex
```

One notes book and one slide deck for the whole course. To add a chapter, follow
`references/structure.md` and start from `templates/`.

## Compiling — always do this

After any edit, build from the directory holding `main.tex` (the class uses relative
paths, so the working directory matters):

```bash
cd documentation/tex/notes    # or documentation/tex/slides
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

`latexmk` drives pdflatex and bibtex and reruns until cross-references settle. Do not
call `pdflatex` directly: on an error it waits at an interactive prompt and hangs.

Then confirm nothing is silently broken — this must print `0`:

```bash
grep -icE 'undefined (control sequence|reference|citation)|LaTeX Warning: Reference' main.log
```

Clean up with `latexmk -c` (keeps the PDF, removes the aux files).

Do not report TeX work as done until both documents compile and that grep returns `0`.
