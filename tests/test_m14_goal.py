"""M14-T002 tests — `kca goal {init, show, update}` + goal.md + reviewer enrichment.

Two posture tiers (mirroring tests/test_m14_db.py):

1. **Ephemeral-Postgres tier** — boots a throwaway Postgres, applies the
   prerequisite FK targets + `0011_m14_goal_loop.sql`, and exercises the CLI
   commands end-to-end: init (happy), init-when-active (ACTIVE_GOAL_EXISTS
   refusal), show --json shape (incl. goal_remaining_delta), update, close.
   SKIPs cleanly when no local Postgres binary exists.

2. **Pure-Python tier** — goal.md render/parse round-trip and the reviewer
   `goal_remaining_delta` enrichment. Runs in any environment.

Run with:
    python -m pytest tests/test_m14_goal.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "0011_m14_goal_loop.sql"

_PG_BINS_PRESENT = all(shutil.which(b) for b in ("initdb", "pg_ctl", "postgres"))

_PREREQ_SQL = """
CREATE TABLE competitions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid,
  platform text DEFAULT 'kaggle',
  slug text UNIQUE,
  title text,
  max_daily_submissions int,
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


@pytest.fixture(scope="module")
def pg_url():
    if not _PG_BINS_PRESENT:
        pytest.skip("no local Postgres binaries (initdb/pg_ctl/postgres) on PATH")
    tmp = tempfile.mkdtemp(prefix="m14goal_")
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
def env(pg_url, monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_DB_URL", pg_url)
    monkeypatch.setenv("KCA_DB_TARGET", "local")
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")
    import goal as _goal

    # Redirect goal.md writes into the test's tmp dir so the repo tree is clean.
    monkeypatch.setattr(_goal, "_repo_root", lambda: tmp_path)
    return _goal


@pytest.fixture
def slug(pg_url):
    import psycopg

    s = f"m14goal-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO competitions (slug) VALUES (%s)", (s,))
    return s


def _ns(**kw):
    import argparse

    return argparse.Namespace(**kw)


def _run(capsys, fn, ns):
    rc = fn(ns)
    out = capsys.readouterr().out.strip()
    return rc, json.loads(out)


def _init_ns(slug, **over):
    base = dict(
        competition=slug,
        target_lb_score=0.85,
        target_lb_rank=30,
        target_rank_kind="percentile",
        deadline="2026-07-01",
        exit_strategy="first_reached",
        max_total_pushes=20,
        stuck_threshold=3,
        json=True,
    )
    base.update(over)
    return _ns(**base)


# ---------------------------------------------------------------------------
# Ephemeral-Postgres tier
# ---------------------------------------------------------------------------


def test_init_happy_writes_row_and_goal_md(env, slug, capsys, tmp_path):
    rc, payload = _run(capsys, env.cmd_init, _init_ns(slug))
    assert rc == 0
    assert payload["ok"] is True
    assert payload["goal"]["target_lb_score"] == 0.85
    assert payload["goal"]["target_rank_kind"] == "percentile"
    assert payload["goal"]["status"] == "active"
    md = Path(payload["goal_md"])
    assert md.exists()
    assert md == tmp_path / "experiments" / slug / "goal.md"
    text = md.read_text()
    assert text.startswith("---")
    # round-trip: front-matter reconstructs the row fields
    parsed = env.parse_goal_md(text)
    assert parsed["competition"] == slug
    assert parsed["target_lb_score"] == 0.85
    assert parsed["target_lb_rank"] == 30
    assert parsed["exit_strategy"] == "first_reached"
    assert parsed["status"] == "active"


def test_second_init_refuses_active_goal_exists(env, slug, capsys):
    _run(capsys, env.cmd_init, _init_ns(slug))
    rc, payload = _run(capsys, env.cmd_init, _init_ns(slug, target_lb_score=0.9))
    assert rc != 0
    assert payload["ok"] is False
    assert payload["error"] == "ACTIVE_GOAL_EXISTS"


def test_init_unregistered_competition_refuses(env, capsys):
    rc, payload = _run(capsys, env.cmd_init, _init_ns("no-such-comp"))
    assert rc != 0
    assert payload["ok"] is False
    assert "not registered" in payload["error"]


