from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HEADER_PREFIX = "# %%"
HEADER_RE = re.compile(r"^\s*#\s*%%(?P<rest>.*)$")
CELL_KIND_RE = re.compile(r"(?:^|\s)\[(code|markdown)\](?=\s|$)")
TAGS_RE = re.compile(r"(?:^|\s)tags=(\[[^\n]*\])(?=\s|$)")
TOPLEVEL_COMMENT_MAGIC_RE = re.compile(r"^(?P<indent>\s*)#\s*(?P<magic>[!%].*)$")
RAW_MAGIC_RE = re.compile(r"^(?P<indent>\s*)(?P<magic>[!%].*)$")


@dataclass
class PercentCell:
    kind: str
    source: str
    tags: list[str] = field(default_factory=list)


class PercentFormatError(ValueError):
    pass


class MagicFormatError(PercentFormatError):
    pass


def _normalize_tags(tags: Any) -> list[str]:
    out: list[str] = []
    for tag in list(tags or []):
        text = str(tag).strip()
        if text:
            out.append(text)
    return out


def _parse_header(line: str) -> tuple[str, list[str]] | None:
    match = HEADER_RE.match(line)
    if not match:
        return None
    rest = (match.group("rest") or "").strip()
    if not rest:
        return "code", []

    kind = "code"
    kind_match = CELL_KIND_RE.search(rest)
    if kind_match:
        kind = kind_match.group(1)
        rest = CELL_KIND_RE.sub(" ", rest, count=1).strip()

    tags: list[str] = []
    tags_match = TAGS_RE.search(rest)
    if tags_match:
        raw = tags_match.group(1)
        try:
            parsed = ast.literal_eval(raw)
        except Exception as exc:
            raise PercentFormatError(f"invalid tags metadata: {raw}") from exc
        if not isinstance(parsed, list):
            raise PercentFormatError("tags metadata must be a Python list literal")
        tags = _normalize_tags(parsed)
        rest = TAGS_RE.sub(" ", rest, count=1).strip()

    if rest:
        raise PercentFormatError(f"unsupported cell header metadata: {rest}")
    return kind, tags


def parse_percent_script(text: str) -> list[PercentCell]:
    lines = text.splitlines()
    cells: list[PercentCell] = []
    current_kind = "code"
    current_tags: list[str] = []
    current_lines: list[str] = []
    saw_header = False

    def flush() -> None:
        nonlocal current_kind, current_tags, current_lines
        if not current_lines and not saw_header:
            return
        source = "\n".join(current_lines).rstrip("\n")
        if source.strip() or current_kind != "code" or current_tags or saw_header:
            cells.append(PercentCell(kind=current_kind, source=source, tags=list(current_tags)))
        current_kind = "code"
        current_tags = []
        current_lines = []

    for line in lines:
        parsed = _parse_header(line)
        if parsed is not None:
            flush()
            current_kind, current_tags = parsed
            saw_header = True
            continue
        current_lines.append(line)
    flush()

    if not cells and text.strip() == "":
        return [PercentCell(kind="code", source="", tags=[])]
    return cells


def _ensure_supported_magic_line(line: str, *, context: str) -> None:
    raw_match = RAW_MAGIC_RE.match(line)
    if raw_match and raw_match.group("magic"):
        indent = raw_match.group("indent") or ""
        if indent:
            raise MagicFormatError(f"indented magic is not supported in {context}: {line!r}")
        raise MagicFormatError(
            f"raw top-level magic is not allowed in percent-v1 source; use comment-magic '# %...' or '# !...': {line!r}"
        )


def code_py_to_nb_source(source: str) -> str:
    out: list[str] = []
    for line in source.splitlines():
        _ensure_supported_magic_line(line, context=".py code cell")
        comment_match = TOPLEVEL_COMMENT_MAGIC_RE.match(line)
        if comment_match and not (comment_match.group("indent") or ""):
            out.append(comment_match.group("magic"))
        else:
            out.append(line)
    return "\n".join(out).rstrip("\n")


def code_nb_to_py_source(source: str) -> str:
    out: list[str] = []
    for line in source.splitlines():
        raw_match = RAW_MAGIC_RE.match(line)
        if raw_match and raw_match.group("magic"):
            indent = raw_match.group("indent") or ""
            magic = raw_match.group("magic")
            if indent:
                raise MagicFormatError(f"indented notebook magic is not supported in percent-v1: {line!r}")
            out.append(f"# {magic}")
        else:
            out.append(line)
    return "\n".join(out).rstrip("\n")


