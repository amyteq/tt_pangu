#!/usr/bin/env python3
"""Claude Code PreToolUse guardrail hook for permissive KCA development.

Policy:
- Allow normal development work without prompts.
- Deny secret access and host-destructive operations.
- Ask only for irreversible or decision-level operations.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def emit(decision: str, reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def normalize_path(value: str) -> str:
    if not value:
        return ""
    return os.path.expanduser(value).replace("\\", "/")


def path_is_protected(path: str) -> bool:
    """Dev-phase carve-out: project .env, .env.local, .env.development and
    ~/.kaggle/kaggle.json are readable so kca / Claude Code can pick up the
    local DSN and Kaggle test credentials without manual handoffs.
    .env.production and .env.test remain protected — these may contain
    production/staging credentials. SSH / AWS / gcloud / gh OAuth token /
    generic secrets/ dir stay protected.
    """
    p = normalize_path(path)
    protected_fragments = [
        "/secrets/",
        "/.ssh/",
        "/.aws/",
        "/.config/gcloud/",
        "/.config/gh/hosts.yml",
        "/.netrc",
        "/id_rsa",
        "/id_ed25519",
    ]
    protected_names = {
        ".env.production",
        ".env.test",
        ".netrc",
        "id_rsa",
        "id_ed25519",
        "hosts.yml",
    }
    name = Path(p).name
    return name in protected_names or any(
        fragment in p for fragment in protected_fragments
    )


def compact(command: str) -> str:
    return " ".join(command.strip().split())


def bash_decision(command: str) -> tuple[str | None, str | None]:
    c = compact(command)
    lc = c.lower()

    # Hard deny: host-destructive, privilege escalation, secret
    # exfiltration, and permanent-deletion remote writes. Project .env
    # and ~/.kaggle/kaggle.json are intentionally not in the secret list
    # (dev-phase carve-out — see path_is_protected docstring).
    deny_patterns = [
        (r"\bsudo\b", "Refusing sudo from the agent."),
        (r"\bsu\s+", "Refusing su from the agent."),
        (r"\bdoas\b", "Refusing doas from the agent."),
        (
            r"\brm\s+-rf\s+(/|~|\$HOME)(\s|$)",
            "Refusing recursive deletion of root/home.",
        ),
        (
            r"\brm\s+-rf\s+/\S+",
            "Refusing recursive deletion of absolute filesystem paths.",
        ),
        (r"\bchmod\s+777\b", "Refusing chmod 777."),
        (r"\bchown\s+.*\s+(/|~|\$HOME)\b", "Refusing ownership change on broad paths."),
        (r"\bdd\s+.*\bof=/dev/", "Refusing raw disk write."),
        (r"\bmkfs(\.|\s|$)", "Refusing filesystem formatting command."),
        (r"\bshutdown\b|\breboot\b|\bhalt\b", "Refusing host power command."),
        (r"\bgit\s+push\s+(-f|--force|--force-with-lease)", "Refusing force push."),
        (
            r"\bgit\s+push\b[^|]*?(--delete\b|\s:\S)",
            "Refusing remote branch deletion (preserve GitHub branch history).",
        ),
        (
            r"\bgh\s+(issue|label|release|repo|secret|webhook|ssh-key|gpg-key|cache|run)\s+delete\b",
            "Refusing permanent GitHub deletion (issues / labels / releases / repo / secrets / webhooks / keys / caches / runs).",
        ),
        (
            r"\bgh\s+extension\s+remove\b",
            "Refusing gh extension removal.",
        ),
        (
            r"\bdocker\s+run\b.*\s--privileged\b",
            "Refusing privileged Docker container.",
        ),
        (
            r"\b(cat|less|more|head|tail|grep|rg|awk|sed|xxd|od|strings)\b.*(id_rsa|id_ed25519|\.aws|\.ssh|\.config/gcloud|secrets/|hosts\.yml|\.netrc)",
            "Refusing shell read of protected secrets.",
        ),
        (
            r"\b(curl|wget|scp|rsync)\b.*(id_rsa|id_ed25519|\.aws|\.ssh|secrets/|metadata\.google|169\.254\.169\.254)",
            "Refusing shell exfiltration/metadata access pattern.",
        ),
        (
            r"\b(psql|sqlite3)\b.*\b(drop\s+database|drop\s+schema)\b",
            "Refusing database/schema drop from the agent.",
        ),
    ]
    for pattern, reason in deny_patterns:
        if re.search(pattern, lc, flags=re.IGNORECASE):
            return "deny", reason

    # Ask: irreversible or product/competition decision gates.
    ask_patterns = [
        (
            r"\brm\b",
            "File deletion requires approval unless implemented through an approved cleanup command.",
        ),
        (r"\brmdir\b", "Directory deletion requires approval."),
        (r"\bfind\b.*\s-delete\b", "find -delete requires approval."),
        (r"\bgit\s+clean\b", "git clean requires approval."),
        (r"\bkaggle\s+kernels\s+push\b", "Kaggle kernel push requires human approval."),
        (
            r"\bkaggle\s+datasets\s+(create|version)\b",
            "Kaggle dataset publication requires human approval.",
        ),
        (
            r"\bpython\s+tools/kca/kca\.py\s+kaggle\s+(push|upload)\b",
            "KCA Kaggle publication requires human approval.",
        ),
        (
            r"\bsupabase\s+db\s+(push|reset)\b",
            "Remote/destructive Supabase database operation requires approval.",
        ),
        (
            r"\b(psql|sqlite3)\b.*\b(truncate|delete\s+from)\b",
            "Destructive SQL requires approval.",
        ),
        (
            r"\bdocker\s+compose\s+down\b.*\s-v\b",
            "Docker volume deletion requires approval.",
        ),
    ]
    for pattern, reason in ask_patterns:
        if re.search(pattern, lc, flags=re.IGNORECASE):
            return "ask", reason

    return None, None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        emit("deny", f"Guard hook could not parse input: {exc}")
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool in {"Read", "Edit", "Write"}:
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        if path_is_protected(file_path):
            emit("deny", f"Protected path blocked: {file_path}")
            return 0

    if tool == "Bash":
        command = tool_input.get("command") or ""
        decision, reason = bash_decision(command)
        if decision and reason:
            emit(decision, reason)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
