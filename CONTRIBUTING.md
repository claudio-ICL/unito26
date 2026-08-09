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
   **It must be green** before the PR is merged.

8. **Review.** The lecturer is auto-requested as reviewer (via `CODEOWNERS`). **Only the
   lecturer approves** PRs.

9. **Merge.** Once approved and green, the PR is **squash-merged** and the branch is deleted
   automatically. Then update your local copy:
   ```bash
   git checkout main
   git pull
   ```

## Conventions

- **Package vs notebooks:** put anything you want to import and test in `unito26/`; keep
  teaching narrative and exercises in `notebooks/`.
- **Data is not tracked:** files under `data/` are git-ignored — don't commit datasets.
- **Keep PRs small and focused** — easier to review, easier to merge.

## A note on enforcement

Today the repository is **private on the free GitHub plan**, so the rules above are
**advisory**: GitHub does not yet *block* direct pushes to `main`, *require* the lecturer's
approval, or *require* CI to be green. They become **enforced** once branch protection is
enabled (GitHub Pro on a private repo, or making the repo public). **Please follow the
workflow either way** — it is how the repository is meant to be used, and enforcement will
be switched on before students are given write access.

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
