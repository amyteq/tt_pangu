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
    """The one shape markdown-it and cmark-gfm disagree on, and the gate leaves it alone.

    markdown-it reads `# a | b` over a delimiter as a two-column table;
    cmark-gfm, which GitHub renders with, reads a heading plus a paragraph.
    Rejecting the table left the delimiter and data rows to be joined as prose,
    which destroyed the table under markdown-it — and the verifier is
    markdown-it, so nothing would have caught it. Doing nothing costs at most a
    missed finding under cmark-gfm's reading. Regression for round-2 finding
    F001; ADR-0024 records the oracle choice, round-3 F001.
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


def test_bare_table_ends_with_the_list_item_holding_it():
    """A table cannot outlive its container any more than a fence can.

    Quote depth was tracked for a pipe-less table but list indentation was not,
    so top-level prose below the list was still read as more rows and its wrap
    went unreported. Regression for round-4 finding F019 on PR #226.
    """
    src = "- item\n\n  a | b\n  --- | ---\nafter one\nafter two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- item\n\n  a | b\n  --- | ---\nafter one after two\n"
    assert mdwrap.structure(src)["tables"] == [(2, 2)]


def test_a_bare_table_inside_a_list_item_still_runs_to_its_own_end():
    """The other direction: rows indented into the item are still that table's rows."""
    src = "- item\n\n  a | b\n  --- | ---\n  c | d\n"
    assert kinds(src) == []
    assert fixed(src) == src


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


def test_setext_h1_underline_is_valid_markdown_not_a_split_block():
    """`===` under a paragraph is an unambiguous setext H1, and this gate has no
    heading-style opinions.

    Reporting it offered `Title ===` as the repair, which destroys the heading;
    the renderer refused that rewrite, so the finding was an unfixable red build.
    Regression for round-3 finding F013 on PR #226.
    """
    for src in ("Title\n===\n", "Some Title\n=========\n\nBody text.\n"):
        assert kinds(src) == []
        assert fixed(src) == src


def test_a_hard_wrapped_setext_h1_is_still_joined():
    """The other direction: the heading's own text may be split, and that is a violation."""
    src = "A heading split\nover two lines\n===\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "A heading split over two lines\n===\n"


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


def test_a_fence_on_the_list_marker_line_is_the_items_code_block():
    """`- ``` ` opens the item's fenced block right there, on the marker line.

    Reading it as an item whose text is ``` made every code line the item's own
    text, so `--fix` flattened the block into it. Part of round-3 finding F002
    on PR #226.
    """
    src = "- ```\n  code one\n  code two\n  ```\n- next item\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_a_top_level_fence_still_spans_a_blank_line():
    """The guard for the container rules below: nothing closes a top-level fence but its closer."""
    src = "```\ncode one\n\ncode two\n```\n\nprose hard\nwrapped\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "```\ncode one\n\ncode two\n```\n\nprose hard wrapped\n"


def test_an_unclosed_fence_in_a_blockquote_ends_with_the_blockquote():
    """A fenced block cannot outlive its container, and the gate resumes below it.

    Tracking the fence without its quote depth let one unclosed inside a
    blockquote hide every line of the file below it. Regression for round-3
    finding F002 on PR #226.
    """
    src = "> ```\n> code\n\npara one\npara two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> ```\n> code\n\npara one para two\n"