def test_show_json_shape_and_remaining_delta(env, slug, pg_url, capsys):
    _run(capsys, env.cmd_init, _init_ns(slug))
    # No scored submission yet -> delta is None.
    rc, payload = _run(capsys, env.cmd_show, _ns(competition=slug, json=True))
    assert rc == 0 and payload["ok"] is True
    assert payload["goal"]["target_lb_score"] == 0.85
    assert payload["goal_remaining_delta"] is None
    assert "goal_id" in payload

    # Add a scored submission: best LB 0.80 -> delta = 0.85 - 0.80 = 0.05.
    import psycopg

    with psycopg.connect(pg_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text FROM competitions WHERE slug=%s", (slug,))
            comp_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO submissions (competition_id, file_path, public_lb_score, "
                "status) VALUES (%s::uuid, 'kca/a', 0.80, 'complete')",
                (comp_id,),
            )
    rc, payload = _run(capsys, env.cmd_show, _ns(competition=slug, json=True))
    assert payload["goal_remaining_delta"] == pytest.approx(0.05)


def test_show_no_active_goal(env, slug, capsys):
    rc, payload = _run(capsys, env.cmd_show, _ns(competition=slug, json=True))
    assert rc != 0
    assert payload["error"] == "NO_ACTIVE_GOAL"


def test_update_partial_fields(env, slug, capsys):
    _run(capsys, env.cmd_init, _init_ns(slug))
    rc, payload = _run(
        capsys,
        env.cmd_update,
        _ns(
            competition=slug,
            target_lb_score=0.92,
            target_lb_rank=None,
            target_rank_kind=None,
            deadline=None,
            exit_strategy=None,
            max_total_pushes=None,
            stuck_threshold=5,
            close=False,
            status="closed",
            reason=None,
            json=True,
        ),
    )
    assert rc == 0 and payload["ok"] is True
    assert payload["goal"]["target_lb_score"] == 0.92
    assert payload["goal"]["stuck_threshold"] == 5
    # goal.md reflects the update
    parsed = env.parse_goal_md(Path(payload["goal_md"]).read_text())
    assert parsed["target_lb_score"] == 0.92
    assert parsed["stuck_threshold"] == 5


def test_update_close_flips_status_and_frees_slot(env, slug, capsys):
    _run(capsys, env.cmd_init, _init_ns(slug))
    rc, payload = _run(
        capsys,
        env.cmd_update,
        _ns(
            competition=slug,
            target_lb_score=None,
            target_lb_rank=None,
            target_rank_kind=None,
            deadline=None,
            exit_strategy=None,
            max_total_pushes=None,
            stuck_threshold=None,
            close=True,
            status="reached",
            reason="hit target",
            json=True,
        ),
    )
    assert rc == 0 and payload["closed"] is True
    assert payload["goal"]["status"] == "reached"
    assert payload["closed_reason"] == "hit target"
    parsed = env.parse_goal_md(Path(payload["goal_md"]).read_text())
    assert parsed["status"] == "reached"
    # a fresh init is now allowed (slot freed)
    rc2, payload2 = _run(capsys, env.cmd_init, _init_ns(slug, target_lb_score=0.95))
    assert rc2 == 0 and payload2["ok"] is True


# ---------------------------------------------------------------------------
# Pure-Python tier (no DB)
# ---------------------------------------------------------------------------


def test_goal_md_render_parse_round_trip():
    import goal as _goal

    row = {
        "id": "abc",
        "target_lb_score": 0.85,
        "target_lb_rank": 30,
        "target_rank_kind": "percentile",
        "deadline": None,
        "exit_strategy": "first_reached",
        "max_total_pushes": 20,
        "stuck_threshold": 3,
        "status": "active",
    }
    text = _goal.render_goal_md("tpu-getting-started", row)
    parsed = _goal.parse_goal_md(text)
    assert parsed["competition"] == "tpu-getting-started"
    assert parsed["target_lb_score"] == 0.85
    assert parsed["target_lb_rank"] == 30
    assert parsed["target_rank_kind"] == "percentile"
    assert parsed["deadline"] is None
    assert parsed["exit_strategy"] == "first_reached"
    assert parsed["max_total_pushes"] == 20
    assert parsed["status"] == "active"


def test_parse_goal_md_requires_front_matter():
    import goal as _goal

    with pytest.raises(ValueError):
        _goal.parse_goal_md("no front matter here\n")


def test_reviewer_surfaces_goal_remaining_delta_for_kernel_push():
    from src.worker import reviewer as _rev

    req = _rev.ReviewRequest(
        job_id="11111111-1111-1111-1111-111111111111",
        target_op="kernel_push",
        tool_name="kernel_push",
        tool_input={"slug": "tpu/x", "goal_remaining_delta": 0.05},
        final_message=None,
        event_trail=[],
    )
    rendered = _rev.render_review_context(req)
    assert "goal_remaining_delta" in rendered
    assert "0.05" in rendered


def test_reviewer_omits_delta_for_non_kernel_push():
    from src.worker import reviewer as _rev

    req = _rev.ReviewRequest(
        job_id="11111111-1111-1111-1111-111111111111",
        target_op="kaggle_submit",
        tool_name="kaggle_submit",
        tool_input={"slug": "tpu/x", "goal_remaining_delta": 0.05},
        final_message=None,
        event_trail=[],
    )
    # For non-kernel_push ops the delta is not lifted to a top-level field;
    # it may still appear nested inside tool_input, which is expected.
    assert _rev._goal_remaining_delta(req) is None


def test_reviewer_tolerates_missing_delta_key():
    from src.worker import reviewer as _rev

    req = _rev.ReviewRequest(
        job_id="11111111-1111-1111-1111-111111111111",
        target_op="kernel_push",
        tool_name="kernel_push",
        tool_input={"slug": "tpu/x"},
        final_message=None,
        event_trail=[],
    )
    assert _rev._goal_remaining_delta(req) is None
