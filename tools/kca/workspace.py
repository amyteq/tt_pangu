"""kca workspace: git worktree-based per-job workspace management."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from _types import EXIT_OK, SideEffect
from _util import REPO_ROOT, warn

_DEFAULT_ROOT = ".workspaces"


def _git(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd or str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _current_branch() -> str:
    rc, out, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    return out if rc == 0 else "main"


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return exit_code


def cmd_init(args: argparse.Namespace) -> int:
    repo_arg = getattr(args, "repo", None)
    if repo_arg:
        repo_root = Path(repo_arg).resolve()
        workspace_dir = repo_root / "jobs" / args.job_id
        git_cwd: str | None = str(repo_root)
    else:
        repo_root = REPO_ROOT
        workspace_dir = Path(args.root) / args.job_id
        git_cwd = None

    if workspace_dir.exists():
        return _emit(
            False,
            {"error": "workspace already exists", "workspace_path": str(workspace_dir)},
            1,
        )

    workspace_dir.parent.mkdir(parents=True, exist_ok=True)

    branch = args.branch or (_current_branch() if not repo_arg else None)
    if args.branch:
        # Ensure branch exists in competition repo first (best-effort).
        if repo_arg:
            subprocess.run(
                ["git", "-C", str(repo_root), "checkout", "-b", args.branch],
                capture_output=True,
                text=True,
            )
            # Switch back to default so the worktree add can claim the branch.
            subprocess.run(
                ["git", "-C", str(repo_root), "checkout", "-"],
                capture_output=True,
                text=True,
            )
        rc, out, err = _git(["worktree", "add", str(workspace_dir), args.branch], cwd=git_cwd)
    else:
        # Default: detached HEAD at current HEAD — never conflicts with the
        # primary worktree and gives the job an isolated snapshot.
        rc, out, err = _git(["worktree", "add", "--detach", str(workspace_dir)], cwd=git_cwd)
        branch = "(detached)"
    if rc != 0:
        return _emit(False, {"error": err or out}, 1)

    runs_dir = workspace_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Best-effort DB update — skip silently if no env.
    import os

    if os.environ.get("SUPABASE_DB_URL"):
        try:
            import sys

            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import db as _db

            _db.update_job(args.job_id, workspace_path=str(workspace_dir))
        except Exception as exc:
            warn(f"workspace init: DB update skipped: {exc}")

    return _emit(
        True,
        {
            "workspace_path": str(workspace_dir),
            "job_id": args.job_id,
            "branch": branch,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        },
    )


def cmd_clean(args: argparse.Namespace) -> int:
    repo_arg = getattr(args, "repo", None)
    if repo_arg:
        repo_root = Path(repo_arg).resolve()
        workspace_dir = repo_root / "jobs" / args.job_id
        git_cwd: str | None = str(repo_root)
    else:
        workspace_dir = Path(args.root) / args.job_id
        git_cwd = None

    if not workspace_dir.exists():
        return _emit(
            False,
            {"error": "workspace not found", "workspace_path": str(workspace_dir)},
            1,
        )

    git_args = ["worktree", "remove", str(workspace_dir)]
    if args.force:
        git_args.append("--force")
    rc, out, err = _git(git_args, cwd=git_cwd)
    if rc != 0:
        return _emit(False, {"error": err or out}, 1)

    # Best-effort DB update.
    import os

    if os.environ.get("SUPABASE_DB_URL"):
        try:
            import sys

            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import db as _db

            _db.update_job(args.job_id, finished_at=datetime.now(timezone.utc))
        except Exception as exc:
            warn(f"workspace clean: DB update skipped: {exc}")

    return _emit(
        True,
        {
            "removed": str(workspace_dir),
            "job_id": args.job_id,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        },
    )


def cmd_list(args: argparse.Namespace) -> int:
    root = args.root
    rc, out, err = _git(["worktree", "list", "--porcelain"])
    if rc != 0:
        return _emit(False, {"error": err or out}, 1)

    workspaces = []
    current: dict = {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if current:
                workspaces.append(current)
            current = {"path": line[len("worktree ") :]}
        elif line.startswith("HEAD "):
            current["commit"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :]
        elif line == "bare":
            current["branch"] = "(bare)"
        elif line == "" and current:
            workspaces.append(current)
            current = {}
    if current:
        workspaces.append(current)

    # Filter to workspaces under the root.
    filtered = []
    for ws in workspaces:
        p = ws.get("path", "")
        if root in p:
            ws["job_id"] = Path(p).name
            filtered.append(ws)

    return _emit(
        True,
        {
            "workspaces": filtered,
            "side_effect": SideEffect.READ_ONLY.value,
        },
    )


def add_parsers(sub: argparse._SubParsersAction) -> None:
    ws = sub.add_parser("workspace", help="Manage per-job git worktree workspaces")
    ws_sub = ws.add_subparsers(dest="workspace_cmd", required=True)

    p_init = ws_sub.add_parser("init", help="Create a workspace for a job (LOCAL_WRITE)")
    p_init.add_argument("--job-id", required=True)
    p_init.add_argument("--branch", default=None)
    p_init.add_argument("--root", default=_DEFAULT_ROOT)
    p_init.add_argument(
        "--repo",
        default=None,
        help="Competition repo path; workspace becomes <repo>/jobs/<job_id>",
    )
    p_init.add_argument("--json", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_clean = ws_sub.add_parser("clean", help="Remove a job workspace (LOCAL_WRITE)")
    p_clean.add_argument("--job-id", required=True)
    p_clean.add_argument("--root", default=_DEFAULT_ROOT)
    p_clean.add_argument(
        "--repo",
        default=None,
        help="Competition repo path; workspace at <repo>/jobs/<job_id>",
    )
    p_clean.add_argument("--force", action="store_true")
    p_clean.add_argument("--json", action="store_true")
    p_clean.set_defaults(func=cmd_clean)

    p_list = ws_sub.add_parser("list", help="List active workspaces (READ_ONLY)")
    p_list.add_argument("--root", default=_DEFAULT_ROOT)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
