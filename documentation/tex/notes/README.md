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
| The LOBSTER dataset | `sec.lobsterEmpirics` | `lobster_empirics.tex` |

`point_processes.tex` and `price_formation.tex` are themselves indexes, holding
`\subsection`/`\label`/`\input` triples:

- point processes: `counting_processes`, `hawkes_processes`, `stability`, `second_order`,
  `simulation`
- price formation: `order_flow_model`, `order_flow_imbalance`, `synthetic_evidence`

Price formation is the end of the chapter and the reason for the rest of it.

**No measured figure appears in the notes.** Coefficients, windows and goodness-of-fit numbers
live in `notebooks/`, which is where they can be re-derived; the notes carry the mechanism and
the signs.

## Building

```bash
cd documentation/tex/notes    # or documentation/tex/slides
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
grep -icE 'undefined (control sequence|reference|citation)' main.log   # must be 0
grep -c 'multiply defined' main.log                                    # must be 0
```