def test_an_unclosed_fence_in_a_list_item_ends_with_the_item():
    """The same for a list item: a non-blank line below its content column leaves it."""
    src = "10. item\n    ```\n    code\n\npara one\npara two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "10. item\n    ```\n    code\n\npara one para two\n"


@pytest.mark.parametrize(
    "src",
    [
        "> ```\n> code\n\nafter one\nafter two\n",  # a fence leaving a blockquote
        "- item\n  ```\n  code\n\nafter one\nafter two\n",  # leaving a bullet item
        "1. item\n   ```\n   code\n\nafter one\nafter two\n",  # leaving an ordered item
        "1. item\n   ~~~\n   code\n\nafter one\nafter two\n",  # a tilde fence too
        "<!--\n```\n-->\n\nafter one\nafter two\n",  # fence-looking text inside a comment
        "> a | b\n> --- | ---\n\nafter one\nafter two\n",  # a bare table leaving a quote
    ],
)
def test_a_repair_below_a_closed_container_is_reported_and_accepted(src):
    """Finding the violation is only half of it; the safety net has to allow the repair.

    `analyse` learned that a fence ends with its container while `structure` did
    not, so the prose below one still counted as fenced code and the correct,
    rendering-preserving rewrite was refused as `fenced code content changed`.
    Both readings now come from one scan. Regression for round-4 finding F016 on
    PR #226; the last shape was already accepted and guards the table path.
    """
    renderer = _renderer()
    assert kinds(src) == ["split-block"]
    assert mdwrap.unsafe_fix_reason(src, fixed(src), renderer) is None


def test_the_equivalence_heuristic_ends_a_fence_where_the_engine_does():
    """The shared scan, asserted directly: `code` stops at the blockquote's end."""
    assert mdwrap.structure("> ```\n> code\n\nafter one\nafter two\n")["code"] == "code"


def test_the_equivalence_heuristic_reads_no_fence_inside_a_comment():
    """An HTML block is opaque to both readings, so the backticks in it open nothing."""
    assert mdwrap.structure("<!--\n```\n-->\n\nafter one\nafter two\n")["code"] == ""


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


def test_a_lowercase_declaration_is_prose_not_an_html_block():
    """CommonMark type 4 needs an uppercase letter after `<!`, and both renderers agree.

    Accepting `<!foo` opened a block that waits for a `>`; without one the whole
    rest of the file was skipped. Regression for round-3 finding F003 on PR #226.
    """
    src = "<!foo\n\npara one\npara two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "<!foo\n\npara one para two\n"


def test_an_uppercase_declaration_is_still_an_html_block():
    """The other direction: `<!DOCTYPE html>` is a real declaration block."""
    src = "<!DOCTYPE html>\n\nProse.\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_an_unclosed_html_block_in_a_blockquote_ends_with_the_blockquote():
    """An HTML block cannot outlive its container either.

    An unterminated `<pre>` inside a quote consumed every line below it, because
    the block's own quote depth was not tracked. Regression for round-3 finding
    F003 on PR #226.
    """
    src = "> <pre>\n> x\n\npara one\npara two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> <pre>\n> x\n\npara one para two\n"


@pytest.mark.parametrize(
    "src",
    [
        "- <!--\n  comment one\n  comment two\n  -->\n",  # type 2, runs to its own terminator
        "- <div>\n  raw one\n  raw two\n  </div>\n",  # type 6, runs to a blank line
        "- <pre>\n  raw one\n  raw two\n  </pre>\n",  # type 1, raw text
        "* <![CDATA[\n  one\n  two\n  ]]>\n",  # type 5
        "1. <!--\n   comment one\n   comment two\n   -->\n",  # an ordered marker too
        "> - <!--\n>   comment one\n>   comment two\n>   -->\n",  # and inside a quote
    ],
)
def test_an_html_block_opening_on_a_list_marker_line_is_never_inspected(src):
    """`- <!--` opens the item's HTML block, not an item whose text is `<!--`.

    Both cmark-gfm and markdown-it put the whole block inside the item. Reading
    the marker line as text made every line below it the item's own prose, so
    `--check` reported content ADR-0024 exempts and `--fix` folded the comment
    onto one line. Regression for round-4 finding F017 on PR #226.
    """
    assert kinds(src) == []
    assert fixed(src) == src


def test_an_html_block_in_a_list_item_still_ends_with_the_item():
    """The other direction: the block stops at the item's content column.

    Without the container exit an unterminated one inside an item would hide
    every line below it, which is the F003 defect one container in.
    """
    src = "- <!--\n  comment\n\npara one\npara two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- <!--\n  comment\n\npara one para two\n"


