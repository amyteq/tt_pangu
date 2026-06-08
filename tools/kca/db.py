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
# KCA_SKIP_DOTENV lets a caller (e.g. a test subprocess that scrubbed its env)
# opt out, so the repo-root secrets file is not silently re-injected regardless
# of cwd — see issue #11 (Kaggle leaderboard pollution).
if not os.environ.get("KCA_SKIP_DOTENV"):
    try:
        from dotenv import load_dotenv as _load_dotenv

        _repo_root = Path(__file__).resolve().parent.parent.parent
        # `.vscode/.env` is the authoritative dev config (user-curated VS Code
        # workspace env, e.g. cloud Supabase DSN) — load with override=True so
        # a stale inherited shell env cannot shadow the intended value. The
        # root `.env` then fills in any keys not already set.
        _load_dotenv(_repo_root / ".vscode" / ".env", override=True)
        _load_dotenv(_repo_root / ".env", override=False)
    except ImportError:
        pass

try:
    import psycopg
    from psycopg import sql  # noqa: F401  # re-exported for callers
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
    "get_decision",
    "list_job_events",
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
    # M5 research / artifacts / citations (0005 schema)
    "create_research_item",
    "get_research_item",
    "list_research_items",
    "find_research_by_url",
    "attach_artifact",
    "cite_research",
    "list_citations",
    # M6 reviews + telemetry (0006 schema)
    "create_review",
    "get_review",
    "list_reviews",
    "find_review_for_op",
    "record_span",
    "list_spans",
    "set_job_trace",
    # M8 tool audit (0007 schema)
    "insert_tool_audit",
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
    job_id: str | None = None,
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
        job_id,
    )


