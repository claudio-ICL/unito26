# Sample questions for the examination

One document, `main.tex`, in the format of the examination of `sec.examination`: a question
shows code and offers lettered choices, exactly one of which is right. One section per topic,
in the order of the notes, one file per section in `sections/`. The solution key is printed at
the end, built from the questions themselves.

Every answer can be read off running code. Each section names, by `\notebook{NN-name}` on its
first line, a notebook of `notebooks/sample-questions/` that runs the code of every question
of the section, evaluates every choice, and asserts that the key holds and that no other choice
does. Beside it, `NN-name-worked-solutions` answers the same questions by hand, as in the
examination. `tests/test_sample_questions.py` holds the document and the notebooks together.

| section | label | file | notebook |
| --- | --- | --- | --- |
| Representing the aggregate book | `sec.representingTheBook` | `representing_the_book.tex` | `01-representing-the-book` |
| Updating the book | `sec.updatingTheBook` | `updating_the_book.tex` | `02-updating-the-book` |
| Traded volume and VWAP | `sec.vwap` | `vwap.tex` | `03-vwap` |
| The book as a fold | `sec.foldingTheStream` | `folding_the_stream.tex` | `04-folding-the-stream` |
| Classes and inheritance | `sec.inheritance` | `inheritance.tex` | `05-inheritance` |
| Simulating a Hawkes process | `sec.simulatingHawkes` | `simulating_hawkes.tex` | `06-simulating-hawkes` |
| Necessary conditions and goodness of fit | `sec.goodnessOfFit` | `goodness_of_fit.tex` | `07-goodness-of-fit` |
| Telling specifications apart | `sec.tellingSpecificationsApart` | `telling_specifications_apart.tex` | `08-telling-specifications-apart` |
| The Markov state | `sec.markovState` | `markov_state.tex` | `09-the-markov-state` |
| The matrix exponential and the expected order flow | `sec.matrixExponential` | `matrix_exponential.tex` | `10-the-matrix-exponential` |
| Integers in binary | `sec.binaryTricks` | `binary_tricks.tex` | `11-binary-tricks` |

The house style of the notes applies: `.claude/skills/writing-in-tex`. Semantic line breaks,
British English, every symbol a macro of `include/notation.tex`, labels `type.camelCase`.

## A question

```tex
\begin{question}
\label{question.imbalanceOverGridLevels}
<the stem: what the code is for, and what the student needs that the code does not show>
\begin{lstlisting}[caption={Alternative A}, label=listing.imbalanceOverGridLevelsA]
...
\end{lstlisting}
<the question itself: "What does the snippet print?", "Which statement holds?">
\begin{choices}
 \choice ...
 \correctchoice ...
 \choice ...
\end{choices}
\explanation{<why, in one to three sentences, citing the notes by label>}
\end{question}
```

- `question` is numbered within its section. Its label is `question.<camelCase>`, naming the
  subject of the question, never its position.
- Exactly one choice is `\correctchoice`. It prints like `\choice` and records its own letter:
  the letter of the key is never typed, and reordering the choices moves it.
- `\explanation` is not printed with the question. It writes the question's row of the key.
- The notes are cited by label with the prefix `notes:`, as
  `Corollary~\ref{notes:corol.meanResponse}`. Their labels are read from the `.aux` files of
  their last build, so the notes are built first. An unlabelled statement of the notes is
  described rather than numbered: a hard-coded number goes stale when the notes grow.

## Listings

A listing carries its options on its first line, always with a caption, and is one of two
kinds, told apart by the caption as in the notes:

- a **quote** of the package names its source as `\protect\codehl{unito26.…}` and marks each
  cut with a line reading `# ...`. The test holds it to the source, verbatim and in order, a
  run of lines being allowed one shift of indentation (a method lifted out of its class). A
  quote of a property quotes the class, `unito26.lob.orderbook.AggregateBook`.
- a **snippet** is anything else: an alternative, a variant of a method of the package, the
  lines that run it. It keeps within 75 columns, and it occurs line for line in a code cell
  of the section's notebook. A variant of a package method does not carry a `unito26.` path
  in its caption, or it would be held to the source.

Snippets omit the standing imports of `front_matter.tex`. A name they do not cover is named
by the stem, with its module. An output is asked of `print`, whose `str` form is stable; the
`repr` of a numpy scalar is not (`np.float64(1.5)` since numpy 2).