def test_a_list_item_whose_text_merely_starts_with_a_tag_is_still_joined():
    """`- <b>bold</b> and more` is an item holding text, not an HTML block.

    A complete tag on a line with text after it satisfies no start condition, so
    the item wraps like any other and its continuation is a violation.
    """
    src = "- <b>bold</b> and more\n  text continuing\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- <b>bold</b> and more text continuing\n"


@pytest.mark.parametrize(
    "src",
    [
        "- item\n<!--\nraw one\nraw two\n-->\n",  # type 2, runs to its own terminator
        "- item\n<div>\nraw one\nraw two\n</div>\n",  # type 6, runs to a blank line
        "- item\n<pre>\nraw one\nraw two\n</pre>\n",  # type 1, raw text
        "1. item\n<!--\nraw one\nraw two\n-->\n",  # an ordered marker too
    ],
)
def test_an_html_block_outdented_from_a_list_is_never_inspected(src):
    """A block at the margin below a list item belongs to the document, not the item.

    Both cmark-gfm and markdown-it close the list on the opening line and make
    the block top-level. The engine kept handing it the item's content column, so
    `html_block_end` found the very next line "outdented from the item" and ended
    the block after one line — everything below it was reported and folded as
    prose. Only a paragraph continues lazily across a missing container prefix;
    a block opener does not. Regression for round-5 finding F020 on PR #226.
    """
    assert kinds(src) == []
    assert fixed(src) == src


@pytest.mark.parametrize(
    "src",
    [
        "- > <!--\n  > comment one\n  > comment two\n  > -->\n",  # item holds quote holds comment
        "- > ```\n  > code one\n  > code two\n  > ```\n",  # and a fence
        "- > quoted text\n  >\n  >     code one\n  >     code two\n",  # and indented code
        "> - ```\n>   code one\n>   code two\n>   ```\n",  # the reverse nesting, as a guard
    ],
)
def test_a_block_inside_a_quote_inside_a_list_item_is_never_inspected(src):
    """Composed containers have to be peeled in the order they were written.

    `> - x` is a quote holding an item and `- > x` an item holding a quote, and
    the engine only understood the first: it stripped every quote marker and then
    measured indentation, so a continuation line of the second read as unindented
    prose and the exempt block it belongs to ended on its opening line. Both
    renderers agree on all four shapes. Regression for round-5 finding F021 on
    PR #226; the last case is the direction that already worked.
    """
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


def test_link_reference_definition_title_may_span_physical_lines():
    """A title runs to its closing delimiter, however many lines that takes.

    Stopping at the first line made `continued"` the head of a paragraph, so the
    prose below it was reported and joined onto invisible metadata — and the
    renderer then refused the rewrite, leaving a red build with no repair.
    Regression for round-3 finding F004 on PR #226.
    """
    src = '[foo]: /url "title\ncontinued"\npara one\npara two\n'
    assert kinds(src) == ["split-block"]
    assert fixed(src) == '[foo]: /url "title\ncontinued"\npara one para two\n'


def test_a_title_that_does_not_parse_leaves_the_line_as_prose():
    """`[foo]: /url "title" ok` is a paragraph to CommonMark, junk and all."""
    src = '[foo]: /url "title" ok\nnext line\n'
    assert kinds(src) == ["split-block"]
    assert fixed(src) == '[foo]: /url "title" ok next line\n'


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


@pytest.mark.parametrize(
    "item",
    ["<!-- c -->", "```", "---", "# h", ">"],
    ids=["html-comment", "fence", "thematic-break", "heading", "empty-nested-quote"],
)
def test_a_quoted_list_item_holding_no_paragraph_does_not_swallow_the_line_below(item):
    """Lazy continuation continues a paragraph, and none of these items holds one.

    An item is not continuable just because it is non-empty: a comment, a fence,
    a break, a heading and an empty nested quote are all complete on their line.
    Joining the unquoted paragraph below onto one moved it into the blockquote,
    the renderer refused the rewrite, and CI went red with nothing `--fix` could
    do. Regression for round-3 finding F006 on PR #226.
    """
    src = f"> - {item}\nplain paragraph\n"
    assert kinds(src) == []
    assert fixed(src) == src


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


