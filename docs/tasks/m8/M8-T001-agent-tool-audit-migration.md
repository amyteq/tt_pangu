# M8-T001: `agent_tool_audit` migration

## Milestone
M8: UI shell + skill→worker wiring + tool-audit DB table + CI hardening.

## Status
backfilled — original task spec was inlined into `docs/milestones/m8/loop-prompts.md`
Loop Prompt 1; extracted here for the double-layer convention.

## Goal
Add a first-class `agent_tool_audit` table, backfill the M7 JSONL records
into it, and switch the audit writer to dual-write (`JSONL` for offline
ops + DB when `SUPABASE_DB_URL` is set).

## Read first
1. `docs/milestones/m7/final-review.md` (§ M8 follow-up #2)
2. `supabase/migrations/0006_m6_reviews_spans.sql` (style template)
3. `tools/kca/agent/audit.py` (AuditRecord fields + JSONL writer)
4. `tools/kca/db.py` (append_job_event implementation)
5. `docs/architecture/kca-cli-architecture.md` (Audit trail section)

## Scope / Files / Implementation guidance

### Step 1 — Write `supabase/migrations/0007_m8_tool_audit.sql`
```sql
CREATE TABLE IF NOT EXISTS agent_tool_audit (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id  UUID        NOT NULL,
  job_id      UUID        NULL REFERENCES agent_jobs(id) ON DELETE SET NULL,
  skill_name  TEXT        NULL,
  tool_name   TEXT        NOT NULL,
  operation   TEXT        NOT NULL,
  decision    TEXT        NOT NULL CHECK (decision IN ('allow','ask','deny')),
  mode        TEXT        NOT NULL DEFAULT 'default',
  policy_profile TEXT     NOT NULL DEFAULT 'default',
  audit_required BOOLEAN  NOT NULL DEFAULT false,
  args_hash   TEXT        NOT NULL,
  extra       JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX agent_tool_audit_session_idx ON agent_tool_audit(session_id);
CREATE INDEX agent_tool_audit_job_idx     ON agent_tool_audit(job_id);
CREATE INDEX agent_tool_audit_ts_idx      ON agent_tool_audit(ts DESC);

CREATE OR REPLACE VIEW v_agent_tool_audit_recent AS
  SELECT a.*, j.skill_name AS job_skill_name, j.status AS job_status
  FROM agent_tool_audit a
  LEFT JOIN agent_jobs j ON j.id = a.job_id
  ORDER BY a.ts DESC
  LIMIT 200;
```

### Step 2 — Update `tools/kca/db.py`
- Add `def insert_tool_audit(rec: dict) -> None` that INSERTs into
  `agent_tool_audit`. Best-effort: if no DB, return silently.
- Keep `append_job_event(event_type="tool_audit", ...)` working but mark
  it deprecated in a docstring.

### Step 3 — Update `tools/kca/agent/audit.py`
- In `AuditLogger.record`, when `backend in ("db", "both")` AND
  `SUPABASE_DB_URL` is set, call `insert_tool_audit(rec)` in addition
  to writing the JSONL line.
- Never raise on DB failure; log to stderr and continue.

### Step 4 — Optional backfill script
`scripts/backfill_tool_audit.py`:
- Reads `.agent/audit.jsonl`
- Inserts each line into `agent_tool_audit` (de-dup by `(session_id, ts, tool_name)`).
- Idempotent.

Document it in `docs/architecture/kca-cli-architecture.md` § Audit trail.

## Acceptance criteria
DB calls require `dangerouslyDisableSandbox=true`.

- Apply migration:
  ```bash
  psql "$SUPABASE_DB_URL" -f supabase/migrations/0007_m8_tool_audit.sql
  psql "$SUPABASE_DB_URL" -c "\d agent_tool_audit"
  ```
  → table present with all columns
- Writer dual-writes:
  ```python
  from tools.kca.agent.audit import AuditLogger
  import pathlib, json, uuid
  log = AuditLogger(backend='both', file_path=pathlib.Path('.agent/audit.jsonl'))
  rec = log.log_policy_decision(
      tool='bash', operation='bash', decision='ask',
      skill_name='_test_fixture', mode='default',
      policy_profile='permissive-dev',
      args={'cmd': 'echo hi'},
  )
  print('wrote', rec.session_id)
  ```
  Then `psql "$SUPABASE_DB_URL" -c "SELECT count(*) FROM agent_tool_audit;"`
  → at least 1
- `python -m pytest tests/ -v -m "not db"` → 0 failures
- `python -m pytest tests/ -v -m db` → all DB tests pass (with sandbox off)

Report: migration applied, row count, JSONL still present, deprecation note added.

## Stop condition
Stop after 30 turns.