## What makes a question

- **The answer is read off running code.** A student who could run the code would see it;
  the question is whether they can tell by reading.
- **The setting is the market.** Books, orders, messages, order flow, the price. A question on
  bits or on classes is asked on the classes and the bits of the book.
- **By hand.** No computer in the examination: every number is reachable with pencil and
  paper, and the stem gives the value of any exponential or logarithm needed, and any fact of
  floating point the question rests on.
- **Self-contained.** The stem quotes what the code relies on; it does not assume the student
  remembers the implementation.
- **One right choice, and wrong ones that are plausible.** A distractor is the answer of a
  definite misreading: an index off by one, the post-jump state for the pre-jump one, a
  transposed kernel, a copy taken for an alias. "Both", "neither", "only A", "only B" are
  natural choices when alternatives are compared.
- **Performance.** Every section asks at least one question of which implementation is
  faster. It claims only what a run on any machine reproduces: a factor of about five or
  more, or a growth in the size (constant against linear, linear against quadratic), never a
  small constant factor.
- **Families are welcome.** Two questions may share a snippet and differ in the book, the
  order or the parameters.

## The notebook of a section

`notebooks/sample-questions/NN-name.ipynb`, kernel `python3`.

- A first markdown cell: the title, the notes it serves, and how it verifies.
- A first code cell: the standing imports, then `outcome` and `verify`, copied from
  `01-representing-the-book`:
  - `outcome(function, *arguments)` returns what a call prints, or the name of the exception
    it raises;
  - `verify("question.<label>", "<key>", [holds_A, holds_B, ...])` asserts that, of the
    choices evaluated in that order, the key holds and no other does.
- One `## \`question.<label>\`: <subject>` section per question, in the order of the
  document, each closed by its single call of `verify`. The test reads the label and the
  letter of that call, so they are written as string literals on its first line.
- A snippet is copied verbatim. Where it prints, it is the body of a function `run`, called
  through `outcome`; the uniform indentation is allowed.
- Every choice is a boolean computed by running code, so that a wrong distractor fails the
  notebook as surely as a wrong key.
- Random draws are seeded, and a Monte Carlo choice is separated from its neighbours by many
  standard errors. Timings are taken with `timeit` over a ladder of sizes, and the ratios that
  decide the choices are printed.
- A notebook runs in a few minutes at most. Outputs are not committed.

## The worked solutions of a section

`notebooks/sample-questions/NN-name-worked-solutions.ipynb`, beside the notebook of the
section, kernel `python3`. It answers the questions as the examination asks them to be
answered, by hand, and runs no snippet.

- A first markdown cell: the title, what an entry holds, the form of a citation, and the
  notebook that verifies the section.
- A code cell importing from `math` what the calculator uses, if it uses anything.
- A markdown cell `# Section N · <title>`, then the facts that two or more questions use,
  numbered, each stated once with its citation.
- One entry per question, in the order of the document, opened by
  `## N.k · \`question.<label>\`` and a line `**Answer: (X).**`. The solution traces the code
  by hand and cites the notes for every formula it uses; `**The other choices.**` names the
  misreading that gives each wrong choice. The test reads the heading and the answer line.
- A code cell is a calculator: arithmetic on the numbers of the question, its value the
  number the prose quotes.
- The notes are cited by number and label, `Theorem 1.3.43 (\`thm.dassiosZhao\`)`,
  `eq. (1.3.41, \`eq.dzDraws\`)`: the number of the build the entry was written against, and
  the label, which survives renumbering. An unlabelled statement is described, not numbered.
- Outputs are not committed.

`worked_examples_for_final_lecture` is the notebook of the lecture that went through
Sections 6 and 7; their worked solutions repeat it.

## Building, running, testing

From `documentation/tex/questions/`, after the notes:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
grep -icE 'undefined (control sequence|reference|citation)|LaTeX Warning: Reference' main.log   # 0
```

One section alone, under a job name of its own, sharing no `.aux` with another build:

```bash
latexmk -pdf -interaction=nonstopmode -jobname=check-vwap -usepretex='\def\onlytopic{vwap}' main.tex
latexmk -C -jobname=check-vwap
```

From the root of the repository, inside the `unito26` environment:

```bash
python -m pytest tests/test_sample_questions.py
jupyter nbconvert --to notebook --execute --output-dir /tmp notebooks/sample-questions/*.ipynb
```
