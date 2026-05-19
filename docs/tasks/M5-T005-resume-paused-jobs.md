# M5-T005: Resume paused jobs after approval

## Milestone
M5: research and browser workflow (M4 follow-up #4).

## Goal
After `kca decisions approve <id>`, `scripts/run_job.py --job-id <uuid>`
should pick up the existing job at the boundary where it paused, instead of
re-running from turn 0.

## Read first
1. `scripts/run_job.py` — current `--job-id` path
2. `src/worker/worker.py` — `AgentWorker.run()` pause/resume hooks
3. `tools/kca/decisions.py` — `cmd_approve`
4. `docs/adr/0006-configurable-approval-gates.md` — pause/resume contract
5. `supabase/migrations/0003_m3_worker.sql` — `agent_job_events` table

## Design
1. When a worker hits `ApprovalRequired`:
   - Persist a `paused` row in `agent_jobs` with `last_turn` already in `turns_used`.
   - Append an `approval_pause` `agent_job_events` row carrying the operation
     name, the tool input that triggered it, and the resulting
     `human_decisions.id`.
2. When `kca decisions approve <id>` runs:
   - Resolve the decision row to a `job_id`.
   - Append an `approval_resume` event with the decision_id.
3. `scripts/run_job.py --job-id <uuid>` (no `--prompt`):
   - Load the job + payload.
   - Walk `agent_job_events` to compute `(turns_used, cost_usd, last_messages)`.
   - Hand them to `AgentWorker` so its budget tracker starts from the
     remaining budget, not zero.
   - Re-attempt the originally blocked tool call as the first turn. If the
     latest event is `approval_resume`, treat the gate as one-shot bypassed
     for that exact `tool_input`.

## CLI
```
scripts/run_job.py --job-id <uuid> --json
   → exit 0 (done) | 1 (failed) | 2 (paused again on a different op)
```

## Acceptance criteria
- Manual flow:
  1. Start a dry-run job that calls a gated op → `status=paused`, exit 2.
  2. `kca decisions list --json` returns the pending row.
  3. `kca decisions approve --id <id>`.
  4. `scripts/run_job.py --job-id <uuid> --dry-run --json` → `status=done`.
- `agent_job_events` contains `approval_pause` → `approval_resume` → `done`
  in order.
- `turns_used` after resume equals total turns across both invocations.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 50 turns. If event-replay turns out fragile, fall back to a
"resume = re-prompt + skip first gate" strategy and ADR-document it.
