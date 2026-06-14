# M5-T006: Model routing per job type

## Milestone
M5: research and browser workflow (M4 follow-up #5).

## Goal
Stop hard-coding `claude-sonnet-4-6` in worker policy. Route models per job
type: Sonnet for implement/experiment, Opus for eval/analysis, Haiku for
log triage. Make the chosen model explicit in job rows and events.

## Read first
1. `src/worker/_types.py` — `JobPolicy.model`
2. `scripts/run_job.py` — `_build_policy`, `_resolve_policy`
3. `docs/adr/0002-hybrid-worker-model-routing.md`
4. `docs/adr/0004-litellm-provider-layer.md`

## Design
1. Introduce `MODEL_ROUTES` in `src/worker/routing.py`:
   ```python
   MODEL_ROUTES = {
       "research":    "claude-haiku-4-5",
       "implement":   "claude-sonnet-4-6",
       "experiment":  "claude-sonnet-4-6",
       "eval":        "claude-opus-4-7",
       "analysis":    "claude-opus-4-7",
       "review":      "claude-opus-4-7",
   }
   def model_for(job_type: str, *, override: str | None = None) -> str:
       return override or MODEL_ROUTES.get(job_type, "claude-sonnet-4-6")
   ```
2. `scripts/run_job.py` gains `--job-type <type>` (default `implement`).
3. `_resolve_policy` calls `routing.model_for(args.job_type, override=args.model)`.
4. New ADR `docs/adr/0010-model-routing.md` documents the routing table,
   how it's overridden per call, and the rationale for Opus on eval/analysis.

## Acceptance criteria
- `python -c "from src.worker.routing import model_for; assert model_for('eval') == 'claude-opus-4-7'; print('PASS')"`.
- `python scripts/run_job.py --prompt p --dry-run --job-type analysis --json | jq -r .model`
  prints an Opus id.
- `--model claude-haiku-4-5` overrides routing for any job type.
- New ADR present and linked from `docs/design-decisions.md`.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 25 turns.
