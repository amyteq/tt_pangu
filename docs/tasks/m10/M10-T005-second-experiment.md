# M10-T005: Second experiment (alt backbone or augmentation), local-only

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Run a second local experiment that varies a single axis (different
backbone OR added augmentation policy), with the same local CV /
holdout harness as M10-T002. Local only — no second real Kaggle
kernel push.

This task assumes **M10-T002 and M10-T004 closeouts are PASS**.

## Read first

1. M10-T002 (baseline) and M10-T004 (LB recorded) closeouts
2. `tools/kca/run.py`
3. `src/worker/`
4. `docs/tasks/m9/M9-T005-second-experiment.md` (the HGB+FE precedent)

## Scope

1. Pick ONE axis to vary, deterministic and documented:
   - Either swap the backbone (e.g. MobileNetV2 → EfficientNetB0 or
     EfficientNetB3), OR
   - Add an augmentation policy (e.g. RandAugment, Mixup, or simple
     flip+crop+color-jitter) on top of the baseline backbone.
   - Pick one. Don't combine — the goal is a clean delta.
2. Re-use the local training harness from M10-T002 (same image size,
   same epochs, same seed). Only the chosen axis changes.
3. Record the new run in `experiment_runs` via `kca run`. External
   name: `alt-backbone-v1` or `aug-randaug-v1` (match the axis you
   picked).
4. Emit a fresh notebook + kernel-metadata.json under
   `runs/tpu-getting-started/<name>/` so future iterations can push
   them if scope ever widens — but **do NOT push** them in M10.
5. Sanity: local CV / holdout should be ≥ the baseline's. If lower,
   surface as a soft blocker — don't iterate forever; note the gap
   and report.

## Non-goals

- No `kca kaggle push` / `submit` / `upload`.
- Don't vary more than one axis.
- Don't tune hyperparameters extensively — this is one-shot.
- Don't re-run M10-T004's real push for the new experiment.

## Acceptance criteria

- `runs/tpu-getting-started/<alt-name>/baseline.ipynb` (or percent-
  format `.py`) exists.
- `runs/tpu-getting-started/<alt-name>/kernel-metadata.json` exists
  and parses (even though it's not pushed in M10).
- A new row in `experiment_runs` references the second run with a
  recorded metric.
- New CV / holdout ≥ M10-T002 baseline (PASS) OR a documented
  reason for the regression (PASS-with-note). Hard FAIL only if the
  metric drops by > 10 percentage points without explanation.
- `kca run list --competition tpu-getting-started --json` shows both
  runs.
- All baseline validation still passes (pytest, ruff, pnpm where
  available).

## Permissions

- `git commit` and `git push` deferred to milestone closeout.
- No real Kaggle calls.

## Closeout format

```
M10-T005 closeout
  Run id: <experiment_run_id>   name: <alt-backbone-v1 | aug-randaug-v1>
  Axis varied: <backbone | augmentation>
  Local metric: holdout_accuracy = <0.xxxx>  (delta vs baseline: <±0.xxxx>)
                macro_f1         = <0.xxxx>  (if computed; delta if computed for baseline)
  Notebook staged (NOT pushed): runs/tpu-getting-started/<alt-name>/baseline.ipynb
  Acceptance: PASS | FAIL — link to issue
  Next: M10-T006 ready to start
```

## Related issues

- #12 — M10 proposal
- #7 — KCA submission-format awareness; second-experiment notebook
  uses the same notebook+metadata shape as the baseline.

## Stop condition

Stop after 80 turns. If the alt-axis configuration won't train
(import errors, OOM, dataset incompatibility) after 3 retries, halt
and ask — do not silently widen the axis.
