"""kca tool: list registered tools, view audit log, and run doctor checks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _types import EXIT_OK, SideEffect  # noqa: E402

from agent.audit import AuditLogger  # noqa: E402
from agent.tool_registry import (  # noqa: E402
    APPROVAL_LABELS,
    SANDBOX_LABELS,
    SIDE_EFFECT_LEVELS,
    TOOL_REGISTRY,
    list_tools,
)


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return exit_code


def cmd_list(args: argparse.Namespace) -> int:
    items = list_tools(tag=getattr(args, "tag", None))
    payload = {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "side_effect": t.side_effect,
                "approval_label": t.approval_label,
                "timeout_s": t.timeout_s,
                "sandbox": t.sandbox,
                "tags": list(t.tags),
            }
            for t in items
        ],
        "side_effect": SideEffect.READ_ONLY.value,
    }
    if getattr(args, "json", False):
        return _emit(True, payload)
    if not items:
        print("(no tools)")
        return EXIT_OK
    name_w = max(len(t.name) for t in items)
    for t in items:
        print(
            f"{t.name:<{name_w}}  {t.side_effect:<12} {t.approval_label:<5} "
            f"{t.sandbox:<14} timeout={t.timeout_s}s  tags={t.tags}"
        )
    return EXIT_OK


def cmd_audit(args: argparse.Namespace) -> int:
    logger = AuditLogger()
    path = logger.file_path
    records: list[dict] = []
    if path.is_file():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return _emit(False, {"error": str(exc), "records": []})
        for line in lines[-int(args.limit) :]:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    payload = {
        "records": records,
        "path": str(path),
        "side_effect": SideEffect.READ_ONLY.value,
    }
    if getattr(args, "json", False):
        return _emit(True, payload)
    for r in records:
        print(
            f"{r.get('timestamp', '')}  {r.get('tool_name', ''):<20} "
            f"{r.get('decision', ''):<5} profile={r.get('policy_profile', '')} "
            f"mode={r.get('mode', '')} skill={r.get('skill_name', '')}"
        )
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    issues: list[dict] = []
    for name, spec in TOOL_REGISTRY.items():
        if spec.side_effect not in SIDE_EFFECT_LEVELS:
            issues.append({"tool": name, "issue": f"bad side_effect {spec.side_effect!r}"})
        if spec.approval_label not in APPROVAL_LABELS:
            issues.append({"tool": name, "issue": f"bad approval_label {spec.approval_label!r}"})
        if spec.sandbox not in SANDBOX_LABELS:
            issues.append({"tool": name, "issue": f"bad sandbox {spec.sandbox!r}"})
        if not isinstance(spec.timeout_s, int) or spec.timeout_s <= 0:
            issues.append({"tool": name, "issue": f"bad timeout {spec.timeout_s!r}"})
    payload = {
        "tools_checked": len(TOOL_REGISTRY),
        "issues": issues,
        "side_effect": SideEffect.READ_ONLY.value,
    }
    if getattr(args, "json", False):
        return _emit(not issues, payload, EXIT_OK)
    print(f"checked {len(TOOL_REGISTRY)} tools; {len(issues)} issue(s)")
    for it in issues:
        print(f"  {it['tool']}: {it['issue']}")
    return EXIT_OK


def add_parsers(sub) -> None:
    p = sub.add_parser("tool", help="Tool registry: list / audit / doctor.")
    sp = p.add_subparsers(dest="action", required=True)

    p_list = sp.add_parser("list", help="List registered tools.")
    p_list.add_argument("--tag")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_audit = sp.add_parser("audit", help="Show recent audit records.")
    p_audit.add_argument("--limit", type=int, default=20)
    p_audit.add_argument("--json", action="store_true")
    p_audit.set_defaults(func=cmd_audit)

    p_doc = sp.add_parser("doctor", help="Validate tool registry metadata.")
    p_doc.add_argument("--json", action="store_true")
    p_doc.set_defaults(func=cmd_doctor)


# Silence unused-import in case future expansions need asdict
_ = asdict
