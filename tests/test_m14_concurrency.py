"""M14-T004 — pre-flight gating for ``cmd_push`` / ``cmd_submit``.

Three gates, in ADR-0020 §7 order, all firing BEFORE the approval gate and
BEFORE any real Kaggle call:

1. **Credentials pre-check (issue #62)** — ``cmd_push`` refuses with the SAME
   envelope shape ``cmd_submit`` uses when ``KAGGLE_USERNAME`` / ``KAGGLE_KEY``
   is absent.
2. **Concurrency gate (issue #53)** — refuse when ``count_active_pushes >=
   competitions.max_concurrent_pushes``, emitting ``active_runs[]``.
3. **Daily-budget gate** — ``cmd_push`` and ``cmd_submit`` refuse past
   ``competitions.max_daily_submissions`` for the UTC calendar day.

Two posture tiers (mirrors tests/test_m14_db.py):

- **Pure-Python tier** — the creds pre-check (no DB) and the "no real Kaggle
  call leaked" sentinel. Runs anywhere.
- **Ephemeral-Postgres tier** — the concurrency + daily-budget gates against a
  fixture competition row. SKIPs cleanly when no local Postgres binary exists.

The fake/fixture competition row is the authority here — there is NO real
Kaggle push or submit on any path (a global ``subprocess.run`` sentinel asserts
this). The gate is a courtesy guard per ADR-0020 §7; Kaggle's own 429/400 is
the hard authority and would HALT the loop, not retry — exercised here only
against the fixture.

Run with:
    python -m pytest tests/test_m14_concurrency.py -v
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "0011_m14_goal_loop.sql"

_PG_BINS_PRESENT = all(shutil.which(b) for b in ("initdb", "pg_ctl", "postgres"))

# Subset of the 0001/0004 shapes the T004 gates touch, plus the two courtesy
# columns 0011 layers on (max_daily_submissions exists pre-0011; the migration
# adds max_concurrent_pushes — both ADD COLUMN IF NOT EXISTS, so seeding them
# here keeps the prereq + migration idempotent under the same process).
_PREREQ_SQL = """
CREATE TABLE competitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  platform text DEFAULT 'kaggle',
  slug text UNIQUE,
  title text,
  max_daily_submissions int,
  max_concurrent_pushes int,
  last_rules_fetch_at timestamptz
);
CREATE TABLE experiments (id uuid PRIMARY KEY DEFAULT gen_random_uuid());
CREATE TABLE experiment_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  experiment_id uuid,
  metrics jsonb DEFAULT '{}',
  analysis text
);
CREATE TABLE submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  competition_id uuid REFERENCES competitions(id),
  file_path text,
  public_lb_score numeric(10,6),
  status text DEFAULT 'prepared',
  submitted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
"""

# Any real Kaggle CLI invocation the gates must NEVER reach in this module.
_REAL_KAGGLE_PREFIXES = (
    ["kaggle", "kernels", "push"],
    ["kaggle", "competitions", "submit"],
)


@pytest.fixture(autouse=True)
def _no_real_kaggle(monkeypatch):
    """Hard sentinel: fail loudly if any test reaches a real Kaggle push/submit.

    Wraps ``subprocess.run`` in both ``kg`` and the stdlib; a kaggle push /
    submit argv raises, so a gate that *fails open* is caught by the test
    rather than silently hitting the network.
    """
    import kg

    real_run = subprocess.run

    def _guard(argv, *a, **kw):
        if isinstance(argv, (list, tuple)):
            head = list(argv)[:3]
            for prefix in _REAL_KAGGLE_PREFIXES:
                if head[: len(prefix)] == prefix:
                    raise AssertionError(f"a real Kaggle command leaked past the gate: {head}")
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(kg.subprocess, "run", _guard)
    return _guard


def _push_args(**over) -> argparse.Namespace:
    base = dict(
        kernel_dir="/dev/null",
        competition=None,
        dry_run=False,
        watch=False,
        poll_seconds=60,
        max_poll_minutes=60,
    )
    base.update(over)
    return argparse.Namespace(**base)


def _submit_args(**over) -> argparse.Namespace:
    base = dict(competition="fixture-comp", file="sub.csv", message="m")
    base.update(over)
    return argparse.Namespace(**base)


def _call(fn, args) -> tuple[int, dict]:
    """Run a cmd_* fn, capture its single JSON line, return (rc, payload)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(args)
    out = buf.getvalue().strip()
    return rc, json.loads(out)


# ---------------------------------------------------------------------------
# Pure-Python tier — credentials pre-check (no DB).
# ---------------------------------------------------------------------------


