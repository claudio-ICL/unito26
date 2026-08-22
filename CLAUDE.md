# CLAUDE.md

Context for working with Claude on this repository.

## About the project

`unito26` holds the material for a **"Python for Finance"** course at the
**University of Turin, fall 2026**. The author is a practising quant (industry
background), and the aim is a modern, industry-flavoured take on the subject.

## Audience

University students. Assume solid mathematical maturity. Material should be readable and self-contained, favouring clear,
idiomatic Python. Coding cleverness and optimization should be taught, and come after the clear idiomatic implementation is fully understood.

## About the course *(background)*

Recorded here as context, not as working instructions:

- The angle is a "fresh perspective from industry". With code assistants and
  LLMs now widespread, the edge is shifting from *writing* working code toward
  **judgment** — making the right choices, evaluating what an assistant
  proposes, and steering it well.
- Because of this, the exam is moving from a coding project to a
  **multiple-choice format**: students read code snippets and judge what they
  do and which is best for a given purpose.
- Planned distinctive content includes the **SABR model** (the option-desk
  standard) and an introduction to **market microstructure**.

See `dev-context/` for the per-topic development notes.

## Repo layout

```
unito26/
├── CLAUDE.md            # this file
├── dev-context/         # development-context notes, one per topic strand
│   ├── sabr.md
│   └── market-microstructure.md
├── data/                # course datasets (not tracked in git)
├── documentation/tex/   # LaTeX lecture notes and slides
├── notebooks/           # Jupyter notebooks for lectures and exercises
├── tests/               # unit tests
└── unito26/             # Python package (reusable code)
```

## Environment & commands

```bash
conda env create -f unito26.yml   # first-time setup
conda activate unito26
python -m pytest tests/           # run tests
```

- Python >= 3.12.
- Core stack: numpy, scipy, pandas, matplotlib, pyarrow, scikit-learn.

## Conventions

- Everything is in **Python**.
- Lectures and exercises live as **notebooks** in `notebooks/`; reusable,
  tested code lives in the **`unito26`** package.
- Add modules to `unito26/__init__.py` as they are actually built.

## Workflow

- Course material is developed on the **`lecturer`** branch and merged into
  `main` once reviewed. Don't commit or push unless asked.



## Writing

LaTeX lecture notes and slides live in `documentation/tex/` — one notes book, one slide
deck, files named after their topic. Before writing or editing any `.tex` file, invoke the
**`writing-in-tex`** skill: it carries the house style (derived from Claudio's thesis), the
shared notation, and the templates for adding a chapter.
