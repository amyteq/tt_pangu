#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INPUT = 2
EXIT_DEP = 3
EXIT_VALIDATE_FAILED = 4

DROP_EXACT_TAGS = {"stub", "xtest"}
HEAD_TAG = "head"

_LOG_QUIET = False
_LOG_VERBOSE = 0


def _set_log_mode(quiet: bool, verbose: int) -> None:
    global _LOG_QUIET, _LOG_VERBOSE
    _LOG_QUIET = bool(quiet)
    _LOG_VERBOSE = max(0, int(verbose or 0))


def _log(message: str, level: str = "INFO") -> None:
    if level == "DEBUG" and _LOG_VERBOSE < 1:
        return
    if _LOG_QUIET and level not in {"WARN", "ERROR"}:
        return
    print(f"{level}: {message}", file=sys.stderr)


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
    error: str = "runtime_error",
    exit_code: int = EXIT_RUNTIME,
    **payload: Any,
) -> int:
    _log(message, "ERROR")
    if args.json:
        print(
            json.dumps(
                {"ok": False, "error": error, "message": message, **payload},
                ensure_ascii=False,
            )
        )
    return exit_code


def _load_notebook(path: Path):
    import nbformat

    with path.open("r", encoding="utf-8") as f:
        return nbformat.read(f, as_version=4)


def _save_notebook(path: Path, notebook) -> None:
    import nbformat

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        nbformat.write(notebook, f)


def _default_dst(src: Path) -> Path:
    return src.with_name(f"{src.stem}_test.ipynb")


def _normalize_tags(cell) -> list[str]:
    tags = cell.metadata.get("tags", [])
    return [str(tag) for tag in tags if str(tag).strip()]


def _lower_tags(cell) -> list[str]:
    return [tag.lower() for tag in _normalize_tags(cell)]


def _has_head_tag(cell) -> bool:
    return HEAD_TAG in _lower_tags(cell)


def _should_drop_cell(cell, *, keep_markdown: bool) -> bool:
    tags = _lower_tags(cell)
    if any(tag in DROP_EXACT_TAGS for tag in tags):
        return True
    if any(tag.startswith("debug") for tag in tags):
        return True
    if cell.cell_type == "markdown":
        return not keep_markdown
    if cell.cell_type != "code":
        return True
    return False


def _clean_copied_cell(cell, src_tag: str):
    new_cell = copy.deepcopy(cell)
    if getattr(new_cell, "cell_type", None) == "code":
        new_cell.outputs = []
        new_cell.execution_count = None
    tags = _normalize_tags(new_cell)
    lowered = {tag.lower() for tag in tags}
    if src_tag.lower() not in lowered:
        tags.append(src_tag)
    new_cell.metadata["tags"] = tags
    return new_cell


def _cell_has_tag(cell, tag: str) -> bool:
    needle = tag.lower()
    return any(t.lower() == needle for t in _normalize_tags(cell))


def _collect_block_ranges(indexes: list[int]) -> list[tuple[int, int]]:
    if not indexes:
        return []
    ranges: list[tuple[int, int]] = []
    start = prev = indexes[0]
    for idx in indexes[1:]:
        if idx == prev + 1:
            prev = idx
            continue
        ranges.append((start, prev))
        start = prev = idx
    ranges.append((start, prev))
    return ranges


def _add_issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, **extra: Any) -> None:
    issues.append({"severity": severity, "code": code, "message": message, **extra})


def merge_notebook(
    src_path: Path,
    dst_path: Path | None = None,
    src_tag: str | None = None,
    keep_markdown: bool = True,
) -> dict[str, Any]:
    src = Path(src_path).expanduser().resolve()
    if not src.exists() or src.suffix.lower() != ".ipynb":
        raise FileNotFoundError(f"source notebook not found or not .ipynb: {src}")

    tag = src_tag or src.stem
    dst = Path(dst_path).expanduser().resolve() if dst_path else _default_dst(src)

    src_nb = _load_notebook(src)
    if dst.exists():
        dst_nb = _load_notebook(dst)
    else:
        import nbformat

        dst_nb = nbformat.v4.new_notebook()

    copied_cells = []
    dropped_non_code = 0
    dropped_tagged = 0
    for cell in src_nb.cells:
        if _should_drop_cell(cell, keep_markdown=keep_markdown):
            if cell.cell_type == "markdown":
                dropped_non_code += 1
            elif cell.cell_type != "code":
                dropped_non_code += 1
            else:
                dropped_tagged += 1
            continue
        copied_cells.append(_clean_copied_cell(cell, tag))

    head_cells = [cell for cell in dst_nb.cells if _has_head_tag(cell) and (keep_markdown or cell.cell_type == "code")]
    remaining_cells = [
        cell
        for cell in dst_nb.cells
        if (keep_markdown or cell.cell_type == "code")
        and not _has_head_tag(cell)
        and tag.lower() not in {t.lower() for t in _normalize_tags(cell)}
    ]

    dst_nb.cells = head_cells + copied_cells + remaining_cells

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
        "notebook": dst_nb,
    }


