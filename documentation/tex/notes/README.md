# The lecture notes

One book, `main.tex`, one `\include` per chapter. The order of those lines is the order of
the course; chapters are named after their subject, never after their position.

The course has **two subject chapters and only two** (see `CLAUDE.md`). A new topic joins
one of them as a section. Ahead of them sits the welcome chapter, which is front matter.

The title page carries `This version: \compilationDate`, the day the book was typeset, so a
reader can tell which printing they hold. The macro is in `unito26notes.cls`; `\today` is
not used, babel's `english` setting it in the American form.

## Chapter 0 — Welcome

Front matter: what the course contains, what is learnt in it, and how it is examined.
`main.tex` sets `\setcounter{chapter}{-1}` before including it, so it is numbered zero and
market microstructure stays chapter 1. **Do not remove that line** — every equation number
and every cross-reference in the book is written against microstructure being chapter 1.

| section | label | file |
| --- | --- | --- |
| The course | `sec.theCourse` | `the_course.tex` |
| What we learn about Python | `sec.learningPython` | `learning_python.tex` |
| What we learn about quantitative finance | `sec.learningFinance` | `learning_finance.tex` |
| The examination | `sec.examination` | `examination.tex` |
| The assignments | `sec.assignments` | `assignments.tex` |

It is the one chapter that speaks about the course rather than about the subject, and the
only one that names the repository. That is a URL, like the exchanges of §1.1 and LOBSTER in
§1.2, and not a reference to a file: no path, no module, no notebook.

## Chapter 1 — Market microstructure

`microstructure/microstructure.tex` carries the sectioning; each section is one file in
`microstructure/sections/`.

| section | label | file |
| --- | --- | --- |
| Order-driven markets | `sec.orderDrivenMarkets` | `order_driven_markets.tex` |
| From message files to the aggregated order book | `sec.messageFiles` | `message_files.tex` |
| Point processes and self-excitation | `sec.pointProcesses` | `point_processes.tex` |
| Price formation | `sec.priceFormation` | `price_formation.tex` |
| Assignment — evidence from recorded data | `sec.lobsterEmpirics` | `lobster_empirics.tex` |

`point_processes.tex` and `price_formation.tex` are themselves indexes, holding
`\subsection`/`\label`/`\input` triples:

- point processes: `counting_processes`, `hawkes_processes`, `exponential_kernels`,
  `stability`, `simulation`
- price formation: `order_flow_imbalance`, `order_flow_model`, `forecasting_the_mid`

`stability.tex` carries four `\subsubsection`s of its own — second-order structure, the
scalar case, timescales, sub- and supercriticality — and `sec.secondOrder` labels the first
of them. It is the one leaf file with nested sectioning; everything else opens straight into
prose.

Price formation is what the chapter is for. It runs from the order flow imbalance, through
the marked point process that generates it, to a forecast of the mid-price. The last section
is the chapter's assignment: it carries the four things the generated setting lacks, and
`assignment.orderFlowImbalance`, which asks that forecast of recorded data.

## Chapter 2 — Option pricing and volatility trading

`options/options.tex`, a placeholder: the chapter title and one line saying when the
material arrives. `options/sections/` is registered in `\input@path` and is empty.

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
