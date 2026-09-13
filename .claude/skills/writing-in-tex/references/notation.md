# Notation reference

All notation for the course lives in `documentation/tex/include/notation.tex`, and it is
shared by the notes and the slides. Nothing is defined anywhere else.

## Why one shared file

The thesis carries four near-identical copies of its notation
(`tex/include/`, `tex/chap3/notation_chap3.tex`, `tex/pipest/include/`,
`viva/tex/include/`) and they have drifted: `\Prob` expands to `{{P}}` in
`tex/include/notation.tex:140` but to `{\mathbb{P}}` in
`tex/chap3/notation_chap3.tex:123`, so the same symbol renders differently in different
chapters of the same document.

This repo has one file. Do not copy it into a chapter, and do not define a macro inside
a content file.

## Naming

Names are descriptive and camelCase. Prefer the long, obvious name:

```tex
\volatilityCoefficient      not \sig
\coeffMarketImpact          not \c1
\timeHorizon                not \T
\bestBidPrice               not \Pb
```

The point is that a reader of the source knows what a symbol means, and that changing
the symbol is a one-line edit rather than a search-and-replace over the whole course.

## The three patterns to reuse

**Optional-argument families** for indexed quantities, with a sensible default:

```tex
\newcommand{\intensity}[1][e]{\lambda_{#1}}          % \intensity -> \lambda_e
\newcommand{\nthBestBidPrice}[1][1]{\price^{b,{#1}}} % \nthBestBidPrice[2]
\newcommand{\bidQueue}[1][t]{Q^{b}_{{#1}}}           % \bidQueue[s]
```

**Composition** — build macros out of macros, never out of raw symbols:

```tex
\newcommand{\R}{\mathbb{R}}
\newcommand{\Rd}{\R^{d}}
\newcommand{\midPrice}{\price^{m}}
\newcommand{\nthBestBidSize}[1][1]{\size^{b,{#1}}}
```

Changing `\price` then moves every price symbol at once.

**Suffix decorations** that attach to whatever precedes them:

```tex
\newcommand{\squared}{^{2}}      % \volatilityCoefficient\squared
\newcommand{\derivative}{^{\prime}}
\newcommand{\inverse}{^{-1}}
\newcommand{\transpose}{^{\mathsf{T}}}
```

## Organisation

The file is grouped under `%% BLOCK %%` comment headers: sets and spaces, decorations,
derivatives, time, probability, option pricing, limit order books. A new chapter adds a
new block at the end; it does not scatter macros into the existing ones.

## Continuity with the thesis

Where a symbol already exists in the thesis, it is carried over **verbatim** so that the
course and the thesis denote the same object the same way. The limit-order-book block is
lifted from `tex/include/notation.tex:371-419`: `\price`, `\tickSizeOfLOB`, `\midPrice`,
`\bestBidPrice`, `\bestAskPrice`, `\bidQueue`, `\askQueue`, `\OFI`, and the
arrival/departure families.

One symbol diverges. The thesis writes `\volume`, $V$, for the quantity resting at a level;
here that is `\size`, $S$, and `\volume` is the volume transacted. The queue-size family and
`\queueImbalance` follow from it. Do not reinstate $V$ for a level's size.

Check the thesis before inventing a name for something it already names.
