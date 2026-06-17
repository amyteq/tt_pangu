#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from percent_nb import (
    PercentCell,
    PercentFormatError,
    parse_percent_script,
    percent_cells_to_text,
)


EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INPUT = 2
EXIT_FORMAT = 3
EXIT_VALIDATE_FAILED = 4

DROP_EXACT_TAGS = {"stub", "xtest"}
HEAD_TAG = "head"


def _normalize_tags(cell: PercentCell) -> list[str]:
    return [str(tag) for tag in (cell.tags or []) if str(tag).strip()]


def _lower_tags(cell: PercentCell) -> list[str]:
    return [tag.lower() for tag in _normalize_tags(cell)]


def _has_head_tag(cell: PercentCell) -> bool:
    return HEAD_TAG in _lower_tags(cell)


def _should_drop_cell(cell: PercentCell, *, keep_markdown: bool) -> bool:
    tags = _lower_tags(cell)
    if any(tag in DROP_EXACT_TAGS for tag in tags):
        return True
    if any(tag.startswith("debug") for tag in tags):
        return True
    if cell.kind == "markdown":
        return not keep_markdown
    if cell.kind != "code":
        return True
    return False


def _clean_copied_cell(cell: PercentCell, src_tag: str) -> PercentCell:
    new_cell = copy.deepcopy(cell)
    tags = _normalize_tags(new_cell)
    lowered = {tag.lower() for tag in tags}
    if src_tag.lower() not in lowered:
        tags.append(src_tag)
    new_cell.tags = tags
    return new_cell


def _load_cells(path: Path) -> list[PercentCell]:
    return parse_percent_script(path.read_text(encoding="utf-8"))


def _default_dst(src: Path) -> Path:
    return src.with_name(f"{src.stem}_test.py")


def merge_script(
    src_path: Path,
    dst_path: Path | None = None,
    src_tag: str | None = None,
    keep_markdown: bool = True,
) -> dict[str, Any]:
    src = Path(src_path).expanduser().resolve()
    if not src.exists() or src.suffix.lower() != ".py":
        raise FileNotFoundError(f"source script not found or not .py: {src}")

    tag = src_tag or src.stem
    dst = Path(dst_path).expanduser().resolve() if dst_path else _default_dst(src)
    src_cells = _load_cells(src)
    dst_cells = _load_cells(dst) if dst.exists() else []

    copied_cells: list[PercentCell] = []
    dropped_non_code = 0
    dropped_tagged = 0
    for cell in src_cells:
        if _should_drop_cell(cell, keep_markdown=keep_markdown):
            if cell.kind in {"markdown"}:
                dropped_non_code += 1
            elif cell.kind != "code":
                dropped_non_code += 1
            else:
                dropped_tagged += 1
            continue
        copied_cells.append(_clean_copied_cell(cell, tag))

    head_cells = [
        copy.deepcopy(cell) for cell in dst_cells if _has_head_tag(cell) and (keep_markdown or cell.kind == "code")
    ]
    remaining_cells = [
        copy.deepcopy(cell)
        for cell in dst_cells
        if (keep_markdown or cell.kind == "code")
        and not _has_head_tag(cell)
        and tag.lower() not in {t.lower() for t in _normalize_tags(cell)}
    ]
    merged_cells = head_cells + copied_cells + remaining_cells
    return {
        "src": str(src),
        "dst": str(dst),
        "src_tag": tag,
        "copied_cells": len(copied_cells),
        "preserved_head_cells": len(head_cells),
        "preserved_other_cells": len(remaining_cells),
        "dropped_non_code_cells": dropped_non_code,
        "dropped_tagged_cells": dropped_tagged,
        "dst_exists": dst.exists(),
        "keep_markdown": keep_markdown,
        "cells": merged_cells,
    }


