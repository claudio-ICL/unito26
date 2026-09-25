# How we work on `unito26`

This document describes the development cycle for this repository — for my future self and
for students added as collaborators. The rule of thumb: **nothing reaches `main` directly;
everything goes through a branch and a pull request.**

## One-time setup

```bash
git clone git@github.com:claudio-ICL/unito26.git
cd unito26
conda env create -f unito26.yml     # creates the `unito26` env (installs the package with `pip install -e .`)
conda activate unito26
python -m pytest tests/             # sanity check: tests should pass
git config core.hooksPath .githooks  # strips notebook outputs before they are committed
```

## The development cycle

1. **Start from an up-to-date `main`:**
   ```bash
   git checkout main
   git pull
   ```

2. **Create a branch** — never commit directly to `main`. Use a short, descriptive name,
   e.g. `new-greeks-method`:
   ```bash
   git checkout -b new-greeks-method
   ```

3. **Make your changes.**
   - Reusable, importable code goes in the `unito26/` package.
   - Lectures and exercises go in `notebooks/`.
   - Write the **clear, idiomatic version first** and make sure it is understood; any
     cleverness or optimization comes *after* that, and is explained and reconciled with the idiomatic version first.

4. **Run the tests locally:**
   ```bash
   python -m pytest tests/
   ```

5. **Commit in small, clear steps, then push:**
   ```bash
   git add -A
   git commit -m "Short, descriptive message"
   git push -u origin cb/sabr-calibration
   ```

6. **Open a pull request into `main`:**
   ```bash
   gh pr create --base main --fill
   ```
   (or use the GitHub web UI). The PR template fills in automatically — complete its
   checklist.

7. **CI runs automatically.** The `CI` workflow runs `python -m pytest tests/` on your PR.
   It must be green: a red `pytest` blocks the merge.

8. **Review.** The lecturer is auto-requested as reviewer (via `CODEOWNERS`) and is the only
   one whose approval counts.

9. **Merge.** The lecturer merges — `main` accepts no other author. The PR is
   **squash-merged** and the branch is deleted automatically. Then update your local copy:
   ```bash
   git checkout main
   git pull
   ```

## Submitting an assignment

The course sets two optional assignments, one per chapter, described in the welcome chapter
of the lecture notes. They are submitted through exactly the cycle above: a branch, the
tests run locally, a pull request into `main`, green CI, lecturer review. The submission is
complete when the pull request stands open with CI green — not when the branch is pushed.

Two things specific to an assignment:

- **No data in the pull request.** `data/` is git-ignored, and the LOBSTER sample files are
  downloaded rather than committed. The work must run from a local `data/` that the reviewer
  also has.
- **The analysis goes in a notebook, the reusable parts in the package.** Anything worth
  importing or testing belongs in `unito26/` with a test beside it in `tests/`; the
  narrative, the figures and the numbers belong in a notebook under `notebooks/`.

## Conventions

- **Package vs notebooks:** put anything you want to import and test in `unito26/`; keep
  teaching narrative and exercises in `notebooks/`.
- **Data is not tracked:** files under `data/` are git-ignored — don't commit datasets.
- **Notebook outputs are not tracked** either: the `pre-commit` hook of `.githooks/` strips
  them from what is staged, and from the file on disk with it. A notebook is re-run to see
  its figures again.
- **Keep PRs small and focused** — easier to review, easier to merge.

## What is enforced

The rules above are not advice: a ruleset on `main` enforces them, with the lecturer as the
only actor who may bypass it. On a pull request into `main`,

- the `pytest` check must be green;
- an approving review from a code owner — the lecturer — is required, and is dismissed if
  you push again afterwards;
- the merge is the lecturer's: `main` accepts no update from anyone else, by push or by
  merge, so the button is disabled for you even on a green, approved pull request;
- `main` cannot be force-pushed or deleted, and merges into it are squashes.

## Quick reference

```bash
git checkout main && git pull
git checkout -b cb/my-topic
# ...edit...
python -m pytest tests/
git add -A && git commit -m "..." && git push -u origin cb/my-topic
gh pr create --base main --fill
# CI green + lecturer approval -> squash-merge -> branch auto-deleted
git checkout main && git pull
```