def test_push_creds_precheck_matches_submit_envelope(monkeypatch):
    """cmd_push refuses with cmd_submit's exact envelope shape when a credential
    is missing, BEFORE the approval gate / any real push."""
    import kg

    # Force the approval gate ON so we can prove the creds check fires FIRST:
    # if the approval gate ran first, the error would be "ApprovalRequired".
    monkeypatch.setenv("KCA_POLICY", json.dumps({"approval_gates": {"kernel_push": True}}))
    monkeypatch.delenv("KCA_ALLOW_REMOTE", raising=False)

    # (a) username missing
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.setenv("KAGGLE_KEY", "stub-key")
    rc, payload = _call(kg.cmd_push, _push_args(competition="fixture-comp"))
    assert rc != 0
    assert payload["ok"] is False
    assert payload["error"] == "KAGGLE_USERNAME not set; cannot submit"
    assert payload["competition"] == "fixture-comp"
    assert payload["side_effect"] == "REMOTE_WRITE"
    # creds check fired BEFORE the approval gate
    assert "ApprovalRequired" not in json.dumps(payload)

    # (b) key missing — same envelope keys as cmd_submit
    monkeypatch.setenv("KAGGLE_USERNAME", "stub-user")
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    rc2, payload2 = _call(kg.cmd_push, _push_args(competition="fixture-comp"))
    assert payload2["error"] == "KAGGLE_KEY not set; cannot submit"

    # Envelope shape parity with cmd_submit's own creds refusal.
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    _, sub_payload = _call(kg.cmd_submit, _submit_args())
    assert (
        set(payload.keys())
        == set(sub_payload.keys())
        == {
            "ok",
            "error",
            "competition",
            "side_effect",
        }
    )


def test_push_dry_run_does_not_require_creds(monkeypatch, tmp_path):
    """--dry-run is READ_ONLY metadata validation; the creds pre-check must NOT
    block it (no Kaggle reached)."""
    import kg

    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    meta = tmp_path / "kernel-metadata.json"
    meta.write_text(json.dumps({"id": "u/k"}))
    rc, payload = _call(kg.cmd_push, _push_args(kernel_dir=str(tmp_path), dry_run=True))
    assert rc == 0
    assert payload["ok"] is True
    assert payload["dry_run"] is True


# ---------------------------------------------------------------------------
# Ephemeral-Postgres tier — concurrency + daily-budget gates.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_url():
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries (initdb/pg_ctl/postgres) on PATH")
    tmp = tempfile.mkdtemp(prefix="m14conc_")
    datadir = os.path.join(tmp, "data")
    sock = os.path.join(tmp, "sock")
    os.makedirs(sock, exist_ok=True)
    logfile = os.path.join(tmp, "pg.log")
    try:
        subprocess.run(
            ["initdb", "-D", datadir, "-U", "postgres", "--auth=trust"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                datadir,
                "-l",
                logfile,
                "-w",
                "-t",
                "30",
                "start",
                "-o",
                f"-c listen_addresses='' -c unix_socket_directories='{sock}'",
            ],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"could not boot ephemeral Postgres (likely sandboxed): {exc}")
    url = f"postgresql://postgres@/postgres?host={sock}"
    try:
        import psycopg

        with psycopg.connect(url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(_PREREQ_SQL)
                cur.execute(MIGRATION.read_text())
        yield url
    finally:
        subprocess.run(["pg_ctl", "-D", datadir, "-w", "stop"], capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def kg_db(pg_url, monkeypatch):
    """Bind kg's `db` module to the ephemeral Postgres + stub creds present."""
    monkeypatch.setenv("SUPABASE_DB_URL", pg_url)
    monkeypatch.setenv("KCA_DB_TARGET", "local")
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")
    monkeypatch.setenv("KAGGLE_USERNAME", "stub-user")
    monkeypatch.setenv("KAGGLE_KEY", "stub-key")
    # Approval gate ON so a passed gate would still be blocked downstream
    # (proves the budget gate fired BEFORE the approval gate when it refuses).
    monkeypatch.setenv("KCA_POLICY", json.dumps({"approval_gates": {"kernel_push": True}}))
    monkeypatch.delenv("KCA_ALLOW_REMOTE", raising=False)
    import kg

    return kg


def _new_comp(pg_url, *, slug, max_concurrent=None, max_daily=None) -> str:
    import psycopg

    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO competitions (slug, max_concurrent_pushes, "
                "max_daily_submissions) VALUES (%s,%s,%s) RETURNING id::text",
                (slug, max_concurrent, max_daily),
            )
            return cur.fetchone()[0]


def test_concurrency_gate_refuses_at_limit(kg_db, pg_url):
    """cmd_push refuses cleanly when count_active_pushes >= max_concurrent_pushes,
    emitting active_runs[], BEFORE the approval gate / any real push."""
    import psycopg

    slug = f"conc-{uuid.uuid4().hex[:8]}"
    comp_id = _new_comp(pg_url, slug=slug, max_concurrent=2)
    # two active (non-terminal) latest-per-slug runs == at the limit of 2
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "created_at) VALUES (%s::uuid,'kca/a','running', now())",
                (comp_id,),
            )
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "created_at) VALUES (%s::uuid,'kca/b','queued', now())",
                (comp_id,),
            )
            # a terminal slug must NOT count toward the limit
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "created_at) VALUES (%s::uuid,'kca/c','complete', now())",
                (comp_id,),
            )

    rc, payload = _call(kg_db.cmd_push, _push_args(competition=slug))
    assert rc == 2, payload  # EXIT_BLOCKED
    assert payload["ok"] is False
    assert "max_concurrent_pushes reached" in payload["error"]
    assert payload["active_pushes"] == 2
    assert payload["max_concurrent_pushes"] == 2
    # active_runs[] names the two non-terminal slugs, not the terminal one
    slugs = {r["file_path"] for r in payload["active_runs"]}
    assert slugs == {"kca/a", "kca/b"}
    assert "kca/c" not in slugs
    # refused BEFORE the approval gate
    assert "ApprovalRequired" not in json.dumps(payload)


