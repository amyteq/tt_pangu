#!/usr/bin/env python3
"""Check Markdown soft wrap (ADR-0024).

ADR-0024 is the whole policy, so this detects exactly two violation classes and
no others — no heading-style, list-marker or line-length opinions:

  split-block   a paragraph, list item or table row whose content continues on
                the next physical line, instead of being one physical line that
                the renderer wraps
  setext-rule   a `---` line with a non-blank line directly above it, which
                CommonMark parses as a setext H2 rather than a thematic break,
                silently rendering the paragraph above as a heading

Line breaks are semantic in some places, so those are never inspected: fenced
code blocks and their contents, YAML frontmatter, indented code blocks, and HTML
blocks. An explicit hard break — a line ending in two or more spaces, or in a
backslash — is authored intent, so the line after it is left alone too, as is
the body line under a GitHub alert marker, which renders as a callout only while
the marker stands alone on its own blockquote line. That is the whole exemption
set: ADR-0024 also exempts a verbatim diff, log excerpt or file listing, which
qualifies by being fenced or indented, because nothing distinguishes bare
verbatim lines from hard-wrapped prose.

This reports and never writes. It began with a `--fix` mode that rejoined split
blocks in place; that mode is gone (issue #237), because keeping a rewrite of
someone's prose honest took more machinery than the gate itself — a renderer, a
structural fingerprint, an HTML and CSS reader to know when the rendering could
be trusted — and every one of those was a way for a checker to damage a file.
A reported violation costs one manual edit, which is the cheaper end of that
trade. What is left is standard-library only, and always will be, because CI
runs it on a bare Python with nothing installed.

The renderer this gate exists for is GitHub's, which is cmark-gfm. Where a
construct is read differently by different CommonMark implementations, the rule
is to leave it alone rather than pick a side, so a disagreement costs a missed
finding and never a false one. ADR-0024 records that choice.

Usage:
  python scripts/check_md_wrap.py --allowlist              # the agent-context set
  python scripts/check_md_wrap.py --changed origin/main    # only what this branch touches
  python scripts/check_md_wrap.py --files a.md b.md        # exactly these

Exactly one scoping mode is required. There is deliberately no "whole
repository" mode: ADR-0024's enforcement is scoped to changed files plus the
allowlist, and the historical backfill was declined (issue #210).

Exit codes:
  0 — no violations
  1 — violations found
  2 — usage error
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Policy data
# --------------------------------------------------------------------------

# Paths ADR-0024's gate does not bind. One line of reason each; keep in sync
# with ADR-0024's Enforcement section.
EXEMPT_PATHS: list[tuple[str, str]] = [
    (
        "worklogs/**",
        "machine-generated session dumps (scripts/worklogs_dump.sh, systemd user timer) — a gate here fails on commits no human wrote",
    ),
    ("logs/**", "same dump pipeline as worklogs/; append-only run archives, not authored prose"),
    ("**/external/**", "verbatim third-party text — reflowing it would edit a quotation"),
]

# The files agents load into their context window, so a wrap defect costs every
# session. Always checked, whether or not a pull request touches them.
ALLOWLIST_GLOBS: list[str] = [
    "CLAUDE.md",
    "CLAUDE_zh.md",
    "AGENTS.md",
    "README.md",
    "PROJECT_STATE.md",
    ".claude/skills/**/*.md",
    ".claude/agents/*.md",
    ".kca/skills/**/*.md",
    ".agents/**/*.md",
    "docs/*.md",  # that directory's root only, not recursive
    "docs/adr/*.md",
    "docs/instructions/*.md",
]

# --------------------------------------------------------------------------
# Glob matching
#
# fnmatch's `*` crosses `/`, and git's pathspec globbing does too, so neither
# can express "docs/*.md but not docs/adr/*.md". Match segment by segment
# instead, with `**` as the only separator-crossing wildcard.
# --------------------------------------------------------------------------


def glob_match(path: str, pattern: str) -> bool:
    """Match `path` against `pattern`, where `*` never crosses a `/` and `**` does."""
    return _match_segments(path.split("/"), pattern.split("/"))


def _match_segments(parts: list[str], pats: list[str]) -> bool:
    if not pats:
        return not parts
    if pats[0] == "**":
        # `**` matches zero or more whole segments.
        for i in range(len(parts) + 1):
            if _match_segments(parts[i:], pats[1:]):
                return True
        return False
    if not parts:
        return False
    if not fnmatch.fnmatchcase(parts[0], pats[0]):
        return False
    return _match_segments(parts[1:], pats[1:])


def is_exempt(path: str) -> str | None:
    """Return the exemption reason if `path` is exempt, else None."""
    for pattern, reason in EXEMPT_PATHS:
        if glob_match(path, pattern):
            return reason
    return None


# --------------------------------------------------------------------------
# Line classification
# --------------------------------------------------------------------------

# A fence run at any indentation. How far it may be indented depends on the
# container it sits in, so the indent is checked separately — see `fence_open`.
FENCE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})")
# A closing fence uses the opening character, is at least as long, and carries
# nothing but whitespace after it. Anything else — a run of backticks with
# trailing text, or one indented out of its container — is still inside the code
# block, and treating it as the closer lets the engine reflow code.
FENCE_CLOSE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*$")
ATX_RE = re.compile(r"^ {0,3}#{1,6}(?: |\t|$)")
HR_DASH_RE = re.compile(r"^ {0,3}-{3,}[ \t]*$")
# A run of `=` under a paragraph is a setext H1. Unlike `---` it has no thematic
# break to be confused with, so it is unambiguous, valid Markdown — and this
# checker has no heading-style opinions. Reading it as prose reported the
# heading as a split block.
SETEXT_H1_RE = re.compile(r"^ {0,3}=+[ \t]*$")
HR_OTHER_RE = re.compile(r"^ {0,3}(?:\*[ \t]*){3,}$|^ {0,3}(?:_[ \t]*){3,}$")
# A list marker may be indented with tabs as well as spaces, and a tab-indented
# child list is an ordinary nested list — reading its items as prose flattens
# the nesting into one paragraph.
LIST_RE = re.compile(r"^[ \t]*(?:[-*+]|\d{1,9}[.)])(?: |\t|$)")
LIST_MARKER_RE = re.compile(r"^(?P<lead>[ \t]*)(?P<marker>[-*+]|\d{1,9}[.)])(?P<gap>[ \t]*)")
TABLE_RE = re.compile(r"^ {0,3}\|")
HTML_RE = re.compile(r"^ {0,3}<")
LINKDEF_RE = re.compile(r"^ {0,3}\[[^\]]+\]:")
# A link reference definition may run onto the following lines: the destination
# and then the title, or just the title — and the title itself may span several
# lines. Those lines belong to the definition and render as nothing, so joining
# a paragraph onto one would promote hidden metadata to visible text.
LINKDEF_TITLE_DELIMS = {'"': '"', "'": "'", "(": ")"}
QUOTE_RE = re.compile(r"^ {0,3}> ?")
HARD_BREAK_RE = re.compile(r"(?:  +|\\)$")

# A GitHub alert's type marker, alone on its blockquote line. GitHub renders the
# callout only in that shape — marker line, then the body on the line below — so
# the break after it is semantic, not whitespace. The five documented types are
# matched and nothing else: a wider match would silently exempt real prose, while
# a narrow one leaves today's behaviour in place. Quote markers are matched here
# rather than stripped by `split_quote`, which leaves them in place on a line
# indented far enough into a list. Syntax reference:
# https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts
ALERT_MARKER_RE = re.compile(
    r"^[ \t]*(?P<quote>(?:>[ \t]*)*)\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*$",
    re.IGNORECASE,
)

# CommonMark HTML blocks do not all end the same way. Types 1-5 run to their own
# terminator and may contain blank lines — an `<!-- ... -->` comment spanning a
# blank line is the common case here, and ending it early would let the engine
# reflow text it promised never to inspect. Types 6 and 7 end at a blank line.
#
# Which type a line opens also decides whether it may interrupt a paragraph:
# types 1-6 may, type 7 may not. And a line starting with `<` is often no block
# at all — `<https://example.com>` is an autolink, ordinary paragraph text —
# so the opener is matched exactly rather than by its first character.
HTML_CDATA_RE = re.compile(r"^ {0,3}<!\[CDATA\[")
HTML_COMMENT_RE = re.compile(r"^ {0,3}<!--")
HTML_PI_RE = re.compile(r"^ {0,3}<\?")
# Type 4's start condition is `<!` followed by an ASCII *uppercase* letter, which
# is what both markdown-it and cmark-gfm implement: `<!foo` is ordinary paragraph
# text to each of them. Accepting it opened a block that waits for a `>`, and an
# unterminated one hid the whole rest of the file from the gate.
HTML_DECL_RE = re.compile(r"^ {0,3}<![A-Z]")
# Type 1's start condition is the tag name followed by whitespace, `>`, or the
# end of the line — a `/` does not satisfy it. `<pre/>` is a complete tag, so it
# is type 7 and ends at the next blank line; reading it as type 1 made the engine
# wait for a `</pre>` that never comes and skip the rest of the file.
HTML_RAW_RE = re.compile(r"^ {0,3}<(script|pre|style|textarea)(?:[ \t>]|$)", re.IGNORECASE)

# CommonMark's type-6 tag list, verbatim.
HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl"
    "|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend"
    "|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td"
    "|tfoot|th|thead|title|tr|track|ul"
)
HTML_TYPE6_RE = re.compile(rf"^ {{0,3}}</?(?:{HTML_BLOCK_TAGS})(?:[ \t]|/?>|$)", re.IGNORECASE)

_TAG_NAME = r"[A-Za-z][A-Za-z0-9-]*"
_ATTR = r"""(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t]*=[ \t]*(?:[^ \t"'=<>`]+|'[^']*'|"[^"]*"))?)"""
HTML_TYPE7_RE = re.compile(rf"^ {{0,3}}(?:<{_TAG_NAME}{_ATTR}*[ \t]*/?>|</{_TAG_NAME}[ \t]*>)[ \t]*$")

# Returned by html_block_start for a block that ends at the next blank line.
ENDS_AT_BLANK_LINE = ""


def html_block_start(content: str, interrupting: bool) -> str | None:
    """The string that closes the HTML block starting here.

    Returns `ENDS_AT_BLANK_LINE` when a blank line closes it, and None when this
    line opens no HTML block at all. `interrupting` says a paragraph is open, in
    which case type 7 — any bare complete tag on its own line — is paragraph
    text rather than a block, per CommonMark.

    The content passed in is a line with its blockquote markers and, for a block
    that opens on a list-marker line, its list marker already stripped: all five
    start conditions are anchored at the container's content column, not at the
    margin.
    """
    if HTML_CDATA_RE.match(content):
        return "]]>"
    if HTML_COMMENT_RE.match(content):
        return "-->"
    if HTML_PI_RE.match(content):
        return "?>"
    if HTML_DECL_RE.match(content):
        return ">"
    m = HTML_RAW_RE.match(content)
    if m:
        return f"</{m.group(1).lower()}>"
    if HTML_TYPE6_RE.match(content):
        return ENDS_AT_BLANK_LINE
    if not interrupting and HTML_TYPE7_RE.match(content):
        return ENDS_AT_BLANK_LINE
    return None


def html_block_end(lines: list[str], start: int, terminator: str, depth: int, item: tuple[int, int] | None) -> int:
    """Index just past the HTML block opening at `lines[start]`.

    An HTML block cannot outlive the container holding it, so this stops at a
    non-blank line shallower than the blockquote it opened in, or one that has
    left the list item it opened in — `item` is that item, as `item_holds`
    understands it. Without that an unterminated block consumed the rest of the
    file. Lazy continuation is no help here: it carries a paragraph and nothing
    else, so an HTML block really does end where its container does.
    """
    i = start
    while i < len(lines):
        body_depth, body = split_quote(lines[i])
        if i > start and body.strip() and (body_depth < depth or (item is not None and not item_holds(lines[i], item))):
            break
        i += 1
        if terminator == ENDS_AT_BLANK_LINE:
            if not body.strip():
                break
        elif terminator in body.lower():
            break
    return i


# GFM makes the leading and trailing pipe of a table row optional, so a table
# can be a run of ordinary-looking text lines. What marks one is the delimiter
# row under its header — and the two must agree on cell count, or GFM renders a
# paragraph instead.
DELIM_CELL_RE = re.compile(r"^:?-+:?$")


def split_table_cells(content: str) -> list[str]:
    """Split a table row on unescaped `|`, dropping the optional outer pipes."""
    s = content.strip()
    cells: list[str] = []
    buf: list[str] = []
    escaped = False
    ended_on_pipe = False
    for ch in s:
        if escaped:
            buf.append(ch)
            escaped = ended_on_pipe = False
        elif ch == "\\":
            buf.append(ch)
            escaped = True
            ended_on_pipe = False
        elif ch == "|":
            cells.append("".join(buf))
            buf = []
            ended_on_pipe = True
        else:
            buf.append(ch)
            ended_on_pipe = False
    cells.append("".join(buf))
    if ended_on_pipe and len(cells) > 1 and not cells[-1].strip():
        cells.pop()
    if s.startswith("|") and len(cells) > 1 and not cells[0].strip():
        cells.pop(0)
    return cells


def is_delimiter_row(content: str) -> bool:
    """True for a GFM delimiter row such as `--- | ---` or `|:--|--:|`.

    A pipe is required, so a bare `---` stays a thematic break / setext rule.
    """
    if "|" not in content:
        return False
    cells = split_table_cells(content)
    return bool(cells) and all(DELIM_CELL_RE.match(c.strip()) for c in cells)


def table_opens_here(header: str, delimiter: str) -> int | None:
    """Column count if `header` + `delimiter` open a GFM table, else None.

    Indented four columns or more, neither line opens anything: a delimiter row
    there is paragraph continuation text, and reading it as a table suppressed
    the wrap findings for the whole run of lines below it.

    An ATX-looking header does open one, and this is the one shape where common
    parsers disagree: `# a | b` over `--- | ---` is a two-column table to
    markdown-it and a heading plus a paragraph to cmark-gfm, which is what
    GitHub renders with. The gate's rule under disagreement is to do nothing.
    Calling it a table means leaving those lines alone and costs at most a
    missed finding; calling it a paragraph means reporting lines that render
    correctly on the only renderer that matters here. A fence or a thematic
    break wins over a table in both parsers.
    """
    if not is_delimiter_row(delimiter):
        return None
    if indent_of(header) >= 4 or indent_of(delimiter) >= 4:
        return None
    if fence_open(header) or HR_DASH_RE.match(header) or HR_OTHER_RE.match(header):
        return None
    cols = len(split_table_cells(header))
    if cols != len(split_table_cells(delimiter)):
        return None
    return cols


def frontmatter_end(lines: list[str]) -> int | None:
    """Index of the `---` closing YAML frontmatter, or None if there is none.

    An opening `---` with no closer is not frontmatter — it is a thematic break,
    and reading it as an unterminated block would exempt the whole file.
    """
    if not lines or lines[0].strip() != "---":
        return None
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            return j
    return None


def split_quote(line: str) -> tuple[int, str]:
    """Strip blockquote markers, returning (depth, remaining content)."""
    depth, rest = 0, line
    while True:
        m = QUOTE_RE.match(rest)
        if not m:
            return depth, rest
        depth += 1
        rest = rest[m.end() :]


def is_alert_marker(content: str, depth: int) -> bool:
    """Is `content` a GitHub alert type marker standing alone *inside* a blockquote?

    GitHub reads the callout only inside a blockquote, so a bare `[!NOTE]` at top
    level is ordinary prose and joins like any other line. The quote can reach
    here two ways, and the marker needs one of them: `split_quote` stripped the
    `>` and reported `depth`, or it left the `>` in the content — which is what
    happens four or more columns into a list item, past `QUOTE_RE`'s reach — for
    the `quote` group to match.
    """
    m = ALERT_MARKER_RE.match(content)
    return bool(m) and (depth > 0 or bool(m["quote"]))


def column_of(prefix: str) -> int:
    """Width of `prefix` in columns; a tab advances to the next multiple of four."""
    width = 0
    for ch in prefix:
        width += 4 - (width % 4) if ch == "\t" else 1
    return width


def indent_of(content: str) -> int:
    """Indentation in columns; a tab advances to the next multiple of four."""
    return column_of(content[: len(content) - len(content.lstrip(" \t"))])


def strip_quotes(line: str, count: int) -> str | None:
    """`line` with exactly `count` blockquote markers removed, or None if it has fewer."""
    rest = line
    for _ in range(count):
        m = QUOTE_RE.match(rest)
        if not m:
            return None
        rest = rest[m.end() :]
    return rest


def item_holds(line: str, item: tuple[int, int] | None) -> bool:
    """True if this non-blank line is still inside the open list item `item`.

    An item's content is whatever is indented to its content column, and that
    column is measured *inside* whatever encloses the item: an item in a
    blockquote is indented from the quote's own content, not from the margin. So
    the enclosing markers come off first — `item` is the (quote depth, content
    column) pair recording how many there are — and the indentation is measured
    on what is left.

    Which is why the two nestings have to be peeled in the order they were
    written. `> - x` is a quote holding an item, `- > x` an item holding a quote;
    stripping every quote marker first and only then measuring reads the second
    one's continuation lines as unindented prose, and the block they belong to
    ends on its opening line.

    A line carrying fewer quote markers than the item's container has left the
    item. Whether it nevertheless continues the item's paragraph lazily is a
    separate question, and the caller's.
    """
    if item is None:
        return False
    depth, indent = item
    rest = strip_quotes(line, depth)
    return rest is not None and indent_of(rest) >= indent


def fence_open(content: str, max_indent: int = 3) -> tuple[str, int] | None:
    """(fence run, indent) if this line opens a fenced block, else None.

    A backtick fence's info string may not contain a backtick: CommonMark reads
    ```` ```a`b ```` as ordinary paragraph text, and entering fence mode there
    hides the rest of the document from the gate.
    """
    m = FENCE_RE.match(content)
    if not m:
        return None
    indent = indent_of(content)
    if indent > max_indent:
        return None
    run = m.group("fence")
    if run[0] == "`" and "`" in content[m.end() :]:
        return None
    return run, indent


def closes_fence(content: str, fence: str, open_indent: int = 0) -> bool:
    """True if this line closes a fenced block opened with `fence` at `open_indent`.

    A closer may be indented up to three columns past its opening fence — which
    for a fence inside a list item means past the item's content column, not
    past the margin.
    """
    m = FENCE_CLOSE_RE.match(content)
    if not m:
        return False
    if indent_of(content) > max(3, open_indent + 3):
        return False
    closer = m.group("fence")
    return closer[0] == fence[0] and len(closer) >= len(fence)


def list_marker(content: str) -> tuple[re.Match[str], int, bool] | None:
    """The list item this line opens: (marker match, content column, content is on this line).

    None where the line opens no item. The padding between the marker and what
    follows decides both of the other two, and it is measured from the marker's
    *ending* column, because that is where a tab's advance starts: after a
    one-column `-` a tab reaches column four, so `-\\t` is three columns of
    padding and `-\\t ` is four — both inside the one to four CommonMark allows.
    Measuring that padding from the margin instead called it five, took the
    over-wide branch below, and put the content column at two; a block of the
    item's own, indented to the five columns it really starts at, then read as
    outdented from the item and ended on its opening line.

    Over four columns of padding opens the item's indented code block, so the
    content column is one past the marker and what follows on the line is that
    block rather than the item's own content. An empty item holds nothing on its
    line either.
    """
    m = LIST_MARKER_RE.match(content) if LIST_RE.match(content) else None
    if m is None:
        return None
    marker_end = column_of(m.group("lead") + m.group("marker"))
    padded_to = column_of(m.group(0))
    if not content[m.end() :].strip() or padded_to - marker_end > 4:
        return m, marker_end + 1, False
    return m, padded_to, True


def list_content_indent(content: str) -> int:
    """The column a list item's own content starts at — where its child blocks live.

    A fence, a nested list or an indented code block belonging to the item is
    indented to at least this column. Zero where the line opens no item.
    """
    opened = list_marker(content)
    return opened[1] if opened else 0


def peel_containers(content: str, depth: int) -> tuple[int, str, tuple[int, int]]:
    """Strip the containers this line opens, in the order they were written.

    `content` is a line at quote depth `depth` that opens a list item, with any
    enclosing blockquote markers already removed. Returns the quote depth
    reached, what is left of the line, and the innermost list item as
    `item_holds` understands it.

    One line can open several containers — `- > x`, `- - x`, `> - > x` — and
    stripping quotes first and markers second only describes one of those
    orders. Each blockquote marker also starts a new frame for measuring
    columns, because a quote's content begins at its own left edge; that is why
    the offset resets at one and accumulates across a nested marker.

    The peel stops where the item's content is not another container: a marker
    followed by more than four columns of padding opens the item's indented code
    block, and what looks like a nested marker there is code. That is
    `list_marker`'s decision, taken once, so the peel and the content column it
    hands on can never disagree about how wide the padding is.
    """
    offset = list_content_indent(content)
    item = (depth, offset)
    while True:
        opened = list_marker(content)
        if opened is None or not opened[2]:
            # No marker, or padding wide enough that the item's content is its own
            # indented code block — where a marker-looking line is code.
            break
        content = content[opened[0].end() :]
        quoted, content = split_quote(content)
        if quoted:
            depth += quoted
            offset = 0  # a quote's content starts its own frame for columns
        if not LIST_RE.match(content):
            break
        offset += list_content_indent(content)
        item = (depth, offset)
    return depth, content, item


def is_block_start(content: str, *, in_paragraph: bool = True, container_indent: int = 0) -> bool:
    """True if this line begins a new block rather than continuing the one above.

    HTML is absent deliberately: an HTML block that may interrupt a paragraph is
    consumed before this is consulted, so a `<` left here opens no block.

    A link reference definition is a block start only where no paragraph is open
    — CommonMark does not let one interrupt a paragraph, so `[foo]: /url` in the
    middle of wrapped prose is prose, and the gate has to say so.

    Indentation is measured from the enclosing container: four columns past the
    open list item's content column is an indented code block, and one of those
    cannot interrupt a paragraph, so nothing that deep starts a block. A tab
    before a `-` is four columns, which is why the paragraph above it simply
    continues.
    """
    if indent_of(content) >= container_indent + 4:
        return False
    return bool(
        ATX_RE.match(content)
        or fence_open(content)
        or HR_DASH_RE.match(content)
        or HR_OTHER_RE.match(content)
        or LIST_RE.match(content)
        or TABLE_RE.match(content)
        or (not in_paragraph and LINKDEF_RE.match(content))
    )


def continues_lazily(content: str, container_indent: int) -> bool:
    """True if a line outdented from an open list item still continues its paragraph.

    CommonMark's lazy continuation carries a *paragraph* across a missing
    container prefix and nothing else, so a line that opens a block of its own
    has left the item however little it is indented. Reading an interrupting
    block opener as still inside the item handed that block the item's content
    column, and an HTML block that outdented from the list was then cut short
    after its opening line — the lines below it, which ADR-0024 exempts, were
    reported and folded as prose.

    The caller has already established that a paragraph is open. HTML is asked
    about separately because `is_block_start` leaves it out by design.
    """
    if html_block_start(content, interrupting=True) is not None:
        return False
    return not is_block_start(content, container_indent=container_indent)


def ends_table(content: str) -> bool:
    """True if this line interrupts an open table rather than being another row."""
    return bool(
        ATX_RE.match(content)
        or HR_DASH_RE.match(content)
        or HR_OTHER_RE.match(content)
        or LIST_RE.match(content)
        or html_block_start(content, interrupting=True) is not None
    )


def title_end(text: str, closer: str) -> int | None:
    """Index just past `closer` in `text`, honouring backslash escapes; None if unclosed."""
    escaped = False
    for idx, ch in enumerate(text):
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == closer:
            return idx + 1
    return None


def linkdef_span(lines: list[str], i: int) -> int | None:
    """How many physical lines the link reference definition at `lines[i]` occupies.

    None if no definition starts there. A definition is a label, a destination
    and an optional title, and each part may sit on its own line — a title may
    run across several of them — so the whole span has to be found before the
    paragraph below it can be judged.

    A title that will not parse means different things in its two positions:
    CommonMark disqualifies the whole definition when the junk is on the
    destination's own line, and simply ends the definition above it when the
    title started on a later line.
    """
    depth, content = split_quote(lines[i])
    m = LINKDEF_RE.match(content)
    if not m:
        return None

    def body(k: int) -> str | None:
        """Line `k`'s content if it is at this definition's quote depth and non-blank."""
        if k >= len(lines):
            return None
        d, c = split_quote(lines[k])
        return c if d == depth and c.strip() else None

    n = 1
    rest = content[m.end() :].strip()
    if not rest:
        nxt = body(i + n)
        if nxt is None or is_block_start(nxt, in_paragraph=False):
            return n
        rest = nxt.strip()
        n += 1

    # `rest` opens with the destination; whatever follows it is the title.
    destination_only = n
    parts = rest.split(None, 1)
    scan = parts[1].strip() if len(parts) > 1 else ""
    unparsable: int | None = None
    if not scan:
        nxt = body(i + n)
        if nxt is None:
            return destination_only
        scan = nxt.strip()
        n += 1
        unparsable = destination_only

    if scan[0] not in LINKDEF_TITLE_DELIMS:
        return unparsable
    closer = LINKDEF_TITLE_DELIMS[scan[0]]
    scan = scan[1:]
    end = title_end(scan, closer)
    while end is None:
        nxt = body(i + n)
        if nxt is None:
            return unparsable
        n += 1
        scan = nxt
        end = title_end(scan, closer)
    return n if not scan[end:].strip() else unparsable


def leaves_block_open(content: str) -> bool:
    """True if a following non-blank line would continue this line's block.

    CommonMark's lazy continuation continues a *paragraph* and nothing else, so
    this asks whether the line ends with one open. Paragraph text and a table row
    do; a heading, a thematic break, a fence, an HTML block and a link reference
    definition are complete on their line.

    A list item or a blockquote holds a paragraph only if its own content does,
    so those are unwrapped and asked again. `> - ---` is a quoted thematic break
    and `> - <!-- c -->` a quoted comment; treating either as an open paragraph
    pulled the unquoted line below it into the blockquote and reported a
    compliant file — a red build on nothing.
    """
    if not content.strip():
        return False
    depth, inner = split_quote(content)
    if depth:
        return leaves_block_open(inner)
    if ATX_RE.match(content) or HR_DASH_RE.match(content) or HR_OTHER_RE.match(content):
        return False
    if fence_open(content):
        return False
    if LINKDEF_RE.match(content):
        # Only if it really parses as one: `[foo]: /url "title" ok` has junk
        # after the title, which makes the whole line an ordinary paragraph.
        return linkdef_span([content], 0) != 1
    if html_block_start(content, interrupting=False) is not None:
        return False
    m = LIST_RE.match(content)
    if m:
        return leaves_block_open(content[m.end() :])
    return True


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------


class Violation:
    __slots__ = ("line", "kind", "message")

    def __init__(self, line: int, kind: str, message: str) -> None:
        self.line, self.kind, self.message = line, kind, message

    def format(self, path: str) -> str:
        return f"{path}:{self.line}: {self.kind}: {self.message}"


SPLIT_MSG = "continues the block on the line above — soft-wrap it onto one physical line"
SETEXT_MSG = "`---` directly below text parses as a setext H2 — leave a blank line above it"

SPLIT_BLOCK = "split-block"
SETEXT_RULE = "setext-rule"

# What `scan` decided a line is. The first six are never inspected, because a
# line break inside them is semantic.
FRONTMATTER = "frontmatter"
FENCE = "fence"  # the opening or closing line of a fenced block
CODE = "code"  # a line inside one
HTML = "html"
INDENTED_CODE = "indented-code"
LINKDEF = "linkdef"
BLANK = "blank"
TEXT = "text"  # an ordinary line, opening a block of its own
SPLIT = "split"  # continues the block above — the class-A violation
BREAK_CONTINUATION = "break"  # continues it, but an authored hard break protects it
SETEXT_H1 = "setext-h1"  # a `=` underline: the block above is a heading, not split
SETEXT_H2 = "setext-h2"  # a `---` under a paragraph — the class-B violation


class ScanLine:
    """One physical line, with the block and container state that explains it."""

    __slots__ = ("raw", "content", "depth", "role", "in_table", "is_item", "tail")

    def __init__(
        self,
        raw: str,
        content: str,
        depth: int,
        role: str,
        in_table: bool,
        is_item: bool,
        tail: str,
    ) -> None:
        self.raw = raw  # the line as written, blockquote markers and all
        self.content = content  # the same line with those markers stripped
        self.depth = depth  # how many blockquote markers were stripped
        self.role = role
        self.in_table = in_table  # a row of an open GFM table
        self.is_item = is_item  # opens a list item, by the renderer's reading
        self.tail = tail  # for SPLIT: what a rejoin would append to the line above


def scan(lines: list[str]) -> list[ScanLine]:
    """Classify every line once: what block it is in, and what container holds it.

    Every fence, HTML block, table, frontmatter run and list container is
    tracked here and nowhere else. When a second reader kept its own copy of
    that state the two drifted — one held a fenced block open past the
    blockquote that had already closed it — and the whole file below the
    disagreement was read wrongly by one of them.

    The state is deliberately thin — quote depth, the innermost list item's
    position, the open fence and the open table — and it is an approximation of
    CommonMark's block grammar rather than an implementation of it. That is
    affordable because the gate only ever reports: where the approximation is
    wrong the cost is a missed violation or, at worst, one line a human looks
    at and leaves alone.
    """
    records: list[ScanLine] = []
    # The open fenced block, if any: its fence run and the column it opened at,
    # plus the container it opened inside. A fenced block cannot outlive the
    # blockquote or list item holding it, and an unclosed one that did hid every
    # line below it from the gate.
    fence: tuple[str, int] | None = None
    fence_quote_depth = 0
    fence_item: tuple[int, int] | None = None
    frontmatter_last = frontmatter_end(lines)
    prev_open = False
    prev_depth = 0
    # Open GFM table, if any: its column count, whether its rows carry a leading
    # pipe, and the list item it opened in. Without the pipe, every line until
    # the table ends is a row — including, until this was tracked, lines that
    # had already left the item holding it.
    table_cols: int | None = None
    bare_table = False
    bare_table_item: tuple[int, int] | None = None
    # The innermost open list item, as (quote depth, content column) — the
    # engine's one piece of list state, and the only way to tell an item's own
    # code block from indented text continuing the item. Both halves are needed
    # because a quote may enclose the item or sit inside it; see `item_holds`.
    item: tuple[int, int] | None = None
    # The content of the last line emitted, which a continuation would join
    # onto. Not always the previous source line: a row already completed by an
    # earlier join is complete, and the line after it opens the next row.
    open_line = ""

    def emit(
        raw: str, content: str, depth: int, role: str, in_table: bool = False, is_item: bool = False, tail: str = ""
    ) -> None:
        records.append(ScanLine(raw, content, depth, role, in_table, is_item, tail))

    def own_indent(depth: int) -> int:
        """The open item's content column in the frame of a line at quote depth `depth`.

        Zero where no item is open, and zero inside a blockquote nested in the
        item: that quote's markers have already consumed the item's indentation,
        so within it the item imposes none of its own.
        """
        return item[1] if item is not None and depth == item[0] else 0

    i = 0
    while i < len(lines):
        raw = lines[i]

        # YAML frontmatter: only when it opens on the very first line and closes.
        if frontmatter_last is not None and i <= frontmatter_last:
            emit(raw, raw, 0, FRONTMATTER)
            i += 1
            continue

        depth, content = split_quote(raw)

        # Inside a fenced block: verbatim until the fence closes, or until the
        # container holding it does. A blockquote ends at a line shallower than
        # itself and a list item at a non-blank line indented less than its
        # content column; the fence ends with either, and this line is then
        # reprocessed at the level it actually sits on.
        if fence is not None:
            blank = not content.strip()
            left_item = fence_item is not None and not blank and not item_holds(raw, fence_item)
            if depth < fence_quote_depth or left_item:
                fence = None
            else:
                closing = closes_fence(content, *fence)
                emit(raw, content, depth, FENCE if closing else CODE)
                if closing:
                    fence = None
                i += 1
                prev_open, open_line = False, content
                continue

        opened = fence_open(content)
        if opened:
            if not item_holds(raw, item):
                # A fence outdented from the item closes the list it interrupts,
                # and the block that follows belongs to whatever held the list.
                item = None
            fence = opened
            fence_quote_depth, fence_item = depth, item
            emit(raw, content, depth, FENCE)
            i += 1
            prev_open, prev_depth, open_line = False, depth, content
            table_cols, bare_table = None, False
            continue

        if not content.strip():
            emit(raw, content, depth, BLANK)
            i += 1
            prev_open, prev_depth, open_line = False, depth, content
            table_cols, bare_table = None, False
            continue

        # Track the innermost open list item. A line indented to its content
        # column belongs to the item; one indented less, with nothing open, has
        # left it.
        marker = LIST_MARKER_RE.match(content) if LIST_RE.match(content) else None
        if marker and indent_of(content) >= own_indent(depth) + 4:
            # Four columns past the open item's content column is no longer a
            # marker: that deep it is an indented code block, or — with a
            # paragraph open above — a lazy continuation of it. A tab is four
            # columns, which is how a tab-indented `-` reached this rule.
            marker = None
        if marker:
            inner_depth, inner, item = peel_containers(content, depth)
        elif item is not None and not item_holds(raw, item):
            # Outdented from the item. Only an open paragraph survives that, and
            # only while the line opens no block of its own.
            if not (prev_open and continues_lazily(content, own_indent(depth))):
                item = None

        # A block can open on the marker line itself, and then the item holds a
        # block rather than text. `- ``` ` opens the item's fenced code block;
        # `- <!--` opens an HTML block that runs to its `-->` several lines
        # below. Reading either as an item whose text happens to be `` ``` `` or
        # `<!--` made the lines below it the item's own text, and reported
        # content ADR-0024 exempts as hard-wrapped prose.
        #
        # The item's content may itself open further containers, in any order —
        # `- > <!--` is an item holding a quote holding a comment and `- - ```
        # ` an item holding an item holding a fence — so `peel_containers` has
        # already taken them all off. The block lives at the composed depth of
        # every quote it sits in, and inside the innermost item.
        if marker:
            opened = fence_open(inner)
            if opened:
                fence = (opened[0], own_indent(inner_depth))
                fence_quote_depth, fence_item = inner_depth, item
                emit(raw, content, depth, FENCE, is_item=True)
                i += 1
                prev_open, prev_depth, open_line = False, depth, content
                table_cols, bare_table = None, False
                continue
            terminator = html_block_start(inner, interrupting=False)
            if terminator is not None:
                end = html_block_end(lines, i, terminator, inner_depth, item)
                for k in range(i, end):
                    emit(lines[k], split_quote(lines[k])[1], inner_depth, HTML, is_item=k == i)
                i = end
                prev_open, prev_depth, open_line = False, depth, records[-1].content
                table_cols, bare_table = None, False
                continue

        # Inside a table whose rows have no leading pipe, an ordinary text line
        # is a row, not a continuation of the row above — joining the two would
        # merge two rendered rows into one. Rows run until some other block
        # interrupts the table, or until the container holding it ends: a bare
        # table in a list item used to swallow the prose below the whole list.
        if bare_table:
            left_item = bare_table_item is not None and not item_holds(raw, bare_table_item)
            if depth == prev_depth and not left_item and not ends_table(content):
                emit(raw, content, depth, TEXT, in_table=True, is_item=bool(marker))
                i += 1
                prev_open, prev_depth, open_line = False, depth, content
                continue
            table_cols, bare_table = None, False

        # An indented code block cannot interrupt a paragraph, so it only starts
        # where nothing is open. It runs until a blank line. Inside a list item
        # it starts four columns past the item's *content* column, not four past
        # the margin — `10. item` puts its own paragraphs at column 4, and
        # reading those as code let them be hard-wrapped straight through CI.
        if not prev_open and indent_of(content) >= own_indent(depth) + 4:
            emit(raw, content, depth, INDENTED_CODE)
            i += 1
            prev_depth, open_line = depth, content
            continue

        # A fence indented into an open list item is that item's fenced code
        # block, not the item's text continuing on another line. Outside a list
        # the same indented run of backticks is paragraph text, so this needs the
        # item's content column to tell them apart:
        #
        #   10. item          <- content column 4
        #       ```           <- a fence, and everything to its closer is code
        if prev_open and item is not None and indent_of(content) >= own_indent(depth):
            opened = fence_open(content, max_indent=indent_of(content))
            if opened:
                fence = opened
                fence_quote_depth, fence_item = depth, item
                emit(raw, content, depth, FENCE)
                i += 1
                prev_open, prev_depth, open_line = False, depth, content
                table_cols, bare_table = None, False
                continue

        # An HTML block runs verbatim to its end condition. Types 1-6 may
        # interrupt an open paragraph; type 7 may not, and is left as prose.
        terminator = html_block_start(content, interrupting=prev_open)
        if terminator is not None:
            end = html_block_end(lines, i, terminator, depth, item)
            for k in range(i, end):
                emit(lines[k], split_quote(lines[k])[1], depth, HTML)
            i = end
            prev_open, prev_depth, open_line = False, depth, records[-1].content
            table_cols, bare_table = None, False
            continue

        # A link reference definition can span lines. The whole definition is one
        # block, so its destination and title stay metadata instead of becoming
        # the head of the paragraph below.
        span = linkdef_span(lines, i) if not prev_open else None
        if span is not None:
            for k in range(i, i + span):
                emit(lines[k], split_quote(lines[k])[1], depth, LINKDEF)
            i += span
            prev_open, prev_depth, open_line = False, depth, records[-1].content
            table_cols, bare_table = None, False
            continue

        # A table opens where a delimiter row follows a header of equal width.
        # Tables may interrupt a paragraph, so this is checked before the join.
        if i + 1 < len(lines):
            next_depth, next_content = split_quote(lines[i + 1])
            if next_depth == depth:
                cols = table_opens_here(content, next_content)
                if cols is not None:
                    table_cols = cols
                    bare_table = not TABLE_RE.match(content)
                    bare_table_item = item
                    emit(raw, content, depth, TEXT, in_table=True, is_item=bool(marker))
                    i += 1
                    prev_open, prev_depth, open_line = not bare_table, depth, content
                    continue

        # A setext H1 underline: the paragraph above it is a heading, not a
        # block continued onto this line. Inside a table the same line is one
        # more row, so this only applies where no table is open.
        if SETEXT_H1_RE.match(content) and prev_open and table_cols is None:
            emit(raw, content, depth, SETEXT_H1)
            i += 1
            prev_open, prev_depth, open_line = False, depth, content
            continue

        # Class B — a thematic break that CommonMark will read as a setext H2.
        if HR_DASH_RE.match(content) and prev_open:
            emit(raw, content, depth, SETEXT_H2)
            i += 1
            prev_open, prev_depth, open_line = False, depth, content
            continue

        # Class A — a block continued on the next physical line. A shallower
        # quote depth still continues it: CommonMark's lazy continuation lets a
        # wrapped blockquote paragraph drop the `>` on its second line.
        if prev_open and depth <= prev_depth and not is_block_start(content, container_indent=own_indent(depth)):
            if table_cols is not None and len(split_table_cells(open_line)) >= table_cols:
                # Inside a table whose previous row is already complete, a line
                # without a leading pipe is the next row — GFM makes that pipe
                # optional — and not the tail of the row above.
                emit(raw, content, depth, TEXT, in_table=True)
                i += 1
                prev_open, open_line = True, content
                continue
            if HARD_BREAK_RE.search(open_line) or is_alert_marker(open_line, prev_depth):
                # An explicit hard break is authored intent; joining would change
                # rendering. Leave it, and leave the line it introduces. A GitHub
                # alert's type marker is the same kind of control line: the
                # callout exists only while `> [!NOTE]` stands alone above its
                # body inside a blockquote, so a join demotes it to an ordinary
                # blockquote printing the literal `[!NOTE]`. `prev_depth` is the
                # quote depth of the line `open_line` came from. The body below
                # is left open, so a body that really is hard-wrapped is still
                # reported.
                emit(raw, content, depth, BREAK_CONTINUATION)
                i += 1
                prev_open, open_line = True, content
                continue
            # Keep this line's own trailing hard break: stripping it deletes the
            # `<br>` between it and the line below, which is authored intent and
            # not whitespace the renderer is free to collapse.
            tail = content.lstrip() if HARD_BREAK_RE.search(content) else content.strip()
            emit(raw, content, depth, SPLIT, tail=tail)
            i += 1
            prev_open, open_line = True, open_line.rstrip() + " " + tail
            continue

        emit(
            raw,
            content,
            depth,
            TEXT,
            in_table=table_cols is not None and bool(TABLE_RE.match(content)),
            is_item=bool(marker),
        )
        prev_open = leaves_block_open(content)
        prev_depth, open_line = depth, content
        if not TABLE_RE.match(content):
            table_cols, bare_table = None, False
        i += 1

    return records


def analyse(text: str) -> list[Violation]:
    """Report every soft-wrap violation in `text`.

    All the reading happens in `scan`; what is left here is turning two of its
    line roles into findings. This is a gate, so that is the whole job — it
    reports what a human then soft-wraps by hand, and writes nothing itself.
    """
    lines = text[:-1].split("\n") if text.endswith("\n") else text.split("\n")

    violations: list[Violation] = []
    for number, line in enumerate(scan(lines), start=1):
        if line.role == SPLIT:
            violations.append(Violation(number, SPLIT_BLOCK, SPLIT_MSG))
        elif line.role == SETEXT_H2:
            violations.append(Violation(number, SETEXT_RULE, SETEXT_MSG))
    return violations


# --------------------------------------------------------------------------
# File selection
# --------------------------------------------------------------------------


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def repo_root() -> Path:
    return Path(git("rev-parse", "--show-toplevel").strip())


def tracked_markdown() -> list[str]:
    return [p for p in git("ls-files", "*.md").split("\n") if p]


def select_allowlist() -> list[str]:
    tracked = tracked_markdown()
    return sorted({p for p in tracked if any(glob_match(p, g) for g in ALLOWLIST_GLOBS)})


def select_changed(base: str) -> list[str]:
    out = git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")
    return sorted(p for p in out.split("\n") if p.endswith(".md"))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="check_md_wrap.py",
        description="Check Markdown soft wrap per ADR-0024.",
    )
    p.add_argument("--check", action="store_true", help="report violations — the default, and the only mode")
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument("--files", nargs="+", metavar="PATH", help="check exactly these paths")
    scope.add_argument("--changed", metavar="REF", help="check only the .md files this branch changes against REF")
    scope.add_argument("--allowlist", action="store_true", help="check the agent-context allowlist")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.allowlist:
        paths = select_allowlist()
    elif args.changed:
        paths = select_changed(args.changed)
    else:
        paths = sorted(args.files)

    root = repo_root()
    skipped = [path for path in paths if is_exempt(path)]
    paths = [path for path in paths if not is_exempt(path)]

    failures = 0
    for rel in paths:
        path = root / rel
        if not path.exists():
            continue
        for violation in analyse(path.read_text(encoding="utf-8")):
            print(violation.format(rel))
            failures += 1

    scope_name = "allowlist" if args.allowlist else (f"changed vs {args.changed}" if args.changed else "files")
    print(f"\n{len(paths)} file(s) checked ({scope_name}); {len(skipped)} exempt.", file=sys.stderr)
    if failures:
        print(f"{failures} violation(s). Each message says what to change; ADR-0024 has the rule.", file=sys.stderr)
        return 1
    print("No violations.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
