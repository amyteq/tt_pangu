"""Unit tests for the ADR-0024 soft-wrap engine (`scripts/check_md_wrap.py`).

The engine's contract is narrow and worth pinning precisely: it finds exactly
two violation classes, it never looks inside a block where line breaks are
semantic, and `--fix` changes whitespace and nothing else.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_md_wrap", REPO_ROOT / "scripts" / "check_md_wrap.py")
assert _spec and _spec.loader
mdwrap = importlib.util.module_from_spec(_spec)
sys.modules["check_md_wrap"] = mdwrap
_spec.loader.exec_module(mdwrap)


def kinds(text: str) -> list[str]:
    return [v.kind for v in mdwrap.analyse(text)[0]]


def fixed(text: str) -> str:
    return mdwrap.analyse(text)[1]


# --------------------------------------------------------------------------
# Class A — split blocks
# --------------------------------------------------------------------------


def test_wrapped_paragraph_is_flagged_and_joined():
    src = "A paragraph that was hard\nwrapped across two lines.\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "A paragraph that was hard wrapped across two lines.\n"


def test_wrapped_list_item_is_flagged_and_joined():
    src = "- an item that was hard\n  wrapped onto a second line\n- a second item\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- an item that was hard wrapped onto a second line\n- a second item\n"


def test_adjacent_list_items_are_not_flagged():
    assert kinds("- one\n- two\n- three\n") == []


def test_wrapped_table_row_is_flagged_and_joined():
    src = "| Scenario | Result |\n|---|---|\n| a long scenario that\nkept going | ok |\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "| Scenario | Result |\n|---|---|\n| a long scenario that kept going | ok |\n"


def test_adjacent_table_rows_are_not_flagged():
    assert kinds("| a | b |\n|---|---|\n| c | d |\n| e | f |\n") == []


def test_pipe_less_table_is_left_alone():
    """GFM makes the outer pipes optional, so this is a table, not a paragraph.

    Joining it flattened a rendered table into one prose line. Regression for
    round-1 finding F001 on PR #226.
    """
    src = "a | b\n--- | ---\nc | d\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_table_may_interrupt_a_paragraph():
    src = "paragraph text\na | b\n--- | ---\nc | d\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_pipe_less_row_after_a_complete_row_is_a_row_not_a_continuation():
    """`| c | d |` is complete, so `e | f` is the next row and must not be absorbed."""
    src = "| a | b |\n|---|---|\n| c | d |\ne | f\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_incomplete_table_row_still_absorbs_its_continuation():
    src = "| a | b |\n|---|---|\n| a cell that\nkept going | d |\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "| a | b |\n|---|---|\n| a cell that kept going | d |\n"


def test_delimiter_row_needs_a_matching_header_width():
    """Cell counts disagree, so GFM renders a paragraph — and it is hard wrapped."""
    src = "abc\n--- | ---\nc | d\n"
    assert kinds(src) == ["split-block", "split-block"]


def test_atx_looking_header_row_still_opens_a_table():
    """markdown-it — and GitHub's preview — read `# a | b` over a delimiter as a table.

    Rejecting it left the delimiter and data rows to be joined as prose, which
    destroyed the table. Regression for round-2 finding F001 on PR #226.
    """
    src = "# a | b\n--- | ---\nc | d\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_delimiter_row_indented_four_columns_opens_nothing():
    """Indented four columns the delimiter is paragraph continuation text, not a table.

    Reading it as a table suppressed the findings for the whole run below it —
    the detection half of round-2 finding F001.
    """
    src = "head | x\n    --- | ---\nrow | y\n"
    assert kinds(src) == ["split-block", "split-block"]
    assert fixed(src) == "head | x --- | --- row | y\n"


def test_thematic_break_still_wins_over_a_table_header():
    src = "***\n--- | ---\nc | d\n"
    assert kinds(src) == ["split-block"]


def test_bare_table_ends_at_the_next_block():
    src = "a | b\n--- | ---\nc | d\n\n- item that\n  wrapped\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "a | b\n--- | ---\nc | d\n\n- item that wrapped\n"


def test_paragraph_after_heading_is_not_flagged():
    assert kinds("# Heading\nA paragraph directly below it.\n") == []


def test_explicit_hard_break_is_preserved():
    """Two trailing spaces and a trailing backslash are authored line breaks."""
    for src in ("line one  \nline two\n", "line one\\\nline two\n"):
        assert kinds(src) == []
        assert fixed(src) == src


def test_a_joined_line_keeps_its_own_trailing_hard_break():
    """Joining must not strip the `<br>` at the end of the line it absorbs.

    `content.strip()` deleted it, so the rendered break between that line and the
    next disappeared — found in `worklogs/orbit2.md:43393` by rendering every
    tracked file before and after `--fix`.
    """
    src = "**Symptom**: something\n**Where**: `file.py:78`  \n**Impact**: none\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "**Symptom**: something **Where**: `file.py:78`  \n**Impact**: none\n"


# --------------------------------------------------------------------------
# Class B — setext hazard
# --------------------------------------------------------------------------


def test_rule_directly_below_text_is_flagged_and_separated():
    src = "Some closing prose.\n---\n\nNext section.\n"
    assert kinds(src) == ["setext-rule"]
    assert fixed(src) == "Some closing prose.\n\n---\n\nNext section.\n"


def test_rule_with_blank_line_above_is_clean():
    assert kinds("Some closing prose.\n\n---\n\nNext section.\n") == []


def test_table_delimiter_row_is_not_a_setext_rule():
    assert kinds("| a | b |\n|---|---|\n| c | d |\n") == []


# --------------------------------------------------------------------------
# Blocks where line breaks are semantic
# --------------------------------------------------------------------------


def test_fenced_code_is_never_inspected():
    src = "```python\nx = 1\ny = 2\n```\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_tilde_fence_is_never_inspected():
    src = "~~~\nshort\nlines\n~~~\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_indented_backticks_do_not_close_a_fence():
    """A closing fence is indented at most three spaces. Regression for F001-F008 round 1 (F002)."""
    src = "```\ncode one\n    ```\ncode two\ncode three\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_fence_closer_with_trailing_text_does_not_close():
    src = "```\ncode one\n``` trailing\ncode two\ncode three\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_shorter_backtick_run_does_not_close_a_longer_fence():
    src = "````\ncode one\n```\ncode two\ncode three\n````\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_fence_closer_indented_three_spaces_still_closes():
    src = "```\ncode one\n   ```\nprose that is hard\nwrapped after it\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "```\ncode one\n   ```\nprose that is hard wrapped after it\n"


def test_fence_inside_a_list_item_is_code_not_the_item_continuing():
    """An indented fence beneath a list marker opens that item's code block.

    Only three columns of indent were allowed, so every line of a fenced block
    nested in a list item read as the item's text and `--fix` flattened the block
    into one inline code span. Regression for round-2 finding F002 on PR #226;
    the shape is live in `docs/tasks/m13/M13-T007-report-aggregator.md:38-51`.
    """
    src = "10. item\n    ```\n    code a\n    code b\n    ```\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_fence_inside_a_nested_list_item_closes_at_its_own_indent():
    src = '   - `Payload` shape:\n     ```jsonc\n     {\n       "a": 1\n     }\n     ```\n   - next item\n'
    assert kinds(src) == []
    assert fixed(src) == src


def test_indented_backticks_outside_a_list_are_still_prose():
    """The other direction: with no list open, an indented fence run is paragraph text."""
    src = "para\n    ```\n    code\n    ```\nafter\n"
    assert kinds(src) == ["split-block", "split-block", "split-block", "split-block"]


def test_backtick_in_the_info_string_is_not_a_fence():
    """CommonMark: a backtick fence's info string may not contain a backtick.

    Accepting one entered fence mode and hid the rest of the document from the
    gate. Regression for round-2 finding F010 on PR #226.
    """
    src = "```a`b\nprose one\nprose two\n"
    assert kinds(src) == ["split-block", "split-block"]
    assert fixed(src) == "```a`b prose one prose two\n"


def test_inline_code_span_starting_a_continuation_line_is_not_a_fence():
    """A triple-backtick code span is not a fence, so the item is simply wrapped."""
    src = "- an item mentioning\n  ```code``` inline\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- an item mentioning ```code``` inline\n"


def test_tab_indented_code_block_is_never_inspected():
    """A tab is four columns of indentation, so this is a code block, not prose."""
    src = "Para.\n\n\tcode one\n\tcode two\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_yaml_frontmatter_is_never_inspected():
    src = "---\nname: a-skill\ndescription: two\n  wrapped looking lines\n---\n\nBody.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_indented_code_block_is_never_inspected():
    src = "Prose.\n\n    code line one\n    code line two\n\nMore prose.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_html_block_is_never_inspected():
    src = "<!--\na comment\nspanning lines\n-->\n\nProse.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_html_comment_containing_a_blank_line_is_never_inspected():
    """A `<!--` block ends at `-->`, not at the first blank line (CommonMark type 2).

    Ending it early let the engine reflow comment text and pull `-->` onto a prose
    line — exactly the edit it promises not to make. Regression for issue #210.
    """
    src = "<!--\nheader note\n  continued here\n\nsecond paragraph of the\ncomment\n-->\n\nProse.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_cdata_and_processing_instruction_blocks_survive_a_blank_line():
    for src in (
        "<![CDATA[\nraw\n\nmore raw\n]]>\n\nProse.\n",
        "<?php\n$a = 1;\n\n$b = 2;\n?>\n\nProse.\n",
    ):
        assert kinds(src) == []
        assert fixed(src) == src


def test_ordinary_html_block_still_ends_at_a_blank_line():
    src = "<details>\n<summary>x</summary>\n\nA paragraph hard\nwrapped after the block.\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "<details>\n<summary>x</summary>\n\nA paragraph hard wrapped after the block.\n"


def test_html_block_interrupting_a_paragraph_is_not_inspected():
    """CommonMark HTML block types 1-6 may interrupt a paragraph.

    Requiring a preceding blank line let the engine reflow the inside of a
    `<pre>` that followed prose. Regression for round-1 finding F003 on PR #226.
    """
    src = "before\n<pre>\none\ntwo\n</pre>\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_uppercase_raw_html_terminator_closes_the_block():
    src = "<PRE>\none\ntwo\n</PRE>\n\nProse.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_autolink_at_line_start_is_prose_not_an_html_block():
    src = "<https://example.com> hard\nwrapped paragraph\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "<https://example.com> hard wrapped paragraph\n"


def test_angle_bracket_placeholder_inside_a_list_item_is_prose():
    """`<path>` is a type-7 tag, which cannot interrupt a paragraph — so this wraps."""
    src = "- `--flag-file\n  <path> [--dry-run]` — submits a flag\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- `--flag-file <path> [--dry-run]` — submits a flag\n"


def test_type_seven_html_block_at_a_block_start_is_not_inspected():
    src = "<custom-tag>\ntext under it\n\nProse.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_self_closing_pre_does_not_disable_the_rest_of_the_file():
    """`<pre/>` is a complete tag (type 7), not the start of a raw-text block.

    Type 1's start condition needs whitespace, `>` or end of line after the tag
    name, so a `/` is not one; waiting for a `</pre>` that never came skipped
    everything below. Regression for round-2 finding F003 on PR #226.
    """
    src = "<pre/>\n\nsplit para\ncontinues here\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "<pre/>\n\nsplit para continues here\n"


def test_real_pre_block_is_still_raw_text():
    src = "<pre>\none\n\ntwo\n</pre>\n\nProse.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_link_reference_definition_title_on_the_next_line_is_not_prose():
    """The title line renders as nothing; joining a paragraph onto it made it visible.

    Regression for round-1 finding F004 on PR #226.
    """
    src = '[foo]: /url\n  "title"\nParagraph after definition.\n'
    assert kinds(src) == []
    assert fixed(src) == src


def test_link_reference_definition_destination_on_the_next_line():
    src = '[foo]:\n/url\n"title"\nParagraph after definition.\n'
    assert kinds(src) == []
    assert fixed(src) == src


def test_complete_link_reference_definition_still_ends_at_its_line():
    src = '[foo]: /url "title"\nA paragraph hard\nwrapped below it.\n'
    assert kinds(src) == ["split-block"]
    assert fixed(src) == '[foo]: /url "title"\nA paragraph hard wrapped below it.\n'


def test_link_reference_definition_title_may_contain_an_escaped_delimiter():
    r"""`"ti\"tle"` is a valid title, so that line is still part of the definition.

    Rejecting it made the engine join the paragraph below onto the title, turning
    invisible metadata into visible text. Regression for round-2 finding F004.
    """
    src = '[foo]: /url\n"ti\\"tle"\nParagraph after definition.\n'
    assert kinds(src) == []
    assert fixed(src) == src


def test_link_reference_definition_cannot_interrupt_a_paragraph():
    """CommonMark: a definition does not interrupt a paragraph, so this is prose.

    Treating it as a block start suppressed every finding below it. Regression
    for round-2 finding F009 on PR #226.
    """
    src = "para text\n[foo]: /url\nmore text\n"
    assert kinds(src) == ["split-block", "split-block"]
    assert fixed(src) == "para text [foo]: /url more text\n"


def test_wrapped_blockquote_is_flagged_and_joined():
    src = "> a quoted paragraph that was\n> hard wrapped\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> a quoted paragraph that was hard wrapped\n"


def test_blockquote_and_body_at_different_depths_are_not_joined():
    assert kinds("> quoted line\n\nplain line\n") == []


def test_lazy_blockquote_continuation_is_flagged_and_joined():
    """CommonMark lets a wrapped quote drop the `>`; the line is still in the quote.

    Requiring equal quote depth let this through the gate. Regression for
    round-1 finding F006 on PR #226.
    """
    src = "> quoted hard\nwrapped lazily\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> quoted hard wrapped lazily\n"


def test_lazy_continuation_of_a_nested_quote_keeps_its_markers():
    src = "> > deep quote that\nwrapped\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> > deep quote that wrapped\n"


def test_blockquote_interrupting_a_paragraph_is_not_joined():
    assert kinds("plain paragraph\n> a quote below it\n") == []


def test_an_empty_quoted_list_item_does_not_swallow_the_paragraph_below():
    """Lazy continuation continues a paragraph, and an empty item holds none.

    `> -` is an empty quoted list item; the unquoted line below it is a separate
    top-level paragraph, and joining the two moved it into the blockquote.
    Regression for round-2 finding F006 on PR #226.
    """
    src = "> -\nplain paragraph\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_an_empty_list_item_does_not_swallow_the_paragraph_below():
    src = "-\nplain paragraph\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_a_non_empty_quoted_list_item_is_still_continued_lazily():
    """The other direction: an item with text does hold a paragraph to continue."""
    src = "> - item text\ncontinues\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> - item text continues\n"


def test_tab_indented_nested_list_is_not_flattened():
    """A tab-indented child list is an ordinary nested list, not prose.

    `LIST_RE` matched space indentation only, so both children read as
    continuations of the parent item and `--fix` flattened three list items into
    one. Regression for round-2 finding F012 on PR #226.
    """
    src = "- parent\n\t- child one\n\t- child two\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_a_tab_indented_wrapped_child_item_is_still_joined():
    src = "- parent\n\t- child that is hard\n\t  wrapped\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- parent\n\t- child that is hard wrapped\n"


# --------------------------------------------------------------------------
# Frontmatter vs a leading thematic break
# --------------------------------------------------------------------------


def test_unclosed_leading_rule_is_not_frontmatter():
    """`---` with no closing `---` is a thematic break, not frontmatter.

    Treating it as unterminated frontmatter disabled the gate for the whole
    file. Regression for round-1 finding F005 on PR #226.
    """
    src = "---\nHard wrapped\nparagraph.\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "---\nHard wrapped paragraph.\n"


def test_closed_frontmatter_is_still_skipped_and_the_body_still_checked():
    src = "---\nname: a-skill\ndescription: two\n  wrapped looking lines\n---\n\nBody that is hard\nwrapped.\n"
    assert kinds(src) == ["split-block"]
    assert (
        fixed(src)
        == "---\nname: a-skill\ndescription: two\n  wrapped looking lines\n---\n\nBody that is hard wrapped.\n"
    )


# --------------------------------------------------------------------------
# Idempotence and safety
# --------------------------------------------------------------------------


def test_compliant_file_is_byte_identical():
    src = (
        "# Title\n\nOne soft-wrapped paragraph on a single physical line.\n\n"
        "- one item\n- another item\n\n| a | b |\n|---|---|\n| c | d |\n\n---\n\nEnd.\n"
    )
    assert kinds(src) == []
    assert fixed(src) == src


def test_fix_is_idempotent():
    src = "A paragraph hard\nwrapped here.\n\n- item that\n  wrapped\n"
    once = fixed(src)
    assert kinds(once) == []
    assert fixed(once) == once


def test_trailing_newline_state_is_preserved():
    assert fixed("a\nb") == "a b"
    assert fixed("a\nb\n") == "a b\n"


def test_repair_selects_which_classes_are_written_out():
    """Both classes are always reported; `repair` only picks what is rewritten."""
    src = "A paragraph hard\nwrapped.\n\nClosing prose.\n---\n\nEnd.\n"
    assert kinds(src) == ["split-block", "setext-rule"]
    joined = mdwrap.analyse(src, repair=(mdwrap.SPLIT_BLOCK,))[1]
    assert joined == "A paragraph hard wrapped.\n\nClosing prose.\n---\n\nEnd.\n"
    ruled = mdwrap.analyse(src, repair=(mdwrap.SETEXT_RULE,))[1]
    assert ruled == "A paragraph hard\nwrapped.\n\nClosing prose.\n\n---\n\nEnd.\n"


# --------------------------------------------------------------------------
# The --fix safety net
#
# `--check` must keep working with no third-party package installed; `--fix`
# must never write a rewrite that changes what the file renders to.
# --------------------------------------------------------------------------


def test_the_checker_imports_only_the_standard_library():
    """CI runs `--check` on a bare setup-python that installs nothing.

    markdown-it-py is imported inside `load_renderer()`, on the `--fix` path
    only, and this pins that: a new module-level import of a third-party package
    would turn every CI run red instead of failing here.
    """
    import ast

    source = (REPO_ROOT / "scripts" / "check_md_wrap.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in tree.body:  # module level only — nested imports are the escape hatch
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names), sorted(imported - set(sys.stdlib_module_names))


def test_canonical_html_collapses_whitespace_only_outside_verbatim_elements():
    assert mdwrap.canonical_html("<p>a\nb</p>") == mdwrap.canonical_html("<p>a b</p>")
    assert mdwrap.canonical_html("<pre>a\nb</pre>") != mdwrap.canonical_html("<pre>a b</pre>")


def _renderer():
    pytest.importorskip("markdown_it", reason="--fix's safety net needs markdown-it-py")
    return mdwrap.load_renderer()


def test_an_ordinary_reflow_passes_the_safety_net():
    renderer = _renderer()
    src = "A paragraph hard\nwrapped.\n\n- item that\n  wrapped\n"
    assert mdwrap.unsafe_fix_reason(src, fixed(src), renderer) is None


def test_the_class_b_repair_passes_the_safety_net():
    """It changes the rendering on purpose, so it is checked structurally instead."""
    renderer = _renderer()
    src = "Some closing prose.\n---\n\nNext section.\n"
    assert mdwrap.unsafe_fix_reason(src, fixed(src), renderer) is None


def test_a_rewrite_that_would_change_rendering_is_refused():
    """Indented backticks under a paragraph are one code span; joining rewrites it.

    The engine reports these lines — correctly, they are a hard-wrapped
    paragraph — but the whitespace-only rejoin does not survive rendering, so
    the file must not be written.
    """
    renderer = _renderer()
    src = "para\n    ```\n    code\n    ```\nafter\n"
    assert kinds(src)
    assert mdwrap.unsafe_fix_reason(src, fixed(src), renderer) == (
        "rejoining its split blocks would change the rendered output"
    )


def test_fix_writes_a_safe_rewrite_and_refuses_an_unsafe_one(tmp_path, monkeypatch, capsys):
    _renderer()
    safe = tmp_path / "safe.md"
    safe.write_text("A paragraph hard\nwrapped.\n", encoding="utf-8")
    unsafe = tmp_path / "unsafe.md"
    unsafe.write_text("para\n    ```\n    code\n    ```\nafter\n", encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)

    code = mdwrap.main(["--fix", "--files", "safe.md", "unsafe.md"])

    assert code == 1, "a refusal is a failure, not a silent skip"
    assert safe.read_text(encoding="utf-8") == "A paragraph hard wrapped.\n"
    assert unsafe.read_text(encoding="utf-8") == "para\n    ```\n    code\n    ```\nafter\n"
    out = capsys.readouterr()
    assert "unsafe.md: REFUSED" in out.out
    assert "1 file(s) refused" in out.err


def test_fix_refuses_to_run_at_all_without_the_renderer(tmp_path, monkeypatch, capsys):
    """Fail closed: no verifier, no rewrite. A warning in a log is not a safety net."""
    target = tmp_path / "a.md"
    target.write_text("A paragraph hard\nwrapped.\n", encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(mdwrap, "load_renderer", lambda: None)

    assert mdwrap.main(["--fix", "--files", "a.md"]) == 2
    assert target.read_text(encoding="utf-8") == "A paragraph hard\nwrapped.\n"
    assert "markdown-it-py" in capsys.readouterr().err


def test_check_still_runs_without_the_renderer(tmp_path, monkeypatch, capsys):
    target = tmp_path / "a.md"
    target.write_text("A paragraph hard\nwrapped.\n", encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(mdwrap, "load_renderer", lambda: None)

    assert mdwrap.main(["--files", "a.md"]) == 1
    assert "split-block" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Path scoping
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,pattern,expected",
    [
        ("docs/adr/0024-x.md", "docs/*.md", False),  # `*` must not cross `/`
        ("docs/readme.md", "docs/*.md", True),
        ("docs/adr/0024-x.md", "docs/adr/*.md", True),
        (".claude/skills/a/SKILL.md", ".claude/skills/**/*.md", True),
        (".kca/skills/a/SKILL.md", ".kca/skills/**/*.md", True),
        (".agents/README.md", ".agents/**/*.md", True),
        ("CLAUDE.md", "CLAUDE.md", True),
    ],
)
def test_glob_match_segments(path, pattern, expected):
    assert mdwrap.glob_match(path, pattern) is expected


@pytest.mark.parametrize(
    "path",
    ["worklogs/orbit5.md", "logs/M9.md", "competitions/nvidia-nemotron/external/writeup.md"],
)
def test_exempt_paths_are_skipped(path):
    assert mdwrap.is_exempt(path) is not None


@pytest.mark.parametrize("path", ["CLAUDE.md", "docs/adr/0024-x.md", ".claude/agents/a.md"])
def test_non_exempt_paths_are_checked(path):
    assert mdwrap.is_exempt(path) is None


def test_allowlist_covers_the_agent_context_files():
    paths = mdwrap.select_allowlist()
    assert "CLAUDE.md" in paths
    assert "AGENTS.md" in paths
    assert any(p.startswith("docs/adr/") for p in paths), "ADRs stay in the allowlist (owner decision, issue #210)"
    assert any(p.startswith(".claude/skills/") for p in paths)
    assert not any(mdwrap.is_exempt(p) for p in paths)


# --------------------------------------------------------------------------
# Structural equivalence
# --------------------------------------------------------------------------


def test_equivalence_holds_across_a_reflow():
    before = "# T\n\nA paragraph hard\nwrapped over lines.\n\n- item one\n- item two\n"
    assert mdwrap.compare_structure(before, fixed(before)) == []


def test_equivalence_detects_a_word_change():
    before = "A paragraph here.\n"
    after = "A paragraph there.\n"
    assert "prose text changed (not a whitespace-only edit)" in mdwrap.compare_structure(before, after)


def test_equivalence_detects_a_dropped_link():
    before = "See [docs](https://example.com/a) and [more](https://example.com/b).\n"
    after = "See [docs](https://example.com/a) and more.\n"
    assert mdwrap.compare_structure(before, after)


def test_equivalence_allows_a_repaired_table():
    """Rejoining a split row repairs a table that was malformed before."""
    before = "| a | b |\n|---|---|\n| a long cell that\nkept going | d |\n"
    assert mdwrap.compare_structure(before, fixed(before)) == []


# Round-1 finding F007 on PR #226: `--equivalence` passed all three of these.


def test_equivalence_detects_lost_list_nesting():
    before = "- outer\n  - inner one\n  - inner two\n"
    after = "- outer\n- inner one\n- inner two\n"
    assert "list nesting changed" in mdwrap.compare_structure(before, after)


def test_equivalence_detects_a_paragraph_becoming_a_setext_heading():
    before = "Some closing prose.\n\n---\n\nNext section.\n"
    after = "Some closing prose.\n---\n\nNext section.\n"
    assert any("setext heading" in d for d in mdwrap.compare_structure(before, after))


def test_equivalence_allows_the_class_b_repair():
    """The reverse direction — removing a setext heading — is what `--fix` does."""
    before = "Some closing prose.\n---\n\nNext section.\n"
    assert mdwrap.compare_structure(before, fixed(before)) == []


def test_equivalence_detects_a_flattened_pipe_less_table():
    before = "a | b\n--- | ---\nc | d\n"
    after = "a | b --- | --- c | d\n"
    assert any("table dimensions changed" in d for d in mdwrap.compare_structure(before, after))


def test_equivalence_holds_across_a_pipe_less_table_reflow():
    before = "Prose that is hard\nwrapped.\n\na | b\n--- | ---\nc | d\n"
    assert mdwrap.compare_structure(before, fixed(before)) == []


# Round-2 finding F007: `--equivalence` passed corruption of its own. The sound
# check is now the renderer; these close the two structural holes that were
# cheap to close.


def test_equivalence_detects_a_table_that_vanished_entirely():
    """An empty table set is vacuously well-formed, so the count has to match too."""
    before = "| a | b |\n|---|---|\n| c |\n"
    after = "a b --- --- c\n"
    assert any("table dimensions changed" in d for d in mdwrap.compare_structure(before, after))


def test_equivalence_detects_a_deleted_hard_break():
    before = "intro line\nvalue: `x`  \nnext line\n"
    after = "intro line value: `x` next line\n"
    assert "authored hard breaks changed: 1 -> 0" in mdwrap.compare_structure(before, after)


def test_equivalence_allows_a_reflow_that_carries_the_hard_break_along():
    before = "intro line\nvalue: `x`  \nnext line\n"
    assert mdwrap.compare_structure(before, fixed(before)) == []