def test_a_tab_indented_marker_cannot_interrupt_a_paragraph():
    """A tab is four columns, and an indented code block cannot interrupt a paragraph.

    So this renders as one wrapped paragraph — but accepting the marker as a
    block start made the gate skip it. Regression for round-3 finding F012 on
    PR #226.
    """
    src = "paragraph\n\t- continuation\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "paragraph - continuation\n"


def test_a_marker_four_columns_past_the_item_content_is_text_not_a_nested_list():
    """`- a` puts its content at column 2, so column 6 is inside its code range."""
    src = "- item\n      - deep\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "- item - deep\n"


def test_a_paragraph_inside_a_list_item_is_not_indented_code():
    """`10. item` puts its own blocks at column 4, so column 4 is prose, not code.

    Measuring the four-column code indent from the margin instead of the item's
    content column let a hard-wrapped paragraph inside an item through the gate
    entirely. Regression for round-3 finding F014 on PR #226.
    """
    src = "10. item\n\n    para one\n    para two\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "10. item\n\n    para one para two\n"


def test_a_real_code_block_inside_a_list_item_is_still_never_inspected():
    """The other direction: four columns past the content column really is code."""
    src = "10. item\n\n        code one\n        code two\n"
    assert kinds(src) == []
    assert fixed(src) == src


def test_the_equivalence_heuristic_counts_the_items_the_engine_does():
    """`structure()` is the second opinion, and it has to agree on what a list item is.

    Counting an over-indented marker as an item made `compare_structure` report
    `list-item count changed` for a rewrite the renderer accepts, so `--fix`
    refused a file it should have rewritten. `docs/tasks/m12/M12-T006-end-to-end-local.md`
    is the live instance, found by rendering all 788 tracked files.
    """
    src = "4. step\n\n   d. sub-step\n        - not a marker at this depth\n"
    assert mdwrap.structure(src)["list_items"] == 1
    assert mdwrap.compare_structure(src, fixed(src)) == []


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


def test_a_white_space_css_declaration_refuses_the_rewrite():
    """`canonical_html` collapses whitespace a `white-space: pre` span preserves.

    Moving the soundness claim onto the renderer did not make it sound: this
    rewrite compared equal and was written, while a browser shows the newline.
    A document the canonicaliser cannot judge is now refused instead. Regression
    for round-3 finding F007 on PR #226.
    """
    renderer = _renderer()
    src = 'before <span style="white-space: pre">a\nb</span> after\n'
    assert kinds(src) == ["split-block"]
    reason = mdwrap.unsafe_fix_reason(src, fixed(src), renderer)
    assert reason is not None and "white-space" in reason


@pytest.mark.parametrize(
    "css",
    [
        "white-space: pre",
        "white-space:pre-wrap",
        "white-space : break-spaces",
        "WHITE-SPACE: PRE-LINE",
        "white-space:/**/pre",  # a comment is a token separator, so this is the declaration
        "white-space/**/:pre",
        "white-spac\\65:pre",  # and a property name may be escaped
        "white-spac\\65 :pre",
        "white-space-collapse: preserve",  # the longhand preserves breaks too
        "white-space: pre !important",
        "white-space: inherit",  # cannot be classified: the parent is not visible here
        "white-space: var(--x)",
        "white-space: unset",
    ],
)
def test_every_whitespace_preserving_css_value_is_caught(css):
    """Read as CSS, not matched as text. Regression for round-5 finding F022 on PR #226.

    The guard looked in the right places by then — a real `style` attribute, the
    text of a real `<style>` — but still recognised the declaration with a
    pattern anchored on `white-space` followed by a colon. A CSS comment and a
    CSS escape are both legal between those two, so `white-space:/**/pre` slipped
    past and `--fix` joined across a newline a browser shows. The last three
    cases are the conservative half: a value this cannot resolve is refused
    rather than assumed safe.
    """
    assert mdwrap.unverifiable_reason(f"<p style='{css}'>a b</p>") is not None
    assert mdwrap.unverifiable_reason(f"<style>\n.x {{ {css}; }}\n</style>\n<p>a b</p>") is not None


