# The lecture notes

One book, `main.tex`, one `\include` per chapter. The order of those lines is the order of
the course; chapters are named after their subject, never after their position.

The course has **two chapters and only two** (see `CLAUDE.md`). A new topic joins one of them
as a section.

## Chapter 1 — Market microstructure

`microstructure/microstructure.tex` carries the sectioning; each section is one file in
`microstructure/sections/`.

| section | label | file |
| --- | --- | --- |
| Order-driven markets | `sec.orderDrivenMarkets` | `order_driven_markets.tex` |
| From message files to the aggregated order book | `sec.messageFiles` | `message_files.tex` |
| Point processes and self-excitation | `sec.pointProcesses` | `point_processes.tex` |
| Price formation | `sec.priceFormation` | `price_formation.tex` |
| Evidence from recorded data | `sec.lobsterEmpirics` | `lobster_empirics.tex` |

`point_processes.tex` and `price_formation.tex` are themselves indexes, holding
`\subsection`/`\label`/`\input` triples:

- point processes: `counting_processes`, `hawkes_processes`, `exponential_kernels`,
  `stability`, `simulation`
- price formation: `order_flow_imbalance`, `order_flow_model`, `reading_the_intensity`,
  `forecasting_the_mid`

`stability.tex` carries four `\subsubsection`s of its own — second-order structure, the
scalar case, timescales, sub- and supercriticality — and `sec.secondOrder` labels the first
of them. It is the one leaf file with nested sectioning; everything else opens straight into
prose.

Price formation is what the chapter is for. It runs from the order flow imbalance, through
the marked point process that generates it, to a forecast of the mid-price; the last section
puts that forecast to recorded data.

**No measured figure appears in the notes.** Coefficients, windows and goodness-of-fit numbers
live in `notebooks/`, which is where they can be re-derived; the notes carry the mechanism and
the signs.

**The notes reference nothing outside themselves** — no notebook, no markdown document, no
module. They are self-contained: it is the notebooks and the documentation that cite the notes,
not the other way round.

## Building

```bash
cd documentation/tex/notes    # or documentation/tex/slides
latexmk -C && latexmk -f -pdf -interaction=nonstopmode main.tex
grep -icE '^! |Undefined control sequence|LaTeX Warning: (Reference|Citation)|multiply defined' \
     main.log   # must be 0

# both documents share include/notation.tex, so both must be built
```
