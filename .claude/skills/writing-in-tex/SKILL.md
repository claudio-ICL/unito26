---
name: writing-in-tex
description: How TeX is written for this course. Load before creating or editing any .tex file in unito26 — lecture notes, slides, beamer frames, class files, notation macros, or the bibliography. Covers the house style (semantic line breaking, labels, notation macros, British English), the layout of documentation/tex/, and how to compile.
---

# Writing in TeX for `unito26`

The house style is Claudio's thesis: `~/Documents/thesis/tex` (the book) and
`~/Documents/thesis/viva/tex` (the beamer deck). Read from it when a case is not
covered here. The worked example inside this repo is the limit-order-book chapter at
`documentation/tex/notes/lob/`.

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
`algo.` `fig.` `tab.` `listing.` `item.` The description names the subject, never a
position: `chap.lob`, not `chap.lec01`.

**6. Names are topics, not numbers.** Files and directories are `lob.tex`, `sabr.tex`.
Order is carried solely by the sequence of `\include` lines in `main.tex`, so inserting
or reordering a lecture renames nothing and breaks no cross-reference.

**7. British English.** `-ise`/`-isation`, `behaviour`, `modelled`, `analysed`. First
person plural. `\emph{}` for emphasis and for the first use of a defined term — never
`\textit` or `\textbf`.

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
