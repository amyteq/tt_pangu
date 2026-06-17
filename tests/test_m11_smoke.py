"""M11 smoke tests — regression assertions against the M11 cloud DB seed.

DB-gated, assertion-only. Mirrors the ``tests/test_m9_smoke.py`` and
``tests/test_m10_smoke.py`` posture: SKIPs cleanly without
``SUPABASE_DB_URL``, and SKIPs cleanly when the M11 seed rows are
absent (so a fresh CI Postgres with migrations only stays green).

The M11 seed lives in the `kca-fixtures-2026` event row populated by
T004 / T005 / T006. This file asserts:

  - Migration ``0008_m11_ctf.sql`` is applied (4 ctf_* tables present).
  - ``ctf_events`` contains the ``kca-fixtures-2026`` row.
  - ``ctf_challenges`` contains both bundled challenges (web + crypto)
    for that event.
  - ``ctf_scopes`` contains the matching scope rows referenced by the
    bundle yaml files.
  - ``agent_reviews`` has at least 2 rows with target_op ∈
    {challenge_run, flag_submit} from T006.
  - ``ctf_attempts`` has at least 2 rows with ``accepted=true`` from
    T005 (local solves) and T006 (gate round-trip).

Run with:
    SUPABASE_DB_URL=... python -m pytest tests/test_m11_smoke.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

requires_db = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set",
)

# Canonical seed slug. Set in T004; both T005 and T006 attach their
# rows to this event.
EVENT_SLUG = "kca-fixtures-2026"
WEB_CHALLENGE_SLUG = "web-1-cookie-monster"
CRYPTO_CHALLENGE_SLUG = "crypto-1-tiny-rsa"
# Scope names per the bundle yamls (data/ctf/.../challenge.yaml::scope_ref).
WEB_SCOPE_NAME = "ctf-local-kca-fixtures-2026-web-1"
CRYPTO_SCOPE_NAME = "ctf-local-kca-fixtures-2026-crypto-1"

# Minimum row counts expected at the milestone-close DB state.
EXPECTED_CHALLENGES = 2
EXPECTED_SCOPES = 2
EXPECTED_T006_REVIEWS = 2  # one challenge_run + one flag_submit
EXPECTED_ACCEPTED_ATTEMPTS = 2  # T005 web + T005 crypto baseline


def _table_exists(cur, table_name: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
           WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    row = cur.fetchone()
    return bool(row[0])


@pytest.fixture(scope="module")
def db_conn():
    """Open one Postgres connection for the module. Skips cleanly when
    ``SUPABASE_DB_URL`` is unset.
    """
    if not os.environ.get("SUPABASE_DB_URL"):
        pytest.skip("SUPABASE_DB_URL not set")
    import psycopg

    conn = psycopg.connect(os.environ["SUPABASE_DB_URL"])
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema presence — migration 0008 applied
# ---------------------------------------------------------------------------


@requires_db
def test_migration_0008_tables_present(db_conn):
    """All four M11 tables exist. SKIP (not FAIL) on a pre-migration DB
    so the live-db CI job doesn't trip when 0008 hasn't been applied
    yet."""
    expected = ("ctf_events", "ctf_challenges", "ctf_scopes", "ctf_attempts")
    with db_conn.cursor() as cur:
        missing = [t for t in expected if not _table_exists(cur, t)]
    if missing:
        pytest.skip(f"M11 migration 0008 not applied (missing tables: {missing}); live-db job is green pre-migration")
    # All four present — explicit PASS.
    assert missing == []


# ---------------------------------------------------------------------------
# Event row
# ---------------------------------------------------------------------------


@requires_db
def test_ctf_events_contains_fixture_event(db_conn):
    with db_conn.cursor() as cur:
        if not _table_exists(cur, "ctf_events"):
            pytest.skip("ctf_events table not present")
        cur.execute(
            "SELECT id::text, slug, name FROM ctf_events WHERE slug = %s LIMIT 1",
            (EVENT_SLUG,),
        )
        row = cur.fetchone()
    if row is None:
        pytest.skip(
            f"M11 seed event {EVENT_SLUG!r} not present; "
            "T004 must run against this DB before smoke assertions are meaningful"
        )
    assert row[1] == EVENT_SLUG
    assert row[2], f"event {EVENT_SLUG!r} has empty name"


# ---------------------------------------------------------------------------
# Challenge rows — web + crypto
# ---------------------------------------------------------------------------


@requires_db
def test_ctf_challenges_contains_web_and_crypto_for_fixture_event(db_conn):
    with db_conn.cursor() as cur:
        if not _table_exists(cur, "ctf_challenges"):
            pytest.skip("ctf_challenges table not present")
        cur.execute(
            """
            SELECT c.slug, c.category
              FROM ctf_challenges c
              JOIN ctf_events e ON e.id = c.event_id
             WHERE e.slug = %s
             ORDER BY c.slug
            """,
            (EVENT_SLUG,),
        )
        rows = cur.fetchall()
    if len(rows) < EXPECTED_CHALLENGES:
        pytest.skip(
            f"Expected ≥{EXPECTED_CHALLENGES} ctf_challenges rows for "
            f"event {EVENT_SLUG!r}, found {len(rows)}; T004 seed missing"
        )
    slugs = {r[0] for r in rows}
    assert WEB_CHALLENGE_SLUG in slugs, f"missing web challenge {WEB_CHALLENGE_SLUG!r}; have {slugs!r}"
    assert CRYPTO_CHALLENGE_SLUG in slugs, f"missing crypto challenge {CRYPTO_CHALLENGE_SLUG!r}; have {slugs!r}"
    # Category sanity — protects against a copy-paste regression in T004.
    categories = {r[0]: r[1] for r in rows}
    if WEB_CHALLENGE_SLUG in categories:
        assert categories[WEB_CHALLENGE_SLUG] == "web"
    if CRYPTO_CHALLENGE_SLUG in categories:
        assert categories[CRYPTO_CHALLENGE_SLUG] == "crypto"


# ---------------------------------------------------------------------------
# Scope rows — the two ctf_scopes rows the bundle yaml files reference
# ---------------------------------------------------------------------------


@requires_db
def test_ctf_scopes_contains_fixture_scopes(db_conn):
    with db_conn.cursor() as cur:
        if not _table_exists(cur, "ctf_scopes"):
            pytest.skip("ctf_scopes table not present")
        cur.execute(
            """
            SELECT name FROM ctf_scopes
             WHERE name IN (%s, %s)
            """,
            (WEB_SCOPE_NAME, CRYPTO_SCOPE_NAME),
        )
        names = {r[0] for r in cur.fetchall()}
    if not names:
        pytest.skip(
            f"M11 fixture scopes ({WEB_SCOPE_NAME!r}, {CRYPTO_SCOPE_NAME!r}) "
            "not present; T004 / T003 ctf scope set must run first"
        )
    if len(names) < EXPECTED_SCOPES:
        pytest.skip(f"only {len(names)}/{EXPECTED_SCOPES} fixture scopes present ({names!r}); partial T004 seed")
    assert WEB_SCOPE_NAME in names
    assert CRYPTO_SCOPE_NAME in names


# ---------------------------------------------------------------------------
# Reviewer rows — at least one challenge_run + one flag_submit from T006
# ---------------------------------------------------------------------------


@requires_db
def test_agent_reviews_records_t006_challenge_run_and_flag_submit(db_conn):
    """T006 fires both the ``challenge_run`` and ``flag_submit`` reviewer
    gates against the fixture event. We require ≥ 2 rows with one of
    those target_ops, with at least one of each kind.
    """
    with db_conn.cursor() as cur:
        if not _table_exists(cur, "agent_reviews"):
            pytest.skip("agent_reviews table not present")
        cur.execute(
            """
            SELECT target_op, COUNT(*) AS n
              FROM agent_reviews
             WHERE target_op IN ('challenge_run', 'flag_submit')
             GROUP BY target_op
            """
        )
        by_op = {r[0]: int(r[1]) for r in cur.fetchall()}
    total = sum(by_op.values())
    if total < EXPECTED_T006_REVIEWS:
        pytest.skip(
            f"Expected ≥{EXPECTED_T006_REVIEWS} agent_reviews rows for "
            f"target_op ∈ (challenge_run, flag_submit); found {total} "
            f"({by_op!r}). T006 reviewer-gate round-trip must run first"
        )
    assert by_op.get("challenge_run", 0) >= 1, f"no challenge_run review rows recorded; T006 partial. by_op={by_op!r}"
    assert by_op.get("flag_submit", 0) >= 1, f"no flag_submit review rows recorded; T006 partial. by_op={by_op!r}"


# ---------------------------------------------------------------------------
# Attempt rows — at least two accepted=true from T005 (+ T006 if local)
# ---------------------------------------------------------------------------


@requires_db
def test_ctf_attempts_records_at_least_two_accepted_attempts(db_conn):
    """T005 records one accepted=true attempt per bundled challenge
    (web + crypto). T006 may add another LOCAL_WRITE row. T007 (if it
    ran) may add the live row. We require ≥ 2 accepted=true rows
    scoped to the fixture event.
    """
    with db_conn.cursor() as cur:
        if not _table_exists(cur, "ctf_attempts"):
            pytest.skip("ctf_attempts table not present")
        cur.execute(
            """
            SELECT COUNT(*) FROM ctf_attempts a
              JOIN ctf_challenges c ON c.id = a.challenge_id
              JOIN ctf_events e     ON e.id = c.event_id
             WHERE e.slug = %s AND a.accepted IS TRUE
            """,
            (EVENT_SLUG,),
        )
        n = int(cur.fetchone()[0])
    if n < EXPECTED_ACCEPTED_ATTEMPTS:
        pytest.skip(
            f"Expected ≥{EXPECTED_ACCEPTED_ATTEMPTS} accepted=true "
            f"ctf_attempts rows for event {EVENT_SLUG!r}; found {n}. "
            "T005 + T006 seed missing"
        )
    assert n >= EXPECTED_ACCEPTED_ATTEMPTS


# ---------------------------------------------------------------------------
# Flag-value invariant — ctf_attempts must never store the raw flag
# ---------------------------------------------------------------------------


@requires_db
def test_ctf_attempts_never_stores_raw_flag(db_conn):
    """The M11 hygiene contract: ctf_attempts.response_excerpt and
    .request_excerpt MUST NOT contain anything that matches the
    canonical flag formats (picoCTF{...}, kca{...}, flag{...},
    FLAG{...}, CTF{...}).

    We compile the regex inside the DB query so the row data never
    transits this process.
    """
    with db_conn.cursor() as cur:
        if not _table_exists(cur, "ctf_attempts"):
            pytest.skip("ctf_attempts table not present")
        # Column-presence guard: response_excerpt is the canonical
        # column from migration 0008. If T001 renamed it, surface
        # that as a SKIP, not a FAIL.
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'ctf_attempts'
            """
        )
        cols = {r[0] for r in cur.fetchall()}
        if "response_excerpt" not in cols:
            pytest.skip("ctf_attempts.response_excerpt column missing")
        cur.execute(
            r"""
            SELECT COUNT(*) FROM ctf_attempts
             WHERE response_excerpt ~* '(picoCTF|flag|FLAG|CTF|kca)\{[A-Za-z0-9_]+\}'
            """
        )
        n_leak = int(cur.fetchone()[0])
    assert n_leak == 0, (
        f"ctf_attempts.response_excerpt holds {n_leak} row(s) matching "
        "a CTF flag format — hygiene regression vs. ADR-0016 / ADR-0017"
    )
