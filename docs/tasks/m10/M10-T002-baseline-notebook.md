# M10-T002: Baseline notebook → local CV / holdout (`tpu-getting-started`)

## Milestone
M10: live end-to-end regression test — Petals to the Metal.

## Goal
Drive the AgentWorker through one baseline image-classification
experiment for Petals to the Metal. Produce a runnable notebook + a
local CV / holdout score recorded in `experiment_runs`. No real Kaggle
push; that's M10-T004.

This task assumes **M10-T000 and M10-T001 closeouts are PASS**.

## Read first

1. M10-T000, M10-T001 closeouts
2. `src/worker/worker.py`, `src/worker/budget.py`, `src/worker/tools.py`
3. `tools/kca/run.py`
4. `tools/kca/skill.py`
5. The `kg-nb` skill SKILL.md (`.kca/skills/kg-nb/` or
   `.claude/skills/kg-nb/`)
6. The `kaggle-experiment-loop` skill SKILL.md
7. `docs/tasks/m9/M9-T002-baseline-loop.md` (the CSV-baseline precedent)
8. `docs/milestones/m9/final-review.md` (note: M9 used `.claude/skills/kaggle-
   experiment-loop/` rather than `.kca/skills/...` because the loader
   only sees the former — same posture here unless that follow-up
   has landed)
9. `data/tpu-getting-started/manifest.json` (from M10-T001)

## Scope

1. Drive a worker job (`kca skill run kaggle-experiment-loop --execute`
   or equivalent) through one baseline experiment:
   - **Backbone:** small pretrained ImageNet model (e.g. MobileNetV2 or
     EfficientNetB0). Choose deterministically (record the choice in
     the closeout).
   - **Image size:** 192x192 by default (smallest variant — fastest
     local iteration). If 192 is unavailable, fall back to the next
     smallest the manifest reports.
   - **Train / val split:** the spec's recommended local split (the
     competition publishes train / val TFRecords separately; use them
     as-is and report holdout accuracy on val).
   - **Optimizer / epochs:** Adam, default learning rate, ≤ 5 epochs
     for the local sanity run. Local training is for the CV / holdout
     evidence, not for SOTA. The Kaggle kernel runner in M10-T004 will
     re-train (or load the same weights) on Kaggle's hardware.
   - **Random seed:** pinned per spec convention (default `seed=42`).
2. Author the kernel-runnable notebook at
   `runs/tpu-getting-started/baseline-tl/baseline.ipynb` (or generate
   it via the `kg-nb` skill from a percent-format `.py`).
3. Author the matching `runs/tpu-getting-started/baseline-tl/kernel-
   metadata.json` that `kca kaggle push` will use in M10-T004:
   ```json
   {
     "id": "<kaggle-username>/petals-baseline-tl",
     "title": "Petals Baseline (transfer learning)",
     "code_file": "baseline.ipynb",
     "language": "python",
     "kernel_type": "notebook",
     "is_private": true,
     "enable_gpu": true,
     "enable_tpu": false,
     "enable_internet": false,
     "competition_sources": ["tpu-getting-started"]
   }
   ```
   (Final field set follows `kaggle kernels init` output; document any
   deviation in the closeout.)
4. Record the local CV / holdout score in `experiment_runs` via
   `kca run`. Metric name: `holdout_accuracy` (and/or `macro_f1` if
   the competition's scoring requires it — Petals to the Metal scores
   on macro F1, so record both if feasible).
5. Verify the notebook executes locally end-to-end at least once
   (e.g. `jupyter nbconvert --to notebook --execute` on a stub run
   with reduced epochs), to catch import errors before the live push.

## Non-goals

- Do not run `kca kaggle push` / `submit` / `upload`.
- Do not invent new top-level `kca` subcommands.
- Do not train for hours — local is for sanity, not LB chasing.
- Do not embed credentials or `KAGGLE_USERNAME` literals in the
  notebook; the kernel runner provides them.
- Do not download the full Petals to the Metal dataset locally; use
  a slice (M10-T001 manifest references) or the small variants only.

## Acceptance criteria

- `runs/tpu-getting-started/baseline-tl/baseline.ipynb` exists and
  executes top-to-bottom locally (or on Colab/Jupyter — capture the
  evidence in the closeout).
- `runs/tpu-getting-started/baseline-tl/kernel-metadata.json` exists
  and validates against `kaggle kernels init` schema (parseable; all
  required keys present).
- A row in `experiment_runs` references the baseline run with a
  recorded metric (`holdout_accuracy` and/or `macro_f1`).
- `kca run list --competition tpu-getting-started --json` shows the
  run.
- Sanity: holdout accuracy is in a safe band (0.30 < acc < 0.99 — a
  trivially-trained backbone should clear 0.30; an accuracy of 1.0
  smells like a leakage bug).
- All baseline validation still passes (pytest, ruff, pnpm where
  available). 0 new regressions vs the M10-T001 baseline.
- The notebook does NOT call `kaggle kernels push` from inside its
  own cells (defense-in-depth: kernel pushing happens via the CLI in
  M10-T004, never from the notebook itself).

## Permissions

- `git commit` and `git push` deferred to milestone closeout.
- The notebook is the deliverable; it lives under `runs/` which is
  gitignored. `kernel-metadata.json` is the small file that gets
  staged (force-add) so M10-T004 can reuse it.
- No real Kaggle write calls.

## Closeout format

```
M10-T002 closeout
  Run id: <experiment_run_id> (external: baseline-tl)
  Backbone: <MobileNetV2 | EfficientNetB0 | ...>
  Local metric: holdout_accuracy = <0.xxxx>  (image_size=<192|224|...>, epochs=<n>, seed=<42>)
                macro_f1         = <0.xxxx>  (if computed)
  Notebook: runs/tpu-getting-started/baseline-tl/baseline.ipynb
            (executes top-to-bottom locally: YES | NO — evidence link)
  Kernel metadata: runs/tpu-getting-started/baseline-tl/kernel-metadata.json
                   (parses against `kaggle kernels init`: YES | NO)
  Worker mode: dry-run (no live API; no real Kaggle push invoked)
  Acceptance: PASS | FAIL — link to issue
  Next: M10-T003 ready to start
```

## Related issues

- #12 — M10 proposal
- #7 — KCA submission-format awareness. M10-T002 hard-codes "this is a
  notebook competition" via the kernel-metadata path; #7 is the
  generalisation. Do not implement #7 here.
- #16 — `reviewer_decision` event_type wording drift. Use whatever
  literals the worker emits today; do not block on closing #16.

## Stop condition

Stop after 80 turns. If the notebook fails to execute locally with
an import error after 5 retries, halt and ask. If the holdout
accuracy is < 0.30 (worse than random for a 104-class task) or > 0.99,
halt and ask — both signal a setup or leakage bug.
