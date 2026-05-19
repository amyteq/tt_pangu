"""kca DB access layer (psycopg3, sync).

Side-effect classification:
  - Operations against a local Supabase stack are LOCAL_WRITE.
  - Operations against a remote Postgres are REMOTE_WRITE and require
    both KCA_DB_TARGET=remote and KCA_ALLOW_REMOTE=1.

Env contract (set in .env, loaded automatically via python-dotenv if installed):
  - SUPABASE_DB_URL         : libpq conninfo string (preferred).
  - KCA_DB_TARGET           : "local" (default) or "remote".
  - KCA_ALLOW_REMOTE        : "1" to allow remote/submission operations.
  - SUPABASE_DB_HOST/PORT/USER/PASSWORD/DB : fallback discrete vars.

See env.example in the repo root for the full template.

Module is importable without a live DB — connections happen lazily.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

# Load .env from repo root automatically if python-dotenv is installed.
# This is a no-op when .env doesn't exist or dotenv isn't installed.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
except ImportError:
    pass

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError as e:  # pragma: no cover
    psycopg = None  # type: ignore
    _import_err = e
else:
    _import_err = None

from _types import SideEffect

__all__ = [
    "RemoteOperationBlocked",
    "DBNotConfigured",
    "DEFAULT_PROJECT_ID",
    "current_side_effect",
    "get_conn",
    "ensure_default_project",
    "ensure_competition",
    # M2 legacy (still used by tools/kca/run.py against the 0001/0002 schema)
    "create_experiment_m2",
    "create_experiment_run",
    "record_metric_m2",
    "list_runs_m2",
    "find_run_by_dir",
    "insert_approval_request",
    # M3 job lifecycle
    "create_job",
    "get_job",
    "lease_job",
    "update_job",
    "append_job_event",
    "list_jobs",
    "list_pending_decisions",
    "resolve_decision",
    # M4 competition/experiment/run/submission (0004 schema)
    "get_competition_by_slug",
    "update_competition",
    "list_competitions",
    "create_experiment",
    "get_experiment",
    "list_experiments",
    "create_run",
    "update_run",
    "record_metric",
    "list_runs",
    "create_submission",
    "update_submission",
]


DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"
_ENV_TARGET = "KCA_DB_TARGET"
_ENV_ALLOW_REMOTE = "KCA_ALLOW_REMOTE"
_ENV_URL = "SUPABASE_DB_URL"


class RemoteOperationBlocked(RuntimeError):
    """Raised when KCA_DB_TARGET=remote without KCA_ALLOW_REMOTE=1."""


class DBNotConfigured(RuntimeError):
    """Raised when no DB connection info is available."""


def current_side_effect() -> SideEffect:
    """Side effect for DB operations under the current env."""
    target = os.environ.get(_ENV_TARGET, "local").strip().lower()
    return SideEffect.REMOTE_WRITE if target == "remote" else SideEffect.LOCAL_WRITE


def _check_remote_gate() -> None:
    target = os.environ.get(_ENV_TARGET, "local").strip().lower()
    if target == "remote" and os.environ.get(_ENV_ALLOW_REMOTE) != "1":
        raise RemoteOperationBlocked(
            f"{_ENV_TARGET}=remote requires {_ENV_ALLOW_REMOTE}=1 and human approval"
        )


def _conninfo() -> str:
    url = os.environ.get(_ENV_URL)
    if url:
        return url
    host = os.environ.get("SUPABASE_DB_HOST")
    if not host:
        raise DBNotConfigured(
            f"Set {_ENV_URL} (preferred) or SUPABASE_DB_HOST + related vars."
        )
    port = os.environ.get("SUPABASE_DB_PORT", "54322")
    user = os.environ.get("SUPABASE_DB_USER", "postgres")
    password = os.environ.get("SUPABASE_DB_PASSWORD", "postgres")
    dbname = os.environ.get("SUPABASE_DB", "postgres")
    return f"postgres://{user}:{password}@{host}:{port}/{dbname}"


def get_conn() -> "psycopg.Connection":
    """Open a new psycopg connection. Caller owns close()."""
    if psycopg is None:
        raise DBNotConfigured(f"psycopg not installed: {_import_err}")
    _check_remote_gate()
    return psycopg.connect(_conninfo(), row_factory=dict_row, autocommit=False)


# ---------------------------------------------------------------------------
# Schema operations
# ---------------------------------------------------------------------------

def ensure_default_project(conn: "psycopg.Connection | None" = None) -> str:
    """Return the bootstrap project id; create the row if absent.

    The row is normally inserted by migration 0002. This is a defensive
    no-op upsert so kca works against a DB that was partially migrated.
    """
    return _with_conn(conn, _ensure_default_project)


def _ensure_default_project(conn: "psycopg.Connection") -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into projects (id, name, kind, description)
            values (%s::uuid, 'local-default', 'general',
                    'Default project for local kca calls.')
            on conflict (id) do nothing
            """,
            (DEFAULT_PROJECT_ID,),
        )
    conn.commit()
    return DEFAULT_PROJECT_ID


