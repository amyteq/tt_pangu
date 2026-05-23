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
                "job_id": "11111111-1111-1111-1111-111111111111",
                "decision_type": "kaggle_submit",
            },
            "open2": {
                "id": "open2",
                "status": "pending",
                "job_id": None,
                "decision_type": "external_fetch",
            },
        }
        self.events: list[dict] = []

    def get_decision(self, decision_id: str) -> dict | None:
        return self.decisions.get(decision_id)

    def resolve_decision(self, decision_id: str, resolution: str, notes=None) -> None:
        self.decisions[decision_id]["status"] = resolution
        self.decisions[decision_id]["notes"] = notes

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
