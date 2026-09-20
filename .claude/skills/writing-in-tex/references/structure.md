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
│   ├── welcome/                    chapter 0, front matter
│   ├── microstructure/             one directory per chapter, named by topic
│   │   ├── microstructure.tex      \chapter + \section/\label/\input triples
│   │   ├── sections/*.tex          prose only
│   │   └── figures/
│   └── options/                    chapter 2, a placeholder today
└── slides/
    ├── unito26slides.cls
    ├── specs.tex                   title, author, institute, date
    ├── slide_formatting.tex        templates, TOC frames, \AtBeginSection
    ├── main.tex                    one \section + \include per chapter
    ├── figures/
    └── sections/microstructure.tex
```

One notes book and one slide deck for the whole course.

**The chapters already exist.** The course has two subject chapters and only two, preceded
by the welcome chapter; a new topic joins one of them as a section, and the procedure below
is how the three were made rather than an invitation to a fourth.

## The chapter numbering

`main.tex` sets `\setcounter{chapter}{-1}` before `\include{welcome/welcome}`, so the
welcome chapter is numbered 0 and market microstructure is numbered 1. Every equation in
the book is `\numberwithin`-ed to its section, hence to its chapter, and every document and
skill in the repository refers to §1.4 and §1.5. **Nothing may be included ahead of the
welcome chapter, and that `\setcounter` line stays.** The guard is a grep on `main.toc`
after a build:

```bash
grep -c 'numberline {1}Market microstructure' main.toc   # 1
```

## Adding a chapter

Say the topic is `<topic>`.

1. `mkdir -p documentation/tex/notes/<topic>/sections documentation/tex/notes/<topic>/figures`
2. Copy `templates/chapter.tex` to `notes/<topic>/<topic>.tex`; set `\chapter{...}` and
   `\label{chap.<topic>}`; write the orienting paragraph; list the sections.
3. Copy `templates/section.tex` once per section into `notes/<topic>/sections/`.
4. **Register the paths in `unito26notes.cls`** — add `{./<topic>/}` and
   `{./<topic>/sections/}` to `\input@path`, and `{./<topic>/figures/}` to `\graphicspath`.
   Forgetting this is the usual cause of a `File not found` on a new chapter.
5. Add `\include{<topic>/<topic>}` to `notes/main.tex`, in the position the course runs —
   after the welcome chapter, so the numbering above holds.
6. Copy `templates/slides-section.tex` to `slides/sections/<topic>.tex`, and add
   `\section{...}` + `\include{sections/<topic>}` to `slides/main.tex`.
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
