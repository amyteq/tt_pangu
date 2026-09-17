"""Parity between `tools/kca/kg.py` and its documentation (issue #198).

`tools/kca/COMMANDS.md` is what a skill, a hook author or a human reads to decide
whether a `kca kaggle` subcommand is safe to run. When it drifts from `kg.py` the
failure is silent and the wrong way round: #198 found `submit` and `upload`
documented as harmless stubs while both were real, credential-using commands that
reach Kaggle.

These tests read the code — `kg.py`'s AST, never the doc's claims about it — and
fail if the `### kca kaggle subcommands` table disagrees on membership or on the
stub/real classification. A new `cmd_*` that lands undocumented fails them too.

Nothing here imports `tools.kca.kg`: the module pulls in `kaggle` and the DB layer
at import time, and this check needs neither.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
KG_PY = REPO_ROOT / "tools" / "kca" / "kg.py"
COMMANDS_MD = REPO_ROOT / "tools" / "kca" / "COMMANDS.md"

DOC_SECTION_HEADING = "### `kca kaggle` subcommands"

# The plain risk vocabulary the table's Side-effect column has to speak. `local-only`
# is a superset of "no network at all"; the two write levels say where the write lands.
SIDE_EFFECT_LEVELS = ("local-only", "network-read", "remote-write")

STATUS_REAL = "real"
STATUS_STUB = "stub"


# --------------------------------------------------------------------------
# kg.py side
# --------------------------------------------------------------------------


def _cli_names_from_parsers(tree: ast.Module) -> dict[str, str]:
    """Map `cmd_*` function name -> CLI subcommand name, read from `add_parsers`.

    Matches the two halves of the argparse idiom on the parser variable:

        p_score = kg_sub.add_parser("score", ...)
        p_score.set_defaults(func=cmd_score)
    """
    var_to_cli: dict[str, str] = {}
    var_to_func: dict[str, str] = {}

    for node in ast.walk(tree):
        # p_x = <something>.add_parser("name", ...)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "add_parser" and call.args:
                first = call.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_to_cli[target.id] = first.value

        # p_x.set_defaults(func=cmd_x)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "set_defaults":
            receiver = node.func.value
            if not isinstance(receiver, ast.Name):
                continue
            for kw in node.keywords:
                if kw.arg == "func" and isinstance(kw.value, ast.Name) and kw.value.id.startswith("cmd_"):
                    var_to_func[receiver.id] = kw.value.id

    return {func: var_to_cli[var] for var, func in var_to_func.items() if var in var_to_cli}


def parse_kg_commands(source: str) -> dict[str, str]:
    """Return {cli subcommand name: "real" | "stub"} for every `cmd_*` in `source`.

    A command is a stub iff its body calls `_emit_stub`, which is the whole of what
    a stub does: emit `{"ok": true, "stub": true}` and return. Anything else is real.
    """
    tree = ast.parse(source)
    cli_names = _cli_names_from_parsers(tree)

    commands: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("cmd_"):
            continue

        emits_stub = any(
            isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "_emit_stub"
            for inner in ast.walk(node)
        )
        # Fall back to the function name when a command is not wired into a parser,
        # so an unwired `cmd_*` still has to be documented rather than vanishing.
        cli = cli_names.get(node.name, node.name[len("cmd_") :].replace("_", "-"))
        commands[cli] = STATUS_STUB if emits_stub else STATUS_REAL

    return commands


# --------------------------------------------------------------------------
# COMMANDS.md side
# --------------------------------------------------------------------------

_ROW_COMMAND = re.compile(r"^`kca kaggle ([a-z0-9][a-z0-9-]*)`$")


def _doc_rows(text: str) -> list[list[str]]:
    """Return the `### kca kaggle subcommands` table's body rows, as trimmed cells."""
    if DOC_SECTION_HEADING not in text:
        raise AssertionError(f"{COMMANDS_MD.name} has no {DOC_SECTION_HEADING!r} section")

    section = text.split(DOC_SECTION_HEADING, 1)[1]
    # Stop at the next heading of the same or higher level.
    for line in section.splitlines():
        if line.startswith("## ") or (line.startswith("### ") and line.strip() != DOC_SECTION_HEADING):
            section = section.split(line, 1)[0]
            break

    rows: list[list[str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not _ROW_COMMAND.match(cells[0]):
            continue  # header, separator, or a non-command row
        rows.append(cells)
    return rows


def parse_doc_commands(text: str) -> dict[str, dict[str, str]]:
    """Return {subcommand: {"status": ..., "side_effect": ...}} from the doc table."""
    documented: dict[str, dict[str, str]] = {}
    for cells in _doc_rows(text):
        name = _ROW_COMMAND.match(cells[0]).group(1)
        status_cell = cells[1].replace("*", "").strip().lower() if len(cells) > 1 else ""
        side_effect_cell = cells[2].replace("*", "").strip().lower() if len(cells) > 2 else ""

        if status_cell in (STATUS_REAL, STATUS_STUB):
            status = status_cell
        else:
            status = f"unparseable:{cells[1] if len(cells) > 1 else ''}"

        documented[name] = {"status": status, "side_effect": side_effect_cell}
    return documented


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def kg_commands() -> dict[str, str]:
    return parse_kg_commands(KG_PY.read_text())


@pytest.fixture(scope="module")
def doc_commands() -> dict[str, dict[str, str]]:
    return parse_doc_commands(COMMANDS_MD.read_text())


# --------------------------------------------------------------------------
# The parity checks
# --------------------------------------------------------------------------


def test_kg_py_has_commands_to_check(kg_commands: dict[str, str]) -> None:
    """Guard the guard: a parser that silently found nothing would pass everything."""
    assert len(kg_commands) >= 9, f"expected kg.py to define at least 9 cmd_* functions, found {kg_commands}"
    assert STATUS_REAL in kg_commands.values()
    assert STATUS_STUB in kg_commands.values()


def test_every_kg_command_is_documented(kg_commands: dict[str, str], doc_commands: dict[str, dict[str, str]]) -> None:
    missing = sorted(set(kg_commands) - set(doc_commands))
    assert not missing, (
        f"{missing} exist in tools/kca/kg.py but have no row in the "
        f"'{DOC_SECTION_HEADING}' table of tools/kca/COMMANDS.md"
    )


def test_no_documented_command_is_invented(
    kg_commands: dict[str, str], doc_commands: dict[str, dict[str, str]]
) -> None:
    extra = sorted(set(doc_commands) - set(kg_commands))
    assert not extra, f"{extra} are documented in tools/kca/COMMANDS.md but no matching cmd_* exists in tools/kca/kg.py"


def test_stub_real_classification_matches(kg_commands: dict[str, str], doc_commands: dict[str, dict[str, str]]) -> None:
    mismatched = {
        name: (status, doc_commands[name]["status"])
        for name, status in sorted(kg_commands.items())
        if name in doc_commands and doc_commands[name]["status"] != status
    }
    assert not mismatched, (
        "tools/kca/COMMANDS.md disagrees with tools/kca/kg.py on stub-vs-real "
        f"(subcommand: code says, doc says): {mismatched}"
    )


def test_every_row_declares_a_side_effect_level(doc_commands: dict[str, dict[str, str]]) -> None:
    undeclared = sorted(
        name
        for name, row in doc_commands.items()
        if not any(level in row["side_effect"] for level in SIDE_EFFECT_LEVELS)
    )
    assert not undeclared, (
        f"{undeclared} have no recognised side-effect level in tools/kca/COMMANDS.md; "
        f"each row's Side-effect cell must name one of {SIDE_EFFECT_LEVELS}"
    )


def test_remote_writes_are_marked_remote_write(doc_commands: dict[str, dict[str, str]]) -> None:
    """The inversion #198 fixed: `submit` and `upload` were documented as harmless."""
    for name in ("submit", "push", "upload"):
        assert name in doc_commands, f"`kca kaggle {name}` must be documented"
        assert "remote-write" in doc_commands[name]["side_effect"], (
            f"`kca kaggle {name}` reaches Kaggle and must be marked remote-write, "
            f"got {doc_commands[name]['side_effect']!r}"
        )


# --------------------------------------------------------------------------
# Self-checks: the parity test has to actually fail on re-drift
# --------------------------------------------------------------------------

_SYNTHETIC_KG = """
def cmd_submit(args):
    proc = subprocess.run(["kaggle", "competitions", "submit"])
    return _emit_json({"ok": True})


def cmd_fetch(args):
    return _emit_stub("fetch", SideEffect.READ_ONLY, {"run": args.run})


def cmd_brand_new(args):
    return _emit_json({"ok": True})


def add_parsers(sub):
    p_submit = kg_sub.add_parser("submit")
    p_submit.set_defaults(func=cmd_submit)
    p_fetch = kg_sub.add_parser("fetch")
    p_fetch.set_defaults(func=cmd_fetch)
    p_new = kg_sub.add_parser("brand-new")
    p_new.set_defaults(func=cmd_brand_new)
"""


def test_parser_classifies_synthetic_source() -> None:
    parsed = parse_kg_commands(_SYNTHETIC_KG)
    assert parsed == {"submit": STATUS_REAL, "fetch": STATUS_STUB, "brand-new": STATUS_REAL}


def test_undocumented_new_command_is_caught(doc_commands: dict[str, dict[str, str]]) -> None:
    """A `cmd_*` landing in kg.py with no COMMANDS.md row must fail parity."""
    parsed = parse_kg_commands(_SYNTHETIC_KG)
    assert "brand-new" in parsed
    assert "brand-new" not in doc_commands
    assert sorted(set(parsed) - set(doc_commands)) == ["brand-new"]


def test_flipped_classification_is_caught() -> None:
    """Re-documenting a real command as a stub must fail parity."""
    flipped = COMMANDS_MD.read_text().replace(
        "| `kca kaggle submit`   | **real** |",
        "| `kca kaggle submit`   | **stub** |",
    )
    assert flipped != COMMANDS_MD.read_text(), "the submit row is not in the shape this self-check patches"

    doc = parse_doc_commands(flipped)
    code = parse_kg_commands(KG_PY.read_text())
    assert doc["submit"]["status"] == STATUS_STUB
    assert code["submit"] == STATUS_REAL
    assert doc["submit"]["status"] != code["submit"]


def test_missing_section_is_an_error() -> None:
    with pytest.raises(AssertionError, match="no '### `kca kaggle` subcommands' section"):
        parse_doc_commands("# kca command reference\n\nnothing here\n")