def ensure_competition(
    slug: str,
    platform: str = "kaggle",
    title: str | None = None,
    project_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Upsert a competitions row keyed by (platform, slug). Return its id (uuid str)."""
    project_id = project_id or DEFAULT_PROJECT_ID
    return _with_conn(conn, _ensure_competition, slug, platform, title, project_id)


def _ensure_competition(
    conn: "psycopg.Connection",
    slug: str,
    platform: str,
    title: str | None,
    project_id: str,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into competitions (project_id, platform, slug, title)
            values (%s::uuid, %s, %s, %s)
            on conflict (platform, slug) do update
              set title = coalesce(excluded.title, competitions.title)
            returning id::text
            """,
            (project_id, platform, slug, title),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def create_experiment_m2(
    name: str,
    hypothesis: str | None = None,
    tags: Iterable[str] | None = None,
    config: dict | None = None,
    project_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Create an experiments row (M2 schema: keyed by project_id + name)."""
    project_id = project_id or DEFAULT_PROJECT_ID
    tags_list = list(tags or [])
    config = config or {}
    return _with_conn(
        conn, _create_experiment_m2, name, hypothesis, tags_list, config, project_id
    )


def _create_experiment_m2(
    conn: "psycopg.Connection",
    name: str,
    hypothesis: str | None,
    tags: list[str],
    config: dict,
    project_id: str,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into experiments
              (project_id, name, hypothesis, tags, config)
            values (%s::uuid, %s, %s, %s, %s::jsonb)
            returning id::text
            """,
            (project_id, name, hypothesis, tags, json.dumps(config)),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def create_experiment_run(
    experiment_id: str,
    external_run_id: str,
    run_dir: str,
    command: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Create an experiment_runs row. Return its id (uuid str)."""
    return _with_conn(
        conn, _create_experiment_run, experiment_id, external_run_id, run_dir, command
    )


def _create_experiment_run(
    conn: "psycopg.Connection",
    experiment_id: str,
    external_run_id: str,
    run_dir: str,
    command: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into experiment_runs
              (experiment_id, external_run_id, run_dir, command, run_number)
            values (
              %s::uuid, %s, %s, %s,
              coalesce((select max(run_number) + 1 from experiment_runs where experiment_id = %s::uuid), 1)
            )
            returning id::text
            """,
            (experiment_id, external_run_id, run_dir, command, experiment_id),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def record_metric_m2(
    experiment_run_id: str,
    key: str,
    value: float,
    metadata: dict | None = None,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """M2: insert into experiment_run_metrics event table + jsonb snapshot."""
    metadata = metadata or {}
    return _with_conn(
        conn, _record_metric_m2, experiment_run_id, key, float(value), metadata
    )


def _record_metric_m2(
    conn: "psycopg.Connection",
    experiment_run_id: str,
    key: str,
    value: float,
    metadata: dict,
) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into experiment_run_metrics
              (experiment_run_id, key, value, metadata)
            values (%s::uuid, %s, %s, %s::jsonb)
            returning id, key, value, recorded_at
            """,
            (experiment_run_id, key, value, json.dumps(metadata)),
        )
        event = cur.fetchone()
        # Update the denormalized snapshot. Cast text/numeric explicitly so
        # Postgres can resolve jsonb_build_object's variadic "any" overload.
        cur.execute(
            """
            update experiment_runs
              set metrics = coalesce(metrics, '{}'::jsonb) ||
                            jsonb_build_object(
                              %s::text,
                              jsonb_build_object('value', %s::numeric, 'recorded_at', now())
                            )
              where id = %s::uuid
            """,
            (key, value, experiment_run_id),
        )
    conn.commit()
    assert event is not None
    return dict(event)


def list_runs_m2(
    competition_slug: str | None = None,
    limit: int = 100,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """M2: join experiments + experiment_runs filtered by run_dir prefix."""
    return _with_conn(conn, _list_runs_m2, competition_slug, limit)


def _list_runs_m2(
    conn: "psycopg.Connection",
    competition_slug: str | None,
    limit: int,
) -> list[dict]:
    # Note: competitions is not directly linked to experiments yet; for M2 we
    # filter via run_dir prefix (runs/<slug>/...) until a join column is added.
    query = """
        select
          er.id::text          as experiment_run_id,
          er.external_run_id   as run_id,
          er.run_dir,
          er.metrics,
          er.created_at,
          e.id::text           as experiment_id,
          e.name               as experiment_name,
          e.hypothesis,
          e.tags
        from experiment_runs er
        join experiments e on e.id = er.experiment_id
        {where}
        order by er.created_at desc
        limit %s
    """
    params: list[Any] = []
    if competition_slug:
        query = query.format(where="where er.run_dir like %s")
        params.append(f"runs/{competition_slug}/%")
    else:
        query = query.format(where="")
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def find_run_by_dir(
    run_dir: str,
    conn: "psycopg.Connection | None" = None,
) -> dict | None:
    """Look up an experiment_run by its run_dir path. Return the row or None."""
    return _with_conn(conn, _find_run_by_dir, run_dir)


def _find_run_by_dir(conn: "psycopg.Connection", run_dir: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              er.id::text         as experiment_run_id,
              er.external_run_id  as run_id,
              er.run_dir,
              e.id::text          as experiment_id
            from experiment_runs er
            join experiments e on e.id = er.experiment_id
            where er.run_dir = %s
            order by er.created_at desc
            limit 1
            """,
            (run_dir,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def insert_approval_request(
    decision_type: str,
    prompt: str,
    options: dict | list | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    requested_by: str | None = "kca",
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a pending human_decisions row. Return its id (uuid str)."""
    project_id = project_id or DEFAULT_PROJECT_ID
    options = options or []
    return _with_conn(
        conn,
        _insert_approval_request,
        decision_type,
        prompt,
        options,
        session_id,
        project_id,
        requested_by,
    )


def _insert_approval_request(
    conn: "psycopg.Connection",
    decision_type: str,
    prompt: str,
    options: dict | list,
    session_id: str | None,
    project_id: str,
    requested_by: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into human_decisions
              (project_id, session_id, decision_type, prompt, options, requested_by)
            values (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s)
            returning id::text
            """,
            (
                project_id,
                session_id,
                decision_type,
                prompt,
                json.dumps(options),
                requested_by,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# M3 job lifecycle
# ---------------------------------------------------------------------------

def create_job(
    project_id: str,
    prompt: str,
    policy: dict,
    model: str = "claude-sonnet-4-6",
    competition_slug: str | None = None,
    session_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a new queued agent_jobs row. Returns job_id (uuid str)."""
    return _with_conn(conn, _create_job, project_id, prompt, policy, model,
                      competition_slug, session_id)


def _create_job(
    conn: "psycopg.Connection",
    project_id: str,
    prompt: str,
    policy: dict,
    model: str,
    competition_slug: str | None,
    session_id: str | None,
) -> str:
    competition_id = None
    if competition_slug:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text FROM competitions WHERE slug = %s LIMIT 1",
                (competition_slug,),
            )
            row = cur.fetchone()
            if row:
                competition_id = row["id"]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_jobs
              (project_id, session_id, competition_id, status, payload,
               prompt, model, policy)
            VALUES
              (%s::uuid, %s::uuid, %s::uuid, 'queued', %s::jsonb,
               %s, %s, %s::jsonb)
            RETURNING id::text
            """,
            (
                project_id,
                session_id,
                competition_id,
                json.dumps(policy),
                prompt,
                model,
                json.dumps(policy),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def get_job(job_id: str, conn: "psycopg.Connection | None" = None) -> dict:
    """Fetch one agent_jobs row as a dict. Raises KeyError if not found."""
    return _with_conn(conn, _get_job, job_id)


def _get_job(conn: "psycopg.Connection", job_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM agent_jobs WHERE id = %s::uuid",
            (job_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"agent_jobs row not found: {job_id}")
    return dict(row)


def lease_job(
    job_id: str,
    worker_id: str,
    lease_seconds: int = 300,
    conn: "psycopg.Connection | None" = None,
) -> bool:
    """Atomically set status='running', leased_by, leased_until.

    Returns True if successfully leased, False if already running/leased.
    """
    return _with_conn(conn, _lease_job, job_id, worker_id, lease_seconds)


def _lease_job(
    conn: "psycopg.Connection",
    job_id: str,
    worker_id: str,
    lease_seconds: int,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE agent_jobs
               SET status = 'running',
                   leased_by = %s,
                   leased_until = now() + (%s || ' seconds')::interval,
                   started_at = COALESCE(started_at, now())
             WHERE id = %s::uuid
               AND status IN ('queued', 'paused')
            """,
            (worker_id, str(lease_seconds), job_id),
        )
        updated = cur.rowcount
    conn.commit()
    return updated > 0


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
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Partial update of agent_jobs columns. Only non-None kwargs are updated."""
    fields: list[str] = []
    params: list[Any] = []
    if status is not None:
        fields.append("status = %s::job_status")
        params.append(status)
    if workspace_path is not None:
        fields.append("workspace_path = %s")
        params.append(workspace_path)
    if turns_used is not None:
        fields.append("turns_used = %s")
        params.append(turns_used)
    if cost_usd is not None:
        fields.append("cost_usd = %s")
        params.append(cost_usd)
    if error is not None:
        fields.append("error = %s")
        params.append(error)
    if started_at is not None:
        fields.append("started_at = %s")
        params.append(started_at)
    if finished_at is not None:
        fields.append("finished_at = %s")
        params.append(finished_at)
    if not fields:
        return
    _with_conn(conn, _update_job, job_id, fields, params)


def _update_job(
    conn: "psycopg.Connection",
    job_id: str,
    fields: list[str],
    params: list[Any],
) -> None:
    set_clause = ", ".join(fields)
    params.append(job_id)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE agent_jobs SET {set_clause} WHERE id = %s::uuid",
            params,
        )
    conn.commit()


def append_job_event(
    job_id: str,
    event_type: str,
    turn_number: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    event_data: dict | None = None,
    conn: "psycopg.Connection | None" = None,
) -> int:
    """Insert one agent_job_events row. Returns the new event id."""
    return _with_conn(conn, _append_job_event, job_id, event_type,
                      turn_number, input_tokens, output_tokens, cost_usd,
                      event_data or {})


def _append_job_event(
    conn: "psycopg.Connection",
    job_id: str,
    event_type: str,
    turn_number: int | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    event_data: dict,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_job_events
              (job_id, event_type, turn_number, input_tokens, output_tokens,
               cost_usd, event_data)
            VALUES
              (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (job_id, event_type, turn_number, input_tokens, output_tokens,
             cost_usd, json.dumps(event_data)),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def list_jobs(
    status: str | None = None,
    limit: int = 20,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List agent_jobs rows, newest first. Filter by status if given."""
    return _with_conn(conn, _list_jobs, status, limit)


def _list_jobs(
    conn: "psycopg.Connection",
    status: str | None,
    limit: int,
) -> list[dict]:
    if status is not None:
        query = ("SELECT * FROM agent_jobs WHERE status = %s::job_status "
                 "ORDER BY created_at DESC LIMIT %s")
        params: list[Any] = [status, limit]
    else:
        query = "SELECT * FROM agent_jobs ORDER BY created_at DESC LIMIT %s"
        params = [limit]
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def list_pending_decisions(
    job_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List human_decisions with status='pending'. Filter by job_id if given."""
    return _with_conn(conn, _list_pending_decisions, job_id)


def _list_pending_decisions(
    conn: "psycopg.Connection",
    job_id: str | None,
) -> list[dict]:
    if job_id is not None:
        query = ("SELECT * FROM human_decisions WHERE status = 'pending' "
                 "AND job_id = %s::uuid ORDER BY created_at DESC")
        params: list[Any] = [job_id]
    else:
        query = ("SELECT * FROM human_decisions WHERE status = 'pending' "
                 "ORDER BY created_at DESC")
        params = []
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def resolve_decision(
    decision_id: str,
    resolution: str,
    notes: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Set human_decisions.status = resolution, decided_at = now(), notes."""
    _with_conn(conn, _resolve_decision, decision_id, resolution, notes)


def _resolve_decision(
    conn: "psycopg.Connection",
    decision_id: str,
    resolution: str,
    notes: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE human_decisions
               SET status = %s,
                   notes = %s,
                   decided_at = now()
             WHERE id = %s::uuid
            """,
            (resolution, notes, decision_id),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# M4: competition / experiment / run / submission (schema in 0004)
# ---------------------------------------------------------------------------

def get_competition_by_slug(
    slug: str,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """Fetch one competitions row by slug. Raises KeyError if not found."""
    return _with_conn(conn, _get_competition_by_slug, slug)


def _get_competition_by_slug(conn: "psycopg.Connection", slug: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM competitions WHERE slug = %s LIMIT 1", (slug,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"competition slug not found: {slug}")
    return dict(row)


def update_competition(
    competition_id: str,
    *,
    repo_url: str | None = None,
    default_branch: str | None = None,
    local_clone_path: str | None = None,
    competition_policy: dict | None = None,
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Partial update of competitions columns. Only non-None kwargs are set."""
    fields: list[str] = []
    params: list[Any] = []
    if repo_url is not None:
        fields.append("repo_url = %s")
        params.append(repo_url)
    if default_branch is not None:
        fields.append("default_branch = %s")
        params.append(default_branch)
    if local_clone_path is not None:
        fields.append("local_clone_path = %s")
        params.append(local_clone_path)
    if competition_policy is not None:
        fields.append("competition_policy = %s::jsonb")
        params.append(json.dumps(competition_policy))
    if not fields:
        return
    _with_conn(conn, _update_competition, competition_id, fields, params)


def _update_competition(
    conn: "psycopg.Connection",
    competition_id: str,
    fields: list[str],
    params: list[Any],
) -> None:
    set_clause = ", ".join(fields)
    params.append(competition_id)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE competitions SET {set_clause} WHERE id = %s::uuid",
            params,
        )
    conn.commit()


def list_competitions(
    limit: int = 50,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List competitions newest first."""
    return _with_conn(conn, _list_competitions, limit)


def _list_competitions(conn: "psycopg.Connection", limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM competitions ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def create_experiment(
    competition_id: str,
    hypothesis: str,
    *,
    job_id: str | None = None,
    branch: str | None = None,
    config: dict | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert an experiments row (M4 schema). Returns experiment_id."""
    return _with_conn(
        conn, _create_experiment_m4, competition_id, hypothesis, job_id, branch,
        config or {},
    )


def _create_experiment_m4(
    conn: "psycopg.Connection",
    competition_id: str,
    hypothesis: str,
    job_id: str | None,
    branch: str | None,
    config: dict,
) -> str:
    # The M1 experiments table requires project_id + name; the M4 INSERT must
    # populate them as well so both schema shapes coexist on the same row.
    with conn.cursor() as cur:
        cur.execute(
            "SELECT project_id::text FROM competitions WHERE id = %s::uuid",
            (competition_id,),
        )
        comp_row = cur.fetchone()
        project_id = (comp_row or {}).get("project_id") or DEFAULT_PROJECT_ID
        synth_name = (branch or hypothesis or "m4-experiment")[:120]
        cur.execute(
            """
            INSERT INTO experiments
              (project_id, name, competition_id, job_id, hypothesis, branch, config)
            VALUES
              (%s::uuid, %s, %s::uuid, %s::uuid, %s, %s, %s::jsonb)
            RETURNING id::text
            """,
            (project_id, synth_name, competition_id, job_id, hypothesis,
             branch, json.dumps(config)),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def get_experiment(
    experiment_id: str,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """Fetch one experiments row. Raises KeyError if not found."""
    return _with_conn(conn, _get_experiment, experiment_id)


def _get_experiment(conn: "psycopg.Connection", experiment_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM experiments WHERE id = %s::uuid", (experiment_id,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"experiment not found: {experiment_id}")
    return dict(row)


def list_experiments(
    competition_id: str,
    status: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List experiments for a competition, newest first."""
    return _with_conn(conn, _list_experiments, competition_id, status)


def _list_experiments(
    conn: "psycopg.Connection",
    competition_id: str,
    status: str | None,
) -> list[dict]:
    if status is not None:
        query = ("SELECT * FROM experiments WHERE competition_id = %s::uuid "
                 "AND status = %s ORDER BY created_at DESC")
        params: list[Any] = [competition_id, status]
    else:
        query = ("SELECT * FROM experiments WHERE competition_id = %s::uuid "
                 "ORDER BY created_at DESC")
        params = [competition_id]
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def create_run(
    experiment_id: str,
    *,
    job_id: str | None = None,
    run_dir: str | None = None,
    command: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a new experiment_runs row (M4 schema) with status='running'."""
    return _with_conn(
        conn, _create_run_m4, experiment_id, job_id, run_dir, command,
    )


def _create_run_m4(
    conn: "psycopg.Connection",
    experiment_id: str,
    job_id: str | None,
    run_dir: str | None,
    command: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO experiment_runs
              (experiment_id, job_id, run_dir, command, status, started_at)
            VALUES
              (%s::uuid, %s::uuid, %s, %s, 'running', now())
            RETURNING id::text
            """,
            (experiment_id, job_id, run_dir, command),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    metrics: dict | None = None,
    artifact_paths: list | None = None,
    analysis: str | None = None,
    finished_at=None,
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Partial update of experiment_runs (M4 schema)."""
    fields: list[str] = []
    params: list[Any] = []
    if status is not None:
        fields.append("status = %s")
        params.append(status)
    if metrics is not None:
        fields.append("metrics = %s::jsonb")
        params.append(json.dumps(metrics))
    if artifact_paths is not None:
        fields.append("artifact_paths = %s::jsonb")
        params.append(json.dumps(artifact_paths))
    if analysis is not None:
        fields.append("analysis = %s")
        params.append(analysis)
    if finished_at is not None:
        fields.append("finished_at = %s")
        params.append(finished_at)
    if not fields:
        return
    _with_conn(conn, _update_run_m4, run_id, fields, params)


def _update_run_m4(
    conn: "psycopg.Connection",
    run_id: str,
    fields: list[str],
    params: list[Any],
) -> None:
    set_clause = ", ".join(fields)
    params.append(run_id)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE experiment_runs SET {set_clause} WHERE id = %s::uuid",
            params,
        )
    conn.commit()


def record_metric(
    run_id: str,
    key: str,
    value: float,
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Merge {key: value} into experiment_runs.metrics (M4: single jsonb UPDATE)."""
    _with_conn(conn, _record_metric_m4, run_id, key, float(value))


def _record_metric_m4(
    conn: "psycopg.Connection",
    run_id: str,
    key: str,
    value: float,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE experiment_runs
               SET metrics = coalesce(metrics, '{}'::jsonb)
                             || jsonb_build_object(%s::text, %s::float)
             WHERE id = %s::uuid
            """,
            (key, value, run_id),
        )
    conn.commit()


def list_runs(
    experiment_id: str | None = None,
    competition_id: str | None = None,
    limit: int = 20,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List experiment_runs (M4). Filter by experiment_id or competition_id."""
    return _with_conn(conn, _list_runs_m4, experiment_id, competition_id, limit)


def _list_runs_m4(
    conn: "psycopg.Connection",
    experiment_id: str | None,
    competition_id: str | None,
    limit: int,
) -> list[dict]:
    if experiment_id is not None:
        query = ("SELECT * FROM experiment_runs WHERE experiment_id = %s::uuid "
                 "ORDER BY created_at DESC LIMIT %s")
        params: list[Any] = [experiment_id, limit]
    elif competition_id is not None:
        query = ("SELECT er.* FROM experiment_runs er "
                 "JOIN experiments e ON e.id = er.experiment_id "
                 "WHERE e.competition_id = %s::uuid "
                 "ORDER BY er.created_at DESC LIMIT %s")
        params = [competition_id, limit]
    else:
        query = "SELECT * FROM experiment_runs ORDER BY created_at DESC LIMIT %s"
        params = [limit]
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def create_submission(
    competition_id: str,
    file_path: str,
    *,
    run_id: str | None = None,
    job_id: str | None = None,
    cv_score: float | None = None,
    note: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a prepared submissions row (M4 schema)."""
    return _with_conn(
        conn, _create_submission_m4, competition_id, file_path,
        run_id, job_id, cv_score, note,
    )


def _create_submission_m4(
    conn: "psycopg.Connection",
    competition_id: str,
    file_path: str,
    run_id: str | None,
    job_id: str | None,
    cv_score: float | None,
    note: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO submissions
              (competition_id, run_id, job_id, file_path, cv_score, note, status)
            VALUES
              (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, 'prepared')
            RETURNING id::text
            """,
            (competition_id, run_id, job_id, file_path, cv_score, note),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def update_submission(
    submission_id: str,
    *,
    public_lb_score: float | None = None,
    status: str | None = None,
    submitted_at=None,
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Update submission after Kaggle response."""
    fields: list[str] = []
    params: list[Any] = []
    if public_lb_score is not None:
        fields.append("public_lb_score = %s")
        params.append(public_lb_score)
    if status is not None:
        fields.append("status = %s")
        params.append(status)
    if submitted_at is not None:
        fields.append("submitted_at = %s")
        params.append(submitted_at)
    if not fields:
        return
    _with_conn(conn, _update_submission_m4, submission_id, fields, params)


def _update_submission_m4(
    conn: "psycopg.Connection",
    submission_id: str,
    fields: list[str],
    params: list[Any],
) -> None:
    set_clause = ", ".join(fields)
    params.append(submission_id)
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE submissions SET {set_clause} WHERE id = %s::uuid",
            params,
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _with_conn(conn, fn, *args, **kwargs):
    """Call fn(conn, *args) using the provided conn or a freshly opened one.

    When this function opens the connection, it also closes it.
    """
    if conn is not None:
        return fn(conn, *args, **kwargs)
    c = get_conn()
    try:
        return fn(c, *args, **kwargs)
    finally:
        c.close()
