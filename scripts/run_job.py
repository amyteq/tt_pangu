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

# Load .env from repo root if python-dotenv is installed.
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

from src.worker._types import JobPolicy  # noqa: E402
from src.worker.worker import AgentWorker  # noqa: E402
from src.worker import routing as _routing  # noqa: E402

_DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


def _build_policy(args: argparse.Namespace) -> JobPolicy:
    allowed = list(args.allowed_tools) if args.allowed_tools else ["kca *", "pytest *"]
    job_type = getattr(args, "job_type", None) or "implement"
    # --model overrides the route table; the routing function preserves this
    # precedence.
    model = _routing.model_for(job_type, override=args.model)
    return JobPolicy(
        max_turns=args.max_turns,
        max_cost_usd=args.max_cost_usd,
        max_runtime_s=args.max_runtime_s,
        allowed_tool_patterns=allowed,
        model=model,
    )


def _resolve_policy(
    args: argparse.Namespace,
    project_row: dict | None = None,
    competition_row: dict | None = None,
) -> JobPolicy:
    """Merge project → competition → CLI policy layers (ADR-0006)."""
    base = _build_policy(args)
    if project_row:
        for k, v in (project_row.get("approval_gates") or {}).items():
            base.approval_gates[k] = v
    if competition_row:
        comp_pol = competition_row.get("competition_policy") or {}
        for k, v in (comp_pol.get("approval_gates") or {}).items():
            # Competition can only tighten (True), not loosen.
            if v:
                base.approval_gates[k] = True
    if getattr(args, "require_approval", None):
        for op in args.require_approval:
            base.approval_gates[op] = True
    return base


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
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "kca" / "kca.py"),
            "workspace",
            "init",
            "--job-id",
            job_id,
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            return data["workspace_path"]
    except Exception:
        pass
    print(json.dumps({"ok": False, "error": result.stderr or result.stdout}))
    return None


def _workspace_init_repo(job_id: str, repo: str, branch: str | None) -> str | None:
    """kca workspace init --job-id <id> --repo <repo> [--branch <branch>]."""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "kca" / "kca.py"),
        "workspace",
        "init",
        "--job-id",
        job_id,
        "--repo",
        repo,
        "--json",
    ]
    if branch:
        cmd += ["--branch", branch]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(result.stdout)
        if data.get("ok"):
            return data["workspace_path"]
    except Exception:
        pass
    print(json.dumps({"ok": False, "error": result.stderr or result.stdout}))
    return None


def _workspace_clean(job_id: str, repo: str | None = None) -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "kca" / "kca.py"),
        "workspace",
        "clean",
        "--job-id",
        job_id,
        "--json",
    ]
    if repo:
        cmd += ["--repo", repo]
    subprocess.run(cmd, capture_output=True)


def _slugify(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip()).strip("-")[:50]


def _resolve_competition_repo(slug: str, _db) -> tuple[str | None, str]:
    """Returns (local_clone_path, default_branch). Clones repo if missing."""
    if _db is None:
        return None, "main"
    try:
        comp = _db.get_competition_by_slug(slug)
    except Exception:
        return None, "main"
    clone_path = comp.get("local_clone_path")
    repo_url = comp.get("repo_url")
    default_branch = comp.get("default_branch") or "main"
    if clone_path and not Path(clone_path).exists() and repo_url:
        try:
            subprocess.run(
                ["git", "clone", repo_url, clone_path],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"[run_job] git clone failed: {exc.stderr or exc.stdout}",
                file=sys.stderr,
            )
            return None, default_branch
    return clone_path, default_branch


def _resolve_branch(args, job_row: dict | None) -> str | None:
    if getattr(args, "branch", None):
        return args.branch
    payload = (job_row or {}).get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if payload.get("branch"):
        return payload["branch"]
    hypothesis = getattr(args, "hypothesis", None) or payload.get("hypothesis") or ""
    if hypothesis:
        return "exp/" + _slugify(hypothesis)
    return None


def _ensure_branch(repo_path: str, branch: str) -> None:
    """Create branch in competition repo if it doesn't already exist."""
    subprocess.run(
        ["git", "-C", repo_path, "checkout", "-b", branch],
        capture_output=True,
        text=True,
    )


