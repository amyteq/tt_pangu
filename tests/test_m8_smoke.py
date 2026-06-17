"""M8 smoke tests — audit / schema / fixture / worker / decision_api / CLI.

Mix of DB-marked and DB-less. DB-marked tests skip cleanly when
SUPABASE_DB_URL is unset.

Run with:
    python -m pytest tests/test_m8_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

requires_db = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set",
)


# ---------------------------------------------------------------------------
# 1. Tool audit table present on db target
# ---------------------------------------------------------------------------
@requires_db
def test_tool_audit_table_present_on_db_target():
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.agent_tool_audit') IS NOT NULL")
            tbl = cur.fetchone()[0]
            cur.execute("SELECT to_regclass('public.v_agent_tool_audit_recent') IS NOT NULL")
            view = cur.fetchone()[0]
    assert tbl, "agent_tool_audit table missing"
    assert view, "v_agent_tool_audit_recent view missing"


# ---------------------------------------------------------------------------
# 2. Dual-write JSONL when DB unconfigured — never raises
# ---------------------------------------------------------------------------
def test_tool_audit_dual_write_jsonl_only(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    from tools.kca.agent.audit import AuditLogger

    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(backend="both", file_path=path)
    rec = logger.log_policy_decision(
        tool="bash",
        operation="bash",
        decision="ask",
        mode="default",
        policy_profile="permissive-dev",
    )
    assert path.is_file()
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["decision"] == "ask"
    assert payload["session_id"] == rec.session_id


# ---------------------------------------------------------------------------
# 3 & 4. Schema validation
# ---------------------------------------------------------------------------
def test_skill_schema_rejects_bad_name(tmp_path):
    from tools.kca.agent.skill_loader import SkillValidationError, load_skill

    d = tmp_path / "skills" / "Bad"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        textwrap.dedent(
            """---
            name: Bad Name
            description: x
            ---
            body
            """
        )
    )
    with pytest.raises(SkillValidationError):
        load_skill("Bad", skills_root=d.parent)


def test_skill_schema_rejects_unknown_tool(tmp_path):
    from tools.kca.agent.skill_loader import SkillValidationError, load_skill

    d = tmp_path / "skills" / "ok"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        textwrap.dedent(
            """---
            name: ok
            description: x
            allowed-tools:
              - made_up_tool
            ---
            body
            """
        )
    )
    with pytest.raises(SkillValidationError):
        load_skill("ok", skills_root=d.parent)


# ---------------------------------------------------------------------------
# 5 & 6. Fixture relocation
# ---------------------------------------------------------------------------
def test_skill_fixture_no_longer_in_kca_skills():
    p = REPO_ROOT / ".kca" / "skills" / "_test_fixture"
    assert not p.exists(), f"unexpected fixture dir present: {p}"


def test_skill_fixture_still_loadable_from_tests_root():
    from tools.kca.agent.skill_loader import load_skill

    root = REPO_ROOT / "tests" / "fixtures" / "skills"
    s = load_skill("_test_fixture", skills_root=root)
    assert s.meta.name == "_test_fixture"


# ---------------------------------------------------------------------------
# 7–9. Worker tool_call paths
# ---------------------------------------------------------------------------
def _build_test_worker(tmp_path, monkeypatch, decision):
    """Shared setup helper for the three worker_tool_call tests."""
    import types as _types

    from src.worker._types import JobPolicy
    from src.worker.worker import AgentWorker, MockLiteLLMClient

    monkeypatch.setenv("KCA_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    (tmp_path / "hello.txt").write_text("hi")

    policy = JobPolicy(
        skill_name="_test_fixture",
        policy_profile="permissive-dev",
        mode="default",
        tool_decisions={"read_file": decision},
    )
    worker = AgentWorker(
        job_id="00000000-0000-0000-0000-000000000000",
        prompt="read it",
        policy=policy,
        workspace=tmp_path,
        db_url=None,
        dry_run=True,
    )

    client = MockLiteLLMClient(scenario="two_turns")
    state = {"n": 0}

    def completion(**_kwargs):
        state["n"] += 1
        if state["n"] == 1:
            tc = _types.SimpleNamespace(
                id="c",
                type="function",
                function=_types.SimpleNamespace(
                    name="read_file",
                    arguments=json.dumps({"path": "hello.txt"}),
                ),
            )
            msg = _types.SimpleNamespace(content=None, tool_calls=[tc])
            return _types.SimpleNamespace(
                choices=[_types.SimpleNamespace(message=msg, finish_reason="tool_calls")],
                usage=_types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )
        msg = _types.SimpleNamespace(content="done", tool_calls=None)
        return _types.SimpleNamespace(
            choices=[_types.SimpleNamespace(message=msg, finish_reason="stop")],
            usage=_types.SimpleNamespace(prompt_tokens=5, completion_tokens=2),
        )

    client.completion = completion  # type: ignore[method-assign]
    worker._mock_client = client
    return worker


def _read_audit(tmp_path):
    p = tmp_path / "audit.jsonl"
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line]


def test_worker_tool_call_allow_path(tmp_path, monkeypatch):
    worker = _build_test_worker(tmp_path, monkeypatch, "allow")
    result = worker.run()
    assert result.status == "done"
    rows = _read_audit(tmp_path)
    assert any(r["tool_name"] == "read_file" and r["decision"] == "allow" for r in rows)


def test_worker_tool_call_ask_path(tmp_path, monkeypatch):
    worker = _build_test_worker(tmp_path, monkeypatch, "ask")
    result = worker.run()
    assert result.status == "paused"
    rows = _read_audit(tmp_path)
    assert any(r["decision"] == "ask" for r in rows)


def test_worker_tool_call_deny_path(tmp_path, monkeypatch):
    worker = _build_test_worker(tmp_path, monkeypatch, "deny")
    result = worker.run()
    assert result.status == "failed"
    assert result.stop_reason == "policy_violation"
    rows = _read_audit(tmp_path)
    assert any(r["decision"] == "deny" for r in rows)


# ---------------------------------------------------------------------------
# 10–12. Decision API
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from services.decision_api.app import make_app

    class _FakeDB:
        def __init__(self):
            self.decisions = {
                "x": {
                    "id": "x",
                    "status": "pending",
                    "job_id": "11111111-1111-1111-1111-111111111111",
                    "decision_type": "kaggle_submit",
                }
            }
            self.events: list[dict] = []

        def get_decision(self, did):
            return self.decisions.get(did)

        def resolve_decision(self, did, resolution, notes=None):
            self.decisions[did]["status"] = resolution
            self.decisions[did]["notes"] = notes

        def append_job_event(self, job_id, event_type, event_data=None, **_):
            self.events.append({"job_id": job_id, "event_type": event_type, "event_data": event_data})
            return len(self.events)

    fake = _FakeDB()
    app = make_app(decisions_module=fake, audit_logger=lambda **_: None)
    c = TestClient(app)
    c.fake = fake  # type: ignore[attr-defined]
    return c


def test_decision_api_approve_idempotent(client):
    r1 = client.post("/decision/x/approve", json={"reason": "ok"})
    assert r1.status_code == 200
    r2 = client.post("/decision/x/approve", json={"reason": "ok"})
    assert r2.status_code == 409


def test_decision_api_reject_minlength(client):
    r = client.post("/decision/x/reject", json={"reason": "short77"})  # 7 chars
    assert r.status_code == 422
    r = client.post("/decision/x/reject", json={"reason": "explanation"})
    assert r.status_code == 200


def test_decision_api_ask_improve_appends_event(client):
    r = client.post("/decision/x/ask-improve", json={"feedback": "please try seed=42"})
    assert r.status_code == 200
    fake = client.fake  # type: ignore[attr-defined]
    feedback_events = [e for e in fake.events if e["event_type"] == "feedback"]
    assert feedback_events
    assert feedback_events[0]["event_data"]["feedback"].startswith("please")


# ---------------------------------------------------------------------------
# 13. kca skill run --execute
# ---------------------------------------------------------------------------
def test_kca_skill_run_execute_creates_job(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("KCA_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "kca" / "kca.py"),
            "skill",
            "run",
            "triage-log",
            "--arg",
            "job_id=00000000-0000-0000-0000-000000000000",
            "--execute",
            "--json",
        ],
        env={**os.environ, "KCA_AUDIT_PATH": str(tmp_path / "audit.jsonl")},
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert "job_id" in data
    assert data["skill"] == "triage-log"