def validate_scripts(
    src_path: Path,
    dst_path: Path | None = None,
    src_tag: str | None = None,
    keep_markdown: bool = True,
) -> dict[str, Any]:
    src = Path(src_path).expanduser().resolve()
    if not src.exists() or src.suffix.lower() != ".py":
        raise FileNotFoundError(f"source script not found or not .py: {src}")

    tag = src_tag or src.stem
    dst = Path(dst_path).expanduser().resolve() if dst_path else _default_dst(src)
    src_cells = _load_cells(src)
    dst_cells = _load_cells(dst) if dst.exists() else []

    src_issues: list[dict[str, Any]] = []
    src_head_indexes: list[int] = []
    src_syncable = 0
    src_dropped_exact = 0
    src_dropped_debug = 0
    for idx, cell in enumerate(src_cells):
        tags = _lower_tags(cell)
        if HEAD_TAG in tags:
            src_head_indexes.append(idx)
        if cell.kind != "code":
            continue
        if any(tag_name in DROP_EXACT_TAGS for tag_name in tags):
            src_dropped_exact += 1
            continue
        if any(tag_name.startswith("debug") for tag_name in tags):
            src_dropped_debug += 1
            continue
        src_syncable += 1
    if src_head_indexes:
        src_issues.append(
            {
                "severity": "warn",
                "code": "source_has_head_tags",
                "message": "source script contains 'head' tags; 'head' is usually reserved for the destination test script.",
                "cell_indexes": src_head_indexes,
            }
        )
    if src_syncable == 0:
        src_issues.append(
            {
                "severity": "warn",
                "code": "no_syncable_code_cells",
                "message": "source script has no syncable code cells after filtering markdown, stub, xtest, and debug* cells.",
            }
        )

    dst_issues: list[dict[str, Any]] = []
    if dst.exists():
        head_indexes: list[int] = []
        src_tag_indexes: list[int] = []
        head_and_src_tag_indexes: list[int] = []
        manual_indexes: list[int] = []
        for idx, cell in enumerate(dst_cells):
            lowered = _lower_tags(cell)
            has_head = HEAD_TAG in lowered
            has_src_tag = tag.lower() in lowered
            if has_head:
                head_indexes.append(idx)
            if has_src_tag:
                src_tag_indexes.append(idx)
            if has_head and has_src_tag:
                head_and_src_tag_indexes.append(idx)
            if not has_head and not has_src_tag:
                manual_indexes.append(idx)
        if head_and_src_tag_indexes:
            dst_issues.append(
                {
                    "severity": "error",
                    "code": "cell_has_head_and_src_tag",
                    "message": "destination cell should not carry both 'head' and current source tag.",
                    "cell_indexes": head_and_src_tag_indexes,
                }
            )
        if head_indexes:
            expected = list(range(min(len(head_indexes), len(dst_cells))))
            if head_indexes != expected:
                dst_issues.append(
                    {
                        "severity": "warn",
                        "code": "head_not_front_contiguous",
                        "message": "destination 'head' cells should be the first contiguous block in the script.",
                        "cell_indexes": head_indexes,
                    }
                )
        else:
            dst_issues.append(
                {
                    "severity": "warn",
                    "code": "missing_head_cells",
                    "message": "destination script has no 'head' cells; a small front bootstrap area is recommended.",
                }
            )
        dst_report = {
            "path": str(dst),
            "role": "destination",
            "exists": True,
            "total_cells": len(dst_cells),
            "head_cells": len(head_indexes),
            "src_tag_cells": len(src_tag_indexes),
            "manual_cells": len(manual_indexes),
            "issues": dst_issues,
        }
    else:
        dst_report = {
            "path": str(dst),
            "role": "destination",
            "exists": False,
            "issues": [
                {
                    "severity": "warn",
                    "code": "destination_missing",
                    "message": "destination script does not exist yet; validation covered only the source script structure.",
                }
            ],
        }

    all_issues = src_issues + dst_report["issues"]
    error_count = sum(1 for item in all_issues if item["severity"] == "error")
    warn_count = sum(1 for item in all_issues if item["severity"] == "warn")

    return {
        "src": str(src),
        "dst": str(dst),
        "src_tag": tag,
        "dst_exists": dst.exists(),
        "keep_markdown": keep_markdown,
        "summary": {
            "errors": error_count,
            "warnings": warn_count,
            "valid": error_count == 0,
        },
        "reports": {
            "src": {
                "path": str(src),
                "role": "source",
                "exists": True,
                "total_cells": len(src_cells),
                "code_cells": sum(1 for cell in src_cells if cell.kind == "code"),
                "markdown_cells": sum(1 for cell in src_cells if cell.kind == "markdown"),
                "syncable_code_cells": src_syncable,
                "excluded_exact_tag_cells": src_dropped_exact,
                "excluded_debug_prefix_cells": src_dropped_debug,
                "issues": src_issues,
            },
            "dst": dst_report,
        },
    }


