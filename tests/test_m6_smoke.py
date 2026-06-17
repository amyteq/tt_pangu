"""M6 smoke tests — all run without ANTHROPIC_API_KEY / KAGGLE_KEY.

A single DB-dependent test skips cleanly when no SUPABASE_DB_URL.

Run with:
    python -m pytest tests/test_m6_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
KCA = [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py")]
RUN_JOB = [sys.executable, str(REPO_ROOT / "scripts" / "run_job.py")]


def _env_clean(**overrides) -> dict:
    env = os.environ.copy()
    for k in (
        "SUPABASE_DB_URL",
        "KCA_DB_TARGET",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
        "ANTHROPIC_API_KEY",
        "KCA_ALLOW_REMOTE",
        "KCA_RESEARCH_ALLOW_DOMAINS",
        "KCA_OTEL_ENABLED",
        "KCA_OTEL_EXPORTERS",
        "KCA_OTEL_SQLITE_PATH",
        "KCA_LOCAL_REQUIRE_LOCAL",
        "KCA_LOCAL_PRIORITY_ORDER",
    ):
        env.pop(k, None)
    for n in range(10):
        for s in ("NAME", "URL", "MODEL", "BACKEND", "API_KEY"):
            env.pop(f"KCA_LOCAL_ENDPOINT_{n}_{s}", None)
    # Prevent db.py from re-injecting popped repo-root / .vscode .env creds (issue #11).
    env["KCA_SKIP_DOTENV"] = "1"
    for k, v in overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def _run(argv, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        env=env if env is not None else _env_clean(),
        cwd=str(REPO_ROOT),
    )


def _scrub_local_endpoints(monkeypatch):
    """Wipe any KCA_LOCAL_ENDPOINT_* the host shell may have set."""
    for n in range(10):
        for s in ("NAME", "URL", "MODEL", "BACKEND", "API_KEY"):
            monkeypatch.delenv(f"KCA_LOCAL_ENDPOINT_{n}_{s}", raising=False)


# ---------------------------------------------------------------------------
# 1. load_endpoints from env
# ---------------------------------------------------------------------------
def test_load_endpoints_from_env(monkeypatch):
    _scrub_local_endpoints(monkeypatch)
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_NAME", "snorlax-vllm")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_URL", "http://192.168.18.66:8000/v1")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_MODEL", "rtx4090")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_BACKEND", "vllm")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_API_KEY", "local")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_1_NAME", "may-vllm")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_1_URL", "http://192.168.18.77:8000/v1")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_1_MODEL", "rtx4090")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_1_BACKEND", "vllm")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_1_API_KEY", "local")

    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.local_model import load_endpoints

    eps = load_endpoints()
    assert len(eps) == 2
    assert eps[0].name == "snorlax-vllm"
    assert eps[1].name == "may-vllm"


# ---------------------------------------------------------------------------
# 2. load_endpoints stops at first gap
# ---------------------------------------------------------------------------
def test_load_endpoints_stops_at_gap(monkeypatch):
    _scrub_local_endpoints(monkeypatch)
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_NAME", "only")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_URL", "http://x/v1")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_MODEL", "m")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_BACKEND", "vllm")
    # Slot 1 missing, slot 2 set
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_2_NAME", "skipped")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_2_URL", "http://y/v1")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_2_MODEL", "m")

    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.local_model import load_endpoints

    eps = load_endpoints()
    assert [e.name for e in eps] == ["only"]


# ---------------------------------------------------------------------------
# 3. probe unreachable returns ok=false
# ---------------------------------------------------------------------------
def test_probe_unreachable_returns_ok_false():
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.local_model import LocalEndpoint, probe

    ep = LocalEndpoint(
        name="t",
        url="http://127.0.0.1:1/v1",
        model="x",
        backend="vllm",
        api_key="local",
    )
    r = probe(ep, timeout_s=1.0)
    assert r["ok"] is False
    assert r["error"]
    assert "connect" in r["error"].lower() or "refused" in r["error"].lower() or "timed out" in r["error"].lower()


# ---------------------------------------------------------------------------
# 4. pick_endpoint returns None when all down
# ---------------------------------------------------------------------------
def test_pick_endpoint_returns_none_when_all_down(monkeypatch):
    _scrub_local_endpoints(monkeypatch)
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_NAME", "a")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_MODEL", "x")
    monkeypatch.setenv("KCA_LOCAL_ENDPOINT_0_BACKEND", "vllm")

    sys.path.insert(0, str(REPO_ROOT))
    from src.worker import local_model as lm

    monkeypatch.setattr(
        lm,
        "probe",
        lambda ep, timeout_s=None: {
            "ok": False,
            "name": ep.name,
            "models": [],
            "latency_ms": 0,
            "error": "down",
        },
    )
    assert lm.pick_endpoint() is None


# ---------------------------------------------------------------------------
# 5. routing fallback when local down
# ---------------------------------------------------------------------------
def test_routing_fallback_when_local_down(monkeypatch):
    _scrub_local_endpoints(monkeypatch)
    monkeypatch.setenv("KCA_LOCAL_FALLBACK_MODEL", "claude-haiku-4-5")
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker import routing, local_model

    monkeypatch.setattr(local_model, "pick_endpoint", lambda: None)
    model, ep = routing.resolve_local_or_fallback("summarise")
    assert ep is None
    assert model == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# 6. reviewer dry-run approves
# ---------------------------------------------------------------------------
def test_reviewer_dry_run_approves():
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.reviewer import Reviewer, ReviewRequest

    r = Reviewer(dry_run=True)
    v = r.review(
        ReviewRequest(
            job_id="job",
            target_op="kaggle_submit",
            tool_name="kaggle_submit",
            tool_input={},
            event_trail=[],
        )
    )
    assert v.verdict == "approve"


# ---------------------------------------------------------------------------
# 7. reviewer prompt truncates long trace
# ---------------------------------------------------------------------------
def test_reviewer_prompt_truncates_long_trace(monkeypatch):
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker import reviewer as rv

    # Force triage path off so we exercise the inline truncation only.
    monkeypatch.setattr(rv, "_EVENT_TRAIL_TRIAGE_THRESHOLD", 10**9)
    events = [
        {
            "event_type": "tool_call",
            "turn_number": i,
            "event_data": {"tool": "read_file", "input": {"path": f"f{i}.py"}},
        }
        for i in range(50)
    ]
    req = rv.ReviewRequest(
        job_id="job",
        target_op="kaggle_submit",
        tool_name="kaggle_submit",
        tool_input={},
        event_trail=events,
    )
    rendered = rv._render_prompt(req)
    assert "REVIEW REQUEST" in rendered
    assert "Return STRICT JSON only" in rendered
    # Trail trimmed to last 20 events
    parsed = json.loads(rendered.split("REVIEW REQUEST:\n", 1)[1].split("\n\nReturn", 1)[0])
    assert len(parsed["event_trail"]) == 20


# ---------------------------------------------------------------------------
# 8. OTEL console exporter writes to stderr
# ---------------------------------------------------------------------------
def test_otel_console_exporter_writes_to_stderr(monkeypatch, capsys):
    monkeypatch.setenv("KCA_OTEL_ENABLED", "1")
    monkeypatch.setenv("KCA_OTEL_EXPORTERS", "console")
    sys.path.insert(0, str(REPO_ROOT))
    # Force re-import so module-level cache picks up new env if any.
    from src.worker import telemetry as tel

    tracer = tel.Tracer()
    assert tracer.is_enabled()
    with tracer.span(kind="job", name="job.test"):
        pass
    captured = capsys.readouterr()
    assert "kind=job" in captured.err
    assert "name=job.test" in captured.err


# ---------------------------------------------------------------------------
# 9. OTEL SQLite exporter persists
# ---------------------------------------------------------------------------
def test_otel_sqlite_exporter_persists(monkeypatch, tmp_path):
    monkeypatch.setenv("KCA_OTEL_ENABLED", "1")
    monkeypatch.setenv("KCA_OTEL_EXPORTERS", "sqlite")
    db_path = tmp_path / "m6.sqlite"
    monkeypatch.setenv("KCA_OTEL_SQLITE_PATH", str(db_path))
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker import telemetry as tel

    tracer = tel.Tracer()
    with tracer.span(kind="turn", name="turn[1]"):
        pass
    assert db_path.exists()
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        rows = list(conn.execute("SELECT kind, name FROM spans"))
    finally:
        conn.close()
    assert rows
    assert rows[0][0] == "turn"


# ---------------------------------------------------------------------------
# 10. OTEL disabled writes nothing
# ---------------------------------------------------------------------------
def test_otel_disabled_writes_nothing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("KCA_OTEL_ENABLED", "0")
    monkeypatch.setenv("KCA_OTEL_EXPORTERS", "console,sqlite")
    db_path = tmp_path / "off.sqlite"
    monkeypatch.setenv("KCA_OTEL_SQLITE_PATH", str(db_path))
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker import telemetry as tel

    tracer = tel.Tracer()
    assert not tracer.is_enabled()
    with tracer.span(kind="job", name="should-not-fire"):
        pass
    captured = capsys.readouterr()
    assert "kind=job" not in captured.err
    assert not db_path.exists()


# ---------------------------------------------------------------------------
# 11. kca local list — no DB needed
# ---------------------------------------------------------------------------
def test_kca_local_list_no_db(monkeypatch):
    env = _env_clean(
        KCA_LOCAL_ENDPOINT_0_NAME="x",
        KCA_LOCAL_ENDPOINT_0_URL="http://x/v1",
        KCA_LOCAL_ENDPOINT_0_MODEL="m",
        KCA_LOCAL_ENDPOINT_0_BACKEND="vllm",
        KCA_LOCAL_ENDPOINT_0_API_KEY="local",
    )
    r = _run(KCA + ["local", "list", "--json"], env=env)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert len(payload["endpoints"]) == 1
    assert payload["endpoints"][0]["name"] == "x"
    assert "db_warning" not in payload


# ---------------------------------------------------------------------------
# 12. kca review list — DB unavailable
# ---------------------------------------------------------------------------
def test_kca_review_list_no_db():
    r = _run(KCA + ["review", "list", "--json"])
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["reviews"] == []
    assert "db_warning" in payload


# ---------------------------------------------------------------------------
# 13. kca review run --dry-run (no DB)
# ---------------------------------------------------------------------------
def test_kca_review_run_dry_run():
    r = _run(
        KCA
        + [
            "review",
            "run",
            "--job-id",
            "00000000-0000-0000-0000-000000000000",
            "--target-op",
            "kaggle_submit",
            "--dry-run",
            "--json",
        ]
    )
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["ok"] is True
    assert payload["verdict"] == "approve"
    assert payload["target_op"] == "kaggle_submit"


# ---------------------------------------------------------------------------
# 14. DB-dependent — review round trip
# ---------------------------------------------------------------------------
def test_review_round_trip():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        pytest.skip("SUPABASE_DB_URL not set")
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    import db as _db
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(db_url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_jobs (project_id, status, prompt, model, job_type) "
                "VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'queued', "
                "'m6 round trip', 'claude-sonnet-4-6', 'test') RETURNING id::text"
            )
            jid = cur.fetchone()["id"]
        conn.commit()
        rid = _db.create_review(
            job_id=jid,
            reviewer_model="claude-opus-4-7",
            verdict="approve",
            target_op="kaggle_submit",
            rationale="ok",
        )
        got = _db.get_review(rid)
        assert got["verdict"] == "approve"
        rows = _db.list_reviews(job_id=jid)
        assert any(str(r["id"]) == rid for r in rows)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agent_jobs WHERE id=%s::uuid", (jid,))
        conn.commit()
        conn.close()
