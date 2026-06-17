from __future__ import annotations

import argparse
import json
from pathlib import Path

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect
from _util import run_legacy


def _resolve(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def _emit(envelope: dict) -> None:
    print(json.dumps(envelope, ensure_ascii=False))


def cmd_to_py(args: argparse.Namespace) -> int:
    src = _resolve(args.source)
    dst = _resolve(args.output) if args.output else None
    legacy_cmd = ["tools/legacy/nb2py.py", src]
    if dst:
        legacy_cmd.append(dst)
    legacy_cmd.append("--json")
    if args.keep_markdown is False:
        legacy_cmd += ["--keep-markdown", "false"]
    elif args.keep_markdown is True:
        legacy_cmd += ["--keep-markdown", "true"]

    ok, parsed, stderr = run_legacy(legacy_cmd)
    envelope = {"side_effect": SideEffect.LOCAL_WRITE.value, "src": src}
    if dst:
        envelope["dst"] = dst
    if ok:
        envelope.update({"ok": True})
        for k, v in parsed.items():
            if k != "ok":
                envelope[k] = v
        _emit(envelope)
        return EXIT_OK
    envelope.update(
        {
            "ok": False,
            "error": parsed.get("message") or parsed.get("error") or stderr.strip() or "nb2py.py failed",
            "legacy": parsed,
            "stderr": stderr.strip(),
        }
    )
    _emit(envelope)
    return EXIT_RUNTIME


def cmd_to_ipynb(args: argparse.Namespace) -> int:
    src = _resolve(args.source)
    dst = _resolve(args.output) if args.output else None
    legacy_cmd = ["tools/legacy/py2nb.py", src]
    if dst:
        legacy_cmd.append(dst)
    legacy_cmd.append("--json")
    if args.keep_markdown:
        legacy_cmd += ["--keep-markdown", "true"]

    ok, parsed, stderr = run_legacy(legacy_cmd)
    envelope = {"side_effect": SideEffect.LOCAL_WRITE.value, "src": src}
    if dst:
        envelope["dst"] = dst
    if ok:
        envelope.update({"ok": True})
        for k, v in parsed.items():
            if k != "ok":
                envelope[k] = v
        _emit(envelope)
        return EXIT_OK
    envelope.update(
        {
            "ok": False,
            "error": parsed.get("message") or parsed.get("error") or stderr.strip() or "py2nb.py failed",
            "legacy": parsed,
            "stderr": stderr.strip(),
        }
    )
    _emit(envelope)
    return EXIT_RUNTIME


def add_parsers(sub: argparse._SubParsersAction) -> None:
    nb = sub.add_parser("nb", help="Notebook <-> percent-format script conversion")
    nb_sub = nb.add_subparsers(dest="nb_cmd", required=True)

    p1 = nb_sub.add_parser("to-py", help="Convert .ipynb to percent-format .py (LOCAL_WRITE)")
    p1.add_argument("source")
    p1.add_argument("--output", "-o", help="Destination .py path")
    p1.add_argument("--json", action="store_true", help="(always JSON; flag kept for compat)")
    p1.add_argument("--keep-markdown", dest="keep_markdown", action="store_true", default=None)
    p1.add_argument("--no-keep-markdown", dest="keep_markdown", action="store_false")
    p1.set_defaults(func=cmd_to_py)

    p2 = nb_sub.add_parser("to-ipynb", help="Convert percent-format .py to .ipynb (LOCAL_WRITE)")
    p2.add_argument("source")
    p2.add_argument("--output", "-o", help="Destination .ipynb path")
    p2.add_argument("--json", action="store_true", help="(always JSON; flag kept for compat)")
    p2.add_argument("--keep-markdown", dest="keep_markdown", action="store_true", default=False)
    p2.set_defaults(func=cmd_to_ipynb)
