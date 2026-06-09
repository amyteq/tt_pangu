-- 0009_m12_competition_type_teams.sql
-- M12: generalize competitions beyond Kaggle/CTF; add teams + team_memberships.
--
-- Forward-only. Idempotent. Additive. Re-runnable without error.
--
-- Implements ADR-0016: competition_type enum + policy resolver routing on it.
-- Existing rows backfill to competition_type='kaggle'.

-- ---------------------------------------------------------------------------
-- Part A: competition_type_enum
-- ---------------------------------------------------------------------------
-- Postgres CREATE TYPE has no IF NOT EXISTS; use a guarded DO block.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'competition_type_enum') THEN
    CREATE TYPE competition_type_enum AS ENUM (
      'kaggle',
      'devpost',
      'hackathon_devpost',
      'ctf',
      'generic'
    );
  END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- Part B: extend competitions with type, deadline, submission_format
-- ---------------------------------------------------------------------------
ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS competition_type competition_type_enum NOT NULL DEFAULT 'kaggle';

ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS deadline timestamptz NULL;

ALTER TABLE competitions
  ADD COLUMN IF NOT EXISTS submission_format jsonb NULL;

-- ---------------------------------------------------------------------------
-- Part C: teams
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  owner_user_id uuid NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE teams ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Part D: team_memberships
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_memberships (
  team_id   uuid NOT NULL REFERENCES teams(id),
  user_id   uuid NOT NULL,
  role      text NOT NULL DEFAULT 'member',
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (team_id, user_id)
);

ALTER TABLE team_memberships ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_team_memberships_user
  ON team_memberships(user_id);
