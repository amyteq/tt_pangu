"""M11-T001 smoke tests — CTF schema + DB helpers.

DB-gated. SKIP cleanly when ``SUPABASE_DB_URL`` is unset, mirroring the
``tests/test_m9_smoke.py`` posture so the no-DB CI job stays green.

Tests exercise:

  - register_event idempotency on (project_id, slug)
  - add_challenge insertion + category enum guard
  - record_attempt with multi-account (event_account / team_id) carry-over
  - get_challenge by (event_slug, challenge_slug)
  - list_events / list_attempts
  - response_excerpt truncation to 256 chars
  - flag-value invariant: helper rejects "flag length" leakage
  - credentials_ref rejects credential-value markers
  - FK cascade: deleting an event removes its challenges + attempts
  - unique-constraint violation on duplicate (event_id, slug)

Each test owns its rows and cleans up by deleting the parent event
(which cascades to challenges + attempts) so re-runs are safe and the
DB is left as-found.

Run with:
    SUPABASE_DB_URL=postgresql://postgres:postgres@172.22.0.2:5432/postgres \\
        python -m pytest tests/test_m11_db.py -v
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

requires_db = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set",
)


@pytest.fixture(scope="module")
def project_id():
    """Bootstrap project for M11 smoke tests — uses kca's DEFAULT_PROJECT_ID."""
    if not os.environ.get("SUPABASE_DB_URL"):
        pytest.skip("SUPABASE_DB_URL not set")
    import db as _kca_db

    return _kca_db.ensure_default_project()


@pytest.fixture
def cleanup_events():
    """Track event ids created in a test; delete them on teardown so
    re-runs are idempotent and other tests don't see leftover rows."""
    created: list[str] = []
    yield created
    if not created:
        return
    if not os.environ.get("SUPABASE_DB_URL"):
        return
    import db as _kca_db

    with _kca_db.get_conn() as conn:
        with conn.cursor() as cur:
            for event_id in created:
                cur.execute(
                    "DELETE FROM ctf_events WHERE id = %s::uuid",
                    (event_id,),
                )
        conn.commit()


# ---------------------------------------------------------------------------
# Pure-Python tests (no DB) — run in any environment.
# ---------------------------------------------------------------------------


def test_helpers_importable():
    """The helper module imports without a live DB connection."""
    from src.db import ctf

    assert callable(ctf.register_event)
    assert callable(ctf.add_challenge)
    assert callable(ctf.set_scope_for_challenge)
    assert callable(ctf.record_attempt)
    assert callable(ctf.list_events)
    assert callable(ctf.get_challenge)
    assert callable(ctf.list_attempts)


def test_record_attempt_rejects_flag_length_in_excerpt():
    """record_attempt refuses to store an excerpt that already echoes
    'flag length' alongside the numeric flag_length column."""
    from src.db import ctf

    with pytest.raises(ValueError, match="flag length"):
        ctf.record_attempt(
            challenge_id=str(uuid.uuid4()),
            accepted=False,
            http_status=400,
            flag_length=32,
            response_excerpt="server says: bad flag length",
        )


def test_record_attempt_rejects_negative_flag_length():
    from src.db import ctf

    with pytest.raises(ValueError, match="flag_length"):
        ctf.record_attempt(
            challenge_id=str(uuid.uuid4()),
            accepted=False,
            http_status=400,
            flag_length=-1,
            response_excerpt=None,
        )


def test_register_event_rejects_credential_values():
    """credentials_ref MUST be a path hint, not a credential value."""
    from src.db import ctf

    with pytest.raises(ValueError, match="path hint"):
        ctf.register_event(
            project_id=str(uuid.uuid4()),
            slug="x",
            name="x",
            credentials_ref='{"token": "secret"}',
        )

    with pytest.raises(ValueError, match="path hint"):
        ctf.register_event(
            project_id=str(uuid.uuid4()),
            slug="x",
            name="x",
            credentials_ref="Bearer sk-abc123",
        )


def test_add_challenge_rejects_unknown_category():
    from src.db import ctf

    with pytest.raises(ValueError, match="category"):
        ctf.add_challenge(
            event_id=str(uuid.uuid4()),
            slug="c",
            name="c",
            category="not-a-category",
        )


# ---------------------------------------------------------------------------
# DB-gated tests — exercise the real schema against the local container.
# ---------------------------------------------------------------------------


@requires_db
def test_register_event_inserts_and_is_idempotent(project_id, cleanup_events):
    from src.db import ctf

    slug = f"m11-smoke-{uuid.uuid4().hex[:8]}"
    eid1 = ctf.register_event(
        project_id=project_id,
        slug=slug,
        name="M11 smoke event",
        credentials_ref="~/.ctf/m11-smoke.json",
        notes="created by tests/test_m11_db.py",
    )
    cleanup_events.append(eid1)

    eid2 = ctf.register_event(
        project_id=project_id,
        slug=slug,
        name="ignored — already exists",
    )
    assert eid1 == eid2, "register_event must be idempotent on (project_id, slug)"


@requires_db
def test_add_challenge_and_get_challenge(project_id, cleanup_events):
    from src.db import ctf

    slug = f"m11-cha-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    cleanup_events.append(event_id)

    challenge_id = ctf.add_challenge(
        event_id=event_id,
        slug="web-1",
        name="cookie-monster",
        category="web",
        points=100,
        description="see attachments",
        expected_flag_format="picoCTF{...}",
    )
    assert challenge_id

    row = ctf.get_challenge(event_slug=slug, challenge_slug="web-1")
    assert row is not None
    assert row["category"] == "web"
    assert row["points"] == 100

    # Idempotency on (event_id, slug).
    challenge_id2 = ctf.add_challenge(
        event_id=event_id,
        slug="web-1",
        name="duplicate-name-ignored",
        category="web",
    )
    assert challenge_id == challenge_id2


