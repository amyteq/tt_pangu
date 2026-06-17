"""Worker tool definitions and executor.

TOOL_SCHEMAS uses OpenAI tool schema format (LiteLLM-compatible for all providers).
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
from pathlib import Path

from src.worker._types import JobPolicy

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file relative to the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to workspace root",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace the first occurrence of old_string with new_string in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": "Run a shell command in the workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout_s": {"type": "integer", "default": 60},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_workspace",
            "description": "Search for a pattern in the workspace files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Side-effect classification helpers
# ---------------------------------------------------------------------------

_SIDE_EFFECT_ORDER = ["READ_ONLY", "LOCAL_WRITE", "REMOTE_WRITE", "SUBMISSION"]

# Hard-deny patterns for run_bash (regardless of policy).
_HARD_DENY_PATTERNS = [
    "sudo *",
    "rm -rf*",
    "git push*",
    "kaggle submit*",
]
_HARD_DENY_SUBSTRINGS = [".."]


def _side_effect_ge(a: str, b: str) -> bool:
    """Return True if side-effect a >= b in severity."""
    try:
        return _SIDE_EFFECT_ORDER.index(a) >= _SIDE_EFFECT_ORDER.index(b)
    except ValueError:
        return False


def _bash_side_effect(command: str) -> str:
    """Classify the side-effect level of a bash command."""
    cmd = command.strip()
    if any(fnmatch.fnmatch(cmd, pat) for pat in ["kca kaggle submit*", "kca kaggle push*", "kca kaggle upload*"]):
        return "SUBMISSION"
    if any(fnmatch.fnmatch(cmd, pat) for pat in ["kca kaggle *", "kca run *", "python *", "pytest *"]):
        return "LOCAL_WRITE"
    return "LOCAL_WRITE"


def _is_bash_allowed(command: str, policy: JobPolicy) -> tuple[bool, str]:
    """Return (allowed, reason). Hard-deny takes priority over policy."""
    cmd = command.strip()
    for sub in _HARD_DENY_SUBSTRINGS:
        if sub in cmd:
            return False, "command not in allowed_tool_patterns"
    for pat in _HARD_DENY_PATTERNS:
        if fnmatch.fnmatch(cmd, pat):
            return False, "command not in allowed_tool_patterns"
    for pat in policy.allowed_tool_patterns:
        if fnmatch.fnmatch(cmd, pat):
            return True, ""
    return False, "command not in allowed_tool_patterns"


# ---------------------------------------------------------------------------
# ApprovalRequired exception
# ---------------------------------------------------------------------------


class ApprovalRequired(Exception):
    """Raised when a tool call exceeds policy.max_side_effect."""

    def __init__(self, tool_name: str, tool_input: dict, side_effect: str):
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.side_effect = side_effect
        super().__init__(f"{tool_name} requires approval (side_effect={side_effect})")


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------


class ToolExecutor:
    def __init__(self, workspace: Path, policy: JobPolicy):
        self.workspace = workspace.resolve()
        self.policy = policy

    def _guard_path(self, path: str) -> tuple[Path | None, str | None]:
        """Resolve path within workspace. Return (resolved, None) or (None, error)."""
        target = (self.workspace / path).resolve()
        if not str(target).startswith(str(self.workspace)):
            return None, f"path traversal rejected: {path}"
        return target, None

    def execute(self, tool_name: str, tool_input: dict) -> str:
        # Determine side effect and check approval gate.
        se = self._classify_side_effect(tool_name, tool_input)
        if _side_effect_ge(se, self.policy.max_side_effect) and se != self.policy.max_side_effect:
            raise ApprovalRequired(tool_name, tool_input, se)

        if tool_name == "read_file":
            return self._read_file(tool_input)
        elif tool_name == "write_file":
            return self._write_file(tool_input)
        elif tool_name == "edit_file":
            return self._edit_file(tool_input)
        elif tool_name == "run_bash":
            return self._run_bash(tool_input)
        elif tool_name == "grep_workspace":
            return self._grep_workspace(tool_input)
        else:
            return f"unknown tool: {tool_name}"

    def _classify_side_effect(self, tool_name: str, tool_input: dict) -> str:
        if tool_name in ("read_file", "grep_workspace"):
            return "READ_ONLY"
        if tool_name in ("write_file", "edit_file"):
            return "LOCAL_WRITE"
        if tool_name == "run_bash":
            return _bash_side_effect(tool_input.get("command", ""))
        return "LOCAL_WRITE"

    def _read_file(self, inp: dict) -> str:
        target, err = self._guard_path(inp["path"])
        if err:
            return err
        try:
            return target.read_text(errors="replace")
        except Exception as e:
            return f"read_file error: {e}"

    def _write_file(self, inp: dict) -> str:
        target, err = self._guard_path(inp["path"])
        if err:
            return err
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(inp["content"])
            return "ok"
        except Exception as e:
            return f"write_file error: {e}"

    def _edit_file(self, inp: dict) -> str:
        target, err = self._guard_path(inp["path"])
        if err:
            return err
        try:
            text = target.read_text(errors="replace")
            old = inp["old_string"]
            new = inp["new_string"]
            if old not in text:
                return f"edit_file error: old_string not found in {inp['path']}"
            target.write_text(text.replace(old, new, 1))
            return "ok"
        except Exception as e:
            return f"edit_file error: {e}"

    def _run_bash(self, inp: dict) -> str:
        command = inp.get("command", "")
        timeout_s = int(inp.get("timeout_s", 60))
        allowed, reason = _is_bash_allowed(command, self.policy)
        if not allowed:
            return json.dumps({"stdout": "", "stderr": reason, "exit_code": 126})
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(self.workspace),
            )
            return json.dumps(
                {
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "exit_code": proc.returncode,
                }
            )
        except subprocess.TimeoutExpired:
            return json.dumps({"stdout": "", "stderr": "timeout", "exit_code": 124})
        except Exception as e:
            return json.dumps({"stdout": "", "stderr": str(e), "exit_code": 1})

    def _grep_workspace(self, inp: dict) -> str:
        pattern = inp.get("pattern", "")
        search_path = inp.get("path", ".")
        target, err = self._guard_path(search_path)
        if err:
            return err
        results = []
        try:
            for p in sorted(target.rglob("*")):
                if not p.is_file():
                    continue
                try:
                    for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                        if pattern.lower() in line.lower():
                            results.append(
                                {
                                    "file": str(p.relative_to(self.workspace)),
                                    "line_number": i,
                                    "line": line,
                                }
                            )
                except Exception:
                    continue
        except Exception as e:
            return f"grep_workspace error: {e}"
        return json.dumps(results)
