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
from typing import Any, Callable, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


TOKEN_ENV = "KCA_DECISION_API_TOKEN"


class ApproveBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=8, max_length=2000)


class AskImproveBody(BaseModel):
    feedback: str = Field(..., min_length=1, max_length=4000)
    metric_target: Optional[str] = None


class DecisionRow(BaseModel):
    """A row from human_decisions — mirrors the UI's HumanDecision TypeScript type."""

    id: str
    project_id: str
    job_id: Optional[str] = None
    decision_type: str
    prompt: str
    options: Optional[Any] = None
    status: str
    rationale: Optional[str] = None
    requested_by: Optional[str] = None
    created_at: str
    decided_at: Optional[str] = None

    model_config = {"extra": "allow"}


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
    submission_pack_provider: Optional[Callable[[str], dict]] = None,
) -> FastAPI:
    """Construct the FastAPI app.

    ``decisions_module`` exposes ``get_decision``, ``resolve_decision``, and
    ``append_job_event``. Tests pass a fake module to avoid touching Supabase.

    ``submission_pack_provider`` is the optional READ_ONLY hook for the
    ``GET /runs/{run_id}/submission_pack`` endpoint (M12-T005). When
    omitted, the endpoint resolves the run -> competition -> slug +
    submission_format via the real DB layer and shells out to
    ``tools/kca/submission_checklist.build_checklist`` so the UI sees the
    same checklist the worker tool sees. Tests inject a deterministic
    in-memory provider to avoid touching Supabase / the filesystem.
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
            audit_logger(decision=decision, decision_id=decision_id, reason=reason or "")
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
        resp: dict = {
            "ok": True,
            "decision_id": decision_id,
            "status": "approved",
            "job_id": row.get("job_id"),
        }
        # M14-T007: a kaggle.exploration_stuck approval's reason/notes become
        # the new exploration seed. Surface the parsed seed so the UI / loop
        # can resume with it. Reuse tools/kca/stuck.resume_seed_from_notes so
        # the CLI and the API parse the human direction identically.
        if row.get("decision_type") == "kaggle.exploration_stuck":
            try:
                import sys
                from pathlib import Path

                sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "kca"))
                import stuck as _stuck  # type: ignore

                resp["resume_seed"] = _stuck.resume_seed_from_notes(body.reason)
                resp["escalation_id"] = decision_id
            except Exception:
                pass
        return resp

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

    # ------------------------------------------------------------------
    # GET /decisions — list decisions by status (issue #15 follow-up C).
    # ------------------------------------------------------------------
    @app.get("/decisions", response_model=list[DecisionRow])
    def list_decisions(
        status: str = Query("pending", description="Filter by status (e.g. pending, approved, rejected)"),
        limit: int = Query(50, ge=1, le=200, description="Maximum rows to return"),
        competition_id: Optional[str] = Query(None, description="Filter by competition UUID (via agent_jobs join)"),
        x_decision_api_token: Optional[str] = Header(default=None),
    ) -> list[dict]:
        """READ_ONLY: list human_decisions filtered by status, with optional competition_id.

        Mirrors the response shape of the UI's ``db.listPendingDecisions()`` call
        so callers can swap from supabase-js to this endpoint without client changes.
        """
        _check_token(x_decision_api_token)
        _db = _resolve_db()
        if hasattr(_db, "list_decisions"):
            rows = _db.list_decisions(
                status=status,
                limit=limit,
                competition_id=competition_id,
            )
        else:
            # Fallback: list_pending_decisions for DI objects that haven't been
            # updated yet (e.g. older test fakes). Ignores status/competition_id.
            rows = _db.list_pending_decisions()
            rows = rows[:limit]
        return [
            {
                **r,
                "id": str(r.get("id", "")),
                "project_id": str(r.get("project_id", "")),
                "job_id": str(r["job_id"]) if r.get("job_id") else None,
                "created_at": str(r.get("created_at", "")),
                "decided_at": str(r["decided_at"]) if r.get("decided_at") else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # M12-T005: READ_ONLY submission_pack inspector for the UI.
    # ------------------------------------------------------------------
    @app.get("/runs/{run_id}/submission_pack")
    def get_submission_pack(
        run_id: str,
        x_decision_api_token: Optional[str] = Header(default=None),
    ) -> dict:
        """READ_ONLY: return the checklist for a run's submission_pack.

        Response shape mirrors
        ``tools/kca/submission_checklist.build_checklist`` so the UI and
        the worker agree on the rendering. Never writes; never mutates.
        """
        _check_token(x_decision_api_token)
        if submission_pack_provider is not None:
            return submission_pack_provider(run_id)
        # Real path: resolve the run -> competition row -> build_checklist.
        try:
            _db = _resolve_db()
            run_row = _db.get_run(run_id) if hasattr(_db, "get_run") else None
        except Exception as exc:  # pragma: no cover — surfaced as 503
            raise HTTPException(
                status_code=503,
                detail=f"db unavailable: {type(exc).__name__}",
            )
        if not run_row:
            raise HTTPException(status_code=404, detail="run not found")
        competition_id = run_row.get("competition_id")
        if not competition_id:
            raise HTTPException(
                status_code=404,
                detail="run has no competition_id",
            )
        try:
            comp = _db.get_competition(competition_id) if hasattr(_db, "get_competition") else None
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=503,
                detail=f"db unavailable: {type(exc).__name__}",
            )
        if not comp:
            raise HTTPException(status_code=404, detail="competition not found")
        try:
            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "kca"))
            from submission_checklist import build_checklist  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=503,
                detail=f"checklist tool unavailable: {type(exc).__name__}",
            )
        checklist = build_checklist(
            slug=comp.get("slug"),
            run_id=run_id,
            submission_format=comp.get("submission_format"),
        )
        return {
            "ok": True,
            "run_id": run_id,
            "slug": comp.get("slug"),
            "checklist": checklist,
        }

    return app


app = make_app()
