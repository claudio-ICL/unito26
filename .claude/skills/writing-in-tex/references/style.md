# Style reference

Every rule below is drawn from Claudio's thesis, cited so it can be checked.
Paths are relative to `~/Documents/thesis/`.

## Prose

**Semantic line breaking.** One sentence or one clause per line; break at commas,
conjunctions, relative pronouns. Model: `tex/chap3/sections/permanent_price_impact.tex`
(≈33 characters per line) and `tex/chap3/chap3.tex:17-33`.

*The thesis is not uniform on this.* Chapter 4 came from a joint paper and uses long
lines. Chapter 3, the most recent original writing, is the model to follow.

**British English**, verified across the thesis: 83 occurrences of `minimisation`, none
of `minimization`. Use `-ise`/`-isation`, `behaviour`, `modelled`, `analysed`,
`characterised`.

**Voice.** First person plural — "we describe", "we now consider". Present tense.

**Emphasis.** `\emph{}` only, both for stress and for the first appearance of a term
being defined. Never `\textit`/`\textbf` for emphasis.

**Chapter openers.** Every chapter begins with a short orienting paragraph: what the
chapter does, what it depends on, and whether it can be read independently. See
`tex/chap3/chap3.tex:5` and `tex/chap4/chap4.tex:5`.

## Structure

**Sectioning in the parent only.** `main.tex` and each chapter file are tables of
contents — `\section` / `\label` / `\input` triples and nothing else
(`tex/chap3/chap3.tex`, `tex/chap4/chap4.tex`). The `\input`ed file starts in prose.

**No preamble in content files.** Everything belongs to the `.cls`
(`tex/myICthesis.cls:1-17,32-39`), including `\input@path` and `\graphicspath`, so
`\input` and `\includegraphics` never carry a directory.

## Labels and references

Format `type.camelCaseDescription`, all lowercase. Prefixes in use: `eq.` `sec.` `chap.`
`prop.` `def.` `lemma.` `thm.` `corol.` `remark.` `example.` `exercise.` `assumption.`
`algo.` `fig.` `tab.` `listing.` `item.`

*Deliberate tightening:* the thesis mixes `eq.`/`Eq.` and `def.`/`defi.`/`Sec.`. Do not
reproduce that inconsistency.

References are written out with the noun, and there is no `cleveref`:

```tex
Section \ref{sec.theBook}          equation \eqref{eq.midPrice}
Proposition \ref{prop.x}           Definition \ref{def.bestQuotes}
Algorithm \ref{algo.x}             Listing \ref{listing.x}
```

`\eqref` for equations, `\ref` for everything else.

## Equations

- `equation` with a `\label` when referenced; `equation*` when not.
- `\label` on its own line, immediately after `\begin{equation}`.
- Multi-line: `split` inside `equation`, aligned on `=` or `=&` at the start of a line.
- Piecewise: `cases`.
- Unnumbered display inside a theorem body: `\[ ... \]`.

```tex
\begin{equation}
\label{eq.positiveSpread}
\LOBspread_t := \bestAskPrice_t - \bestBidPrice_t \geq \tickSizeOfLOB
\end{equation}
```

## Theorem environments

Declared in the class off one shared counter numbered within section
(`tex/myICthesis.cls:65-77`): `theorem`/`thm`, `prop`, `lemma`, `corol`, `defi`,
`remark`, `example`, `exercise`, `assumption`, `model`, `conjecture`, `approximation`.
`\label` goes on its own line right after `\begin{...}`. Proofs use `proof`.

Note for slides: beamer already defines `example` and `corollary`, so
`unito26slides.cls` does not redefine them.

## Figures and tables

```tex
\begin{figure}
	\centering
	\includegraphics[width=0.9\textwidth]{orderbook}
	\caption{...}
	\label{fig.orderBook}
\end{figure}
```

No path in `\includegraphics` — `\graphicspath` resolves it. The thesis often nests a
`tabular` inside the figure to stack an image above a table of the parameters that
produced it (`tex/chap3/sections/tables_and_figures.tex`).

## Code

Style comes from `include/snippets_stylerendering.tex`, defaulting to Python.

- Prefer `\lstinputlisting[language=Python,caption=...,label=listing.x]{path/to/file.py}`
  over inline listings, so the code that appears in the notes is code that runs.
- `\codehl{...}` for inline identifiers in prose — `\codehl{OrderQueue::add}`,
  `\codehl{.csv}`. See `tex/appendix/simulob_implementation.tex`.

## Algorithms

`algorithm` + `algorithmic`, caption first then label, with `\REQUIRE` `\STATE` `\WHILE`
`\ENDWHILE` `\RETURN` (`tex/chap1/sections/hawkes_processes.tex:123`).

## Bibliography

`natbib[round,sort,comma,numbers,authoryear]` with `\bibliographystyle{apalike}`.

**Key format** (read off `tex/bibliography.bib`):

- one author — first three letters of the surname + two-digit year + first three letters
  of the title: `Haw71spe`, `Nut12pat`, `Bre81poi`, `Kyl85con`;
- several authors — the initials of the surnames + year + three letters: `ABBC21opt`,
  `SV16pat`, `BDHM13mod`, `GM85bid`.

Pinpoints: `\cite[Chapter 2]{LB07ana}`, `\citealp[Algorithm 2.4]{MP18sta}`.

The bibliography file is shared, one directory up, so main files reference it as
`\bibliography{../bibliography}`. Do not rely on `\input@path` here — bibtex does not
read it.

## Slides

- `\begin{frame}` then `\frametitle{...}` on the next line.
- One idea per frame; `\pause` between beats.
- A long statement is split across frames titled `... - 1 of 3`
  (`viva/tex/sections/sec4.tex`).
- Reuse the notes' theorem environments and the *same label names*, so a statement can
  move between deck and notes without rewriting.
- `\nocite{key}` — **one per line**. A multi-key `\nocite{...}` spanning several lines
  makes bibtex choke on the whitespace; `viva/tex/sections/sec1.tex` uses one per line
  for this reason.
