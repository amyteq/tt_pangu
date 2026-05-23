# M9-T002: Worker baseline LR loop → submission.csv

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Drive the M3 AgentWorker through a complete baseline experiment loop for
Spaceship Titanic: research → baseline LogisticRegression → cross-validation
→ `submission.csv`. The result is a *staged* submission file and a CV
score recorded in the `runs` table. **No** real Kaggle submission.

This task assumes **M9-T000 and M9-T001 closeouts are PASS**.

## Read first

1. M9-T001 closeout
2. `src/worker/worker.py`, `src/worker/budget.py`, `src/worker/tools.py`,
   `src/worker/reviewer.py`, `src/worker/routing.py`
3. `tools/kca/run.py` (run-init + record-metric)
4. `tools/kca/skill.py` (`kca skill run --execute`)
5. `.kca/skills/kaggle-experiment-loop/SKILL.md`
6. `supabase/migrations/0005_m5_research_citations.sql`,
   `supabase/migrations/0006_m6_reviews_spans.sql`
7. `docs/architecture/kca-cli-architecture.md`

## Submission-format note

**Spaceship Titanic accepts CSV submissions only** (`PassengerId,Transported`).
The current `tools/kca/kg.py::cmd_submit` is format-agnostic — it shells
out to `kaggle competitions submit -c <slug> -f <file> -m <msg>` with the
file path verbatim, and lets the Kaggle server validate the format. KCA
does **not** read competition rules at runtime to confirm the expected
submission format or pick between `submit` (CSV / zip) and `push` (kernel
notebook).

For M9 this is acceptable because Spaceship Titanic is a CSV competition.
For other competitions (code competitions → kernels via `kca kaggle push`;
some CV competitions → `submission.zip`; some structured competitions →
JSON), the executor must know the format up front; KCA will not auto-detect.

A follow-up issue tracks adding runtime format awareness to KCA
(see `area:kaggle` / `type:feature` issues filed alongside this milestone).
That work is **not** in scope for M9-T002 or any other M9 task — M9 uses
the existing `submit` surface and assumes CSV for Spaceship Titanic.

## Scope

1. `kca run init --competition spaceship-titanic --name baseline-lr` to
   create a run artifact directory under
   `runs/spaceship-titanic/baseline-lr/`.
2. Execute the kaggle-experiment-loop skill via
   `kca skill run kaggle-experiment-loop --execute --arg metric=Accuracy`
   (or equivalent — match the skill's declared arguments).
3. Inside the worker, produce:
   - a brief research summary citing competition page + 1–2 forum
     references (M5 surface);
   - a baseline `LogisticRegression` model trained on `train.csv` with
     a deterministic CV split (seed pinned, recorded in the run meta);
   - CV accuracy recorded via `kca run record-metric` (writes to `runs`).
4. Produce `runs/spaceship-titanic/baseline-lr/submission.csv` matching
   the `sample_submission.csv` schema (`PassengerId`, `Transported`).
5. Quick sanity validation: row count == test.csv row count; columns
   match sample; values are booleans (or 0/1).

## Non-goals

- Do not call `kca kaggle submit`. The submission file is *staged* only.
- Do not push a kernel.
- Do not iterate beyond the baseline within this Loop Prompt — feature
  engineering and HGB are M9-T005.
- Do not call the real Anthropic API outside skill-declared paths; if the
  worker is run with `--dry-run`, that's acceptable — record the
  dry-run flag in the closeout.

## Acceptance criteria

- `runs/spaceship-titanic/baseline-lr/submission.csv` exists.
- A row in `runs` references the baseline run with a recorded CV metric.
- Sanity validation passes (row count, column names, value types).
- `kca run list --competition spaceship-titanic --json` shows the run.
- All baseline validation still passes (pytest, ruff, pnpm).

## Permissions

- Local writes under `runs/`, `data/`, and `artifacts/` are allowed.
- DB writes (`runs`, `agent_telemetry_spans`) require `dangerouslyDisableSandbox=true`.
- No real Kaggle / Anthropic API outside dry-run.
- `git commit` / `git push` deferred to milestone closeout.

## Closeout format

```
M9-T002 closeout
  Run id: <uuid>
  CV metric: <name> = <value>  (seed: <int>; folds: <n>)
  Submission: runs/spaceship-titanic/baseline-lr/submission.csv
    rows: <n>   columns: PassengerId, Transported   dtype OK: YES | NO
  Worker mode: dry-run | live  (must match approval status)
  Acceptance: PASS | FAIL — link to issue
  Next: M9-T003 ready to start
```

## Stop condition

Stop after 80 turns. If CV is suspiciously high (≥ 0.95) or low (< 0.70),
halt and ask — likely a data-leakage or schema bug, not a model bug.
