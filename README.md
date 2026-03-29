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
