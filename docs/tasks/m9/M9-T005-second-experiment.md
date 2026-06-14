# M9-T005: Second experiment — HGB + feature engineering (local-only)

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Run a second local experiment using `HistGradientBoostingClassifier` with
basic feature engineering. Same CV harness as M9-T002. The deliverable is
an improved CV score recorded against a new `runs` row. **No second
real Kaggle submission** — improvement is measured by CV delta only.

This task assumes **M9-T004 closeout is PASS** (the baseline LB score is
already recorded; we don't need a second LB number to prove improvement).

## Read first

1. M9-T002, M9-T004 closeouts
2. `src/worker/worker.py`, `src/worker/tools.py`
3. `tools/kca/run.py`
4. The baseline run's metadata under
   `runs/spaceship-titanic/baseline-lr/`

## Scope

1. `kca run init --competition spaceship-titanic --name hgb-fe-v1` to
   create a sibling run directory.
2. Drive the worker through a second skill invocation with the agent
   producing:
   - feature engineering: at minimum a categorical-encoded `HomePlanet`,
     `Destination`, `CryoSleep`, plus numeric imputation for
     `Age`/`RoomService`/`FoodCourt`/etc.;
   - `HistGradientBoostingClassifier` baseline with the same CV split
     (same seed, same folds) as M9-T002;
   - CV accuracy recorded via `kca run record-metric`.
3. Produce a `submission.csv` under the new run directory but **do not
   submit**. The file is for completeness, not for Kaggle.

## Non-goals

- No second `kaggle competitions submit`.
- No kernel push, dataset / model upload.
- No deviation from the M9-T002 CV harness — the comparison is only
  valid if the splits match.
- No model search loop (no Optuna sweep, no autoML). One HGB model with
  one feature pipeline.

## Acceptance criteria

- `runs/spaceship-titanic/hgb-fe-v1/submission.csv` exists.
- A new `runs` row with the HGB metric value.
- HGB CV > LR CV (otherwise the milestone fails the M9-T006 assertion).
- `kca run list --json` shows both runs.
- All baseline validation still passes (pytest, ruff, pnpm).

## Permissions

- Local writes only.
- DB write requires `dangerouslyDisableSandbox=true`.
- `git commit` / `git push` deferred to milestone closeout.

## Closeout format

```
M9-T005 closeout
  Run id: <uuid>   name: hgb-fe-v1
  CV metric: <name> = <value>   (delta vs baseline: +<x>)
  Submission staged (no submit): runs/spaceship-titanic/hgb-fe-v1/submission.csv
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T006 ready to start
```

## Stop condition

Stop after 80 turns. If HGB CV does NOT beat LR CV by a meaningful
margin, halt and inspect — likely a CV-split mismatch or a leakage bug.
Do not lower the M9-T006 threshold to fit a weak second experiment.
