from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _types import SideEffect

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEGACY_DIR = REPO_ROOT / "tools" / "legacy"


def emit_json(ok: bool, side_effect: SideEffect, payload: dict[str, Any] | None = None) -> None:
    out = {"ok": bool(ok), "side_effect": side_effect.value}
    if payload:
        out.update(payload)
    print(json.dumps(out, ensure_ascii=False))


def warn(msg: str) -> None:
    print(f"[kca] {msg}", file=sys.stderr)


def stub_emit(command: str, side_effect: SideEffect) -> int:
    warn(f"NOT-IMPLEMENTED: {command} (stub)")
    print(
        json.dumps(
            {
                "ok": True,
                "stub": True,
                "command": command,
                "side_effect": side_effect.value,
            },
            ensure_ascii=False,
        )
    )
    return 0


def run_legacy(cmd: list[str]) -> tuple[bool, dict[str, Any], str]:
    """Run a legacy tool from LEGACY_DIR; return (ok, parsed_json_or_empty, stderr_text).

    First element of cmd is the path to the legacy script, relative to REPO_ROOT.
    """
    try:
        proc = subprocess.run(
            [sys.executable, *[str(REPO_ROOT / cmd[0])], *cmd[1:]],
            cwd=str(LEGACY_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        return False, {}, str(e)

    stdout = (proc.stdout or "").strip()
    parsed: dict[str, Any] = {}
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = {"raw_stdout": stdout}
    ok = (proc.returncode == 0) and bool(parsed.get("ok", True))
    return ok, parsed, (proc.stderr or "")
