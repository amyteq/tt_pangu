-- 0008_m11_ctf.sql
-- M11: authorized CTF / lab workflow — event / challenge / attempt schema.
--
-- Forward-only. Idempotent. Additive. All indexes use IF NOT EXISTS so the
-- migration is safe to re-apply.
--
-- Tables:
--   ctf_events        — top-level event identity (per-project, per-slug).
--   ctf_challenges    — jeopardy-style challenges within an event, optionally
--                       linked to a ctf_scopes (0001) authorization row.
--   ctf_attempts      — every flag-submit attempt, accepted or not.
--
-- The pre-existing ctf_scopes table from 0001_init.sql is left untouched.
-- Cross-link: see docs/adr/0016-ctf-data-model.md for the full design and
-- the M12 competition_type open question.

CREATE TABLE IF NOT EXISTS ctf_events (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id         uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  slug               text NOT NULL UNIQUE,
  name               text NOT NULL,
  ctftime_event_id   integer,
  event_url          text,
  start_at           timestamptz,
  end_at             timestamptz,
  scoring            text DEFAULT 'jeopardy',
  credentials_ref    text,  -- path hint, e.g. '~/.ctf/<slug>.json'; never the value
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ctf_events_project
  ON ctf_events(project_id);

CREATE TABLE IF NOT EXISTS ctf_challenges (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id              uuid NOT NULL REFERENCES ctf_events(id) ON DELETE CASCADE,
  scope_id              uuid REFERENCES ctf_scopes(id) ON DELETE SET NULL,
  slug                  text NOT NULL,
  name                  text NOT NULL,
  category              text NOT NULL CHECK (
    category IN ('web','crypto','rev','pwn','forensics','osint','misc')
  ),
  points                integer,
  description           text,
  expected_flag_format  text,
  attachments_path      text,
  remote_endpoint       text,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_ctf_challenges_event
  ON ctf_challenges(event_id);
CREATE INDEX IF NOT EXISTS idx_ctf_challenges_scope
  ON ctf_challenges(scope_id) WHERE scope_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ctf_attempts (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  challenge_id      uuid NOT NULL REFERENCES ctf_challenges(id) ON DELETE CASCADE,
  run_id            uuid REFERENCES experiment_runs(id) ON DELETE SET NULL,
  accepted          boolean,
  http_status       integer,
  flag_length       integer,  -- NEVER the flag value
  -- Multi-account / team identity columns (T000 design-red-team carry-over).
  -- The kkr.py M9.4 replay surfaced the "owner on the submission row" gap;
  -- recording which event credential actually hit the event prevents the
  -- same failure mode (wrong-team-id submission, mis-attributed accept).
  event_account     text,
  team_id           text,
  submitted_at      timestamptz NOT NULL DEFAULT now(),
  response_excerpt  text  -- 256-char cap, redact any string that looks like a flag
);

CREATE INDEX IF NOT EXISTS idx_ctf_attempts_challenge
  ON ctf_attempts(challenge_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_ctf_attempts_run
  ON ctf_attempts(run_id) WHERE run_id IS NOT NULL;

-- Enable RLS now; add real policies once auth/user model is finalized
-- (same posture as ctf_scopes in migration 0001).
ALTER TABLE ctf_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ctf_challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE ctf_attempts   ENABLE ROW LEVEL SECURITY;
