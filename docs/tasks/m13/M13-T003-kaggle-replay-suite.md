# M13-T003: Kaggle classic-practice replay suite (offline fixtures)

## Milestone
M13: evaluation, reliability, and regression suite.

## Goal
Add three offline Kaggle replays — Titanic, Spaceship Titanic,
House Prices — each reading a frozen sub-sample of the training
CSV and executing a deterministic baseline (LR or LR-equivalent),
recording local CV / RMSLE into `eval_results`. No real Kaggle
network. No real Anthropic call by default (the optional `--route`
flag defers to T006).

This task assumes **M13-T002 closeout is PASS**.

## Read first

1. M13-T000, M13-T001, M13-T002 closeouts.
2. `docs/tasks/m4/M4-T008-tc1-titanic-end-to-end.md` (Titanic precedent).
3. `docs/tasks/m5/M5-T008-tc2-house-prices.md` (House Prices RMSLE
   precedent).
4. `docs/tasks/m9/M9-T002-baseline-loop.md` (Spaceship Titanic LR
   baseline precedent — CV 0.79144 ±0.0086 in M9 final review).
5. `tests/test_m9_e2e.py` (closest dry-run replay pattern).
6. `runs/spaceship-titanic/` (existing M9 run artefacts — the
   replay should match their shape, not re-create them).
7. `tools/kca/eval/suites/tool_smoke/` (the T002 driver shape).
8. `docs/architecture/eval-regression-suite.md` (per-suite metric
   contract).

## Scope

1. **Fixtures under `tests/fixtures/`** — frozen sub-samples (≤ ~5 MB
   each), checked into git:
   - `tests/fixtures/titanic/train.csv` — first ~200 rows of the
     real Titanic train.csv, same columns.
   - `tests/fixtures/spaceship-titanic/train.csv` — first ~200 rows
     of the real Spaceship Titanic train.csv. Reuse the existing
     M9 fixture if present.
   - `tests/fixtures/house-prices/train.csv` — first ~200 rows
     (note: this is enough rows for a CV harness to run; not enough
     for realistic scores — that's by design, M13 baselines values
     and is not chasing leaderboard quality).

2. **Three suite modules** under `tools/kca/eval/suites/`:
   - `kaggle_replay_titanic/` — logistic regression on a fixed
     feature set; records `cv_accuracy_mean`, `cv_accuracy_std`,
     `holdout_accuracy`, `fit_time_ms`.
   - `kaggle_replay_spaceship_titanic/` — LR mirror of M9-T002's
     baseline; records same keys.
   - `kaggle_replay_house_prices/` — LR / Ridge mirror of M5-T008;
     records `cv_rmsle_mean`, `cv_rmsle_std`, `holdout_rmsle`,
     `fit_time_ms`.

3. **Determinism.** Each replay seeds `random.seed(0)` +
   `numpy.random.seed(0)` + `sklearn` `random_state=0`. Two
   consecutive runs against the same fixture must produce
   byte-identical `metrics` JSON.

4. **No real Kaggle.** Replays read CSVs from
   `tests/fixtures/<comp>/` — they never call `kaggle competitions
   download`, `kaggle competitions files`, or any `kaggle` CLI.
   Inherit the M10-T007 audit-grep sentinel.

5. **Route plumbing.** The `--route` flag is wired but defaults to
   `mocked`. When `--route mocked` is selected, no LLM call is made
   — the baseline is pure sklearn / pandas. When `--route claude_*`
   is selected, the suite defers to T006's harness (this task does
   not implement T006; the wiring is just an interface stub that
   raises `NotImplementedError` for now, to be filled in T006).

6. **Wire into `kca eval run`.** After T003:
   - `kca eval list --json` shows three new suites
     (`kaggle-replay-titanic`, `kaggle-replay-spaceship-titanic`,
     `kaggle-replay-house-prices`).
   - `kca eval run --suite kaggle-replay-spaceship-titanic --route
     mocked --dry-run --json` exits 0, creates one `eval_runs` row,
     inserts one `eval_results` row per case (default: a single
     `baseline_lr` case per suite).

## Non-goals

- No real Kaggle network calls. None.
- No LLM calls in `--route mocked` (the default).
- No new top-level CLI subcommands.
- No model-route comparison — that's T006.
- No tuning the baseline to a specific score target. M13 baselines
  values; future milestones decide on score-delta gates.
- No notebook/kernel path — that's T004.

## Acceptance criteria

- Three fixtures under `tests/fixtures/<comp>/` exist; total size
  ≤ ~15 MB combined; the CSVs parse via `pandas.read_csv`.
- Three suite modules registered; `kca eval list --json` shows
  five suites total (tool-smoke + three Kaggle replays + the
  T001 placeholder count).
- Each replay run produces ≥1 `eval_results` row with the metric
  keys listed in scope step 2.
- Determinism check: 2 consecutive runs produce byte-identical
  `metrics` JSON per case.
- Audit-grep guard PASSes: 0 lines for the four forbidden Kaggle
  CLI commands.
- `ruff check .` + `ruff format --check .` clean.
- `pytest tests/ services/decision_api/tests` — 0 regressions vs
  T002 baseline.

## Permissions

- `git add` / `git commit` deferred to milestone closeout.
- Force-add allowed for the small CSV fixtures if `.gitignore`
  excludes them (verify; the `data/` directory is gitignored but
  `tests/fixtures/` is not — fixtures belong under
  `tests/fixtures/`).
- No Kaggle / LLM calls.

## Closeout format

```
M13-T003 closeout
  Fixtures: tests/fixtures/titanic/train.csv (<n1> rows, <s1> KB), tests/fixtures/spaceship-titanic/train.csv (<n2> rows, <s2> KB), tests/fixtures/house-prices/train.csv (<n3> rows, <s3> KB)
  Suites: kaggle-replay-titanic, kaggle-replay-spaceship-titanic, kaggle-replay-house-prices (all v0.1.0)
  Metric snapshot (route=mocked, fixture rows only — not LB-comparable):
    titanic: cv_accuracy_mean=<a>, cv_accuracy_std=<b>
    spaceship-titanic: cv_accuracy_mean=<a>, cv_accuracy_std=<b>
    house-prices: cv_rmsle_mean=<c>, cv_rmsle_std=<d>
  Determinism check: 2 consecutive runs — byte-identical metrics: YES
  Audit-grep guard: 0 lines matching forbidden Kaggle CLI commands
  pytest: <X> passed / <Y> skipped (0 regressions)
  ruff check + ruff format --check: clean
  Acceptance: PASS
  Next: M13-T004 (notebook/kernel dry-run regression)
```

## Related issues

- M13 proposal issue.

## Stop condition

Stop after 80 turns. HALT and ask if:
- Any fixture sub-sample is missing required columns and the
  baseline cannot fit a model. Re-cut the fixture with a fixed
  seed so the column distribution is reasonable.
- Determinism check FAILs — investigate the non-deterministic
  source (often: hash-randomization, unordered dict iteration,
  scikit-learn version drift).
- A replay accidentally reaches the kaggle CLI — surface as a P0.
