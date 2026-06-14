# M3-T001: Migration 0003 — agent job events schema + db.py job methods

## Milestone
M3: Python-first competition worker v0.

## Goal
Extend the Postgres schema to support the M3 worker lifecycle: per-job policy storage,
workspace tracking, per-turn event logging, and decision-to-job linkage.
Extend `tools/kca/db.py` with job CRUD and decision resolution methods.

## Read first
1. `supabase/migrations/0001_init.sql` — `agent_jobs` table, `job_status` enum
2. `supabase/migrations/0002_kca_run_alignment.sql` — migration pattern, idempotency style
3. `tools/kca/db.py` — current public API and `__all__`
4. `docs/milestones/m2/final-review.md` — M3 follow-up list item 2 and 4

## Migration: `supabase/migrations/0003_m3_worker.sql`

Forward-only. Idempotent. No destructive drops.

### 1. Extend `job_status` enum

```sql
ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'paused' AFTER 'running';
```

### 2. Add columns to `agent_jobs`

```sql
ALTER TABLE agent_jobs
  ADD COLUMN IF NOT EXISTS workspace_path text,
  ADD COLUMN IF NOT EXISTS prompt         text,
  ADD COLUMN IF NOT EXISTS model          text NOT NULL DEFAULT 'claude-sonnet-4-6',
  ADD COLUMN IF NOT EXISTS turns_used     int  NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cost_usd       numeric(10,4) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS policy         jsonb NOT NULL DEFAULT '{}';
```

Policy jsonb shape (document in a comment in the migration):
```json
{
  "max_turns": 30,
  "max_cost_usd": 5.0,
  "max_runtime_s": 3600,
  "allowed_tool_patterns": ["kca *", "pytest *"],
  "max_side_effect": "LOCAL_WRITE"
}
```

### 3. Create `agent_job_events`

```sql
CREATE TABLE IF NOT EXISTS agent_job_events (
  id            bigserial PRIMARY KEY,
  job_id        uuid NOT NULL REFERENCES agent_jobs(id) ON DELETE CASCADE,
  event_type    text NOT NULL,
  -- values: turn_start | tool_call | tool_result | approval_pause
  --         approval_resume | budget_stop | done | error
  turn_number   int,
  input_tokens  int,
  output_tokens int,
  cost_usd      numeric(10,4),
  event_data    jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_turn
  ON agent_job_events(job_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_job_events_type
  ON agent_job_events(event_type);

ALTER TABLE agent_job_events ENABLE ROW LEVEL SECURITY;
```

### 4. Link `human_decisions` → `agent_jobs`

```sql
ALTER TABLE human_decisions
  ADD COLUMN IF NOT EXISTS job_id uuid REFERENCES agent_jobs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_human_decisions_job
  ON human_decisions(job_id) WHERE job_id IS NOT NULL;
```

## db.py additions

Add to `__all__` and implement:

```python
def create_job(
    project_id: str,
    prompt: str,
    policy: dict,
    model: str = 'claude-sonnet-4-6',
    competition_slug: str | None = None,
    session_id: str | None = None,
) -> str:
    """Insert a new queued agent_jobs row. Returns job_id (uuid str)."""

def get_job(job_id: str) -> dict:
    """Fetch one agent_jobs row as a dict. Raises KeyError if not found."""

def lease_job(job_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
    """Atomically set status='running', leased_by, leased_until.
    Returns True on success, False if job was already leased/running."""

def update_job(
    job_id: str,
    *,
    status: str | None = None,
    workspace_path: str | None = None,
    turns_used: int | None = None,
    cost_usd: float | None = None,
    error: str | None = None,
    started_at=None,
    finished_at=None,
) -> None:
    """Partial update of agent_jobs columns. Only non-None kwargs are updated."""

def append_job_event(
    job_id: str,
    event_type: str,
    turn_number: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    event_data: dict | None = None,
) -> int:
    """Insert one agent_job_events row. Returns the new event id."""

def list_jobs(status: str | None = None, limit: int = 20) -> list[dict]:
    """List agent_jobs rows, newest first. Filter by status if given."""

def list_pending_decisions(job_id: str | None = None) -> list[dict]:
    """List human_decisions with status='pending'. Filter by job_id if given."""

def resolve_decision(
    decision_id: str,
    resolution: str,   # 'approved' | 'rejected'
    notes: str | None = None,
) -> None:
    """Set human_decisions.status = resolution, decided_at = now(), notes."""
```

## Design constraints
- No async. Parameterised SQL (no f-string user data).
- Importable without a live DB (lazy connection).
- `KCA_DB_TARGET=remote` without `KCA_ALLOW_REMOTE=1` raises `RemoteOperationBlocked`.
- All new functions follow the same error-surface pattern as existing db.py functions.

## Acceptance criteria
- `supabase db reset` (or direct psql apply) succeeds with 0003 added.
- `python -c "from tools.kca import db; print([f for f in db.__all__ if 'job' in f or 'decision' in f])"` lists all 8 new symbols.
- `python -m pytest tests/ -v` — 0 failures (DB tests skip if no env).
- Running `create_job → lease_job → append_job_event → update_job(status='succeeded')` against a live local DB produces consistent rows.

## Stop condition
Stop after 40 turns. If migration apply fails, report the exact psql error and proposed fix.