@requires_db
def test_record_attempt_with_multi_account_columns(project_id, cleanup_events):
    """The event_account / team_id columns (T000 carry-over) MUST round-trip."""
    from src.db import ctf

    slug = f"m11-att-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    cleanup_events.append(event_id)
    challenge_id = ctf.add_challenge(
        event_id=event_id,
        slug="crypto-1",
        name="rsa-baby",
        category="crypto",
    )

    attempt_id = ctf.record_attempt(
        challenge_id=challenge_id,
        accepted=True,
        http_status=200,
        flag_length=42,
        response_excerpt="ok",
        event_account="agent@example.test",
        team_id="t-001",
    )
    assert attempt_id

    rows = ctf.list_attempts(challenge_id=challenge_id)
    assert len(rows) == 1
    assert rows[0]["event_account"] == "agent@example.test"
    assert rows[0]["team_id"] == "t-001"
    assert rows[0]["flag_length"] == 42
    assert rows[0]["accepted"] is True


@requires_db
def test_response_excerpt_truncated_to_256(project_id, cleanup_events):
    from src.db import ctf

    slug = f"m11-trunc-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    cleanup_events.append(event_id)
    challenge_id = ctf.add_challenge(
        event_id=event_id,
        slug="web-1",
        name="excerpt-test",
        category="web",
    )

    long_excerpt = "x" * 1000  # well over the 256 cap
    ctf.record_attempt(
        challenge_id=challenge_id,
        accepted=False,
        http_status=400,
        flag_length=None,
        response_excerpt=long_excerpt,
    )

    rows = ctf.list_attempts(challenge_id=challenge_id)
    assert len(rows) == 1
    stored = rows[0]["response_excerpt"]
    assert stored is not None
    assert len(stored) <= ctf.RESPONSE_EXCERPT_MAX_LEN


@requires_db
def test_list_events_filters_by_project(project_id, cleanup_events):
    from src.db import ctf

    slug = f"m11-list-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    cleanup_events.append(event_id)

    rows = ctf.list_events(project_id=project_id, limit=100)
    assert any(r["id"] == uuid.UUID(event_id) or str(r["id"]) == event_id for r in rows)


@requires_db
def test_unique_event_slug_violation(project_id, cleanup_events):
    """ctf_events.slug is UNIQUE globally; a second project can't reuse it
    via a raw INSERT (helper is idempotent — this checks the schema)."""
    import db as _kca_db
    import psycopg
    from src.db import ctf

    slug = f"m11-unique-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    cleanup_events.append(event_id)

    with _kca_db.get_conn() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.UniqueViolation):
                cur.execute(
                    """
                    INSERT INTO ctf_events (project_id, slug, name)
                    VALUES (%s::uuid, %s, %s)
                    """,
                    (project_id, slug, "dup"),
                )


@requires_db
def test_event_delete_cascades_to_challenges_and_attempts(project_id):
    """ON DELETE CASCADE: removing an event removes its challenges and
    (via the challenge cascade) its attempts."""
    import db as _kca_db
    from src.db import ctf

    slug = f"m11-casc-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    challenge_id = ctf.add_challenge(
        event_id=event_id,
        slug="web-1",
        name="casc-test",
        category="web",
    )
    ctf.record_attempt(
        challenge_id=challenge_id,
        accepted=False,
        http_status=400,
        flag_length=None,
        response_excerpt=None,
    )

    with _kca_db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ctf_events WHERE id = %s::uuid", (event_id,))
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*)::int AS n FROM ctf_challenges WHERE id = %s::uuid",
                (challenge_id,),
            )
            assert cur.fetchone()["n"] == 0
            cur.execute(
                "SELECT count(*)::int AS n FROM ctf_attempts WHERE challenge_id = %s::uuid",
                (challenge_id,),
            )
            assert cur.fetchone()["n"] == 0


@requires_db
def test_set_scope_for_challenge(project_id, cleanup_events):
    """set_scope_for_challenge updates the scope_id FK to ctf_scopes(id)."""
    import db as _kca_db
    from src.db import ctf

    slug = f"m11-scope-{uuid.uuid4().hex[:8]}"
    event_id = ctf.register_event(project_id=project_id, slug=slug, name="evt")
    cleanup_events.append(event_id)
    challenge_id = ctf.add_challenge(
        event_id=event_id,
        slug="web-1",
        name="scope-test",
        category="web",
    )

    # Manually insert a ctf_scopes row (T003 owns the CLI for this; here
    # we just exercise the helper).
    with _kca_db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ctf_scopes
                  (project_id, name, authorized_scope, target_urls, local_only)
                VALUES
                  (%s::uuid, %s, %s, %s::jsonb, true)
                RETURNING id::text
                """,
                (
                    project_id,
                    f"scope-{slug}",
                    "local-only test scope for M11 smoke",
                    "[]",
                ),
            )
            scope_id = cur.fetchone()["id"]
        conn.commit()

    ctf.set_scope_for_challenge(challenge_id=challenge_id, scope_id=scope_id)

    row = ctf.get_challenge(event_slug=slug, challenge_slug="web-1")
    assert row is not None
    assert str(row["scope_id"]) == scope_id

    # Cleanup scope row (cleanup_events handles the event/challenge cascade).
    with _kca_db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ctf_challenges SET scope_id = NULL WHERE id = %s::uuid",
                (challenge_id,),
            )
            cur.execute("DELETE FROM ctf_scopes WHERE id = %s::uuid", (scope_id,))
        conn.commit()
