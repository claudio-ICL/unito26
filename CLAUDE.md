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
jupyter notebook                  # from inside the env: plotly renders server-side
```

- Python >= 3.12.
- Core stack: numpy, scipy, pandas, pandera, matplotlib, plotly, pyarrow, scikit-learn.

## Conventions

- Everything is in **Python**.
- Lectures and exercises live as **notebooks** in `notebooks/`; reusable,
  tested code lives in the **`unito26`** package.
- Add modules to `unito26/__init__.py` as they are actually built.
- Before writing or reviewing code on limit order books or market microstructure,
  invoke the **`market-microstructure`** skill: it carries the notation, the mechanics
  and the invariants fixed in
  [`documentation/order-driven-markets-notation.md`](documentation/order-driven-markets-notation.md).
- Before writing or reviewing code or prose on point processes, Hawkes self-excitation or
  the synthetic order-flow generator, invoke the **`point-processes`** skill: it carries the
  notation, the invariants and the statistical traps fixed in
  [`documentation/point-processes-and-hawkes.md`](documentation/point-processes-and-hawkes.md).

### Python style

- **Few comments.** A comment earns its place only when it is essential to understanding
  the code *and* will still be true and useful to someone meeting the file cold in a year.
  Not restating what a line does, not narrating a decision, not defending a rejected
  alternative, not marking what changed. The code says what it does; a comment is for what
  it cannot say — an invariant, a sign convention, a "why this and not the obvious thing".
- **Never use `*` in a function signature.** Where two arguments of the same type could be
  swapped, give them distinct types (`NewType`) rather than forcing keywords.
- **Default arguments only for genuinely superfluous parameters** — a random generator the
  caller may not want to seed. A parameter that changes what the function *means* is
  required.
- **A serialized type owns its own serialization**: a `schema()` returning the pandera
  schema, a `to_frame`/`from_frame` pair, and the record and JSON forms inherited from
  `unito26.lob.frames.FrameSerializable`. The round trip is tested.
- **Model parametrizations ship as frozen dictionaries**, never as code that computes a
  "default". A default invites a reader to skip the choice, and the choice is usually the
  subject.

## Workflow

- Don't commit or push unless asked.



## Writing

LaTeX lecture notes and slides live in `documentation/tex/` — one notes book, one slide
deck, files named after their topic. Before writing or editing any `.tex` file, invoke the
**`writing-in-tex`** skill: it carries the house style (derived from Claudio's thesis), the
shared notation, and the templates for adding a chapter.



## How I want you to write

The default output of a coding assistant is journalistic, verbose, inelegant and
transient. Those are the four things to avoid here. The register is the one that shows
first; transience is the one that costs most.

**Register.** The register is the classroom: precise, dry, to the point, claims made
softly. Not journalism — no "which is a gift", no "the summit this strand points at", no
flourish where a statement will do. Not knowingness — no "and that is not luck", no
"impostor", no rhetorical questions, no exclamation marks, no addressing the reader as
though correcting them. State the thing; if it needs a qualification, qualify it; if it
does not survive being read aloud in a lecture, it does not belong in the file.

**Verbose.** I value conciseness: say it once and stop. Do not over-explain and do not
over-do. If I want something expanded, I will ask for a follow-up — so between two
correct explanations, give me the shorter one.

**Inelegant.** This one is subjective, but: be a mathematician with a sweet tooth for
aesthetics. One idea per definition, no special case that a better formulation would
remove, and names taken from the notation rather than invented alongside it.

**Transient.** Code, comments in code and paragraphs in the lecture notes tend to
*answer a prompt*. What you write makes sense in the context of our conversation and
ages very badly as soon as that conversation is lost. So: no "as requested", no note on
what changed, no defence of the alternative that was rejected. Write for someone meeting
the file for the first time, a year from now. Only write things that will endure.