def test_terminal_status_casing_normalized_not_counted_active(kg_db, pg_url):
    """Regression for M14-T009 finding #4: a finished run whose status is written
    as the Python enum repr ('SubmissionStatus.COMPLETE') or upper-case ('COMPLETE')
    must normalize to the terminal token 'complete' and NOT be miscounted as an
    active concurrency slot. The earlier code compared lower(status) only, so
    'submissionstatus.complete' / 'COMPLETE' leaked through as active."""
    import psycopg

    slug = f"casing-{uuid.uuid4().hex[:8]}"
    comp_id = _new_comp(pg_url, slug=slug, max_concurrent=2)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            # three finished runs, three casings — all must read terminal
            for slug_path, status in (
                ("kca/x", "SubmissionStatus.COMPLETE"),
                ("kca/y", "COMPLETE"),
                ("kca/z", "complete"),
            ):
                cur.execute(
                    "INSERT INTO submissions (competition_id, file_path, status, "
                    "created_at) VALUES (%s::uuid,%s,%s, now())",
                    (comp_id, slug_path, status),
                )

    # All three finished rows normalize to terminal -> zero active slots, so the
    # push proceeds past the concurrency gate (the approval gate then refuses).
    # If the casing leaked through as active, max_concurrent (2) would trip first.
    rc, payload = _call(kg_db.cmd_push, _push_args(competition=slug))
    assert payload["ok"] is False
    assert "max_concurrent_pushes" not in payload
    assert "ApprovalRequired: kernel_push" in payload["error"]


def test_concurrency_gate_allows_below_limit(kg_db, pg_url):
    """Below max_concurrent_pushes, the concurrency gate does NOT refuse — the
    push proceeds to the approval gate (which blocks it, proving no real push)."""
    slug = f"conc-ok-{uuid.uuid4().hex[:8]}"
    _new_comp(pg_url, slug=slug, max_concurrent=2)  # zero active runs

    rc, payload = _call(kg_db.cmd_push, _push_args(competition=slug))
    # Concurrency gate passed; approval gate then refuses (EXIT_BLOCKED) — and
    # crucially the _no_real_kaggle sentinel did not fire.
    assert payload["ok"] is False
    assert "ApprovalRequired: kernel_push" in payload["error"]
    assert "max_concurrent_pushes" not in payload