@pytest.mark.parametrize(
    "css",
    [
        "color: red",
        "white-space: normal",
        "white-space: nowrap",
        "white-space: collapse balance",  # the shorthand's other components
        "content: 'white-space:pre'",  # a string is not a declaration
        "white-spac/**/e:pre",  # two idents, so no `white-space` property at all
        "font-family: 'a;b'; color: red",
        "background: url(a;b.png)",
    ],
)
def test_css_that_collapses_whitespace_still_allows_the_repair(css):
    """The other half of F022: refusing everything would be no safer than missing this.

    A refusal costs a contributor a manual fix, so the reader has to keep the
    declarations it can resolve apart from the ones it cannot — including the
    three ways a `;` or a `:` can appear without separating anything.
    """
    assert mdwrap.unverifiable_reason(f"<p style='{css}'>a b</p>") is None
    assert mdwrap.unverifiable_reason(f"<style>\n.x {{ {css}; }}\n</style>\n<p>a b</p>") is None


def test_ordinary_rendered_html_is_verifiable():
    """The other direction: nothing about a plain document is unjudgeable."""
    assert mdwrap.unverifiable_reason("<p>a b</p>\n<pre>code\n</pre>\n") is None


def test_writing_about_white_space_pre_does_not_make_a_file_unfixable():
    """The declaration is CSS only where CSS lives — `style=`, or a `<style>` element.

    ADR-0024 documents this very hazard, so its own rendered output contains the
    string inside a `<code>` span with the quotes escaped. Matching that refused
    `--fix` on the ADR, which is the unfixable-red-build failure mode the guard
    exists to prevent.
    """
    renderer = _renderer()
    src = 'A `<span style="white-space: pre">` span keeps its breaks, as does\n`white-space: pre-wrap`.\n'
    assert kinds(src) == ["split-block"]
    assert mdwrap.unverifiable_reason(renderer.render(src)) is None
    assert mdwrap.unsafe_fix_reason(src, fixed(src), renderer) is None


def test_an_unbalanced_verbatim_element_refuses_the_rewrite():
    """An unclosed `<pre>` preformats everything below it, and a text scan cannot see it.

    A verbatim region needs a closing tag to be found at all, so whitespace a
    browser preserves would be collapsed and compared equal. Part of round-3
    finding F007 on PR #226.
    """
    renderer = _renderer()
    src = "> <pre>\n> x\n\npara one\npara two\n"
    assert kinds(src) == ["split-block"]
    reason = mdwrap.unsafe_fix_reason(src, fixed(src), renderer)
    assert reason is not None and "unbalanced <pre>" in reason


def test_a_self_closing_pre_is_still_unbalanced():
    """A browser ignores the `/` on a non-void element, so `<pre/>` opens a `<pre>`.

    Reading it as a complete empty element balances it and hides the hazard.
    """
    assert mdwrap.unverifiable_reason("<pre/>\n<p>a b</p>\n") is not None


