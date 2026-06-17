"""CTF DB helpers (M11-T001).

Thin wrappers around `tools/kca/db.get_conn()` for the M11 schema:
`ctf_events`, `ctf_challenges`, `ctf_attempts`. The pre-existing
`ctf_scopes` table from migration 0001 is treated as read-only here;
authoring scope rows belongs to `tools/kca/ctf.py` (M11-T003).

Side-effect classification:
  - All helpers are LOCAL_WRITE / LOCAL_READ. Remote-write gating
    happens at the underlying `tools/kca/db.get_conn()` layer.

Invariants enforced here (cross-link: docs/adr/0016-ctf-data-model.md):

  - The flag *value* is never accepted as a parameter and never persisted.
    `record_attempt` takes `flag_length` (int) only.
  - `response_excerpt` is truncated to 256 chars; callers are expected to
    pre-scrub anything matching `expected_flag_format`.
  - `credentials_ref` on events is a path hint (string), not a credential
    value; the helper rejects values that look like credentials.

Module is importable without a live DB — connection happens lazily inside
each helper (delegated to `tools.kca.db._with_conn`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Make tools/kca/ importable for the shared `db` module + helpers. The
# downstream `tools/kca/db.py` adds repo-root to sys.path via dotenv, so
# we mirror its discovery path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_KCA = _REPO_ROOT / "tools" / "kca"
if str(_TOOLS_KCA) not in sys.path:
    sys.path.insert(0, str(_TOOLS_KCA))

import db as _db  # noqa: E402  (path manipulation must precede import)

__all__ = [
    "register_event",
    "add_challenge",
    "set_scope_for_challenge",
    "record_attempt",
    "list_events",
    "get_challenge",
    "list_attempts",
    "VALID_CATEGORIES",
    "RESPONSE_EXCERPT_MAX_LEN",
]

VALID_CATEGORIES: tuple[str, ...] = (
    "web",
    "crypto",
    "rev",
    "pwn",
    "forensics",
    "osint",
    "misc",
)

RESPONSE_EXCERPT_MAX_LEN = 256

# Heuristic prefixes used to reject obvious credential-value leakage into
# `credentials_ref`. The intent is a path hint; we refuse anything that
# looks like a token, JSON blob, or env-var value pair.
_CREDENTIAL_VALUE_MARKERS = ("=", "{", '"token"', "Bearer ", "sk-", "eyJ")


def _validate_credentials_ref(ref: str | None) -> None:
    if ref is None:
        return
    if any(marker in ref for marker in _CREDENTIAL_VALUE_MARKERS):
        raise ValueError(
            "credentials_ref must be a path hint (e.g. '~/.ctf/<slug>.json'), never the credential value itself"
        )


def _truncate_excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= RESPONSE_EXCERPT_MAX_LEN:
        return text
    return text[: RESPONSE_EXCERPT_MAX_LEN - 1] + "…"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def register_event(
    project_id: str,
    slug: str,
    name: str,
    *,
    ctftime_event_id: int | None = None,
    event_url: str | None = None,
    start_at: Any = None,
    end_at: Any = None,
    scoring: str = "jeopardy",
    credentials_ref: str | None = None,
    notes: str | None = None,
    conn=None,
) -> str:
    """Insert a ctf_events row. Returns the new event id (uuid str).

    Idempotent on (project_id, slug): re-inserting the same slug returns
    the existing row's id. Other columns are NOT updated on conflict.
    """
    if not slug:
        raise ValueError("slug is required")
    if not name:
        raise ValueError("name is required")
    _validate_credentials_ref(credentials_ref)
    return _db._with_conn(
        conn,
        _register_event,
        project_id,
        slug,
        name,
        ctftime_event_id,
        event_url,
        start_at,
        end_at,
        scoring,
        credentials_ref,
        notes,
    )


def _register_event(
    conn,
    project_id: str,
    slug: str,
    name: str,
    ctftime_event_id: int | None,
    event_url: str | None,
    start_at: Any,
    end_at: Any,
    scoring: str,
    credentials_ref: str | None,
    notes: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ctf_events
              (project_id, slug, name, ctftime_event_id, event_url,
               start_at, end_at, scoring, credentials_ref, notes)
            VALUES
              (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE
              SET slug = EXCLUDED.slug
            RETURNING id::text
            """,
            (
                project_id,
                slug,
                name,
                ctftime_event_id,
                event_url,
                start_at,
                end_at,
                scoring,
                credentials_ref,
                notes,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def list_events(
    project_id: str | None = None,
    limit: int = 100,
    conn=None,
) -> list[dict]:
    """List ctf_events rows newest first. Optional project_id filter."""
    return _db._with_conn(conn, _list_events, project_id, limit)


def _list_events(conn, project_id: str | None, limit: int) -> list[dict]:
    if project_id is not None:
        query = "SELECT * FROM ctf_events WHERE project_id = %s::uuid ORDER BY created_at DESC LIMIT %s"
        params: list[Any] = [project_id, limit]
    else:
        query = "SELECT * FROM ctf_events ORDER BY created_at DESC LIMIT %s"
        params = [limit]
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------


def add_challenge(
    event_id: str,
    slug: str,
    name: str,
    category: str,
    *,
    points: int | None = None,
    description: str | None = None,
    expected_flag_format: str | None = None,
    attachments_path: str | None = None,
    remote_endpoint: str | None = None,
    scope_id: str | None = None,
    conn=None,
) -> str:
    """Insert a ctf_challenges row. Returns the new challenge id (uuid str).

    Idempotent on (event_id, slug): re-inserting the same (event, slug)
    pair returns the existing row's id without modifying any column.
    """
    if not slug:
        raise ValueError("slug is required")
    if not name:
        raise ValueError("name is required")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {VALID_CATEGORIES!r}, got {category!r}")
    return _db._with_conn(
        conn,
        _add_challenge,
        event_id,
        slug,
        name,
        category,
        points,
        description,
        expected_flag_format,
        attachments_path,
        remote_endpoint,
        scope_id,
    )


def _add_challenge(
    conn,
    event_id: str,
    slug: str,
    name: str,
    category: str,
    points: int | None,
    description: str | None,
    expected_flag_format: str | None,
    attachments_path: str | None,
    remote_endpoint: str | None,
    scope_id: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ctf_challenges
              (event_id, scope_id, slug, name, category, points,
               description, expected_flag_format, attachments_path,
               remote_endpoint)
            VALUES
              (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id, slug) DO UPDATE
              SET slug = EXCLUDED.slug
            RETURNING id::text
            """,
            (
                event_id,
                scope_id,
                slug,
                name,
                category,
                points,
                description,
                expected_flag_format,
                attachments_path,
                remote_endpoint,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def set_scope_for_challenge(
    challenge_id: str,
    scope_id: str | None,
    conn=None,
) -> None:
    """Set / clear the ctf_challenges.scope_id FK to ctf_scopes(id)."""
    _db._with_conn(conn, _set_scope_for_challenge, challenge_id, scope_id)


def _set_scope_for_challenge(
    conn,
    challenge_id: str,
    scope_id: str | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ctf_challenges
               SET scope_id = %s::uuid
             WHERE id = %s::uuid
            """,
            (scope_id, challenge_id),
        )
    conn.commit()


def get_challenge(
    event_slug: str,
    challenge_slug: str,
    conn=None,
) -> dict | None:
    """Look up a single ctf_challenges row by (event_slug, challenge_slug).

    Returns the row dict (including the joined event_id), or None if no
    matching row exists.
    """
    return _db._with_conn(conn, _get_challenge, event_slug, challenge_slug)


def _get_challenge(conn, event_slug: str, challenge_slug: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.*
              FROM ctf_challenges c
              JOIN ctf_events e ON e.id = c.event_id
             WHERE e.slug = %s AND c.slug = %s
             LIMIT 1
            """,
            (event_slug, challenge_slug),
        )
        row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Attempts
# ---------------------------------------------------------------------------


def record_attempt(
    challenge_id: str,
    accepted: bool | None,
    http_status: int | None,
    flag_length: int | None,
    response_excerpt: str | None,
    *,
    run_id: str | None = None,
    event_account: str | None = None,
    team_id: str | None = None,
    conn=None,
) -> str:
    """Insert a ctf_attempts row. Returns the new attempt id (uuid str).

    `flag_length` records only the integer length — the flag value MUST
    never be persisted. `response_excerpt` is truncated to 256 chars.
    `event_account` and `team_id` record the credential identity that
    actually made the submission (multi-account safety; see ADR-0016 and
    the M9.4 kkr.py replay).

    Note on length-vs-identifier disclosure (per task spec invariant):
    the helper rejects passing `flag_length` together with a
    `response_excerpt` that already contains the literal phrase
    "flag length" — a pattern that would let an observer reconstruct
    the flag from row contents alone. Callers should pre-scrub the
    excerpt before invoking this helper.
    """
    if flag_length is not None and flag_length < 0:
        raise ValueError("flag_length must be non-negative")
    if flag_length is not None and response_excerpt is not None and "flag length" in response_excerpt.lower():
        raise ValueError(
            "response_excerpt must not echo 'flag length' alongside the "
            "numeric flag_length column; scrub the excerpt first"
        )
    excerpt = _truncate_excerpt(response_excerpt)
    return _db._with_conn(
        conn,
        _record_attempt,
        challenge_id,
        accepted,
        http_status,
        flag_length,
        excerpt,
        run_id,
        event_account,
        team_id,
    )


def _record_attempt(
    conn,
    challenge_id: str,
    accepted: bool | None,
    http_status: int | None,
    flag_length: int | None,
    response_excerpt: str | None,
    run_id: str | None,
    event_account: str | None,
    team_id: str | None,
) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ctf_attempts
              (challenge_id, run_id, accepted, http_status, flag_length,
               event_account, team_id, response_excerpt)
            VALUES
              (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            (
                challenge_id,
                run_id,
                accepted,
                http_status,
                flag_length,
                event_account,
                team_id,
                response_excerpt,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row["id"]


def list_attempts(
    challenge_id: str,
    limit: int = 50,
    conn=None,
) -> list[dict]:
    """List ctf_attempts for a challenge, newest first."""
    return _db._with_conn(conn, _list_attempts, challenge_id, limit)


def _list_attempts(conn, challenge_id: str, limit: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM ctf_attempts
             WHERE challenge_id = %s::uuid
             ORDER BY submitted_at DESC
             LIMIT %s
            """,
            (challenge_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
