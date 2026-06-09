#!/usr/bin/env python3
"""Claude Code PreToolUse gate: ruff must be clean before push / PR.

Mirrors the CI job (`ruff check .` + `ruff format --check .`) but runs it
*before* a `git push` or `gh pr create|ready` so formatting/lint problems are
caught locally instead of failing CI after the PR is already open.

Behaviour:
- Only inspects Bash commands; only acts on `git push` and `gh pr create|ready`.
- Runs ruff from the repo root. If ruff is missing or errors out, it ALLOWS
  (the gate can only block on a definite failure, never on its own breakage).
- On a real ruff failure it DENIES with the failing output and the fix command.
- Escape hatch: set `SKIP_RUFF_GATE=1` in the environment to bypass (e.g. for a
  deliberate work-in-progress push).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

GATED = re.compile(r"\bgh\s+pr\s+(?:create|ready)\b|\bgit\s+push\b")


def emit_deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def repo_root() -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip())
    except Exception:
        pass
    return Path.cwd()


def ruff_failures(root: Path) -> list[str] | None:
    """Return a list of failure blurbs, [] if clean, or None if ruff could not
    be run (missing / errored) — in which case the gate stays out of the way."""
    ruff = shutil.which("ruff")
    if not ruff:
        return None
    failures: list[str] = []
    for args, label in (
        ([ruff, "format", "--check", "."], "ruff format --check ."),
        ([ruff, "check", "."], "ruff check ."),
    ):
        try:
            proc = subprocess.run(
                args,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception:
            return None
        if proc.returncode != 0:
            tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-15:]
            failures.append(f"$ {label}\n" + "\n".join(tail))
    return failures


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GATED.search(command):
        return 0
    if os.environ.get("SKIP_RUFF_GATE") == "1":
        return 0

    failures = ruff_failures(repo_root())
    if not failures:
        return 0

    emit_deny(
        "ruff is not clean — fix formatting/lint before pushing or opening a PR "
        "(this is what CI enforces). Run `ruff format . && ruff check . --fix`, "
        "re-run the checks, then retry. To bypass for a deliberate WIP push, set "
        "SKIP_RUFF_GATE=1.\n\n" + "\n\n".join(failures)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