@pytest.mark.parametrize(
    "tag",
    [
        "<span style=white-space:pre>",  # unquoted, the reopened F007 reproduction
        "<span style='white-space: pre'>",
        '<span style = "white-space: pre" >',
        "<span class=x style=white-space:pre-wrap data-y=1>",
    ],
)
def test_a_style_attribute_refuses_the_rewrite_however_it_is_quoted(tag):
    """A valid unquoted attribute value reached the same browser-visible corruption.

    The guard read quoted values only, so `style=white-space:pre` bypassed it and
    `--fix` joined across a newline the reader can see. Widening the pattern is
    not the fix — parsing HTML with a regular expression is why it was wrong —
    so the attribute now comes from `HtmlScan`. Regression for round-4 finding
    F007 on PR #226.
    """
    renderer = _renderer()
    src = f"before {tag}a\nb</span> after\n"
    assert kinds(src) == ["split-block"]
    reason = mdwrap.unsafe_fix_reason(src, fixed(src), renderer)
    assert reason is not None and "white-space" in reason


@pytest.mark.parametrize(
    "html",
    [
        "<!-- mention <pre> -->\n<p>a b</p>\n",  # a comment is not markup
        "<!-- <span style='white-space: pre'> -->\n<p>a b</p>\n",
        '<script>var x = "<pre>";</script>\n<p>a b</p>\n',  # raw-text content is text
        "<textarea><pre></textarea>\n<p>a b</p>\n",
    ],
)
def test_a_verbatim_tag_that_is_not_a_tag_leaves_the_document_verifiable(html):
    """Tag-looking text in a comment or a raw-text element creates no element.

    Counting pattern matches across serialized HTML called these unbalanced and
    refused a repair that both renderers agree is safe — the unfixable-red-build
    failure mode again. Regression for round-4 finding F018 on PR #226.
    """
    assert mdwrap.unverifiable_reason(html) is None


def test_a_comment_mentioning_pre_still_allows_the_repair():
    """The end-to-end shape behind F018: one real finding, and it is repairable."""
    renderer = _renderer()
    src = "<!-- mention <pre> -->\n\nafter one\nafter two\n"
    assert kinds(src) == ["split-block"]
    assert mdwrap.unsafe_fix_reason(src, fixed(src), renderer) is None


def test_a_commented_pre_opens_no_verbatim_region():
    """`canonical_html` had the same flaw: its region pattern matched into a comment.

    A `<pre>` named in a comment and a real `</pre>` later would bracket the
    prose between them, freezing its whitespace and refusing any repair there.
    """
    html = "<!-- <pre> -->\n<p>a\nb</p>\n<pre>x\ny</pre>\n"
    assert mdwrap.canonical_html(html) == mdwrap.canonical_html(html.replace("<p>a\nb</p>", "<p>a b</p>"))
    assert mdwrap.canonical_html(html) != mdwrap.canonical_html(html.replace("<pre>x\ny</pre>", "<pre>x y</pre>"))


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


def test_fix_never_leaves_a_half_written_file(tmp_path, monkeypatch):
    """The rewrite lands whole or not at all.

    `Path.write_text` truncates the target first, so an interruption between the
    truncate and the write left a partially written Markdown file — the one
    outcome this tool must never produce. Regression for round-3 finding F015 on
    PR #226.
    """
    _renderer()
    target = tmp_path / "a.md"
    original = "A paragraph hard\nwrapped.\n"
    target.write_text(original, encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)

    def interrupted(src, dst):
        raise OSError("interrupted between write and rename")

    monkeypatch.setattr(mdwrap.os, "replace", interrupted)

    with pytest.raises(OSError):
        mdwrap.main(["--fix", "--files", "a.md"])

    assert target.read_text(encoding="utf-8") == original, "the original must survive intact"
    assert [p.name for p in tmp_path.iterdir()] == ["a.md"], "no temporary file left behind"


def test_fix_states_the_boundary_of_what_it_verified(tmp_path, monkeypatch, capsys):
    """An unqualified guarantee is worse than a stated limit, so --fix prints the limit."""
    _renderer()
    target = tmp_path / "a.md"
    target.write_text("A paragraph hard\nwrapped.\n", encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)

    assert mdwrap.main(["--fix", "--files", "a.md"]) == 0
    err = capsys.readouterr().err
    assert "markdown-it-py" in err and "cmark-gfm" in err and "ADR-0024" in err


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
