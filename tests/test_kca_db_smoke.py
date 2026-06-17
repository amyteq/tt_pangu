"""M2 DB smoke tests for the kca↔Postgres path.

Requires a live local Supabase (or any Postgres with 0001+0002 applied).
Skips cleanly when KCA_DB_TARGET / SUPABASE_DB_URL aren't set.

Run with:
    KCA_DB_TARGET=local SUPABASE_DB_URL=postgres://postgres:postgres@127.0.0.1:54322/postgres \
      python -m pytest tests/test_kca_db_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Skip the whole module without psycopg or DB config.
psycopg = pytest.importorskip("psycopg")

requires_db = pytest.mark.skipif(
    not (os.environ.get("KCA_DB_TARGET") and os.environ.get("SUPABASE_DB_URL")),
    reason="M2 DB tests require KCA_DB_TARGET=local + SUPABASE_DB_URL.",
)

REPO_ROOT = Path(__file__).resolve().parent.parent
KCA = [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*argv: str, env_override: dict | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env_override is not None:
        for k, v in env_override.items():
            if v is None:
                full_env.pop(k, None)
            else:
                full_env[k] = v
    return subprocess.run(
        [*KCA, *argv],
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
        cwd=str(REPO_ROOT),
    )


def _parse(proc: subprocess.CompletedProcess) -> dict:
    stdout = (proc.stdout or "").strip()
    assert stdout, f"empty stdout; stderr={proc.stderr!r}"
    return json.loads(stdout)


def _query_one(db_url: str, sql: str, params: tuple = ()) -> tuple | None:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def _query_all(db_url: str, sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _cleanup_competition(db_url: str, slug: str) -> None:
    """Drop the DB rows created during a test (cascade handles dependents)."""
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("delete from competitions where slug = %s", (slug,))
            cur.execute(
                "delete from experiment_runs where run_dir like %s",
                (f"runs/{slug}/%",),
            )
            cur.execute(
                "delete from experiments where name in "
                "(select external_run_id from experiment_runs where run_dir like %s)",
                (f"runs/{slug}/%",),
            )
            cur.execute(
                "delete from human_decisions where prompt like %s",
                (f"%competition={slug}%",),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@requires_db
def test_run_init_writes_db_and_fs(db_url: str, cleanup_run_dir: str) -> None:
    slug = cleanup_run_dir
    try:
        proc = _run(
            "run",
            "init",
            "--competition",
            slug,
            "--hypothesis",
            "smoke baseline",
            "--tag",
            "smoke",
            "--json",
        )
        assert proc.returncode == 0, proc.stderr
        payload = _parse(proc)
        assert payload["ok"] is True
        assert payload["competition"] == slug
        run_dir_str = payload["run_dir"]
        assert (REPO_ROOT / run_dir_str / "meta.json").is_file()
        assert (REPO_ROOT / run_dir_str / "metrics.json").is_file()
        assert (REPO_ROOT / run_dir_str / "config.json").is_file()

        # DB side: one row each in competitions, experiments, experiment_runs.
        row = _query_one(
            db_url,
            "select count(*) from experiment_runs where run_dir = %s",
            (run_dir_str,),
        )
        assert row and row[0] == 1
        row = _query_one(
            db_url,
            "select hypothesis, tags from experiments where id = %s::uuid",
            (payload["experiment_id"],),
        )
        assert row and row[0] == "smoke baseline" and row[1] == ["smoke"]
    finally:
        _cleanup_competition(db_url, slug)


@requires_db
def test_record_metric_writes_event_and_jsonb(db_url: str, cleanup_run_dir: str) -> None:
    slug = cleanup_run_dir
    try:
        init = _parse(_run("run", "init", "--competition", slug, "--hypothesis", "h", "--json"))
        run_dir = init["run_dir"]
        run_id_uuid = init["experiment_run_id"]

        # Record two events on the same key + one on a different key.
        for k, v in [("cv_score", 0.701), ("cv_score", 0.722), ("leaderboard", 0.689)]:
            p = _run(
                "run",
                "record-metric",
                "--run-dir",
                run_dir,
                "--key",
                k,
                "--value",
                str(v),
                "--json",
            )
            assert p.returncode == 0, p.stderr
            assert _parse(p)["ok"] is True

        events = _query_all(
            db_url,
            "select key, value::float from experiment_run_metrics where experiment_run_id = %s::uuid order by recorded_at",
            (run_id_uuid,),
        )
        assert len(events) == 3
        assert [e[0] for e in events] == ["cv_score", "cv_score", "leaderboard"]

        snapshot = _query_one(
            db_url,
            "select metrics from experiment_runs where id = %s::uuid",
            (run_id_uuid,),
        )
        # M2 jsonb snapshot keeps the nested {value, recorded_at} shape because
        # record_metric_m2 builds it that way.
        assert snapshot and snapshot[0]["cv_score"]["value"] == 0.722
        assert snapshot[0]["leaderboard"]["value"] == 0.689

        # M4 run.py made metrics.json flat (key→value); FS cache no longer
        # mirrors the M2 nested shape.
        # Run-dir lives under the cwd (REPO_ROOT for these tests).
        cache = json.loads((REPO_ROOT / run_dir / "metrics.json").read_text())
        assert cache["cv_score"] == 0.722
        assert cache["leaderboard"] == 0.689
    finally:
        _cleanup_competition(db_url, slug)


@requires_db
def test_run_list_sources_from_db(db_url: str, cleanup_run_dir: str) -> None:
    slug = cleanup_run_dir
    try:
        _parse(_run("run", "init", "--competition", slug, "--hypothesis", "h", "--json"))
        list_proc = _run("run", "list", "--competition", slug, "--json")
        assert list_proc.returncode == 0, list_proc.stderr
        payload = _parse(list_proc)
        assert payload["ok"] is True
        assert payload["count"] >= 1
        assert payload["runs"][0]["run_dir"].startswith(f"runs/{slug}/")
    finally:
        _cleanup_competition(db_url, slug)


@requires_db
def test_db_unreachable_degrades_gracefully(cleanup_run_dir: str) -> None:
    """M4: run init is FS-first; DB failure becomes a warning, FS still wins."""
    slug = cleanup_run_dir
    proc = _run(
        "run",
        "init",
        "--competition",
        slug,
        "--json",
        env_override={
            "SUPABASE_DB_URL": "postgres://postgres:postgres@127.0.0.1:54998/postgres",
            # Opt out of the .vscode/.env auto-load so the intentionally-bad
            # DSN above isn't clobbered by the workspace's cloud DSN.
            "KCA_SKIP_DOTENV": "1",
        },
    )
    assert proc.returncode == 0, proc.stderr
    payload = _parse(proc)
    assert payload["ok"] is True
    assert payload.get("db_warning"), "DB failure should surface as db_warning"
    # FS state still created (relative to the worker's cwd = REPO_ROOT).
    assert (REPO_ROOT / payload["run_dir"] / "meta.json").exists()


@requires_db
def test_kaggle_submit_blocks_and_records_approval(db_url: str) -> None:
    """M4: with credentials present + policy tightened, submit is gated by
    ApprovalRequired and the blocked envelope records a human_decisions row."""
    marker = f"smoke_marker_{os.urandom(4).hex()}"
    proc = _run(
        "kaggle",
        "submit",
        "--competition",
        marker,
        "--file",
        "/dev/null",
        "--message",
        "smoke",
        "--json",
        env_override={
            "KCA_ALLOW_REMOTE": None,
            "KAGGLE_USERNAME": "smoke-user",
            "KAGGLE_KEY": "smoke-key",
            "KCA_POLICY": json.dumps({"approval_gates": {"kaggle_submit": True}}),
        },
    )
    try:
        assert proc.returncode == 2, proc.stderr
        payload = _parse(proc)
        assert payload["ok"] is False
        assert payload["approval_recorded"] is True
        assert payload["approval_request_id"]

        row = _query_one(
            db_url,
            "select decision_type, status from human_decisions where id = %s::uuid",
            (payload["approval_request_id"],),
        )
        assert row and row[0] == "kaggle.submit" and row[1] == "pending"
    finally:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from human_decisions where prompt like %s",
                    (f"%competition={marker}%",),
                )
            conn.commit()
