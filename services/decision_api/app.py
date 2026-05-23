"""FastAPI action service for the M8 Decision Gate UI.

The browser never holds a service-role Supabase key. It posts to
``/decision/<id>/approve|reject|ask-improve``; this service re-uses the
existing ``tools/kca/decisions.py`` functions and ``tools/kca/db.py`` writes
so the M7 permission policy stays authoritative.

Auth: a shared token in ``KCA_DECISION_API_TOKEN``. Requests must include the
matching ``X-Decision-Api-Token`` header. Multi-user auth lands in M9+.

Testing: pass a ``decisions_module`` override (e.g. via dependency injection)
to swap in a mocked DB layer.
"""

from __future__ import annotations

import hmac
import os
from typing import Callable, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


TOKEN_ENV = "KCA_DECISION_API_TOKEN"


class ApproveBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=8, max_length=2000)


class AskImproveBody(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=4000)
    metric_target: Optional[str] = None


def _check_token(provided: Optional[str]) -> None:
    expected = os.environ.get(TOKEN_ENV, "")
    if not expected:
        # If the server has no token configured, accept any (local dev only).
        return
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid token")


def make_app(
    decisions_module: Optional[object] = None,
    audit_logger: Optional[Callable] = None,
) -> FastAPI:
    """Construct the FastAPI app.

    ``decisions_module`` exposes ``get_decision``, ``resolve_decision``, and
    ``append_job_event``. Tests pass a fake module to avoid touching Supabase.
    """
    app = FastAPI(title="kca decision_api", version="0.1.0")

    def _resolve_db():
        if decisions_module is not None:
            return decisions_module
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "kca"))
        import db as _db  # type: ignore

        return _db

    def _audit(*, decision: str, decision_id: str, reason: Optional[str]) -> None:
        if audit_logger is not None:
            audit_logger(
                decision=decision, decision_id=decision_id, reason=reason or ""
            )
            return
        try:
            from tools.kca.agent.audit import log_policy_decision  # type: ignore

            log_policy_decision(
                tool="decision_api",
                operation=f"decision_{decision}",
                decision="allow",
                policy_profile="default",
                args={"decision_id": decision_id, "reason_len": len(reason or "")},
            )
        except Exception:
            pass

    def _get_pending(decision_id: str):
        _db = _resolve_db()
        row = _db.get_decision(decision_id)
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        if row.get("status") != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"decision is {row.get('status')}, not pending",
            )
        return row

    @app.post("/decision/{decision_id}/approve")
    def approve(
        decision_id: str,
        body: ApproveBody,
        x_decision_api_token: Optional[str] = Header(default=None),
    ) -> dict:
        _check_token(x_decision_api_token)
        row = _get_pending(decision_id)
        _db = _resolve_db()
        _db.resolve_decision(decision_id, "approved", notes=body.reason)
        _audit(decision="approve", decision_id=decision_id, reason=body.reason)
        return {
            "ok": True,
            "decision_id": decision_id,
            "status": "approved",
            "job_id": row.get("job_id"),
        }

    @app.post("/decision/{decision_id}/reject")
    def reject(
        decision_id: str,
        body: RejectBody,
        x_decision_api_token: Optional[str] = Header(default=None),
    ) -> dict:
        _check_token(x_decision_api_token)
        row = _get_pending(decision_id)
        _db = _resolve_db()
        _db.resolve_decision(decision_id, "rejected", notes=body.reason)
        _audit(decision="reject", decision_id=decision_id, reason=body.reason)
        return {
            "ok": True,
            "decision_id": decision_id,
            "status": "rejected",
            "job_id": row.get("job_id"),
        }

    @app.post("/decision/{decision_id}/ask-improve")
    def ask_improve(
        decision_id: str,
        body: AskImproveBody,
        x_decision_api_token: Optional[str] = Header(default=None),
    ) -> dict:
        _check_token(x_decision_api_token)
        row = _get_pending(decision_id)
        _db = _resolve_db()
        # Append a feedback event so the worker can pick it up on resume.
        if row.get("job_id"):
            _db.append_job_event(
                job_id=str(row["job_id"]),
                event_type="feedback",
                event_data={
                    "feedback": body.feedback,
                    "metric_target": body.metric_target,
                    "source": "decision_api.ask_improve",
                },
            )
        _db.resolve_decision(decision_id, "needs_improvement", notes=body.feedback)
        _audit(decision="ask_improve", decision_id=decision_id, reason=body.feedback)
        return {
            "ok": True,
            "decision_id": decision_id,
            "status": "needs_improvement",
            "job_id": row.get("job_id"),
        }

    return app


app = make_app()
