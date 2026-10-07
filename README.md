# unito26

Course material for **Python for Finance**, University of Turin, Fall 2026.

The course is on market microstructure: the first half in lectures, the second in laboratory
work on the implementation. The lecture notes carry a second chapter, on option pricing and
volatility trading, as optional reading that is neither taught nor examined. The notes are
the authority; the notebooks and the documentation cite them, not the other way round.

## Setup

Starting from a laptop with nothing installed, follow [`GETTING-STARTED.md`](GETTING-STARTED.md).
With conda and git already in place:

```bash
conda env create -f unito26.yml
conda activate unito26
```

## Structure

```
unito26/
├── data/               # Course datasets (not tracked in git)
├── documentation/      # LaTeX lecture notes and slides
│   └── tex/
├── notebooks/          # Jupyter notebooks for lectures and exercises
├── tests/              # Unit tests
└── unito26/            # Python package
    └── lob/            # Limit order books, LOBSTER data, Hawkes order flow
```

## Assessment

- A **multiple-choice questionnaire**, marked out of 100, pass mark 60. Sample questions
  are published during the course.
- **One optional assignment**, marked out of 50. It is not added to the questionnaire: it
  lowers the pass mark by the points scored, from 60 to as low as 10.
- The assignment is submitted as a **pull request** into this repository. See
  [`CONTRIBUTING.md`](CONTRIBUTING.md).

The notes state all of this in their welcome chapter.

## Running tests

```bash
python -m pytest tests/
```

## Running the notebooks

```bash
conda activate unito26
jupyter notebook
```

Launch Jupyter from inside the environment, not from a base install that merely offers
`unito26` as a kernel. Plotly draws a figure as a custom output type, and the code that
draws it ships with the *server*, not the kernel — so a server from elsewhere leaves
every plot as a blank cell, with no error to explain it.
