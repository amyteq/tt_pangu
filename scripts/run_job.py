#!/usr/bin/env python3
"""Local M3 job runner.

Orchestrates: create → lease → workspace → worker → update → cleanup.

Exit codes:
  0  job succeeded
  1  job failed (budget, error, or tool error)
  2  job paused (awaiting approval)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure repo root is on the path.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

from src.worker._types import JobPolicy
from src.worker.worker import AgentWorker

_DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


def _build_policy(args: argparse.Namespace) -> JobPolicy:
    allowed = list(args.allowed_tools) if args.allowed_tools else ["kca *", "pytest *"]
    return JobPolicy(
        max_turns=args.max_turns,
        max_cost_usd=args.max_cost_usd,
        max_runtime_s=args.max_runtime_s,
        allowed_tool_patterns=allowed,
        model=args.model,
    )


def _try_db():
    """Return the db module or None if DB is unavailable."""
    try:
        import db as _db
        # Cheap import check — don't open a connection yet.
        return _db
    except Exception:
        return None


def _workspace_init(job_id: str) -> str | None:
    """Create worktree workspace; return workspace_path or None on failure."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py"),
         "workspace", "init", "--job-id", job_id, "--json"],
        capture_output=True, text=True,
    )
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            return data["workspace_path"]
    except Exception:
        pass
    print(json.dumps({"ok": False, "error": result.stderr or result.stdout}))
    return None


def _workspace_clean(job_id: str) -> None:
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py"),
         "workspace", "clean", "--job-id", job_id, "--json"],
        capture_output=True,
    )


def _result_json(result) -> dict:
    return {
        "status": result.status,
        "turns_used": result.turns_used,
        "cost_usd": round(result.cost_usd, 6),
        "duration_s": round(result.duration_s, 2),
        "final_message": result.final_message,
        "stop_reason": result.stop_reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_job.py",
        description="Run an M3 agent worker job locally.",
    )
    # New job from prompt
    parser.add_argument("--prompt", default=None, help="Agent prompt")
    parser.add_argument("--competition", default=None, metavar="SLUG")
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--max-cost-usd", type=float, default=5.0)
    parser.add_argument("--max-runtime-s", type=int, default=3600)
    parser.add_argument("--allowed-tools", nargs="+", metavar="PATTERN")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    # Existing queued job
    parser.add_argument("--job-id", default=None, metavar="UUID")
    # Behaviour flags
    parser.add_argument("--dry-run", action="store_true",
                        help="No real API calls; use MockLiteLLMClient")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="Keep workspace after job")
    parser.add_argument("--json", action="store_true",
                        help="Emit result as JSON to stdout")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)

    if not args.prompt and not args.job_id:
        parser.error("one of --prompt or --job-id is required")

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — use --dry-run for testing", file=sys.stderr)
        return 1

    policy = _build_policy(args)
    _db = None if args.dry_run else _try_db()

    # ---- Step 2: Create or load job ----------------------------------------
    job_id = args.job_id
    prompt = args.prompt or ""

    if _db is not None:
        try:
            if job_id:
                job_row = _db.get_job(job_id)
                prompt = job_row.get("prompt") or prompt
            else:
                job_id = _db.create_job(
                    project_id=_DEFAULT_PROJECT_ID,
                    prompt=prompt,
                    policy=vars(policy),
                    model=policy.model,
                    competition_slug=args.competition,
                )
        except Exception as exc:
            print(f"[run_job] DB create_job failed (continuing offline): {exc}",
                  file=sys.stderr)
            _db = None

    if not job_id:
        import uuid
        job_id = str(uuid.uuid4())

    # ---- Step 3: Lease job --------------------------------------------------
    if _db is not None:
        try:
            _db.lease_job(job_id, worker_id=socket.gethostname())
        except Exception as exc:
            print(f"[run_job] lease_job failed (continuing): {exc}", file=sys.stderr)

    # ---- Step 4: Resolve workspace ------------------------------------------
    workspace_was_created = False
    if args.dry_run:
        workspace = Path(tempfile.mkdtemp())
        # Seed a README for the mock tool call to succeed.
        (workspace / "README.md").write_text("M3 dry-run workspace")
    else:
        ws_path = _workspace_init(job_id)
        if ws_path is None:
            return 1
        workspace = Path(ws_path)
        workspace_was_created = True

    # ---- Step 5+6: Run worker -----------------------------------------------
    worker = AgentWorker(
        job_id=job_id,
        prompt=prompt,
        policy=policy,
        workspace=workspace,
        db_url=os.environ.get("SUPABASE_DB_URL") if _db is not None else None,
        dry_run=args.dry_run,
    )
    result = worker.run()

    if args.verbose:
        print(f"[run_job] result: {result}", file=sys.stderr)

    # ---- Step 7: Update job status ------------------------------------------
    if _db is not None:
        import datetime
        try:
            _db.update_job(
                job_id,
                status=result.status if result.status != "budget_stop" else "failed",
                turns_used=result.turns_used,
                cost_usd=result.cost_usd,
                finished_at=datetime.datetime.now(datetime.timezone.utc),
            )
        except Exception as exc:
            print(f"[run_job] update_job failed: {exc}", file=sys.stderr)

    # ---- Step 8: Cleanup ----------------------------------------------------
    should_clean = not args.no_cleanup and result.status != "paused"
    if should_clean:
        if args.dry_run:
            shutil.rmtree(workspace, ignore_errors=True)
        elif workspace_was_created:
            _workspace_clean(job_id)

    # ---- Step 9: Print result -----------------------------------------------
    if args.json:
        print(json.dumps(_result_json(result), ensure_ascii=False))
    else:
        status_emoji = {"done": "✓", "budget_stop": "✗", "failed": "✗", "paused": "⏸"}.get(
            result.status, "?"
        )
        print(f"[run_job] {status_emoji} status={result.status} "
              f"turns={result.turns_used} cost=${result.cost_usd:.4f} "
              f"job_id={job_id}")

    # ---- Step 10: Exit code --------------------------------------------------
    if result.status == "done":
        return 0
    if result.status == "paused":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
