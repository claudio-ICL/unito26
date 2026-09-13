# unito26

Course material for **Quantitative Finance and Option Pricing Models**,
University of Turin, 2026.

## Setup

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
    ├── constants.py    # Project paths
    ├── utils.py        # Shared utilities (BSM helpers, etc.)
    ├── models/         # Pricing models (Black-Scholes, binomial, etc.)
    └── pricers/        # Pricing engines
```

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
