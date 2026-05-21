"""kca skill: list / show / run [--dry-run] surface over the skill loader."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect  # noqa: E402

from agent.permission_policy import resolve_for_skill  # noqa: E402
from agent.skill_loader import list_skills, load_skill, render_skill  # noqa: E402


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    return exit_code


def _meta_to_dict(meta) -> dict:
    d = asdict(meta)
    # Drop body from list-style summaries to keep output compact.
    return d


def _parse_args(arg_list: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in arg_list or []:
        if "=" not in item:
            raise ValueError(f"--arg must be key=value, got {item!r}")
        key, _, value = item.partition("=")
        if not key:
            raise ValueError(f"--arg key empty in {item!r}")
        out[key] = value
    return out


def cmd_list(args: argparse.Namespace) -> int:
    metas = list_skills()
    if getattr(args, "tag", None):
        metas = [m for m in metas if args.tag in (m.tags or [])]

    summaries = [
        {
            "name": m.name,
            "description": m.description,
            "version": m.version,
            "approval_policy": m.approval_policy,
            "tags": list(m.tags),
            "allowed_tools": list(m.allowed_tools),
        }
        for m in metas
    ]
    if getattr(args, "json", False):
        return _emit(
            True,
            {"skills": summaries, "side_effect": SideEffect.READ_ONLY.value},
        )
    # Human format
    if not summaries:
        print("(no skills)")
        return EXIT_OK
    name_w = max(len(s["name"]) for s in summaries)
    policy_w = max(len(s["approval_policy"]) for s in summaries)
    for s in summaries:
        print(
            f"{s['name']:<{name_w}}  {s['approval_policy']:<{policy_w}}  {s['description']}"
        )
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    try:
        skill = load_skill(args.name)
    except FileNotFoundError as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)
    meta_dict = _meta_to_dict(skill.meta)
    if getattr(args, "json", False):
        return _emit(
            True,
            {"skill": meta_dict, "side_effect": SideEffect.READ_ONLY.value},
        )
    print(f"name: {skill.meta.name}")
    print(f"description: {skill.meta.description}")
    print(f"version: {skill.meta.version}")
    print(f"approval-policy: {skill.meta.approval_policy}")
    print(f"arguments: {skill.meta.arguments}")
    print(f"allowed-tools: {skill.meta.allowed_tools}")
    print(f"tags: {skill.meta.tags}")
    print()
    print(skill.meta.body.rstrip())
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    try:
        skill = load_skill(args.name)
    except FileNotFoundError as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)
    try:
        arg_dict = _parse_args(args.arg)
    except ValueError as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)
    missing = [a for a in skill.meta.arguments if a not in arg_dict]
    if missing:
        return _emit(
            False,
            {"error": f"missing argument: {', '.join(missing)}"},
            EXIT_RUNTIME,
        )
    try:
        rendered = render_skill(skill, arg_dict)
    except ValueError as exc:
        return _emit(False, {"error": str(exc)}, EXIT_RUNTIME)

    mode = args.mode or "default"
    tool_perms: list[dict] = []
    for tool in skill.meta.allowed_tools:
        decision = resolve_for_skill(skill.meta, tool, mode=mode)
        tool_perms.append(
            {
                "tool": tool,
                "decision": decision,
                "reason": f"profile={skill.meta.approval_policy} mode={mode}",
            }
        )

    if args.dry_run:
        payload = {
            "dry_run": True,
            "skill": skill.meta.name,
            "mode": mode,
            "args": arg_dict,
            "tool_permissions": tool_perms,
            "rendered_prompt": rendered,
            "side_effect": SideEffect.READ_ONLY.value,
        }
        return _emit(True, payload)

    # Non-dry-run path: emit audit records, then note that execution is M8 scope.
    try:
        from agent.audit import AuditLogger

        logger = AuditLogger()
        for entry in tool_perms:
            logger.log_policy_decision(
                tool=entry["tool"],
                operation=entry["tool"],
                decision=entry["decision"],
                skill_name=skill.meta.name,
                mode=mode,
                policy_profile=skill.meta.approval_policy,
                args=arg_dict,
            )
    except Exception as exc:  # best-effort audit
        sys.stderr.write(f"[audit warn] {exc}\n")

    if getattr(args, "json", False):
        return _emit(
            True,
            {
                "dry_run": False,
                "skill": skill.meta.name,
                "mode": mode,
                "args": arg_dict,
                "tool_permissions": tool_perms,
                "rendered_prompt": rendered,
                "note": "actual execution not implemented in M7 — use kca job run",
                "side_effect": SideEffect.READ_ONLY.value,
            },
        )
    print(rendered)
    for entry in tool_perms:
        print(f"  tool={entry['tool']:<20} decision={entry['decision']}")
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": False,
                "note": "actual execution not implemented in M7 — use kca job run",
            }
        )
    )
    return EXIT_OK


def add_parsers(sub) -> None:
    p = sub.add_parser("skill", help="Skill loader CLI (list / show / run).")
    sp = p.add_subparsers(dest="action", required=True)

    p_list = sp.add_parser("list", help="List available skills.")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--tag")
    p_list.set_defaults(func=cmd_list)

    p_show = sp.add_parser("show", help="Show a skill's parsed metadata.")
    p_show.add_argument("name")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_run = sp.add_parser("run", help="Render a skill and resolve tool permissions.")
    p_run.add_argument("name")
    p_run.add_argument(
        "--arg",
        action="append",
        default=[],
        help="key=value (repeatable) substitution variable",
    )
    p_run.add_argument("--mode", default=None)
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--json", action="store_true")
    p_run.set_defaults(func=cmd_run)
