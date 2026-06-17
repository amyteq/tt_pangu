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
    parse_percent_script,
    percent_cells_to_notebook_cells,
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


def build_notebook(src: Path, *, keep_markdown: bool) -> tuple[Any, dict[str, Any]]:
    text = src.read_text(encoding="utf-8")
    cells = parse_percent_script(text)
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.from_dict(cell) for cell in percent_cells_to_notebook_cells(cells, delete_markdown=not keep_markdown)
    ]
    nb.metadata.setdefault("language_info", {"name": "python"})
    nb.metadata.setdefault(
        "kernelspec",
        {"name": "python3", "display_name": "Python 3", "language": "python"},
    )
    code_cells = sum(1 for cell in nb.cells if cell.cell_type == "code")
    markdown_cells = sum(1 for cell in nb.cells if cell.cell_type == "markdown")
    summary = {
        "written_cells": len(nb.cells),
        "code_cells": code_cells,
        "markdown_cells": markdown_cells,
        "keep_markdown": keep_markdown,
    }
    return nb, summary


def _parse_bool_arg(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got: {value!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="py2nb.py",
        description="Convert a percent-v1 Python script into a Jupyter notebook.",
    )
    parser.add_argument("src", help="source python file")
    parser.add_argument("dst", nargs="?", help="destination notebook path; default: <src>.ipynb")
    parser.add_argument(
        "--keep-markdown",
        type=_parse_bool_arg,
        default=False,
        metavar="BOOL",
        help="keep markdown cells in the generated notebook (default: false)",
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
        if not src.exists() or src.suffix.lower() != ".py":
            return _emit(
                args,
                False,
                {
                    "error": "invalid_input",
                    "message": f"source python file not found: {src}",
                },
                EXIT_INPUT,
            )
        dst = Path(args.dst).expanduser().resolve() if args.dst else src.with_suffix(".ipynb")
        nb, summary = build_notebook(src, keep_markdown=bool(args.keep_markdown))
        changed = True
        if dst.exists():
            try:
                with dst.open("r", encoding="utf-8") as fh:
                    current = nbformat.read(fh, as_version=4)
                changed = nbformat.writes(current) != nbformat.writes(nb)
            except Exception:
                changed = True
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with dst.open("w", encoding="utf-8") as fh:
                nbformat.write(nb, fh)
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