def validate_notebooks(
    src_path: Path,
    dst_path: Path | None = None,
    src_tag: str | None = None,
    keep_markdown: bool = True,
) -> dict[str, Any]:
    import nbformat

    src = Path(src_path).expanduser().resolve()
    if not src.exists() or src.suffix.lower() != ".ipynb":
        raise FileNotFoundError(f"source notebook not found or not .ipynb: {src}")

    tag = src_tag or src.stem
    dst = Path(dst_path).expanduser().resolve() if dst_path else _default_dst(src)

    src_nb = _load_notebook(src)
    src_issues: list[dict[str, Any]] = []
    src_total = len(src_nb.cells)
    src_code = sum(1 for cell in src_nb.cells if cell.cell_type == "code")
    src_non_code = src_total - src_code
    src_head_indexes: list[int] = []
    src_syncable = 0
    src_dropped_exact = 0
    src_dropped_debug = 0

    for idx, cell in enumerate(src_nb.cells):
        tags = _lower_tags(cell)
        if HEAD_TAG in tags:
            src_head_indexes.append(idx)
        if cell.cell_type != "code":
            continue
        if any(tag in DROP_EXACT_TAGS for tag in tags):
            src_dropped_exact += 1
            continue
        if any(tag.startswith("debug") for tag in tags):
            src_dropped_debug += 1
            continue
        src_syncable += 1

    if src_head_indexes:
        _add_issue(
            src_issues,
            "warn",
            "source_has_head_tags",
            "source notebook contains 'head' tags; 'head' is usually reserved for the destination test notebook.",
            cell_indexes=src_head_indexes,
        )
    if src_syncable == 0:
        _add_issue(
            src_issues,
            "warn",
            "no_syncable_code_cells",
            "source notebook has no syncable code cells after filtering non-code, stub, xtest, and debug* cells.",
        )

    reports: dict[str, Any] = {
        "src": {
            "path": str(src),
            "role": "source",
            "exists": True,
            "total_cells": src_total,
            "code_cells": src_code,
            "non_code_cells": src_non_code,
            "syncable_code_cells": src_syncable,
            "excluded_exact_tag_cells": src_dropped_exact,
            "excluded_debug_prefix_cells": src_dropped_debug,
            "issues": src_issues,
        }
    }

    checked_dst = False
    dst_exists = dst.exists()
    would_change = None

    if dst_exists:
        checked_dst = True
        dst_nb = _load_notebook(dst)
        dst_issues: list[dict[str, Any]] = []
        total = len(dst_nb.cells)
        head_indexes: list[int] = []
        src_tag_indexes: list[int] = []
        manual_indexes: list[int] = []
        head_and_src_tag_indexes: list[int] = []

        for idx, cell in enumerate(dst_nb.cells):
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
            _add_issue(
                dst_issues,
                "error",
                "cell_has_head_and_src_tag",
                "destination cell should not carry both 'head' and current source tag.",
                cell_indexes=head_and_src_tag_indexes,
            )

        if head_indexes:
            expected = list(range(min(len(head_indexes), total)))
            if head_indexes != expected:
                _add_issue(
                    dst_issues,
                    "warn",
                    "head_not_front_contiguous",
                    "destination 'head' cells should be the first contiguous block in the notebook.",
                    cell_indexes=head_indexes,
                )
        else:
            _add_issue(
                dst_issues,
                "warn",
                "missing_head_cells",
                "destination notebook has no 'head' cells; a small front bootstrap area is recommended.",
            )

        if src_tag_indexes:
            block_ranges = _collect_block_ranges(src_tag_indexes)
            if len(block_ranges) > 1:
                _add_issue(
                    dst_issues,
                    "warn",
                    "src_tag_not_contiguous",
                    "destination source-tag cells should form a single contiguous auto-generated block.",
                    cell_indexes=src_tag_indexes,
                    blocks=[[a, b] for a, b in block_ranges],
                )
        else:
            _add_issue(
                dst_issues,
                "warn",
                "missing_src_tag_block",
                "destination notebook has no cells tagged with the current source tag; it may not have been refreshed yet.",
            )

        if src_tag_indexes and manual_indexes:
            first_src = min(src_tag_indexes)
            manual_before_src = [idx for idx in manual_indexes if idx < first_src]
            if manual_before_src:
                _add_issue(
                    dst_issues,
                    "warn",
                    "manual_cells_before_src_block",
                    "manual test cells appear before the source-tag block; the recommended order is head -> source block -> manual tests.",
                    cell_indexes=manual_before_src,
                )

        if src_tag_indexes:
            first_src = min(src_tag_indexes)
            last_src = max(src_tag_indexes)
            manual_inside_src_gap = [idx for idx in manual_indexes if first_src < idx < last_src]
            if manual_inside_src_gap:
                _add_issue(
                    dst_issues,
                    "warn",
                    "manual_cells_inside_src_block",
                    "manual cells are interleaved inside the source-tag region; they may shift after refresh.",
                    cell_indexes=manual_inside_src_gap,
                )

        if not manual_indexes:
            _add_issue(
                dst_issues,
                "warn",
                "missing_manual_test_area",
                "destination notebook has no manual test cells outside head/source blocks.",
            )

        merge_preview = merge_notebook(src, dst, tag, keep_markdown=keep_markdown)
        merged_nb = merge_preview["notebook"]
        would_change = nbformat.writes(dst_nb, version=4) != nbformat.writes(merged_nb, version=4)

        reports["dst"] = {
            "path": str(dst),
            "role": "destination",
            "exists": True,
            "total_cells": total,
            "head_cells": len(head_indexes),
            "src_tag_cells": len(src_tag_indexes),
            "manual_cells": len(manual_indexes),
            "issues": dst_issues,
        }
    elif dst_path is not None:
        checked_dst = True
        reports["dst"] = {
            "path": str(dst),
            "role": "destination",
            "exists": False,
            "issues": [
                {
                    "severity": "warn",
                    "code": "destination_missing",
                    "message": "destination notebook does not exist yet; validation covered only the source notebook structure.",
                }
            ],
        }
    else:
        reports["dst"] = {
            "path": str(dst),
            "role": "destination",
            "exists": False,
            "issues": [],
        }

    all_issues = reports["src"]["issues"] + reports["dst"]["issues"]
    error_count = sum(1 for item in all_issues if item["severity"] == "error")
    warn_count = sum(1 for item in all_issues if item["severity"] == "warn")

    return {
        "src": str(src),
        "dst": str(dst),
        "src_tag": tag,
        "checked_dst": checked_dst,
        "dst_exists": dst_exists,
        "would_change": would_change,
        "summary": {
            "errors": error_count,
            "warnings": warn_count,
            "valid": error_count == 0,
        },
        "reports": reports,
    }


