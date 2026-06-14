# M3-T005: Approval gate pause/resume + `kca decisions` CLI

## Milestone
M3: Python-first competition worker v0.

## Goal
Wire the `ApprovalRequired` exception into `AgentWorker.run()` so that a job pauses
and records a `human_decisions` row when it tries to call a REMOTE_WRITE or SUBMISSION
tool. Add `kca decisions list/approve/deny` so a human can see and resolve pending gates.

## Read first
1. `src/worker/tools.py` — `ApprovalRequired`, `ToolExecutor`, side-effect levels
2. `src/worker/worker.py` — `AgentWorker.run()`, where `ApprovalRequired` is caught
3. `tools/kca/db.py` — `insert_approval_request`, `list_pending_decisions`, `resolve_decision`
4. `tools/kca/kca.py` — subcommand registration pattern
5. `docs/milestones/README.md` — M3 "Worker enforces approval gates"

## Part A: Catch `ApprovalRequired` in `AgentWorker.run()`

Replace the bare `raise` in the tool-use block with:

```python
except ApprovalRequired as exc:
    decision_id = self._record_approval_request(exc)
    self._append_event('approval_pause', budget.turns,
        event_data={'tool': exc.tool_name, 'decision_id': decision_id})
    self._update_status('paused', budget=budget)
    import sys
    print(
        f"JOB PAUSED — tool '{exc.tool_name}' requires approval.\n"
        f"  Run: kca decisions approve --id {decision_id}\n"
        f"  Or:  kca decisions deny --id {decision_id}",
        file=sys.stderr)
    return WorkerResult(
        status='paused', turns_used=budget.turns,
        cost_usd=budget.cost_usd,
        duration_s=time.monotonic() - start,
        final_message=f"awaiting approval: decision_id={decision_id}",
        stop_reason='approval_required')
```

`_record_approval_request` helper:
```python
def _record_approval_request(self, exc: ApprovalRequired) -> str:
    """Insert a pending human_decisions row; return decision_id str."""
    if not self.db_url:
        return "no-db-decision-id"
    try:
        from tools.kca import db
        return db.insert_approval_request(
            session_id=None,
            decision_type='tool_approval',
            prompt=(f"Worker job {self.job_id} wants to call '{exc.tool_name}' "
                    f"(side_effect={exc.side_effect_level})."),
            options={"approve": "allow this tool call once",
                     "deny": "block and stop job"},
            job_id=self.job_id)
    except Exception:
        return "db-error"
```

Note: resume (re-running the paused job with the granted tool call) is out of scope
for M3. A paused job must be manually restarted with an adjusted prompt or policy.
Resume logic is M4+ scope.

## Part B: `kca decisions` CLI

New file `tools/kca/decisions.py`. Register as subcommand group `decisions` in `kca.py`.

### `kca decisions list`
```
kca decisions list [--pending] [--job-id <id>] [--limit 20] [--json]
```
Side effect: READ_ONLY

- Calls `db.list_pending_decisions(job_id=...)`.
- If `--pending` flag, filter to `status='pending'` only (default: all).
- Output: `{"ok": true, "decisions": [{id, decision_type, status, prompt, created_at, job_id}, ...]}`

### `kca decisions approve`
```
kca decisions approve --id <decision_id> [--notes <text>] [--json]
```
Side effect: LOCAL_WRITE

- Calls `db.resolve_decision(decision_id, 'approved', notes=notes)`.
- Output: `{"ok": true, "decision_id": "...", "resolution": "approved"}`

### `kca decisions deny`
```
kca decisions deny --id <decision_id> [--notes <text>] [--json]
```
Side effect: LOCAL_WRITE

- Calls `db.resolve_decision(decision_id, 'rejected', notes=notes)`.
- Output: `{"ok": true, "decision_id": "...", "resolution": "rejected"}`

Add all three to `tools/kca/COMMANDS.md` under a `decisions` section.

## Smoke test (with DB up)

```bash
# 1. Trigger a paused job via dry-run with ApprovalRequired
#    (requires adding a SUBMISSION-level test tool to MockAnthropicClient scenario)
#    OR: directly insert a human_decisions row for testing:

python - <<'EOF'
import os
from tools.kca import db
decision_id = db.insert_approval_request(
    session_id=None,
    decision_type='tool_approval',
    prompt='Test approval request from M3-T005',
    options={"approve": "yes", "deny": "no"},
    job_id=None)
print("Created decision:", decision_id)
EOF

# 2. List pending
python tools/kca/kca.py decisions list --pending --json
# → ok=true, decisions array contains the row

# 3. Approve
python tools/kca/kca.py decisions approve --id <id-from-step-1> --notes "test" --json
# → ok=true, resolution=approved

# 4. Confirm gone from pending
python tools/kca/kca.py decisions list --pending --json
# → decisions array empty (or not contains the row)
```

## Acceptance criteria
- `kca decisions list --pending --json` exits 0 and emits valid JSON with DB up.
- `kca decisions list --pending --json` exits 0 and emits `{"ok": false, "error": "..."}` gracefully when DB is down.
- Approve and deny update `status` in `human_decisions`.
- AgentWorker returns `WorkerResult(status='paused')` when ApprovalRequired is raised.
- `--pending` filtering works correctly.

## Stop condition
Stop after 30 turns.
