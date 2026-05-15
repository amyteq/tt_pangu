-- Initial Supabase/Postgres schema for Kaggle / CTF Code Agent.
-- Review RLS policies before production use.

create extension if not exists "pgcrypto";

create type project_kind as enum ('kaggle', 'ctf', 'general');
create type session_status as enum ('queued', 'running', 'waiting_for_human', 'succeeded', 'failed', 'cancelled');
create type job_status as enum ('queued', 'leased', 'running', 'succeeded', 'failed', 'cancelled');
create type run_status as enum ('queued', 'running', 'succeeded', 'failed', 'cancelled');
create type trust_level as enum ('official', 'trusted_public', 'community', 'untrusted', 'unknown');
create type decision_status as enum ('pending', 'approved', 'rejected', 'expired');

create table projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  kind project_kind not null default 'general',
  repo_url text,
  default_branch text default 'main',
  description text,
  created_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table competitions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  platform text not null default 'kaggle',
  slug text not null,
  title text,
  rules_url text,
  data_url text,
  metric_name text,
  objective text,
  max_daily_submissions int,
  current_best_metric numeric,
  current_best_submission_id uuid,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(platform, slug)
);

create table agent_sessions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  parent_session_id uuid references agent_sessions(id) on delete set null,
  claude_session_id text,
  mode text not null default 'plan',
  status session_status not null default 'queued',
  goal text,
  branch text,
  workspace_ref text,
  started_at timestamptz,
  ended_at timestamptz,
  cost_usd numeric,
  usage jsonb not null default '{}',
  metadata jsonb not null default '{}',
  created_by uuid,
  created_at timestamptz not null default now()
);

create table agent_jobs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  session_id uuid references agent_sessions(id) on delete cascade,
  status job_status not null default 'queued',
  priority int not null default 100,
  job_type text not null,
  payload jsonb not null default '{}',
  attempts int not null default 0,
  max_attempts int not null default 3,
  due_at timestamptz not null default now(),
  leased_by text,
  leased_until timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  error text,
  created_at timestamptz not null default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references agent_sessions(id) on delete cascade,
  role text not null check (role in ('system', 'user', 'assistant', 'tool')),
  content jsonb not null,
  token_count int,
  created_at timestamptz not null default now()
);

create table research_items (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  session_id uuid references agent_sessions(id) on delete set null,
  url text,
  title text,
  source_type text,
  trust trust_level not null default 'unknown',
  summary text,
  relevant_quotes jsonb not null default '[]',
  screenshot_artifact_id uuid,
  metadata jsonb not null default '{}',
  fetched_at timestamptz,
  created_at timestamptz not null default now()
);

create table experiments (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  session_id uuid references agent_sessions(id) on delete set null,
  name text not null,
  hypothesis text,
  status run_status not null default 'queued',
  code_ref text,
  config jsonb not null default '{}',
  dataset_version text,
  baseline_experiment_id uuid references experiments(id) on delete set null,
  created_at timestamptz not null default now()
);

create table experiment_runs (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references experiments(id) on delete cascade,
  run_number int not null default 1,
  command text,
  status run_status not null default 'queued',
  metrics jsonb not null default '{}',
  stdout_artifact_id uuid,
  stderr_artifact_id uuid,
  artifacts jsonb not null default '[]',
  started_at timestamptz,
  ended_at timestamptz,
  analysis text,
  created_at timestamptz not null default now(),
  unique(experiment_id, run_number)
);

create table submissions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  competition_id uuid references competitions(id) on delete set null,
  experiment_run_id uuid references experiment_runs(id) on delete set null,
  platform text not null default 'kaggle',
  submission_file_artifact_id uuid,
  external_submission_id text,
  public_score numeric,
  private_score numeric,
  status text not null default 'prepared',
  submitted_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

alter table competitions
  add constraint competitions_best_submission_fk
  foreign key (current_best_submission_id) references submissions(id) on delete set null;

create table human_decisions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  session_id uuid references agent_sessions(id) on delete cascade,
  decision_type text not null,
  prompt text not null,
  options jsonb not null default '[]',
  status decision_status not null default 'pending',
  selected jsonb,
  rationale text,
  requested_by text,
  decided_by uuid,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  decided_at timestamptz
);

create table artifacts (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  session_id uuid references agent_sessions(id) on delete set null,
  kind text not null,
  storage_path text not null,
  content_hash text,
  byte_size bigint,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

alter table research_items
  add constraint research_items_screenshot_fk
  foreign key (screenshot_artifact_id) references artifacts(id) on delete set null;

alter table experiment_runs
  add constraint experiment_runs_stdout_fk
  foreign key (stdout_artifact_id) references artifacts(id) on delete set null;

alter table experiment_runs
  add constraint experiment_runs_stderr_fk
  foreign key (stderr_artifact_id) references artifacts(id) on delete set null;

alter table submissions
  add constraint submissions_file_fk
  foreign key (submission_file_artifact_id) references artifacts(id) on delete set null;

create table agent_events (
  id bigserial primary key,
  project_id uuid references projects(id) on delete cascade,
  session_id uuid references agent_sessions(id) on delete cascade,
  event_type text not null,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table ctf_scopes (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  name text not null,
  authorized_scope text not null,
  target_urls jsonb not null default '[]',
  local_only boolean not null default true,
  expires_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

create index idx_agent_jobs_status_due on agent_jobs(status, due_at, priority);
create index idx_agent_sessions_project_status on agent_sessions(project_id, status, created_at desc);
create index idx_messages_session_created on messages(session_id, created_at);
create index idx_research_project_created on research_items(project_id, created_at desc);
create index idx_experiments_project_created on experiments(project_id, created_at desc);
create index idx_runs_experiment_created on experiment_runs(experiment_id, created_at desc);
create index idx_events_session_created on agent_events(session_id, created_at desc);

-- Enable RLS now; add real policies once auth/user model is finalized.
alter table projects enable row level security;
alter table competitions enable row level security;
alter table agent_sessions enable row level security;
alter table agent_jobs enable row level security;
alter table messages enable row level security;
alter table research_items enable row level security;
alter table experiments enable row level security;
alter table experiment_runs enable row level security;
alter table submissions enable row level security;
alter table human_decisions enable row level security;
alter table artifacts enable row level security;
alter table agent_events enable row level security;
alter table ctf_scopes enable row level security;
