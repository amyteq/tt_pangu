"""Unit tests for the ADR-0024 soft-wrap gate (`scripts/check_md_wrap.py`).

The gate's contract is narrow and worth pinning precisely: it finds exactly two
violation classes, it never looks inside a block where line breaks are semantic,
and it reports without ever writing.

Most assertions here come in pairs — which lines were flagged, and what the
document looks like with every flagged line rejoined. The second is `fixed()`
below: a test oracle rather than shipped behaviour, because a joined document
says which line continues which block far more legibly than a list of line
numbers can.
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
    return [v.kind for v in mdwrap.analyse(text)]


def fixed(text: str) -> str:
    """Rejoin every split block, and give every `---` the blank line it is missing.

    This is the tests' oracle, not a feature: the gate reports and writes
    nothing (issue #237). It reads the same `scan()` the gate does, so what it
    produces is exactly the engine's own opinion of where each block begins and
    which container holds it — stated as a document a reader can check.
    """
    had_newline = text.endswith("\n")
    lines = text[:-1].split("\n") if had_newline else text.split("\n")
    out: list[str] = []
    for line in mdwrap.scan(lines):
        if line.role == mdwrap.SPLIT:
            out[-1] = out[-1].rstrip() + " " + line.tail
            continue
        if line.role == mdwrap.SETEXT_H2:
            out.append(line.raw[: len(line.raw) - len(line.content)])
        out.append(line.raw)
    return "\n".join(out) + ("\n" if had_newline else "")


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


def test_github_alert_marker_does_not_join_its_body():
    """GitHub only reads the callout when the type marker stands alone on its line.

    Joining `> [!NOTE]` onto the line below it renders as an ordinary blockquote
    containing the literal text `[!NOTE]`. No renderer available here implements
    the extension, so the `--fix` safety net cannot see that; the marker is
    exempted in the engine instead.
    """
    for kind in ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"):
        src = f"> [!{kind}]\n> Useful information.\n"
        assert kinds(src) == []
        assert fixed(src) == src
    lower = "> [!note]\n> Useful information.\n"
    assert kinds(lower) == []
    assert fixed(lower) == lower


def test_github_alert_body_is_still_rejoined():
    """Only the marker line is exempt — a hard-wrapped body is an ordinary split."""
    src = "> [!NOTE]\n> First half\n> second half\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "> [!NOTE]\n> First half second half\n"


def test_github_alert_marker_is_exempt_at_any_depth_and_inside_a_list():
    for src in (
        ">> [!WARNING]\n>> Nested in a second quote.\n",
        "- an item\n\n  > [!TIP]\n  > Alerts nest inside list items.\n",
        # Four columns into an item, past `QUOTE_RE`'s reach: `split_quote`
        # reports depth 0 and the `>` stays in the content, so the exemption
        # has to read the quote off the line itself.
        "1.  an item\n\n    > [!TIP]\n    > Still an alert.\n",
    ):
        assert kinds(src) == []
        assert fixed(src) == src


def test_a_bare_alert_marker_outside_a_blockquote_is_prose():
    """GitHub reads the callout only inside a blockquote; alone it is plain text."""
    src = "[!NOTE]\nBody.\n"
    assert kinds(src) == ["split-block"]
    assert fixed(src) == "[!NOTE] Body.\n"


def test_a_line_that_only_looks_like_an_alert_marker_still_joins():
    """The match is deliberately narrow: only the five documented types, alone."""
    for src, joined in (
        ("> [!NOPE]\n> body\n", "> [!NOPE] body\n"),
        ("> [!NOTE] already inline\n> body\n", "> [!NOTE] already inline body\n"),
        ("> [!note] extra words\n> body\n", "> [!note] extra words body\n"),
    ):
        assert kinds(src) == ["split-block"]
        assert fixed(src) == joined


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


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("- > Some text\n  > ---\n", "- > Some text\n  > \n  > ---\n"),
        ("1. > Some text\n   > ---\n", "1. > Some text\n   > \n   > ---\n"),
        ("- > - Some text\n  >   ---\n", "- > - Some text\n  > \n  >   ---\n"),
        ("> - > Some text\n>   > ---\n", "> - > Some text\n>   > \n>   > ---\n"),
    ],
    ids=["list-quote", "ordered-quote", "list-quote-list", "quote-list-quote"],
)
def test_the_inserted_blank_line_keeps_the_rules_own_container(src, want):
    """A quote inside a list needs the list's indentation on the blank line too.

    Synthesising the prefix as one `> ` per quote level rebuilt the quotes and
    dropped the list: the blank line landed at the margin, which closed the item,
    and the thematic break below it rendered in a new top-level blockquote after
    the list. Copying the prefix the `---` already carries cannot do that.
    Regression for round-7 finding F028 on PR #226.
    """
    assert kinds(src) == ["setext-rule"]
    assert fixed(src) == want


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("Some text\n---\n", "Some text\n\n---\n"),
        ("> Some text\n> ---\n", "> Some text\n> \n> ---\n"),
        ("- Some text\n  ---\n", "- Some text\n\n  ---\n"),
    ],
    ids=["top-level", "quote", "list"],
)
def test_the_plain_containers_still_get_the_blank_line_they_always_did(src, want):
    """The three shapes the prefix change must leave exactly as they were."""
    assert kinds(src) == ["setext-rule"]
    assert fixed(src) == want


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
def test_prose_below_a_closed_container_is_ordinary_prose(src):
    """A fence, a comment or a table ends with the container holding it.

    When a second reader of the file kept its own fence state it ran an
    unclosed fence to the end of the document, so the prose below the
    blockquote that had already closed it was read as more code and its wrap
    went unreported. One scan now answers for both. Regression for round-4
    finding F016 on PR #226; the last shape guards the table path.
    """
    assert kinds(src) == ["split-block"]


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
        "- - ```\n    code one\n    code two\n    ```\n",  # item holds item holds fence
        "- - <!--\n    comment one\n    comment two\n    -->\n",
        "1. - <div>\n     raw one\n     raw two\n     </div>\n",
        "- > - ```\n  >   code one\n  >   code two\n  >   ```\n",  # all three orders at once
        "> - ```\n>   code one\n>   code two\n>   ```\n",  # the reverse nesting, as a guard
    ],
)
def test_a_block_inside_nested_containers_on_one_line_is_never_inspected(src):
    """Composed containers have to be peeled in the order they were written.

    `> - x` is a quote holding an item and `- > x` an item holding a quote, and
    the engine only understood the first: it stripped every quote marker, looked
    for one list marker behind them and then measured indentation, so a
    continuation line of any other order read as unindented prose and the exempt
    block it belongs to ended on its opening line. Both renderers agree on all
    eight shapes. Regression for round-5 finding F021 on PR #226 — the quote
    cases are the ones it named, the doubly-nested items are the same defect in
    the list direction, and the last case is the direction that already worked.
    """
    assert kinds(src) == []
    assert fixed(src) == src


@pytest.mark.parametrize(
    "src",
    [
        "-\t <!--\n     raw one\n     raw two\n     -->\n",  # tab then space: four columns of padding
        "-\t <div>\n     raw one\n     raw two\n     </div>\n",
        "-\t <pre>\n     raw one\n     raw two\n     </pre>\n",
        "-\t ```\n     code one\n     code two\n     ```\n",  # a fence measures the same padding
        " -\t <!--\n     raw one\n     raw two\n     -->\n",  # an indented marker starts its tab later
        "1.\t  <!--\n      raw one\n      raw two\n      -->\n",  # a two-column marker too
        "10.\t <!--\n     raw one\n     raw two\n     -->\n",
        "> -\t <!--\n>      raw one\n>      raw two\n>      -->\n",  # and inside a quote
    ],
)
def test_a_block_on_a_tab_padded_marker_line_is_never_inspected(src):
    """A tab's advance starts at the marker, not at the margin.

    `-\\t ` is four columns of padding — the tab reaches column four from the
    marker's column one, and the space makes five — which is the one-to-four
    CommonMark allows, so the item's content starts at column five and the block
    indented there is the item's own. Measuring that padding from the margin
    called it five, took the over-wide branch that puts the content column two
    columns in, and every line of the block then read as outdented from the item:
    `--check` reported exempt content and `--fix` folded it. Both renderers put
    the block inside the item. Regression for round-6 finding F023 on PR #226.
    """
    assert kinds(src) == []
    assert fixed(src) == src


def test_a_block_outdented_from_a_tab_padded_item_is_never_inspected():
    """The same mismeasurement, reached from the other side — F020's failure mode.

    With the content column two instead of five, an HTML block at column two
    looked like it was still inside the item, so `html_block_end` was handed
    stale item state and ended the block at the first line below it. cmark-gfm
    closes the list on the block's opening line and makes it top-level.
    """
    src = "-\t item\n  <!--\nraw one\nraw two\n-->\n"
    assert kinds(src) == []
    assert fixed(src) == src


@pytest.mark.parametrize(
    "src,want",
    [
        ("-\t item one\n     item one continued\n", "-\t item one item one continued\n"),
        ("1.\t  item one\n      item one continued\n", "1.\t  item one item one continued\n"),
    ],
)
def test_a_wrapped_tab_padded_item_is_still_joined(src, want):
    """The other direction: a deeper content column must not hide a real violation."""
    assert kinds(src) == ["split-block"]
    assert fixed(src) == want


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


def test_a_document_with_every_violation_repaired_reports_nothing():
    """What the gate asks for is reachable: rejoin the reported lines and it goes quiet."""
    src = "A paragraph hard\nwrapped here.\n\n- item that\n  wrapped\n"
    once = fixed(src)
    assert kinds(once) == []
    assert fixed(once) == once


def test_trailing_newline_state_is_preserved():
    assert fixed("a\nb") == "a b"
    assert fixed("a\nb\n") == "a b\n"


def test_both_classes_are_reported_from_one_document():
    """Each violation is reported once, in line order, whatever class it is."""
    src = "A paragraph hard\nwrapped.\n\nClosing prose.\n---\n\nEnd.\n"
    assert [(v.line, v.kind) for v in mdwrap.analyse(src)] == [(2, "split-block"), (5, "setext-rule")]


# --------------------------------------------------------------------------
# The command line
#
# It must keep working with no third-party package installed, and it must never
# write to the files it checks.
# --------------------------------------------------------------------------


def test_the_checker_imports_only_the_standard_library():
    """CI runs this on a bare setup-python that installs nothing.

    Nothing outside the standard library is imported anywhere now — the one
    third-party import this file ever had was the renderer that verified
    `--fix`, and that went with it (issue #237). A new module-level import of a
    third-party package would turn every CI run red instead of failing here.
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


def test_check_reports_and_leaves_the_file_alone(tmp_path, monkeypatch, capsys):
    """The gate's whole contract: a located message, a non-zero exit, an untouched file."""
    target = tmp_path / "a.md"
    original = "A paragraph hard\nwrapped.\n"
    target.write_text(original, encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)

    assert mdwrap.main(["--files", "a.md"]) == 1
    assert target.read_text(encoding="utf-8") == original, "a gate never edits the file it checks"
    out = capsys.readouterr()
    assert "a.md:2: split-block" in out.out
    assert "1 violation(s)" in out.err


def test_a_compliant_file_exits_zero(tmp_path, monkeypatch, capsys):
    target = tmp_path / "a.md"
    target.write_text("One line, left for the renderer to wrap.\n", encoding="utf-8")
    monkeypatch.setattr(mdwrap, "repo_root", lambda: tmp_path)

    assert mdwrap.main(["--files", "a.md"]) == 0
    assert "No violations." in capsys.readouterr().err


def test_nothing_on_the_command_line_can_ask_it_to_rewrite_a_file():
    """There is no `--fix`, and that is the contract rather than an omission.

    Keeping a rewrite of someone's prose honest needed a renderer, a structural
    fingerprint and an HTML/CSS reader to know when the rendering could be
    trusted — most of the file, and the home of nearly every defect the review
    of PR #226 turned up. A checker that cannot write cannot corrupt (#237).
    """
    with pytest.raises(SystemExit) as raised:
        mdwrap.build_parser().parse_args(["--fix", "--files", "a.md"])
    assert raised.value.code == 2
    assert not hasattr(mdwrap, "write_atomically")
    assert not hasattr(mdwrap, "load_renderer")


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
