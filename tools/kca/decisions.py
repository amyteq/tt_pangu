"""kca decisions: list, approve, and deny human approval requests."""

from __future__ import annotations

import argparse
import json

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return exit_code


def _load_db():
    """Import db module; raise ImportError or DBNotConfigured if unavailable."""
    import db as _db

    return _db


def cmd_list(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        job_id = getattr(args, "job_id", None)
        rows = _db.list_pending_decisions(job_id=job_id)
        decisions = [
            {
                "id": str(r.get("id", "")),
                "decision_type": r.get("decision_type", ""),
                "status": r.get("status", ""),
                "prompt": r.get("prompt", ""),
                "created_at": str(r.get("created_at", "")),
                "job_id": str(r.get("job_id", "")) if r.get("job_id") else None,
            }
            for r in rows
        ]
        payload: dict = {
            "decisions": decisions,
            "side_effect": SideEffect.READ_ONLY.value,
        }
        if getattr(args, "include_reviews", False):
            review_rows = _db.list_reviews(job_id=job_id, limit=50)
            payload["reviews"] = [
                {
                    "id": str(r.get("id", "")),
                    "job_id": str(r.get("job_id", "")) if r.get("job_id") else None,
                    "verdict": r.get("verdict", ""),
                    "target_op": r.get("target_op", ""),
                    "reviewer_model": r.get("reviewer_model", ""),
                    "rationale": (r.get("rationale") or "")[:200],
                    "created_at": str(r.get("created_at", "")),
                }
                for r in review_rows
            ]
        return _emit(True, payload)
    except Exception as exc:
        # Exit 0 with ok=false for graceful DB-unavailable degradation.
        return _emit(False, {"error": str(exc), "decisions": []})


def cmd_approve(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        notes = getattr(args, "notes", None)
        _db.resolve_decision(args.id, "approved", notes=notes)
        # If the decision is linked to a job, append an approval_resume event
        # so a subsequent `scripts/run_job.py --job-id <uuid>` resume path can
        # find it.
        job_id = None
        decision_type = None
        try:
            row = _db.get_decision(args.id)
            job_id = row.get("job_id")
            decision_type = row.get("decision_type")
        except Exception:
            job_id = None
        if job_id:
            try:
                _db.append_job_event(
                    str(job_id),
                    "approval_resume",
                    event_data={"decision_id": args.id},
                )
            except Exception:
                pass
        payload: dict = {
            "decision_id": args.id,
            "resolution": "approved",
            "job_id": str(job_id) if job_id else None,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        }
        # M14-T007: a kaggle.exploration_stuck approval's notes become the new
        # exploration seed. Parse them into a structured option or free-text
        # direction so the resuming loop (T008) can mint the next batch and
        # record this decision id on the run's analysis_jsonb.escalation_id.
        if decision_type == "kaggle.exploration_stuck":
            try:
                import stuck as _stuck

                payload["resume_seed"] = _stuck.resume_seed_from_notes(notes)
                payload["escalation_id"] = args.id
            except Exception:
                pass
        return _emit(True, payload)
    except Exception as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)


def cmd_deny(args: argparse.Namespace) -> int:
    try:
        _db = _load_db()
        notes = getattr(args, "notes", None)
        _db.resolve_decision(args.id, "rejected", notes=notes)
        return _emit(
            True,
            {
                "decision_id": args.id,
                "resolution": "rejected",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
        )
    except Exception as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    dec = sub.add_parser("decisions", help="Manage pending human approval decisions")
    dec_sub = dec.add_subparsers(dest="decisions_cmd", required=True)

    p_list = dec_sub.add_parser("list", help="List pending decisions (READ_ONLY)")
    p_list.add_argument(
        "--pending",
        action="store_true",
        help="Filter to pending status only (default behaviour)",
    )
    p_list.add_argument("--job-id", dest="job_id", default=None, help="Filter to a specific job")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument(
        "--include-reviews",
        dest="include_reviews",
        action="store_true",
        help="Also surface reviewer verdict rows (M6)",
    )
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_approve = dec_sub.add_parser("approve", help="Approve a pending decision (LOCAL_WRITE)")
    p_approve.add_argument("--id", required=True, help="decision_id to approve")
    p_approve.add_argument("--notes", default=None)
    p_approve.add_argument("--json", action="store_true")
    p_approve.set_defaults(func=cmd_approve)

    p_deny = dec_sub.add_parser("deny", help="Deny a pending decision (LOCAL_WRITE)")
    p_deny.add_argument("--id", required=True, help="decision_id to deny")
    p_deny.add_argument("--notes", default=None)
    p_deny.add_argument("--json", action="store_true")
    p_deny.set_defaults(func=cmd_deny)
