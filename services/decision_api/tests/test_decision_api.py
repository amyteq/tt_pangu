"""decision_api tests with a mocked DB layer (no real Supabase calls)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.decision_api.app import make_app


class FakeDB:
    """In-memory stand-in for tools/kca/db. Captures calls so tests can assert."""

    def __init__(self) -> None:
        self.decisions: dict = {
            "abc": {
                "id": "abc",
                "status": "pending",
                "project_id": "proj-1",
                "job_id": "11111111-1111-1111-1111-111111111111",
                "decision_type": "kaggle_submit",
                "prompt": "Submit?",
                "options": [],
                "rationale": None,
                "requested_by": None,
                "created_at": "2024-01-01T00:00:00",
                "decided_at": None,
                "competition_id": "comp-a",
            },
            "open2": {
                "id": "open2",
                "status": "pending",
                "project_id": "proj-1",
                "job_id": None,
                "decision_type": "external_fetch",
                "prompt": "Fetch?",
                "options": [],
                "rationale": None,
                "requested_by": None,
                "created_at": "2024-01-02T00:00:00",
                "decided_at": None,
                "competition_id": None,
            },
            "done1": {
                "id": "done1",
                "status": "approved",
                "project_id": "proj-1",
                "job_id": None,
                "decision_type": "kaggle_submit",
                "prompt": "Old submit",
                "options": [],
                "rationale": "looked good",
                "requested_by": None,
                "created_at": "2024-01-03T00:00:00",
                "decided_at": "2024-01-03T01:00:00",
                "competition_id": "comp-a",
            },
        }
        self.events: list[dict] = []

    def get_decision(self, decision_id: str) -> dict | None:
        return self.decisions.get(decision_id)

    def resolve_decision(self, decision_id: str, resolution: str, notes=None) -> None:
        self.decisions[decision_id]["status"] = resolution
        self.decisions[decision_id]["notes"] = notes

    def list_decisions(
        self,
        status: str = "pending",
        limit: int = 50,
        competition_id: str | None = None,
    ) -> list[dict]:
        result = [d for d in self.decisions.values() if d.get("status") == status]
        if competition_id is not None:
            result = [d for d in result if d.get("competition_id") == competition_id]
        return result[:limit]

    def append_job_event(
        self,
        job_id: str,
        event_type: str,
        event_data=None,
        **_kwargs,
    ) -> int:
        evt = {"job_id": job_id, "event_type": event_type, "event_data": event_data}
        self.events.append(evt)
        return len(self.events)


@pytest.fixture
def client() -> TestClient:
    fake = FakeDB()
    app = make_app(decisions_module=fake, audit_logger=lambda **_: None)
    c = TestClient(app)
    c.app = app  # type: ignore[attr-defined]
    c.fake = fake  # type: ignore[attr-defined]
    return c


def test_decision_api_approve_idempotent(client: TestClient) -> None:
    r1 = client.post("/decision/abc/approve", json={"reason": "ok"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "approved"

    r2 = client.post("/decision/abc/approve", json={"reason": "ok"})
    assert r2.status_code == 409, r2.text


def test_decision_api_reject_minlength(client: TestClient) -> None:
    short = client.post("/decision/abc/reject", json={"reason": "short"})  # 5
    assert short.status_code == 422

    ok = client.post("/decision/abc/reject", json={"reason": "explanation"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "rejected"


def test_decision_api_ask_improve_appends_event(client: TestClient) -> None:
    r = client.post(
        "/decision/abc/ask-improve",
        json={"feedback": "please retry with seed=42"},
    )
    assert r.status_code == 200, r.text
    fake = client.fake  # type: ignore[attr-defined]
    feedback_events = [e for e in fake.events if e["event_type"] == "feedback"]
    assert feedback_events, "expected a feedback event"
    assert feedback_events[0]["event_data"]["feedback"].startswith("please retry")


def test_decision_api_404_for_unknown(client: TestClient) -> None:
    r = client.post("/decision/no_such/approve", json={})
    assert r.status_code == 404


def test_submission_pack_endpoint_read_only(client: TestClient) -> None:
    """M12-T005: GET /runs/<run_id>/submission_pack returns the checklist.

    Uses a stub `submission_pack_provider` so the test never touches
    Supabase or the local runs/ tree. Verifies (a) the endpoint is
    HTTP GET, (b) it returns the checklist shape the UI expects, and
    (c) HTTP POST against the same path returns 405 Method Not Allowed
    (i.e. the endpoint is READ_ONLY).
    """
    fake = FakeDB()
    payload = {
        "ok": True,
        "run_id": "r-1",
        "slug": "demo-hack",
        "checklist": [
            {
                "item": "README.md",
                "status": "done",
                "evidence": "runs/demo-hack/r-1/submission_pack/README.md",
            },
            {"item": "demo-plan.md", "status": "todo", "evidence": ""},
        ],
    }
    app = make_app(
        decisions_module=fake,
        audit_logger=lambda **_: None,
        submission_pack_provider=lambda _run_id: payload,
    )
    c = TestClient(app)

    r = c.get("/runs/r-1/submission_pack")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["slug"] == "demo-hack"
    assert isinstance(body["checklist"], list)
    assert body["checklist"][0]["item"] == "README.md"
    assert body["checklist"][0]["status"] == "done"

    # READ_ONLY: POST must NOT mutate. FastAPI returns 405 for an
    # undeclared verb on a registered route.
    r_post = c.post("/runs/r-1/submission_pack", json={})
    assert r_post.status_code == 405


def test_decision_api_token_required(monkeypatch) -> None:
    fake = FakeDB()
    monkeypatch.setenv("KCA_DECISION_API_TOKEN", "secret")
    app = make_app(decisions_module=fake, audit_logger=lambda **_: None)
    c = TestClient(app)
    r = c.post("/decision/abc/approve", json={"reason": "x"})
    assert r.status_code == 401
    r2 = c.post(
        "/decision/abc/approve",
        json={"reason": "x"},
        headers={"X-Decision-Api-Token": "secret"},
    )
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# GET /decisions tests (issue #15 — M9 follow-up C)
# ---------------------------------------------------------------------------


def test_get_decisions_requires_token(monkeypatch) -> None:
    fake = FakeDB()
    monkeypatch.setenv("KCA_DECISION_API_TOKEN", "secret")
    app = make_app(decisions_module=fake, audit_logger=lambda **_: None)
    c = TestClient(app)
    r = c.get("/decisions")
    assert r.status_code == 401


def test_get_decisions_default_pending(client: TestClient) -> None:
    r = client.get("/decisions")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    statuses = {d["status"] for d in body}
    assert statuses == {"pending"}, f"expected only pending, got {statuses}"
    ids = {d["id"] for d in body}
    assert "done1" not in ids, "approved decision should not appear in default listing"


def test_get_decisions_response_shape(client: TestClient) -> None:
    r = client.get("/decisions")
    assert r.status_code == 200
    rows = r.json()
    assert rows, "expected at least one pending decision"
    row = rows[0]
    for field in (
        "id",
        "project_id",
        "decision_type",
        "prompt",
        "status",
        "created_at",
    ):
        assert field in row, f"missing field {field!r} in response row"


def test_get_decisions_status_filter(client: TestClient) -> None:
    r = client.get("/decisions?status=approved")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert any(d["id"] == "done1" for d in body), "approved decision should appear"
    assert all(d["status"] == "approved" for d in body)


def test_get_decisions_limit(client: TestClient) -> None:
    r = client.get("/decisions?status=pending&limit=1")
    assert r.status_code == 200
    body = r.json()
    assert len(body) <= 1, "limit=1 should return at most 1 row"


def test_get_decisions_competition_id_filter(client: TestClient) -> None:
    r = client.get("/decisions?competition_id=comp-a")
    assert r.status_code == 200
    body = r.json()
    ids = {d["id"] for d in body}
    assert "abc" in ids, "decision with competition_id=comp-a should appear"
    assert "open2" not in ids, "decision without competition_id should be excluded"
