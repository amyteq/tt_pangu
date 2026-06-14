# M14-T003: `kca explore {init, run, rank}` + local-screening fan-out (issue #52)

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Implement the exploration-batch lifecycle (ADR-0020 §4 / §5):
mechanically expand a search-space YAML into per-cell experiment dirs,
fan out local screenings, and rank candidates by holdout CV. No Kaggle
push here.

Assumes **M14-T000 / T001 / T002 closeouts are PASS**.

## Read first
1. M14-T000 / T001 / T002 closeouts.
2. `docs/adr/0020-goal-driven-kaggle-loop.md` §4 (search-space) + §5 (batch lifecycle).
3. Issue #52 (acceptance criteria).
4. `experiments/tpu-getting-started/baseline-tl/baseline.py` (the seed template).
5. `scripts/m10_t002_local_train.py`, `scripts/m10_t005_local_train.py` (local-train pattern).
6. `src/worker/worker.py` (worker harness for fan-out).
7. `tools/kca/db.py` (T001 helpers: `set_run_analysis_jsonb`, `get_active_goal`, `create_experiment_run`, `record_metric`).

## Scope
1. `tools/kca/explore.py` exporting `add_parsers(subparsers)`, registered
   from `tools/kca/kca.py`:
   - `kca explore init --competition <slug> --search-space <yaml> [--json]`
     — reads the axes file (ADR-0020 §4), mints `exploration_batch_id`,
     writes `experiments/<comp>/<batch-id>/batch.yaml` + one
     `experiments/<comp>/<run-id>/` per cell (or random sub-sample) with a
     `baseline.py` templated from `seed_template` and a `cell.yaml`
     recording axis values. Creates one `experiment_runs` row per cell with
     `status='planned'` + `analysis_jsonb.exploration_batch_id`. Refuses
     if the goal already has a batch in `init`/`fan-out`/`screen`.
   - `kca explore run --batch <id> [--max-concurrent N] [--json]` — fans
     out local screenings via a process pool with a GPU-memory check
     (N defaults to a VRAM-aware value; 1 / serial on CPU-only with a
     logged warning). Each screening writes `holdout_accuracy`,
     `macro_f1`, `train_seconds` to `experiment_runs.metrics` and flips
     `status='screened'`.
   - `kca explore rank --batch <id> [--json]` — lists screened candidates
     sorted by `holdout_accuracy`, marking which **qualify** (holdout >=
     `goal_screen_threshold`, default 0.90 × `target_lb_score`).
   - `kca explore prune --batch <id>` — GC `status='planned'` runs that
     were never screened (resolves orphan-run accumulation).
2. Search-space expansion: full cross-product by default; deterministic
   `sample: {random: N, seed: S}` sub-sample.
3. `--dry-run` path for tests: generate dirs + rows without real training.

## Non-goals
- No Kaggle push / submit (T004 / T008).
- No idea-sourcing (`propose-next` is T006).
- No smart-polling (T005).
- No new migration (uses T001's `analysis_jsonb`).

## Acceptance criteria
- `kca explore init --search-space <yaml> --json` against a 3×2×2 fixture
  generates 12 cells (full product) and 12 `experiment_runs` rows with
  `analysis_jsonb.exploration_batch_id` set; `sample: {random: 4}`
  generates exactly 4, deterministically (same seed → same cells).
- A second `init` while a batch is active refuses
  (`{"ok": false, "error": "ACTIVE_BATCH_EXISTS"}`).
- `kca explore run --batch <id> --dry-run --json` records
  `holdout_accuracy` / `macro_f1` / `train_seconds` and flips status to
  `screened` for each cell, with NO real training and NO Kaggle call.
- `kca explore rank --batch <id> --json` lists the cohort sorted by
  holdout with a `qualifies: bool` per cell.
- `kca explore prune` removes only `planned` runs.
- Audit-grep: 0 lines reach `kaggle kernels push` / `kaggle competitions submit`.
- `ruff check .` / `ruff format --check .` clean; no pytest regressions.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/explore.py`, `tools/kca/kca.py` (registration),
  `src/worker/` integration for fan-out (read/extend, not rewrite),
  `tests/fixtures/<comp>/search-space*.yaml`, `experiments/<comp>/**` (generated).
- FORBIDDEN: `tools/kca/kg.py`, `supabase/migrations/**`,
  `tools/kca/db.py` schema changes.

## Permissions
- LOCAL_WRITE (Supabase + filesystem) — ALLOWED.
- No real Kaggle / LLM. `git add` deferred to T009.

## Closeout format
```
M14-T003 closeout
  CLI: kca explore init/run/rank/prune — registered; `kca explore --help` prints verbs
  Search-space: 3x2x2 fixture -> 12 cells (full); random sample deterministic
  Fan-out: dry-run records holdout/macro_f1/train_seconds; status planned->screened
  Rank: cohort sorted by holdout with qualifies flag
  ACTIVE_BATCH_EXISTS refusal: verified
  Audit-grep: 0 real Kaggle lines
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M14-T004 (multi-push concurrency enforcement)
```

## Related issues
- #52 (parallel exploration with local GPU screening).

## Stop condition
Stop after 80 turns. HALT and ask if:
- The GPU-memory check cannot bound `--max-concurrent` safely on the
  target host — fall back to serial and log, do not OOM.
- The seed `baseline.py` template cannot be parameterised by the axis set
  without rewriting the M10 baseline — surface and ask.
