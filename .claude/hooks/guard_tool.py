#!/usr/bin/env python3
"""Claude Code PreToolUse guardrail hook.

Reads hook JSON from stdin. Blocks obvious dangerous actions and protected
secret paths. This is a deterministic safety net, not a replacement for
container isolation, permission settings, or human review.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def emit(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


def normalize_path(value: str) -> str:
    if not value:
        return ""
    return os.path.expanduser(value).replace("\\", "/")


def path_is_protected(path: str) -> bool:
    p = normalize_path(path)
    protected_fragments = [
        "/.env", "/secrets/", "/.ssh/", "/.aws/", "/.config/gcloud/",
        "/kaggle.json", "/.netrc", "/id_rsa", "/id_ed25519",
    ]
    protected_names = {".env", "kaggle.json", ".netrc", "id_rsa", "id_ed25519"}
    name = Path(p).name
    return name in protected_names or any(fragment in p for fragment in protected_fragments)


def bash_is_blocked(command: str) -> str | None:
    c = " ".join(command.strip().split())
    dangerous_patterns = [
        (r"\brm\s+-rf\s+(/|~|\$HOME)(\s|$)", "Refusing recursive deletion of root/home."),
        (r"\bsudo\b", "Refusing sudo from the agent."),
        (r"\bchmod\s+777\b", "Refusing chmod 777."),
        (r"\bchown\s+.*\s+(/|~|\$HOME)\b", "Refusing ownership change on broad paths."),
        (r"\bdd\s+.*\bof=/", "Refusing raw disk write."),
        (r"\bmkfs(\.|\s|$)", "Refusing filesystem formatting command."),
        (r"\bshutdown\b|\breboot\b|\bhalt\b", "Refusing host power command."),
        (r"\bgit\s+push\s+--force", "Refusing force push."),
        (r"\bdocker\s+run\b.*\s--privileged\b", "Refusing privileged Docker container."),
        (r"\b(cat|less|more|head|tail|grep)\b.*(\.env|kaggle\.json|id_rsa|id_ed25519|\.aws|\.ssh)", "Refusing shell read of protected secrets."),
        (r"\b(curl|wget)\b.*(\.env|kaggle\.json|id_rsa|id_ed25519|metadata\.google|169\.254\.169\.254)", "Refusing shell exfiltration/metadata access pattern."),
    ]
    for pattern, reason in dangerous_patterns:
        if re.search(pattern, c, flags=re.IGNORECASE):
            return reason

    ask_patterns = [
        (r"\bkaggle\s+competitions\s+submit\b", "Kaggle submission requires human approval."),
        (r"\bgit\s+push\b", "Git push requires human approval."),
        (r"\bgh\s+pr\s+(create|merge)\b", "GitHub PR side effect requires human approval."),
        (r"\bsupabase\s+db\s+push\b", "Supabase database push requires human approval."),
        (r"\bnmap\b", "Network scanning requires explicit authorized CTF scope and human approval."),
        (r"\b(sqlmap|hydra|metasploit|msfconsole)\b", "Dual-use security tool requires explicit authorized CTF scope and human approval."),
    ]
    for pattern, reason in ask_patterns:
        if re.search(pattern, c, flags=re.IGNORECASE):
            return "ASK:" + reason

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # fail closed
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
        reason = bash_is_blocked(command)
        if reason:
            if reason.startswith("ASK:"):
                emit("ask", reason[4:])
            else:
                emit("deny", reason)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
