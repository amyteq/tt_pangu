from __future__ import annotations

import argparse
import json
import os

from _types import EXIT_OK, EXIT_BLOCKED, SideEffect
from _util import warn

_GATE_ENV = "KCA_ALLOW_REMOTE"


def _gate(side_effect: SideEffect, command_name: str) -> tuple[bool, str | None]:
    if side_effect in (SideEffect.READ_ONLY, SideEffect.LOCAL_WRITE):
        return True, None
    if os.environ.get(_GATE_ENV) == "1":
        warn(f"REMOTE OPERATION: kaggle {command_name} — {_GATE_ENV} is set")
        return True, None
    return False, f"remote operation requires {_GATE_ENV}=1 and human approval"


def _emit_blocked(command_name: str, side_effect: SideEffect, reason: str) -> int:
    print(json.dumps({
        "ok": False,
        "error": reason,
        "command": f"kaggle {command_name}",
        "side_effect": side_effect.value,
    }, ensure_ascii=False))
    return EXIT_BLOCKED


def _emit_stub(command_name: str, side_effect: SideEffect, extra: dict | None = None) -> int:
    out = {
        "ok": True,
        "stub": True,
        "command": f"kaggle {command_name}",
        "side_effect": side_effect.value,
    }
    if extra:
        out.update(extra)
    print(json.dumps(out, ensure_ascii=False))
    return EXIT_OK


def cmd_submit(args: argparse.Namespace) -> int:
    se = SideEffect.SUBMISSION
    ok, reason = _gate(se, "submit")
    if not ok:
        return _emit_blocked("submit", se, reason or "blocked")
    return _emit_stub("submit", se, {
        "competition": args.competition,
        "file": args.file,
        "message": args.message,
    })


def cmd_push(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    ok, reason = _gate(se, "push")
    if not ok:
        return _emit_blocked("push", se, reason or "blocked")
    return _emit_stub("push", se, {"name": args.name})


def cmd_upload(args: argparse.Namespace) -> int:
    se = SideEffect.REMOTE_WRITE
    ok, reason = _gate(se, "upload")
    if not ok:
        return _emit_blocked("upload", se, reason or "blocked")
    return _emit_stub("upload", se, {"path": args.path})


def cmd_watch(args: argparse.Namespace) -> int:
    return _emit_stub("watch", SideEffect.READ_ONLY, {"run": args.run})


def cmd_fetch(args: argparse.Namespace) -> int:
    return _emit_stub("fetch", SideEffect.READ_ONLY, {"run": args.run})


def cmd_list(args: argparse.Namespace) -> int:
    return _emit_stub("list", SideEffect.READ_ONLY)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    kg = sub.add_parser("kaggle", help="Kaggle remote operations (gated)")
    kg_sub = kg.add_subparsers(dest="kaggle_cmd", required=True)

    p_submit = kg_sub.add_parser("submit", help="Submit to a competition (SUBMISSION)")
    p_submit.add_argument("--competition", required=True)
    p_submit.add_argument("--file", required=True)
    p_submit.add_argument("--message", required=True)
    p_submit.add_argument("--json", action="store_true")
    p_submit.set_defaults(func=cmd_submit)

    p_push = kg_sub.add_parser("push", help="Push a kernel (REMOTE_WRITE)")
    p_push.add_argument("--name", required=True)
    p_push.add_argument("--json", action="store_true")
    p_push.set_defaults(func=cmd_push)

    p_upload = kg_sub.add_parser("upload", help="Upload dataset (REMOTE_WRITE)")
    p_upload.add_argument("--path", required=True)
    p_upload.add_argument("--json", action="store_true")
    p_upload.set_defaults(func=cmd_upload)

    p_watch = kg_sub.add_parser("watch", help="Watch a run (READ_ONLY)")
    p_watch.add_argument("--run", required=True)
    p_watch.add_argument("--json", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    p_fetch = kg_sub.add_parser("fetch", help="Fetch run artifacts (READ_ONLY)")
    p_fetch.add_argument("--run", required=True)
    p_fetch.add_argument("--json", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_list = kg_sub.add_parser("list", help="List Kaggle runs (READ_ONLY)")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)
