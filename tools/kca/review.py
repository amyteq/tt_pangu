"""kca review: list, show, and run reviewer verdicts (M6-T007)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False, default=str))
    return exit_code


def _load_db():
    import db as _db

    return _db


def _shape_review(r: dict) -> dict:
    return {
        "id": str(r.get("id", "")),
        "job_id": str(r.get("job_id", "")) if r.get("job_id") else None,
        "verdict": r.get("verdict", ""),
        "target_op": r.get("target_op", ""),
        "reviewer_model": r.get("reviewer_model", ""),
        "reviewer_kind": r.get("reviewer_kind", ""),
        "rationale": r.get("rationale") or "",
        "evidence": r.get("evidence") or {},
        "cost_usd": float(r.get("cost_usd") or 0.0),
        "created_at": str(r.get("created_at", "")),
    }


def cmd_list(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        rows = _db.list_reviews(
            job_id=getattr(args, "job_id", None),
            verdict=getattr(args, "verdict", None),
            limit=args.limit,
        )
        reviews = [_shape_review(r) for r in rows]
        return _emit(
            True,
            {
                "reviews": reviews,
                "side_effect": SideEffect.READ_ONLY.value,
            },
        )
    except Exception as exc:
        return _emit(
            True,
            {
                "reviews": [],
                "db_warning": str(exc),
                "side_effect": SideEffect.READ_ONLY.value,
            },
        )


def cmd_show(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        r = _db.get_review(args.id)
        return _emit(
            True,
            {
                "review": _shape_review(r),
                "side_effect": SideEffect.READ_ONLY.value,
            },
        )
    except KeyError as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)
    except Exception as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)


def cmd_run(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        job_id = args.job_id
        try:
            events = _db.list_job_events(job_id)
        except Exception:
            events = []
        try:
            job = _db.get_job(job_id)
        except Exception:
            job = {}
        from src.worker.reviewer import Reviewer, ReviewRequest

        req = ReviewRequest(
            job_id=job_id,
            target_op=args.target_op or "manual",
            tool_name=args.target_op or "manual",
            tool_input={},
            final_message=(job.get("prompt") if isinstance(job, dict) else None),
            event_trail=events,
        )
        reviewer = Reviewer(
            model=args.reviewer_model,
            dry_run=args.dry_run,
        )
        verdict = reviewer.review(req)
        try:
            rid = _db.create_review(
                job_id=job_id,
                reviewer_model=verdict.reviewer_model,
                verdict=verdict.verdict,
                reviewer_kind="async_postmortem",
                target_op=req.target_op,
                rationale=verdict.rationale,
                evidence=verdict.evidence,
                cost_usd=verdict.cost_usd,
            )
        except Exception as exc:
            rid = None
            db_warning = str(exc)
        else:
            db_warning = None
        payload = {
            "review_id": rid,
            "job_id": job_id,
            "target_op": req.target_op,
            "verdict": verdict.verdict,
            "rationale": verdict.rationale,
            "reviewer_model": verdict.reviewer_model,
            "cost_usd": verdict.cost_usd,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        }
        if db_warning:
            payload["db_warning"] = db_warning
        return _emit(True, payload)
    except Exception as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("review", help="List, show, or trigger reviewer verdicts (M6).")
    inner = p.add_subparsers(dest="review_cmd", required=True)

    p_list = inner.add_parser("list", help="List reviewer rows (READ_ONLY).")
    p_list.add_argument("--job-id", dest="job_id", default=None)
    p_list.add_argument("--verdict", default=None, choices=("approve", "reject", "abstain"))
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = inner.add_parser("show", help="Show one reviewer row (READ_ONLY).")
    p_show.add_argument("--id", required=True)
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_run = inner.add_parser("run", help="Run reviewer against a job (LOCAL_WRITE).")
    p_run.add_argument("--job-id", dest="job_id", required=True)
    p_run.add_argument("--target-op", dest="target_op", default=None)
    p_run.add_argument("--reviewer-model", dest="reviewer_model", default=None)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--json", action="store_true")
    p_run.set_defaults(func=cmd_run)