def test_daily_budget_gate_push_refuses_past_limit(kg_db, pg_url):
    """cmd_push refuses past max_daily_submissions for the UTC calendar day."""
    import psycopg

    slug = f"daily-{uuid.uuid4().hex[:8]}"
    comp_id = _new_comp(pg_url, slug=slug, max_concurrent=10, max_daily=2)
    now = dt.datetime.now(dt.timezone.utc)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today_midnight - dt.timedelta(minutes=1)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            # two submitted today (== the limit of 2)
            for i in range(2):
                cur.execute(
                    "INSERT INTO submissions (competition_id, file_path, status, "
                    "submitted_at) VALUES (%s::uuid,%s,'complete',%s)",
                    (comp_id, f"today-{i}.csv", today_midnight + dt.timedelta(hours=1)),
                )
            # one submitted yesterday — across the UTC-midnight boundary, must
            # NOT count toward today's budget (the count resets at UTC 00:00)
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "submitted_at) VALUES (%s::uuid,'yday.csv','complete',%s)",
                (comp_id, yesterday),
            )

    rc, payload = _call(kg_db.cmd_push, _push_args(competition=slug))
    assert rc == 2, payload
    assert payload["ok"] is False
    assert "max_daily_submissions reached" in payload["error"]
    assert payload["today_submissions"] == 2  # yesterday excluded by UTC window
    assert payload["max_daily_submissions"] == 2
    assert "next_window_open_utc" in payload
    assert "ApprovalRequired" not in json.dumps(payload)


def test_daily_budget_gate_submit_refuses_past_limit(kg_db, pg_url):
    """cmd_submit shares the daily-budget gate; refuses past max_daily_submissions
    BEFORE the approval gate / any real submit."""
    import psycopg

    slug = f"daily-sub-{uuid.uuid4().hex[:8]}"
    comp_id = _new_comp(pg_url, slug=slug, max_daily=1)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "submitted_at) VALUES (%s::uuid,'one.csv','complete', now())",
                (comp_id,),
            )

    rc, payload = _call(kg_db.cmd_submit, _submit_args(competition=slug))
    assert rc == 2, payload
    assert payload["ok"] is False
    assert "max_daily_submissions reached" in payload["error"]
    assert payload["today_submissions"] == 1
    assert "ApprovalRequired" not in json.dumps(payload)


def test_daily_budget_resets_next_utc_day(kg_db, pg_url):
    """With submissions only from yesterday, today's count is 0 and the gate
    does not refuse — the UTC-day window reset is exercised deterministically
    via row timestamps (no wall-clock dependency)."""
    import psycopg

    slug = f"reset-{uuid.uuid4().hex[:8]}"
    comp_id = _new_comp(pg_url, slug=slug, max_concurrent=10, max_daily=1)
    now = dt.datetime.now(dt.timezone.utc)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today_midnight - dt.timedelta(hours=1)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, status, "
                "submitted_at) VALUES (%s::uuid,'yday.csv','complete',%s)",
                (comp_id, yesterday),
            )

    rc, payload = _call(kg_db.cmd_push, _push_args(competition=slug))
    # daily gate passed (0 today); approval gate then refuses — no budget block
    assert payload["ok"] is False
    assert "max_daily_submissions" not in payload
    assert "ApprovalRequired: kernel_push" in payload["error"]


def test_missing_competition_skips_db_gates(kg_db):
    """No --competition → DB-backed gates are skipped (courtesy guard is
    best-effort); creds present, so control reaches the approval gate."""
    rc, payload = _call(kg_db.cmd_push, _push_args(competition=None))
    assert payload["ok"] is False
    assert "ApprovalRequired: kernel_push" in payload["error"]
    assert "max_concurrent_pushes" not in payload
    assert "max_daily_submissions" not in payload


# ---------------------------------------------------------------------------
# Audit-grep sentinel — 0 real Kaggle lines from this module's source.
# ---------------------------------------------------------------------------


def test_no_real_kaggle_invocation_in_this_module():
    """The gate code in kg.py issues no real Kaggle push/submit on any refusal
    path — the three gates return BEFORE the `kaggle kernels push` /
    `kaggle competitions submit` subprocess. We assert structurally that every
    gate refusal in `kg.cmd_push` / `kg.cmd_submit` precedes the
    `subprocess.run([... "kaggle" ...])` call site."""
    kg_src = (REPO_ROOT / "tools" / "kca" / "kg.py").read_text()
    push_start = kg_src.index("def cmd_push(")
    push_end = kg_src.index("def _watch_kernel_until_terminal(")
    push_body = kg_src[push_start:push_end]
    # The real push subprocess must come AFTER all three gate refusals.
    real_push_at = push_body.index('"kaggle", "kernels", "push"')
    creds_at = push_body.index("_missing_kaggle_creds()")
    gate_at = push_body.index("_check_budget_gates(")
    approval_at = push_body.index('_check_approval_gate("kernel_push"')
    assert creds_at < gate_at < approval_at < real_push_at, (
        "gate ordering regressed: creds → budget → approval must precede the real `kaggle kernels push` subprocess"
    )
