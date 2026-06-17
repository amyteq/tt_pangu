#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import nbformat

from percent_nb import (
    MagicFormatError,
    PercentFormatError,
    notebook_to_percent_cells,
    percent_cells_to_text,
)

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INPUT = 2
EXIT_FORMAT = 3


def _emit(args: argparse.Namespace, ok: bool, payload: dict[str, Any], exit_code: int) -> int:
    if args.json:
        print(json.dumps({"ok": ok, **payload}, ensure_ascii=False))
    elif ok:
        print(
            f"Wrote {payload['dst']} "
            f"({payload['written_cells']} cells; code={payload['code_cells']} markdown={payload['markdown_cells']})"
        )
    else:
        print(payload.get("message", "error"), file=sys.stderr)
    return exit_code


def build_script(src: Path, *, keep_markdown: bool) -> tuple[str, dict[str, Any]]:
    with src.open("r", encoding="utf-8") as fh:
        nb = nbformat.read(fh, as_version=4)
    cells = notebook_to_percent_cells(nb, delete_markdown=not keep_markdown)
    text = percent_cells_to_text(cells)
    code_cells = sum(1 for cell in cells if cell.kind == "code")
    markdown_cells = sum(1 for cell in cells if cell.kind == "markdown")
    summary = {
        "written_cells": len(cells),
        "code_cells": code_cells,
        "markdown_cells": markdown_cells,
        "keep_markdown": keep_markdown,
    }
    return text, summary


def _parse_bool_arg(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got: {value!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nb2py.py",
        description="Convert a Jupyter notebook into a percent-v1 Python script.",
    )
    parser.add_argument("src", help="source notebook file")
    parser.add_argument("dst", nargs="?", help="destination python path; default: <src>.py")
    parser.add_argument(
        "--keep-markdown",
        type=_parse_bool_arg,
        default=True,
        metavar="BOOL",
        help="keep markdown cells in the generated python script (default: true)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write, only report whether output would change",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON to stdout")
    args = parser.parse_args(argv)

    try:
        src = Path(args.src).expanduser().resolve()
        if not src.exists() or src.suffix.lower() != ".ipynb":
            return _emit(
                args,
                False,
                {
                    "error": "invalid_input",
                    "message": f"source notebook file not found: {src}",
                },
                EXIT_INPUT,
            )
        dst = Path(args.dst).expanduser().resolve() if args.dst else src.with_suffix(".py")
        payload, summary = build_script(src, keep_markdown=bool(args.keep_markdown))
        changed = True
        if dst.exists():
            try:
                changed = dst.read_text(encoding="utf-8") != payload
            except Exception:
                changed = True
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(payload, encoding="utf-8")
        result = {
            "src": str(src),
            "dst": str(dst),
            "changed": changed,
            "check_only": bool(args.check),
            **summary,
        }
        return _emit(args, True, result, EXIT_OK)
    except (PercentFormatError, MagicFormatError) as exc:
        return _emit(args, False, {"error": "format_error", "message": str(exc)}, EXIT_FORMAT)
    except Exception as exc:
        return _emit(args, False, {"error": "runtime_error", "message": str(exc)}, EXIT_RUNTIME)


if __name__ == "__main__":
    raise SystemExit(main())
