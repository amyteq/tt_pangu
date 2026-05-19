"""kca DB access layer (psycopg3, sync).

Side-effect classification:
  - Operations against a local Supabase stack are LOCAL_WRITE.
  - Operations against a remote Postgres are REMOTE_WRITE and require
    both KCA_DB_TARGET=remote and KCA_ALLOW_REMOTE=1.

Env contract:
  - KCA_DB_TARGET           : "local" (default) or "remote".
  - SUPABASE_DB_URL         : libpq conninfo string (preferred).
  - SUPABASE_DB_HOST/PORT/USER/PASSWORD/DB : fallback discrete vars.

Module is importable without a live DB — connections happen lazily.
"""
from __future__ import annotations

import json
import os
from typing import Any, Iterable

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
    "create_experiment",
    "create_experiment_run",
    "record_metric",
    "list_runs",
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


def create_experiment(
    name: str,
    hypothesis: str | None = None,
    tags: Iterable[str] | None = None,
    config: dict | None = None,
    project_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Create an experiments row. Return its id (uuid str)."""
    project_id = project_id or DEFAULT_PROJECT_ID
    tags_list = list(tags or [])
    config = config or {}
    return _with_conn(
        conn, _create_experiment, name, hypothesis, tags_list, config, project_id
    )


def _create_experiment(
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


def record_metric(
    experiment_run_id: str,
    key: str,
    value: float,
    metadata: dict | None = None,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """Insert metric event AND update experiment_runs.metrics jsonb snapshot.

    Returns the inserted event row.
    """
    metadata = metadata or {}
    return _with_conn(
        conn, _record_metric, experiment_run_id, key, float(value), metadata
    )


def _record_metric(
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


def list_runs(
    competition_slug: str | None = None,
    limit: int = 100,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """Join experiments + experiment_runs + competitions; return flat rows."""
    return _with_conn(conn, _list_runs, competition_slug, limit)


def _list_runs(
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