def _emit_ok(args: argparse.Namespace, **payload: Any) -> int:
    if args.json:
        print(json.dumps({"ok": True, **payload}, ensure_ascii=False))
    else:
        print("ok")
    return EXIT_OK


def _emit_fail(
    args: argparse.Namespace,
    message: str,
    *,
    error: str,
    exit_code: int,
    **payload: Any,
) -> int:
    if args.json:
        print(
            json.dumps(
                {"ok": False, "error": error, "message": message, **payload},
                ensure_ascii=False,
            )
        )
    else:
        print(message, file=sys.stderr)
    return exit_code


def _parse_bool_arg(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got: {value!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="py2test.py",
        description="Build, refresh, or validate a *_test.py script from a source percent-v1 Python script.",
    )
    parser.add_argument("src", help="Source .py file")
    parser.add_argument("dst", nargs="?", help="Destination .py file; default: <src_stem>_test.py")
    parser.add_argument(
        "--src-tag",
        help="Override the tag added to copied cells; default: source script stem",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout")
    parser.add_argument(
        "--keep-markdown",
        type=_parse_bool_arg,
        default=True,
        metavar="BOOL",
        help="keep markdown cells in the merged test script (default: true)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the planned merge without writing the script",
    )
    parser.add_argument(
        "--check",
        dest="check",
        action="store_true",
        help="Validate source/destination script structure without writing files",
    )
    parser.add_argument("--validate", dest="check", action="store_true", help="Alias of --check")
    args = parser.parse_args(argv)

    try:
        if args.check:
            result = validate_scripts(args.src, args.dst, args.src_tag, bool(args.keep_markdown))
            if result["summary"]["valid"]:
                return _emit_ok(args, action="validate", **result)
            if args.json:
                print(
                    json.dumps(
                        {"ok": False, "error": "validation_failed", **result},
                        ensure_ascii=False,
                    )
                )
            return EXIT_VALIDATE_FAILED

        result = merge_script(args.src, args.dst, args.src_tag, bool(args.keep_markdown))
        cells = result.pop("cells")
        payload = percent_cells_to_text(cells)
        changed = True
        dst_path = Path(result["dst"])
        if dst_path.exists():
            try:
                changed = dst_path.read_text(encoding="utf-8") != payload
            except Exception:
                changed = True
        if not args.dry_run:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_text(payload, encoding="utf-8")
        return _emit_ok(
            args,
            action="merge",
            dry_run=bool(args.dry_run),
            changed=changed,
            written_cells=len(cells),
            **result,
        )
    except FileNotFoundError as exc:
        return _emit_fail(args, str(exc), error="invalid_input", exit_code=EXIT_INPUT)
    except PercentFormatError as exc:
        return _emit_fail(args, str(exc), error="format_error", exit_code=EXIT_FORMAT)
    except Exception as exc:
        return _emit_fail(args, str(exc), error="runtime_error", exit_code=EXIT_RUNTIME)


if __name__ == "__main__":
    raise SystemExit(main())
