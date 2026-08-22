# Structure reference

## Layout

```
documentation/tex/
├── bibliography.bib                shared by notes and slides
├── include/                        shared — the single source of truth
│   ├── notation.tex
│   ├── snippets_stylerendering.tex
│   └── sethyperref.tex
├── notes/
│   ├── unito26notes.cls            owns the whole preamble
│   ├── mypagestyle.tex
│   ├── main.tex                    one \include line per chapter
│   ├── figures/
│   └── lob/                        one directory per chapter, named by topic
│       ├── lob.tex                 \chapter + \section/\label/\input triples
│       ├── sections/*.tex          prose only
│       └── figures/
└── slides/
    ├── unito26slides.cls
    ├── specs.tex                   title, author, institute, date
    ├── slide_formatting.tex        templates, TOC frames, \AtBeginSection
    ├── main.tex                    one \section + \include per chapter
    ├── figures/
    └── sections/lob.tex
```

One notes book and one slide deck for the whole course.

## Adding a chapter

Say the topic is SABR.

1. `mkdir -p documentation/tex/notes/sabr/sections documentation/tex/notes/sabr/figures`
2. Copy `templates/chapter.tex` to `notes/sabr/sabr.tex`; set `\chapter{...}` and
   `\label{chap.sabr}`; write the orienting paragraph; list the sections.
3. Copy `templates/section.tex` once per section into `notes/sabr/sections/`.
4. **Register the paths in `unito26notes.cls`** — add `{./sabr/}` and
   `{./sabr/sections/}` to `\input@path`, and `{./sabr/figures/}` to `\graphicspath`.
   Forgetting this is the usual cause of a `File not found` on a new chapter.
5. Add `\include{sabr/sabr}` to `notes/main.tex`, in the position the course runs.
6. Copy `templates/slides-section.tex` to `slides/sections/sabr.tex`, and add
   `\section{SABR}` + `\include{sections/sabr}` to `slides/main.tex`.
7. Add any new symbols to `include/notation.tex`, in a new block at the end.
8. Compile both documents (see SKILL.md).

Ordering is carried only by the `\include` lines. Reordering the course is reordering
those lines — no file is renamed, no label changes, no cross-reference breaks.

## Why the working directory matters

Both class files set `\input@path` and `\graphicspath` with paths relative to the
directory containing `main.tex`. Compiling from anywhere else fails to find the shared
includes. Always `cd` into `notes/` or `slides/` first.

The bibliography is the one exception to `\input@path`: bibtex does not read it, so the
main files say `\bibliography{../bibliography}` explicitly.

## Keeping notes and slides in step

The deck mirrors the book: one `\section` per chapter, in the same order, with the same
topic name. Statements shared between the two use the **same label**, so a definition
can be moved or copied without editing its cross-references.
