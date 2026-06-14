# M6-T008: TC-3 Spaceship Titanic — reviewer-gate end-to-end

## Milestone
M6.

## Goal
Add a third end-to-end test case that exercises the reviewer-gate path on
the submission step. Mirrors the TC-1 (binary classification) and TC-2
(regression) shapes but uses synthetic data so no Kaggle credentials or
network are required.

## Read first
1. `docs/testing/competition-test-cases.md` (TC-1, TC-2 layout).
2. `docs/milestones/m4/loop-prompts.md` Loop Prompt 8 (TC-1 structure).
3. `docs/milestones/m5/loop-prompts.md` Loop Prompt 8 (TC-2 structure).
4. `docs/tasks/m6/M6-T004-reviewer-worker.md`.

## Setup
```
TMPCOMP=$TMPDIR/m6test/kaggle-spaceship-titanic
rm -rf "$TMPCOMP"
mkdir -p "$TMPCOMP"/{src/spaceship_titanic,notebooks,kernels,docs/research,runs,artifacts,data}
cd "$TMPCOMP"
git init -q -b main
git config user.email t@t && git config user.name t
echo "# Spaceship Titanic" > README.md
git add . && git commit -q -m init
```

## Baseline script (`src/spaceship_titanic/baseline.py`)
- Synthetic dataset via `sklearn.datasets.make_classification(n_samples=8000,
  n_features=14, n_informative=10, n_classes=2, weights=[0.55, 0.45],
  random_state=42)`. Metric: AUC.
- `LogisticRegression(C=1.0, random_state=42)` 5-fold KFold.
- Submission: 4277 rows (1 header + 4276) with `PassengerId,Transported`
  where `Transported ∈ {True, False}`.

## Iteration script (`src/spaceship_titanic/gbdt.py`)
- Same dataset; `HistGradientBoostingClassifier(random_state=42)`.
- Should beat the logistic baseline AUC.

## Reviewer-gate exercise
- After both runs finish, simulate the submission gate: call
  `scripts/run_job.py --prompt "prepare submission" --require-approval
  kaggle_submit --dry-run --json` against the workspace.
- The reviewer (dry-run mode) returns `approve`. An `agent_reviews` row
  is created with `target_op=kaggle_submit`, `verdict=approve`. The job
  ends `succeeded` without ever calling the real Kaggle API.

## Validation (PASS/FAIL per line)
1. R1 + R2 `meta.json` + `metrics.json` exist.
2. `submission.csv` is 4277 lines for both runs (1 header + 4276 rows).
3. Header is exactly `PassengerId,Transported`.
4. Transported values are all `True` or `False` (no other strings).
5. `cv_auc(R2) > cv_auc(R1)`.
6. `kca review list --job-id <reviewer-job> --json` shows 1 row with
   `verdict=approve` and `target_op=kaggle_submit`.
7. `kca decisions list --json` — no pending items left.
8. `python -m pytest tests/ -v` — 0 failures.

Output `TC-3 SPACESHIP-TITANIC PASS` if all 8 pass.

## Acceptance criteria
All 8 validation lines PASS.

## Stop condition
Stop after 30 turns. If the synthetic data produces a baseline AUC > 0.95
(too easy), drop `n_informative` to 6 so the iteration model has room to
improve.