def _insert_approval_request(
    conn: "psycopg.Connection",
    decision_type: str,
    prompt: str,
    options: dict | list,
    session_id: str | None,
    project_id: str,
    requested_by: str | None,
    job_id: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into human_decisions
              (project_id, session_id, decision_type, prompt, options,
               requested_by, job_id)
            values (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s::uuid)
            returning id::text
            """,
            (
                project_id,
                session_id,
                decision_type,
                prompt,
                json.dumps(options),
                requested_by,
                job_id,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def get_decision(
    decision_id: str,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """Fetch one human_decisions row. Raises KeyError if not found."""
    return _with_conn(conn, _get_decision, decision_id)


def _get_decision(conn: "psycopg.Connection", decision_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM human_decisions WHERE id = %s::uuid", (decision_id,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"decision not found: {decision_id}")
    return dict(row)


def list_job_events(
    job_id: str,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List agent_job_events rows for a job in id order."""
    return _with_conn(conn, _list_job_events, job_id)


def _list_job_events(conn: "psycopg.Connection", job_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM agent_job_events WHERE job_id = %s::uuid ORDER BY id",
            (job_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


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
    return _with_conn(
        conn,
        _create_job,
        project_id,
        prompt,
        policy,
        model,
        competition_slug,
        session_id,
    )


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
    return _with_conn(
        conn,
        _append_job_event,
        job_id,
        event_type,
        turn_number,
        input_tokens,
        output_tokens,
        cost_usd,
        event_data or {},
    )


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
            (
                job_id,
                event_type,
                turn_number,
                input_tokens,
                output_tokens,
                cost_usd,
                json.dumps(event_data),
            ),
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
        query = (
            "SELECT * FROM agent_jobs WHERE status = %s::job_status "
            "ORDER BY created_at DESC LIMIT %s"
        )
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
        query = (
            "SELECT * FROM human_decisions WHERE status = 'pending' "
            "AND job_id = %s::uuid ORDER BY created_at DESC"
        )
        params: list[Any] = [job_id]
    else:
        query = (
            "SELECT * FROM human_decisions WHERE status = 'pending' "
            "ORDER BY created_at DESC"
        )
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
               SET status = %s::decision_status,
                   rationale = %s,
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
        conn,
        _create_experiment_m4,
        competition_id,
        hypothesis,
        job_id,
        branch,
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
            (
                project_id,
                synth_name,
                competition_id,
                job_id,
                hypothesis,
                branch,
                json.dumps(config),
            ),
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
        query = (
            "SELECT * FROM experiments WHERE competition_id = %s::uuid "
            "AND status = %s ORDER BY created_at DESC"
        )
        params: list[Any] = [competition_id, status]
    else:
        query = (
            "SELECT * FROM experiments WHERE competition_id = %s::uuid "
            "ORDER BY created_at DESC"
        )
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
        conn,
        _create_run_m4,
        experiment_id,
        job_id,
        run_dir,
        command,
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
        query = (
            "SELECT * FROM experiment_runs WHERE experiment_id = %s::uuid "
            "ORDER BY created_at DESC LIMIT %s"
        )
        params: list[Any] = [experiment_id, limit]
    elif competition_id is not None:
        query = (
            "SELECT er.* FROM experiment_runs er "
            "JOIN experiments e ON e.id = er.experiment_id "
            "WHERE e.competition_id = %s::uuid "
            "ORDER BY er.created_at DESC LIMIT %s"
        )
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
        conn,
        _create_submission_m4,
        competition_id,
        file_path,
        run_id,
        job_id,
        cv_score,
        note,
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
# M5: research items / artifacts / citations (schema in 0005)
# ---------------------------------------------------------------------------


def attach_artifact(
    kind: str,
    storage_path: str,
    *,
    content_hash: str | None = None,
    byte_size: int | None = None,
    metadata: dict | None = None,
    project_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert an artifacts row. Returns artifact_id."""
    project_id = project_id or DEFAULT_PROJECT_ID
    return _with_conn(
        conn,
        _attach_artifact,
        kind,
        storage_path,
        content_hash,
        byte_size,
        metadata or {},
        project_id,
    )


def _attach_artifact(
    conn: "psycopg.Connection",
    kind: str,
    storage_path: str,
    content_hash: str | None,
    byte_size: int | None,
    metadata: dict,
    project_id: str,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO artifacts
              (project_id, kind, storage_path, content_hash, byte_size, metadata)
            VALUES
              (%s::uuid, %s, %s, %s, %s, %s::jsonb)
            RETURNING id::text
            """,
            (
                project_id,
                kind,
                storage_path,
                content_hash,
                byte_size,
                json.dumps(metadata),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def create_research_item(
    *,
    url: str,
    title: str | None = None,
    source_kind: str | None = None,
    trust: str = "unknown",
    summary: str | None = None,
    competition_id: str | None = None,
    fetcher: str | None = None,
    http_status: int | None = None,
    content_hash: str | None = None,
    html_artifact_id: str | None = None,
    text_artifact_id: str | None = None,
    source_policy: dict | None = None,
    project_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a research_items row (M5 fields). Returns item id."""
    project_id = project_id or DEFAULT_PROJECT_ID
    return _with_conn(
        conn,
        _create_research_item,
        url,
        title,
        source_kind,
        trust,
        summary,
        competition_id,
        fetcher,
        http_status,
        content_hash,
        html_artifact_id,
        text_artifact_id,
        source_policy or {},
        project_id,
    )


def _create_research_item(
    conn: "psycopg.Connection",
    url: str,
    title: str | None,
    source_kind: str | None,
    trust: str,
    summary: str | None,
    competition_id: str | None,
    fetcher: str | None,
    http_status: int | None,
    content_hash: str | None,
    html_artifact_id: str | None,
    text_artifact_id: str | None,
    source_policy: dict,
    project_id: str,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO research_items
              (project_id, url, title, source_kind, trust, summary,
               competition_id, fetcher, http_status, content_hash,
               html_artifact_id, text_artifact_id, source_policy, fetched_at)
            VALUES
              (%s::uuid, %s, %s, %s, %s::trust_level, %s,
               %s::uuid, %s, %s, %s,
               %s::uuid, %s::uuid, %s::jsonb, now())
            RETURNING id::text
            """,
            (
                project_id,
                url,
                title,
                source_kind,
                trust,
                summary,
                competition_id,
                fetcher,
                http_status,
                content_hash,
                html_artifact_id,
                text_artifact_id,
                json.dumps(source_policy),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def get_research_item(
    item_id: str,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """Fetch one research_items row. Raises KeyError if not found."""
    return _with_conn(conn, _get_research_item, item_id)


def _get_research_item(conn: "psycopg.Connection", item_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM research_items WHERE id = %s::uuid", (item_id,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"research_item not found: {item_id}")
    return dict(row)


def list_research_items(
    competition_id: str | None = None,
    limit: int = 50,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List research_items, newest first; optionally filter by competition."""
    return _with_conn(conn, _list_research_items, competition_id, limit)


def _list_research_items(
    conn: "psycopg.Connection",
    competition_id: str | None,
    limit: int,
) -> list[dict]:
    if competition_id is not None:
        query = (
            "SELECT * FROM research_items WHERE competition_id = %s::uuid "
            "ORDER BY created_at DESC LIMIT %s"
        )
        params: list[Any] = [competition_id, limit]
    else:
        query = "SELECT * FROM research_items ORDER BY created_at DESC LIMIT %s"
        params = [limit]
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def find_research_by_url(
    url: str,
    conn: "psycopg.Connection | None" = None,
) -> dict | None:
    """Return the newest research_items row matching the URL, or None."""
    return _with_conn(conn, _find_research_by_url, url)


def _find_research_by_url(conn: "psycopg.Connection", url: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM research_items
             WHERE url = %s
             ORDER BY created_at DESC
             LIMIT 1
            """,
            (url,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def cite_research(
    research_item_id: str,
    *,
    run_id: str | None = None,
    experiment_id: str | None = None,
    job_id: str | None = None,
    quote: str | None = None,
    page_anchor: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a research_citations row. Returns citation id."""
    return _with_conn(
        conn,
        _cite_research,
        research_item_id,
        run_id,
        experiment_id,
        job_id,
        quote,
        page_anchor,
    )


def _cite_research(
    conn: "psycopg.Connection",
    research_item_id: str,
    run_id: str | None,
    experiment_id: str | None,
    job_id: str | None,
    quote: str | None,
    page_anchor: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO research_citations
              (research_item_id, run_id, experiment_id, job_id, quote, page_anchor)
            VALUES
              (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s)
            RETURNING id::text
            """,
            (research_item_id, run_id, experiment_id, job_id, quote, page_anchor),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def list_citations(
    run_id: str | None = None,
    experiment_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List research_citations filtered by run_id or experiment_id."""
    return _with_conn(conn, _list_citations, run_id, experiment_id)


def _list_citations(
    conn: "psycopg.Connection",
    run_id: str | None,
    experiment_id: str | None,
) -> list[dict]:
    if run_id is not None:
        query = (
            "SELECT * FROM research_citations WHERE run_id = %s::uuid "
            "ORDER BY created_at DESC"
        )
        params: list[Any] = [run_id]
    elif experiment_id is not None:
        query = (
            "SELECT * FROM research_citations WHERE experiment_id = %s::uuid "
            "ORDER BY created_at DESC"
        )
        params = [experiment_id]
    else:
        query = "SELECT * FROM research_citations ORDER BY created_at DESC LIMIT 100"
        params = []
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# M6: reviews + telemetry (schema in 0006)
# ---------------------------------------------------------------------------

_VALID_VERDICTS = {"approve", "reject", "abstain"}


def create_review(
    *,
    job_id: str,
    reviewer_model: str,
    verdict: str,
    reviewer_kind: str = "sync",
    target_op: str | None = None,
    rationale: str | None = None,
    evidence: dict | None = None,
    run_id: str | None = None,
    cost_usd: float = 0.0,
    decision_id: str | None = None,
    otel_span_id: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> str:
    """Insert a row into agent_reviews. Returns the new review id."""
    if verdict not in _VALID_VERDICTS:
        raise ValueError(
            f"verdict must be one of {sorted(_VALID_VERDICTS)}, got {verdict!r}"
        )
    return _with_conn(
        conn,
        _create_review,
        job_id,
        reviewer_model,
        verdict,
        reviewer_kind,
        target_op,
        rationale,
        evidence or {},
        run_id,
        float(cost_usd),
        decision_id,
        otel_span_id,
    )


def _create_review(
    conn: "psycopg.Connection",
    job_id: str,
    reviewer_model: str,
    verdict: str,
    reviewer_kind: str,
    target_op: str | None,
    rationale: str | None,
    evidence: dict,
    run_id: str | None,
    cost_usd: float,
    decision_id: str | None,
    otel_span_id: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_reviews
              (job_id, run_id, reviewer_model, reviewer_kind, target_op,
               verdict, rationale, evidence, cost_usd, decision_id, otel_span_id)
            VALUES
              (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::uuid, %s)
            RETURNING id::text
            """,
            (
                job_id,
                run_id,
                reviewer_model,
                reviewer_kind,
                target_op,
                verdict,
                rationale,
                json.dumps(evidence),
                cost_usd,
                decision_id,
                otel_span_id,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def get_review(
    review_id: str,
    conn: "psycopg.Connection | None" = None,
) -> dict:
    """Fetch one agent_reviews row. Raises KeyError if not found."""
    return _with_conn(conn, _get_review, review_id)


def _get_review(conn: "psycopg.Connection", review_id: str) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM agent_reviews WHERE id = %s::uuid", (review_id,))
        row = cur.fetchone()
    if row is None:
        raise KeyError(f"agent_reviews row not found: {review_id}")
    return dict(row)


def list_reviews(
    job_id: str | None = None,
    verdict: str | None = None,
    limit: int = 50,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List agent_reviews rows, newest first."""
    return _with_conn(conn, _list_reviews, job_id, verdict, limit)


def _list_reviews(
    conn: "psycopg.Connection",
    job_id: str | None,
    verdict: str | None,
    limit: int,
) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if job_id is not None:
        clauses.append("job_id = %s::uuid")
        params.append(job_id)
    if verdict is not None:
        clauses.append("verdict = %s")
        params.append(verdict)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM agent_reviews {where} ORDER BY created_at DESC LIMIT %s",
            params,
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def find_review_for_op(
    job_id: str,
    target_op: str,
    conn: "psycopg.Connection | None" = None,
) -> dict | None:
    """Return the newest review row for (job_id, target_op), or None."""
    return _with_conn(conn, _find_review_for_op, job_id, target_op)


def _find_review_for_op(
    conn: "psycopg.Connection",
    job_id: str,
    target_op: str,
) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM agent_reviews
             WHERE job_id = %s::uuid AND target_op = %s
             ORDER BY created_at DESC
             LIMIT 1
            """,
            (job_id, target_op),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def record_span(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None = None,
    job_id: str | None = None,
    kind: str,
    name: str,
    started_at,
    ended_at=None,
    duration_ms: int | None = None,
    attributes: dict | None = None,
    status: str = "ok",
    error: str | None = None,
    conn: "psycopg.Connection | None" = None,
) -> int:
    """Insert one agent_telemetry_spans row. Best-effort: never raises.

    Returns the new span row id, or -1 if the DB is unreachable.
    """
    try:
        return _with_conn(
            conn,
            _record_span,
            trace_id,
            span_id,
            parent_span_id,
            job_id,
            kind,
            name,
            started_at,
            ended_at,
            duration_ms,
            attributes or {},
            status,
            error,
        )
    except Exception as exc:  # pragma: no cover - best-effort exporter
        import sys

        print(f"[record_span] DB unavailable: {exc}", file=sys.stderr)
        return -1


def _record_span(
    conn: "psycopg.Connection",
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    job_id: str | None,
    kind: str,
    name: str,
    started_at,
    ended_at,
    duration_ms: int | None,
    attributes: dict,
    status: str,
    error: str | None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_telemetry_spans
              (trace_id, span_id, parent_span_id, job_id, kind, name,
               started_at, ended_at, duration_ms, attributes, status, error)
            VALUES
              (%s, %s, %s, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            RETURNING id
            """,
            (
                trace_id,
                span_id,
                parent_span_id,
                job_id,
                kind,
                name,
                started_at,
                ended_at,
                duration_ms,
                json.dumps(attributes),
                status,
                error,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def list_spans(
    trace_id: str | None = None,
    job_id: str | None = None,
    kind: str | None = None,
    limit: int = 200,
    conn: "psycopg.Connection | None" = None,
) -> list[dict]:
    """List agent_telemetry_spans rows."""
    return _with_conn(conn, _list_spans, trace_id, job_id, kind, limit)


def _list_spans(
    conn: "psycopg.Connection",
    trace_id: str | None,
    job_id: str | None,
    kind: str | None,
    limit: int,
) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if trace_id is not None:
        clauses.append("trace_id = %s")
        params.append(trace_id)
    if job_id is not None:
        clauses.append("job_id = %s::uuid")
        params.append(job_id)
    if kind is not None:
        clauses.append("kind = %s")
        params.append(kind)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM agent_telemetry_spans {where} "
            f"ORDER BY started_at DESC LIMIT %s",
            params,
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def set_job_trace(
    job_id: str,
    trace_id: str,
    root_span_id: str,
    conn: "psycopg.Connection | None" = None,
) -> None:
    """Set agent_jobs.otel_trace_id and otel_root_span_id."""
    _with_conn(conn, _set_job_trace, job_id, trace_id, root_span_id)


def _set_job_trace(
    conn: "psycopg.Connection",
    job_id: str,
    trace_id: str,
    root_span_id: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE agent_jobs
               SET otel_trace_id = %s,
                   otel_root_span_id = %s
             WHERE id = %s::uuid
            """,
            (trace_id, root_span_id, job_id),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# M8: agent_tool_audit (schema in 0007)
# ---------------------------------------------------------------------------


def insert_tool_audit(
    rec: dict,
    conn: "psycopg.Connection | None" = None,
) -> int:
    """Insert one agent_tool_audit row from an audit record dict.

    Best-effort: if the DB is unreachable, returns -1 and prints a warning
    to stderr instead of raising. Caller is responsible for keeping the
    JSONL file backend in sync.

    Expected ``rec`` shape (matches ``AuditRecord.to_dict()``):
      timestamp, session_id, skill_name, tool_name, operation, decision,
      mode, policy_profile, audit_required, args_hash[, job_id, extra].

    Note: ``append_job_event(event_type="tool_audit", ...)`` is the M7-era
    audit path and is preserved for the offline-only mode. Prefer this
    function for new callers — it gives a typed table and indexes for
    operator queries.
    """
    try:
        return _with_conn(conn, _insert_tool_audit, rec)
    except Exception as exc:
        import sys

        sys.stderr.write(f"[insert_tool_audit warn] {exc}\n")
        return -1


def _insert_tool_audit(conn: "psycopg.Connection", rec: dict) -> int:
    extra = rec.get("extra") or {}
    job_id = rec.get("job_id")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agent_tool_audit
              (ts, session_id, job_id, skill_name, tool_name, operation,
               decision, mode, policy_profile, audit_required, args_hash, extra)
            VALUES
              (%s, %s::uuid, %s::uuid, %s, %s, %s,
               %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                rec.get("timestamp"),
                rec.get("session_id"),
                job_id,
                rec.get("skill_name"),
                rec.get("tool_name"),
                rec.get("operation"),
                rec.get("decision"),
                rec.get("mode", "default"),
                rec.get("policy_profile", "default"),
                bool(rec.get("audit_required", False)),
                rec.get("args_hash", ""),
                json.dumps(extra),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


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
