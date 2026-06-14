# M5-T008: TC-2 House Prices end-to-end

## Milestone
M5: research and browser workflow (regression test).

## Goal
Validate the multi-experiment feature-engineering loop against a regression
metric (RMSLE). Mirror the TC-1 Titanic structure from M4-T008 but with two
experiments (`baseline` and `+log1p-target`) to exercise comparison.

## Read first
1. `docs/testing/competition-test-cases.md` (TC-2 section)
2. `docs/milestones/m4/loop-prompts.md` Loop Prompt 8 (TC-1 structure)
3. `tools/kca/db.py` — `create_experiment`, `create_run`, `record_metric`

## Setup
- Create competition repo `/tmp/kaggle-house-prices/` with the standard
  `src / notebooks / kernels / docs / runs / artifacts / data` layout.
- Register via `kca competition register --slug house-prices-advanced-regression-techniques`.
- Use `sklearn.datasets.fetch_california_housing` as the stand-in dataset
  (no Kaggle network call). Pretend it is the House Prices schema for the
  test; the goal is the loop, not real LB scores.

## Experiments
1. **`exp/baseline`** — Ridge regression on raw features. Record
   `cv_rmsle`.
2. **`exp/log1p-target`** — same model with `log1p(y)` target. Record
   `cv_rmsle`. Compare against baseline via `kca run list --competition …`.

## Validation checklist
1. `kca competition info --slug house-prices-advanced-regression-techniques --json`
   shows `repo_url` + `local_clone_path`.
2. Two experiments exist via `kca` (or `psql`).
3. Two runs exist, each with `metrics.cv_rmsle` populated.
4. `submission.csv` for the better experiment has the expected schema
   (`Id,SalePrice`, 1459 rows).
5. `cv_rmsle` for `+log1p-target` is **lower** than `baseline`.
6. `kca decisions list --json` shows no pending items.
7. `python -m pytest tests/ -v` — 0 failures.

## Output
Print `TC-2 HOUSE-PRICES PASS` after all 7 checks succeed.

## Stop condition
Stop after 60 turns. If the chosen synthetic dataset doesn't differentiate
the two experiments, switch to seaborn's `mpg` dataset with rmsle on `mpg`.
Document the substitution.