def markdown_py_to_nb_source(source: str) -> str:
    out: list[str] = []
    for line in source.splitlines():
        if not line.strip():
            out.append("")
            continue
        if line == "#":
            out.append("")
            continue
        if line.startswith("# "):
            out.append(line[2:])
            continue
        if line.startswith("#"):
            out.append(line[1:])
            continue
        raise PercentFormatError(f"markdown cells must contain comment lines or blanks in .py form; got: {line!r}")
    return "\n".join(out).rstrip("\n")


def markdown_nb_to_py_source(source: str) -> str:
    out: list[str] = []
    for line in source.splitlines():
        if line:
            out.append(f"# {line}")
        else:
            out.append("#")
    return "\n".join(out).rstrip("\n")


def make_header(kind: str, tags: list[str] | None = None) -> str:
    parts = [HEADER_PREFIX]
    if kind == "markdown":
        parts.append("[markdown]")
    elif kind != "code":
        raise PercentFormatError(f"unsupported cell kind: {kind}")
    norm_tags = _normalize_tags(tags or [])
    if norm_tags:
        parts.append(f"tags={norm_tags!r}")
    return " ".join(parts)


def notebook_to_percent_cells(nb: Any, *, delete_markdown: bool = False) -> list[PercentCell]:
    cells: list[PercentCell] = []
    for cell in list(getattr(nb, "cells", [])):
        kind = getattr(cell, "cell_type", None)
        if kind == "raw":
            raise PercentFormatError("raw cells are not supported in percent-v1")
        if kind == "markdown":
            if delete_markdown:
                continue
            source = markdown_nb_to_py_source(str(getattr(cell, "source", "") or ""))
            cells.append(
                PercentCell(
                    kind="markdown",
                    source=source,
                    tags=_normalize_tags(cell.metadata.get("tags", [])),
                )
            )
            continue
        if kind == "code":
            source = code_nb_to_py_source(str(getattr(cell, "source", "") or ""))
            cells.append(
                PercentCell(
                    kind="code",
                    source=source,
                    tags=_normalize_tags(cell.metadata.get("tags", [])),
                )
            )
            continue
        raise PercentFormatError(f"unsupported notebook cell type: {kind}")
    return cells


def _cell_id(cell: PercentCell, index: int) -> str:
    seed = f"{index}|{cell.kind}|{cell.tags}|{cell.source}".encode("utf-8", errors="ignore")
    return hashlib.blake2s(seed, digest_size=6).hexdigest()


def percent_cells_to_notebook_cells(cells: list[PercentCell], *, delete_markdown: bool = False) -> list[dict[str, Any]]:
    nb_cells: list[dict[str, Any]] = []
    out_index = 0
    for cell in cells:
        if cell.kind == "markdown":
            if delete_markdown:
                continue
            nb_cells.append(
                {
                    "cell_type": "markdown",
                    "id": _cell_id(cell, out_index),
                    "metadata": ({"tags": list(cell.tags)} if cell.tags else {}),
                    "source": markdown_py_to_nb_source(cell.source),
                }
            )
            out_index += 1
            continue
        if cell.kind != "code":
            raise PercentFormatError(f"unsupported cell kind: {cell.kind}")
        nb_cells.append(
            {
                "cell_type": "code",
                "id": _cell_id(cell, out_index),
                "execution_count": None,
                "metadata": ({"tags": list(cell.tags)} if cell.tags else {}),
                "outputs": [],
                "source": code_py_to_nb_source(cell.source),
            }
        )
        out_index += 1
    return nb_cells


def percent_cells_to_text(cells: list[PercentCell]) -> str:
    chunks: list[str] = []
    for index, cell in enumerate(cells):
        if index:
            chunks.append("")
        chunks.append(make_header(cell.kind, cell.tags))
        if cell.source:
            chunks.extend(cell.source.splitlines())
    return "\n".join(chunks).rstrip() + "\n"


def canonical_notebook_payload(nb: dict[str, Any]) -> str:
    return json.dumps(nb, ensure_ascii=False, indent=2) + "\n"


def default_notebook_metadata(src_name: str) -> dict[str, Any]:
    return {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3",
        },
        "source_script": src_name,
        "percent_v1": True,
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
