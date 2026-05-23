-- 0007_m8_tool_audit.sql
-- M8: agent_tool_audit table + recent-audit view.
--
-- Forward-only. Idempotent. Additive. All indexes use IF NOT EXISTS so the
-- migration is safe to re-apply.

CREATE TABLE IF NOT EXISTS agent_tool_audit (
  id              BIGSERIAL PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id      UUID        NOT NULL,
  job_id          UUID        NULL REFERENCES agent_jobs(id) ON DELETE SET NULL,
  skill_name      TEXT        NULL,
  tool_name       TEXT        NOT NULL,
  operation       TEXT        NOT NULL,
  decision        TEXT        NOT NULL CHECK (decision IN ('allow', 'ask', 'deny')),
  mode            TEXT        NOT NULL DEFAULT 'default',
  policy_profile  TEXT        NOT NULL DEFAULT 'default',
  audit_required  BOOLEAN     NOT NULL DEFAULT false,
  args_hash       TEXT        NOT NULL,
  extra           JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS agent_tool_audit_session_idx
  ON agent_tool_audit(session_id);
CREATE INDEX IF NOT EXISTS agent_tool_audit_job_idx
  ON agent_tool_audit(job_id);
CREATE INDEX IF NOT EXISTS agent_tool_audit_ts_idx
  ON agent_tool_audit(ts DESC);

ALTER TABLE agent_tool_audit ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE VIEW v_agent_tool_audit_recent AS
  SELECT
    a.*,
    j.policy AS job_policy,
    j.status AS job_status
  FROM agent_tool_audit a
  LEFT JOIN agent_jobs j ON j.id = a.job_id
  ORDER BY a.ts DESC
  LIMIT 200;