def _result_json(result, job_id: str | None = None, model: str | None = None) -> dict:
    out = {
        "status": result.status,
        "turns_used": result.turns_used,
        "cost_usd": round(result.cost_usd, 6),
        "duration_s": round(result.duration_s, 2),
        "final_message": result.final_message,
        "stop_reason": result.stop_reason,
    }
    if job_id:
        out["job_id"] = job_id
    if model:
        out["model"] = model
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_job.py",
        description="Run an M3 agent worker job locally.",
    )
    # New job from prompt
    parser.add_argument("--prompt", default=None, help="Agent prompt")
    parser.add_argument("--competition", default=None, metavar="SLUG")
    parser.add_argument(
        "--competition-slug",
        dest="competition_slug",
        default=None,
        metavar="SLUG",
        help="Competition slug (M4): looks up repo + branch in DB",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Experiment branch (auto-derived from --hypothesis if not given)",
    )
    parser.add_argument(
        "--hypothesis",
        default=None,
        help="Hypothesis text; auto-derives branch as exp/<slugified>",
    )
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--max-cost-usd", type=float, default=5.0)
    parser.add_argument("--max-runtime-s", type=int, default=3600)
    parser.add_argument("--allowed-tools", nargs="+", metavar="PATTERN")
    parser.add_argument(
        "--require-approval",
        nargs="+",
        metavar="OP",
        help="Force approval on these operations (ADR-0006)",
    )
    parser.add_argument("--model", default=None, help="Override the routed model id")
    parser.add_argument(
        "--job-type",
        dest="job_type",
        default="implement",
        choices=("research", "implement", "experiment", "eval", "analysis", "review"),
        help="Job type for model routing (ADR-0010)",
    )
    # Existing queued job
    parser.add_argument("--job-id", default=None, metavar="UUID")
    # Behaviour flags
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No real API calls; use MockLiteLLMClient",
    )
    parser.add_argument("--no-cleanup", action="store_true", help="Keep workspace after job")
    parser.add_argument("--json", action="store_true", help="Emit result as JSON to stdout")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)

    if not args.prompt and not args.job_id:
        parser.error("one of --prompt or --job-id is required")

    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — use --dry-run for testing", file=sys.stderr)
        return 1

    policy = _resolve_policy(args)
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
            print(
                f"[run_job] DB create_job failed (continuing offline): {exc}",
                file=sys.stderr,
            )
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

    # ---- Step 3.5: Resolve competition repo (M4) ----------------------------
    comp_slug = args.competition_slug or args.competition
    competition_repo_path: str | None = None
    branch: str | None = None
    if comp_slug:
        job_row = None
        if _db is not None:
            try:
                job_row = _db.get_job(job_id)
            except Exception:
                job_row = None
        competition_repo_path, default_branch = _resolve_competition_repo(
            comp_slug,
            _db,
        )
        branch = _resolve_branch(args, job_row) or default_branch

    # ---- Step 4: Resolve workspace ------------------------------------------
    workspace_was_created = False
    if args.dry_run:
        workspace = Path(tempfile.mkdtemp())
        # Seed a README for the mock tool call to succeed.
        (workspace / "README.md").write_text("M3/M4 dry-run workspace")
    elif competition_repo_path:
        if branch:
            _ensure_branch(competition_repo_path, branch)
        ws_path = _workspace_init_repo(job_id, competition_repo_path, branch)
        if ws_path is None:
            return 1
        workspace = Path(ws_path)
        workspace_was_created = True
    else:
        ws_path = _workspace_init(job_id)
        if ws_path is None:
            return 1
        workspace = Path(ws_path)
        workspace_was_created = True

    # ---- Step 5+6: Run worker -----------------------------------------------
    is_resume = bool(args.job_id and _db is not None and not args.prompt)
    if is_resume:
        try:
            worker = AgentWorker.resume(
                job_id=job_id,
                workspace=workspace,
                policy=policy,
                db_url=os.environ.get("SUPABASE_DB_URL"),
                dry_run=args.dry_run,
            )
        except Exception as exc:
            print(
                f"[run_job] resume failed, falling back to fresh start: {exc}",
                file=sys.stderr,
            )
            worker = AgentWorker(
                job_id=job_id,
                prompt=prompt,
                policy=policy,
                workspace=workspace,
                db_url=os.environ.get("SUPABASE_DB_URL") if _db is not None else None,
                dry_run=args.dry_run,
            )
    else:
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

    # ---- Step 7b: commit agent changes on success (M4) ---------------------
    if competition_repo_path and result.status == "done" and not args.dry_run:
        subprocess.run(["git", "-C", str(workspace), "add", "-A"], check=False)
        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "commit",
                "-m",
                f"job/{job_id[:8]}: agent changes",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    # ---- Step 8: Cleanup ----------------------------------------------------
    should_clean = not args.no_cleanup and result.status != "paused"
    if should_clean:
        if args.dry_run:
            shutil.rmtree(workspace, ignore_errors=True)
        elif workspace_was_created:
            _workspace_clean(job_id, repo=competition_repo_path)

    # ---- Step 9: Print result -----------------------------------------------
    if args.json:
        print(
            json.dumps(
                _result_json(result, job_id=job_id, model=policy.model),
                ensure_ascii=False,
            )
        )
    else:
        status_emoji = {
            "done": "✓",
            "budget_stop": "✗",
            "failed": "✗",
            "paused": "⏸",
        }.get(result.status, "?")
        print(
            f"[run_job] {status_emoji} status={result.status} "
            f"turns={result.turns_used} cost=${result.cost_usd:.4f} "
            f"job_id={job_id}"
        )

    # ---- Step 10: Exit code --------------------------------------------------
    if result.status == "done":
        return 0
    if result.status == "paused":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
