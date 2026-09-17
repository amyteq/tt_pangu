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