def _parse_bool_arg(value: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got: {value!r}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nb2test.py",
        description="Build, refresh, or validate a *_test.ipynb notebook from a source notebook.",
    )
    parser.add_argument("src", help="Source .ipynb file")
    parser.add_argument("dst", nargs="?", help="Destination .ipynb file; default: <src_stem>_test.ipynb")
    parser.add_argument(
        "--src-tag",
        help="Override the tag added to copied cells; default: source notebook stem",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout")
    parser.add_argument(
        "--keep-markdown",
        type=_parse_bool_arg,
        default=True,
        metavar="BOOL",
        help="keep markdown cells in the merged test notebook (default: true)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the planned merge without writing the notebook",
    )
    parser.add_argument(
        "--check",
        dest="check",
        action="store_true",
        help="Validate source/destination notebook structure without writing files",
    )
    parser.add_argument(
        "--validate",
        dest="check",
        action="store_true",
        help="Alias of --check",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quiet", action="store_true", help="Suppress non-error stderr logs")
    group.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Increase stderr log detail; repeat for more detail",
    )
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv[1:])
    _set_log_mode(args.quiet, args.verbose)

    try:
        if args.check:
            result = validate_notebooks(args.src, args.dst, args.src_tag, bool(args.keep_markdown))
            _log(
                "validation complete: "
                f"src={result['src']} dst={result['dst']} "
                f"errors={result['summary']['errors']} warnings={result['summary']['warnings']}",
                "INFO",
            )
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

        result = merge_notebook(args.src, args.dst, args.src_tag, bool(args.keep_markdown))
        notebook = result.pop("notebook")
        _log(
            "merge planned: "
            f"src={result['src']} dst={result['dst']} copied={result['copied_cells']} "
            f"head={result['preserved_head_cells']} keep={result['preserved_other_cells']}",
            "INFO",
        )
        if not args.dry_run:
            _save_notebook(Path(result["dst"]), notebook)
            _log(f"wrote notebook: {result['dst']}", "INFO")
        return _emit_ok(args, action="merge", dry_run=bool(args.dry_run), **result)
    except FileNotFoundError as exc:
        return _emit_fail(args, str(exc), error="invalid_input", exit_code=EXIT_INPUT)
    except ImportError as exc:
        return _emit_fail(args, str(exc), error="missing_dependency", exit_code=EXIT_DEP)
    except KeyboardInterrupt:
        return _emit_fail(args, "interrupted", error="interrupted", exit_code=EXIT_RUNTIME)
    except Exception as exc:
        return _emit_fail(args, str(exc), error="runtime_error", exit_code=EXIT_RUNTIME)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
