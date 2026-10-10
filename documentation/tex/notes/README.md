# The lecture notes

One book, `main.tex`, one `\include` per chapter. The order of those lines is the order of
the course; chapters are named after their subject, never after their position.

The notes have **two subject chapters and only two** (see `CLAUDE.md`), the second of them
optional reading. A new topic joins one of them as a section. Ahead of them sits the welcome
chapter, which is front matter.

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
| Prerequisites | `sec.prerequisites` | `prerequisites.tex` |
| What we learn about Python | `sec.learningPython` | `learning_python.tex` |
| What we learn about quantitative finance | `sec.learningFinance` | `learning_finance.tex` |
| The examination | `sec.examination` | `examination.tex` |
| The assignment | `sec.assignments` | `assignments.tex` |
| Reading list | `sec.readingList` | `reading_list.tex` |

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
of them.

`message_files.tex` carries its own `\subsection`s: what an exchange disseminates, the book as
a fold, the fold in the course repository (`sec.foldImplementation`), a faster book
(`sec.fasterBook`), and LOBSTER, whose last `\subsubsection` reads a LOBSTER pair into a
session. The two implementation subsections and that subsubsection walk the reader through the
package, under the exception stated below.

Price formation is what the chapter is for. It runs from the order flow imbalance, through
the marked point process that generates it, to a forecast of the mid-price. The last section
is the chapter's assignment: it carries the five things the generated setting lacks, and
`assignment.orderFlowImbalance`, which asks that forecast of recorded data.

## Chapter 2 — Option pricing and volatility trading

Optional reading: neither taught in class nor examined, and added to the notes towards the
end of the course. `options/options.tex` is a placeholder, the chapter title and three lines
saying so. `options/sections/` is registered in `\input@path` and is empty.

## Appendix A — Integers in binary

Back matter: `\appendix`, then `\include{appendix/appendix}`, after the two chapters. It is
lettered and is not a subject chapter; it serves `sec.fasterBook`, proving the properties of
the binary representation that the array-backed book is written in.
`appendix/appendix.tex` carries the sectioning and each section is one file in
`appendix/sections/`, named `binary_*` so that no name clashes on the shared input path.

## Appendix B — Object-oriented programming

Back matter, after Appendix A: `\include{appendix/objects}`. It serves `sec.foldImplementation`
and `sec.fasterBook`, which speak of instances, constructors and inheritance without defining
them: it defines those terms on the classes of the package, from one rule for the reference of
an attribute (`def.attributeReference`). The course does not assume classes, and
`sec.theCourse` sends the reader here.
`appendix/objects.tex` carries the sectioning and each section is one file in
`appendix/sections/`, named `objects_*`.

| section | label | file |
| --- | --- | --- |
| Names and objects | `sec.namesAndObjects` | `objects_names.tex` |
| Classes and instances | `sec.classesAndInstances` | `objects_classes.tex` |
| Attribute references | `sec.attributeReferences` | `objects_references.tex` |
| Data classes | `sec.dataClasses` | `objects_dataclasses.tex` |
| Properties and class methods | `sec.propertiesAndClassMethods` | `objects_properties.tex` |
| State and its invariants | `sec.stateAndInvariants` | `objects_invariants.tex` |
| Inheritance | `sec.inheritance` | `objects_inheritance.tex` |
| Abstract classes and duck typing | `sec.abstractClasses` | `objects_abstract.tex` |
| Composition | `sec.composition` | `objects_composition.tex` |

**No measured figure appears in the notes.** Coefficients, windows and goodness-of-fit numbers
live in `notebooks/`, which is where they can be re-derived; the notes carry the mechanism and
the signs.

**The notes reference nothing outside themselves** — no notebook, no markdown document, no
module. They are self-contained: it is the notebooks and the documentation that cite the notes,
not the other way round.

The one exception is scoped: `sec.foldImplementation`, `sec.fasterBook`, the LOBSTER-session
subsubsection of §1.2 and Appendices A and B name the package's modules, classes, functions
and test modules, and quote its code. A quote names its source in its caption as
`\codehl{unito26.…}` and marks each cut with a line reading `# ...`;
`tests/test_notes_quote_the_package.py` keeps every quote verbatim and runs every other
listing, which therefore names no `unito26.` path in its caption. A listing keeps to 75
columns, the width the page prints without wrapping. Notebooks and markdown documents are
never named.

## Building

```bash
cd documentation/tex/notes    # or documentation/tex/slides
latexmk -C && latexmk -f -pdf -interaction=nonstopmode main.tex
grep -icE '^! |Undefined control sequence|LaTeX Warning: (Reference|Citation)|multiply defined' \
     main.log   # must be 0

# both documents share include/notation.tex, so both must be built
```
