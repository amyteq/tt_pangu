#!/usr/bin/env python3
"""Append Claude Code hook events to a local JSONL audit log."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        payload = {"parse_error": str(exc)}

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    log_dir = project_dir / ".agent" / "audit"
    log_dir.mkdir(parents=True, exist_ok=True)

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hook_event_name": payload.get("hook_event_name"),
        "tool_name": payload.get("tool_name"),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "payload": payload,
    }

    with (log_dir / "tool-events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
