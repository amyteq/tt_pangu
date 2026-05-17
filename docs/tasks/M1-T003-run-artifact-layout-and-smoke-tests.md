# M1-T003: run artifact layout and smoke tests

## Milestone
M1 / MVP-1: local Kaggle tooling wrapper baseline.

## Goal
Make the local run artifact layout testable and documented. This gives Claude Code and future runtime competition agents a predictable place to store generated code, notebooks, outputs, metrics, logs, research notes, and approval records.

## Read first
1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/tooling/kca-command-spec.md`
5. `docs/tooling/kca-side-effect-levels.md`
6. `tools/kca/` implementation

## Required layout
For a competition slug and run ID:

```text
runs/<competition>/<run_id>/
  run.json
  README.md
  inputs/
  src/
  notebooks/
  outputs/
  submissions/
  metrics/
  logs/
  research/
  analysis/
  approvals/
```

## `run.json` schema v1
Document and test at least these fields:

```json
{
  "schema_version": 1,
  "competition": "smoke-test",
  "run_id": "test-run-001",
  "created_by": "kca",
  "created_at": "<ISO-8601 timestamp>",
  "side_effect_level": "local-write",
  "status": "initialized"
}
```

## Tasks
1. Add or refine `kca runs init` so it creates the required layout.
2. Add `--dry-run` if useful and cheap.
3. Add tests using a temporary directory.
4. Document the run artifact layout.
5. Ensure generated `runs/` artifacts from tests are not committed.

## Expected files to create or update
- `tools/kca/runs.py`
- `tests/test_kca_runs.py`
- `docs/tooling/run-artifact-layout.md`
- `.gitignore` if needed
- `docs/tooling/kca-command-spec.md`

## Acceptance criteria
- `kca runs init` creates exactly the documented directory structure in a temp path.
- `run.json` is valid JSON and contains the required fields.
- The command fails cleanly for invalid competition slug or run ID.
- Smoke tests pass.
- Test artifacts do not pollute the repo.

## Suggested tests

```bash
python -m tools.kca runs init --competition smoke-test --run-id test-run-001 --root /tmp/kca-runs
python -m pytest -q tests/test_kca_runs.py
```

## Non-goals
- Do not implement experiment tracking.
- Do not implement metrics ingestion beyond directory/schema basics.
- Do not write to Supabase.
- Do not submit to Kaggle.

## Stop condition
Stop after 60 turns if there is a conflict with existing repo artifact conventions. Document the conflict and propose a minimal ADR update.
