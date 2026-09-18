#!/usr/bin/env python3
"""Check and fix Markdown soft wrap (ADR-0024).

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
backslash — is authored intent, so the line after it is left alone too. That is
the whole exemption set: ADR-0024 also exempts a verbatim diff, log excerpt or
file listing, which qualifies by being fenced or indented, because nothing
distinguishes bare verbatim lines from hard-wrapped prose.

`--fix` is whitespace only. It rejoins a split block onto the line above with a
single space, and inserts the missing blank line above a `---`. It never alters
words, punctuation, link targets or block structure, and on an already-compliant
file its output is byte-identical to its input.

That promise is verified rather than asserted: every rewrite is rendered with
markdown-it-py and compared against the original before the file is written, and
a file whose rendering would change is reported and left alone. `--fix`
therefore needs markdown-it-py installed; `--check` is standard-library only and
always will be, because CI runs it on a bare Python with nothing installed.

The renderer this gate exists for is GitHub's, which is cmark-gfm. The renderer
it verifies with is markdown-it-py, which is pure Python and can be a hard
dependency of `--fix` on any machine. They agree almost everywhere; where they
do not, the rule is to leave the construct alone rather than pick a side, so a
disagreement costs a missed finding and never a bad rewrite. ADR-0024 records
that choice and why cmark-gfm was not made the verifier.

Usage:
  python scripts/check_md_wrap.py --allowlist              # the agent-context set
  python scripts/check_md_wrap.py --changed origin/main    # only what this branch touches
  python scripts/check_md_wrap.py --files a.md b.md        # exactly these
  python scripts/check_md_wrap.py --fix --allowlist        # rewrite in place (needs markdown-it-py)
  python scripts/check_md_wrap.py --equivalence origin/main --allowlist

Exactly one scoping mode is required. There is deliberately no "whole
repository" mode: ADR-0024's enforcement is scoped to changed files plus the
allowlist, and the historical backfill was declined (issue #210).

Exit codes:
  0 — no violations (or, with --fix, everything fixed)
  1 — violations found, or --fix refused to rewrite a file
  2 — usage error, or --fix without markdown-it-py to verify itself
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
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
# heading as a split block and offered `Title ===` as the repair.
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

    An ATX-looking header does open one, and this is the one shape where the two
    parsers disagree: `# a | b` over `--- | ---` is a two-column table to
    markdown-it and a heading plus a paragraph to cmark-gfm, which is what
    GitHub renders with. The gate's rule under disagreement is to do nothing,
    because only one of the two readings is checkable by the verifier it has —
    calling it a table means leaving those lines alone, which costs at most a
    missed finding, while calling it a paragraph means rewriting lines that the
    verifier would then have to approve on markdown-it's reading of them. See
    ADR-0024 for why the target renderer and the verifier are different
    programs. A fence or a thematic break wins over a table in both parsers.
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
    pulled the unquoted line below it into the blockquote, and the renderer then
    refused the rewrite — an unfixable false positive rather than a corruption,
    but a red build either way.
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
ALL_REPAIRS = (SPLIT_BLOCK, SETEXT_RULE)

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
        self.tail = tail  # for SPLIT: the text to append to the line above


def scan(lines: list[str]) -> list[ScanLine]:
    """Classify every line once, and let both readers of the document share it.

    `analyse` and `structure` read the same file for different reasons — one
    decides what to report and rewrite, the other fingerprints what a rewrite
    must not change — so they have to agree about where blocks begin and end.
    While each tracked its own they drifted, and the cost fell on correct
    repairs: `structure` kept a fenced block open past the blockquote that had
    already closed it, so ordinary prose below looked like code the rewrite had
    edited, and `--fix` refused a file it should have fixed. Every fence, HTML
    block, table, frontmatter and list container is tracked here and nowhere
    else, which is what stops that happening again.

    The state is deliberately thin — quote depth, the innermost list item's
    position, the open fence and the open table — and it is an approximation of
    CommonMark's block grammar rather than an implementation of it. The `--fix`
    safety net exists because of that.
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
        # `<!--` made the lines below it the item's own text, and `--fix`
        # flattened content ADR-0024 exempts into one line.
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
            if HARD_BREAK_RE.search(open_line):
                # An explicit hard break is authored intent; joining would change
                # rendering. Leave it, and leave the line it introduces.
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


def analyse(text: str, repair: tuple[str, ...] = ALL_REPAIRS) -> tuple[list[Violation], str]:
    """Return (violations, fixed_text). `fixed_text` differs only in whitespace.

    `repair` selects which violation classes are written into `fixed_text`;
    everything is still reported. Only the safety check uses this: a class-A
    rejoin must leave the rendered output identical, while the class-B repair
    deliberately changes it — that is the point of splitting a setext heading
    back into a paragraph and a thematic break.

    All the reading happens in `scan`. What is left here is the two repairs: a
    continuation is folded onto the line above, and a `---` that would make the
    paragraph above it a heading gets the blank line it is missing.
    """
    had_trailing_newline = text.endswith("\n")
    lines = text[:-1].split("\n") if had_trailing_newline else text.split("\n")

    out: list[str] = []
    violations: list[Violation] = []
    for number, line in enumerate(scan(lines), start=1):
        if line.role == SPLIT:
            violations.append(Violation(number, SPLIT_BLOCK, SPLIT_MSG))
            if SPLIT_BLOCK in repair:
                out[-1] = out[-1].rstrip() + " " + line.tail
                continue
        elif line.role == SETEXT_H2:
            violations.append(Violation(number, SETEXT_RULE, SETEXT_MSG))
            if SETEXT_RULE in repair:
                out.append("> " * line.depth if line.depth else "")
        out.append(line.raw)

    fixed = "\n".join(out)
    if had_trailing_newline:
        fixed += "\n"
    return violations, fixed


# --------------------------------------------------------------------------
# Structural equivalence
# --------------------------------------------------------------------------

INLINE_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)")
CODE_SPAN_RE = re.compile(r"`[^`]*`")


SETEXT_RE = re.compile(r"^ {0,3}(?P<rule>=+|-+)[ \t]*$")


def structure(text: str) -> dict:
    """Extract wrap-invariant structure, for before/after comparison.

    The text stream drops `|` before comparing. Rejoining a split table row moves
    its tail from a prose line into a table cell, which is a repair rather than a
    content change, and only pipe-blindness makes the two states comparable.

    Nesting is recorded, not just counted: a list that lost its indentation, a
    table that lost a row and a paragraph that became a setext heading all read
    as the same text, and only their shape gives them away.

    Where a block begins and ends is `scan`'s answer, not a second opinion. This
    used to keep its own fence, table and list-indent rules, and every time one
    of them fell behind the engine the result was a refusal on a correct repair
    — prose below a closed blockquote counted as fenced code, a paragraph after
    a list counted as one more row of a table. It now only fingerprints.
    """
    stream: list[str] = []
    headings: list[tuple[int, str, str]] = []
    code: list[str] = []
    links: list[str] = []
    list_shape: list[tuple[int, str]] = []
    list_indents: list[int] = []
    tables: list[tuple[int, ...]] = []
    table_rows: list[int] = []
    hard_breaks = 0
    # The last line of an open top-level paragraph, if one is open: only such a
    # paragraph can be turned into a setext heading by a `---` below it.
    open_paragraph: str | None = None
    open_other_block = False

    def close_table() -> None:
        if table_rows:
            tables.append(tuple(table_rows))
            table_rows.clear()

    for line in scan(text.split("\n")):
        content = line.content
        if line.role == CODE:
            code.append(content)
            continue
        if line.role in (FENCE, FRONTMATTER, BLANK):
            close_table()
            open_paragraph, open_other_block = None, False
            continue

        if line.in_table:
            table_rows.append(len(split_table_cells(content)))
        else:
            close_table()

        # A setext underline turns the paragraph above it into a heading — the
        # class-B hazard. Record it, so a comparison can see one appear.
        sx = SETEXT_RE.match(content)
        if sx and open_paragraph is not None and not line.in_table:
            headings.append((1 if sx.group("rule")[0] == "=" else 2, open_paragraph, "setext"))
            open_paragraph = None
            stream.append(content)
            continue

        stream.append(content)
        # An authored hard break renders as a `<br>`; a join that swallows one
        # deletes a visible line break, so count them.
        if HARD_BREAK_RE.search(content):
            hard_breaks += 1
        links.extend(m.group("target") for m in INLINE_LINK_RE.finditer(content))
        h = re.match(r"^ {0,3}(#{1,6})(?: +)(.*?)\s*#*\s*$", content)
        if h:
            headings.append((len(h.group(1)), " ".join(h.group(2).split()), "atx"))
            open_paragraph, open_other_block = None, False
            continue
        indent = indent_of(content)
        if LIST_RE.match(content):
            while list_indents and indent < list_indents[-1]:
                list_indents.pop()
        if line.is_item:
            # Whether a marker this deep is a marker at all is `scan`'s call —
            # four columns past the enclosing item's content column it is
            # indented text. Deciding that twice is what made this heuristic
            # count items the renderer does not, and refuse a rewrite that
            # renders identically.
            if not list_indents or indent > list_indents[-1]:
                list_indents.append(indent)
            list_shape.append((len(list_indents), "ol" if content.lstrip(" \t")[0].isdigit() else "ul"))
        elif indent == 0 and not line.in_table and not open_other_block:
            list_indents.clear()

        if HR_DASH_RE.match(content) or HR_OTHER_RE.match(content):
            open_paragraph, open_other_block = None, False
        elif line.in_table or LIST_RE.match(content) or LINKDEF_RE.match(content) or indent >= 4:
            open_paragraph, open_other_block = None, True
        elif open_other_block:
            open_paragraph = None  # a continuation line of a list item or table
        else:
            open_paragraph = " ".join(content.split())

    close_table()

    return {
        "prose": " ".join(" ".join(stream).replace("|", " ").split()),
        "headings": headings,
        "code": "\n".join(code),
        "links": sorted(links),
        "list_items": len(list_shape),
        "list_shape": list_shape,
        "tables": tables,
        "hard_breaks": hard_breaks,
    }


def _malformed(tables: list[tuple[int, ...]]) -> bool:
    """True if any table's rows disagree on column count."""
    return any(len(widths) > 1 and len(set(widths)) > 1 for widths in tables)


def compare_structure(before: str, after: str) -> list[str]:
    """Differences that mean the reflow changed more than whitespace."""
    a, b = structure(before), structure(after)
    diffs: list[str] = []
    if a["prose"] != b["prose"]:
        diffs.append("prose text changed (not a whitespace-only edit)")

    # ATX headings are invariant. Setext headings may only disappear: removing
    # one is the class-B repair, while creating one silently promotes a
    # paragraph to a heading.
    atx = [h for h in a["headings"] if h[2] == "atx"], [h for h in b["headings"] if h[2] == "atx"]
    if atx[0] != atx[1]:
        diffs.append(f"heading sequence changed: {len(atx[0])} -> {len(atx[1])}")
    setext_before = [h for h in a["headings"] if h[2] == "setext"]
    new_setext = [h for h in b["headings"] if h[2] == "setext" and h not in setext_before]
    if new_setext:
        diffs.append(f"a paragraph became a setext heading: {new_setext[0][1]!r}")

    if a["code"] != b["code"]:
        diffs.append("fenced code content changed")
    if a["hard_breaks"] != b["hard_breaks"]:
        diffs.append(f"authored hard breaks changed: {a['hard_breaks']} -> {b['hard_breaks']}")
    if a["links"] != b["links"]:
        diffs.append("link targets changed")
    if a["list_items"] != b["list_items"]:
        diffs.append(f"list-item count changed: {a['list_items']} -> {b['list_items']}")
    elif a["list_shape"] != b["list_shape"]:
        diffs.append("list nesting changed")
    if a["tables"] != b["tables"]:
        # Rejoining a split row legitimately repairs a table that was broken
        # before, so a dimension change is only a defect when the result is
        # still malformed. A well-formed table has one column count throughout —
        # but a table that disappeared entirely leaves an empty, vacuously
        # well-formed set behind, so the count has to match too.
        if len(a["tables"]) != len(b["tables"]) or _malformed(b["tables"]) or not _malformed(a["tables"]):
            diffs.append(f"table dimensions changed: {a['tables']} -> {b['tables']}")
    return diffs


# --------------------------------------------------------------------------
# The --fix safety net
#
# Everything above is a hand-written approximation of CommonMark's block
# grammar, and its container model has a long tail: four review rounds on PR
# #226 found real corruptions in it — a fence inside a list item, a tab-indented
# nested list, a lazy continuation into an empty quoted item, an HTML block
# opening on a list-marker line. Each was fixed, and that is exactly the reason
# not to trust the next one. `--check` can only be wrong about a finding;
# `--fix` writes files, and CLAUDE.md tells every agent in this repository to
# run it.
#
# So a rewrite is verified before it is written: render the original and the
# rewrite with a real CommonMark+GFM parser and compare the HTML the way a
# browser resolves it — whitespace collapsed outside verbatim elements, byte
# for byte inside them. If they differ, the file is not written and the refusal
# is reported.
#
# The split of responsibilities is deliberate. `--check` stays standard-library
# only: CI runs it on a bare `setup-python` that installs nothing, and a check
# that never writes cannot corrupt anything. `--fix` requires markdown-it-py and
# refuses to run without it, rather than warning and writing anyway — a warning
# in a scrolling agent log is not a safety net, and the install is one line.
# --------------------------------------------------------------------------

# Elements whose whitespace a browser preserves. Everywhere else a newline and a
# space render the same, which is the whole premise of soft wrapping.
VERBATIM_TAGS = ("pre", "textarea", "script", "style")
# Elements whose content is text, not markup: a `<pre>` written inside one of
# them opens nothing.
RAW_TEXT_TAGS = ("script", "style", "textarea")

# Two things in the rendered HTML break `canonical_html`'s premise, and a text
# comparison of the two renderings cannot see either:
#
#   - a CSS `white-space` value that keeps line breaks. `white-space: pre` on a
#     span makes a source newline visible, so joining across it changes what the
#     reader sees while the canonicalised HTML compares equal.
#   - an unbalanced verbatim element. An unclosed `<pre>` makes everything after
#     it preformatted in a browser, but a verbatim region needs a closing tag to
#     be found at all, so the canonicaliser collapses it.
#
# Neither can be judged, so such a file is refused rather than verified. No
# tracked file hits either today.
#
# The first of the two is a CSS question, and a pattern is no better at CSS than
# it was at HTML. `white-space:/**/pre` is that declaration — a comment is a
# token separator, so a browser computes `white-space: pre` — and
# `white-spac\65:pre` is too, because a property name may be escaped. Both slid
# past a pattern anchored on the literal text `white-space` followed by a colon,
# and `--fix` then joined across a newline the reader can see. So the
# declarations are read out rather than matched.
CSS_COMMENT_RE = re.compile(r"/\*.*?(?:\*/|$)", re.DOTALL)
# A CSS escape is `\` plus one to six hex digits, which may absorb one following
# whitespace character, or `\` plus any other single character taken literally.
CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9A-Fa-f]{1,6})[ \t\n\r\f]?|(.))", re.DOTALL)
CSS_IMPORTANT_RE = re.compile(r"!\s*important\s*$")

# The properties that decide whether a source line break survives, and the
# values that answer either way. `white-space-collapse` is the longhand, and
# `white-space` is now a shorthand that also carries text-wrap and trim values,
# so a declaration can hold several tokens.
WHITESPACE_PROPERTIES = frozenset({"white-space", "white-space-collapse"})
# Any of these keeps a line break, `pre-line` included: it collapses spaces but
# not newlines, which is exactly the break this gate would delete.
PRESERVING_VALUES = frozenset(
    {"pre", "pre-wrap", "pre-line", "break-spaces", "preserve", "preserve-breaks", "preserve-spaces"}
)
# And these collapse it, which is the premise soft wrapping rests on.
COLLAPSING_VALUES = frozenset(
    {"normal", "nowrap", "initial", "collapse", "wrap", "balance", "pretty", "stable", "auto"}
)


class HtmlScan(HTMLParser):
    """The real tags, CSS and verbatim regions of a rendered document.

    A regular expression is the wrong tool for every question this answers, and
    each wrong answer was a defect: `<!-- mention <pre> -->` contains no `<pre>`
    element but matches a tag pattern, `<span style=white-space:pre>` is a valid
    unquoted attribute that a quoted-value pattern misses, and a `<pre>` written
    inside `<script>` is text. So this asks a parser instead — `html.parser` is
    standard library, which the whole module has to stay inside.

    Three products, all from one pass:

      `css`        every declaration block a browser would apply — the `style`
                   attribute of each real tag, and the text of each `<style>`
      `spans`      the offsets of each balanced verbatim region, outermost only
      `unbalanced` verbatim tags that are opened and never closed
    """

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self._html = html
        self._line_start = [0]
        for line in html.split("\n"):
            self._line_start.append(self._line_start[-1] + len(line) + 1)
        self.css: list[str] = []
        self.spans: list[tuple[int, int]] = []
        self._open: list[tuple[str, int]] = []
        self._raw_text: str | None = None
        self.feed(html)
        self.close()
        self.unbalanced = sorted({tag for tag, _ in self._open})

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_start[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._raw_text is not None:
            return  # markup inside a raw-text element is that element's text
        self.css.extend(value for name, value in attrs if name.lower() == "style" and value)
        if tag in RAW_TEXT_TAGS:
            self._raw_text = tag
        if tag in VERBATIM_TAGS:
            self._open.append((tag, self._offset()))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # A browser ignores the `/` on a non-void element, so `<pre/>` opens a
        # `<pre>` that nothing closes. Reading it as a complete empty element
        # would balance it and hide the very hazard this looks for.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._raw_text is not None:
            if tag != self._raw_text:
                return
            self._raw_text = None
        for k in range(len(self._open) - 1, -1, -1):
            if self._open[k][0] != tag:
                continue
            start = self._open[k][1]
            del self._open[k:]
            if not self._open:
                close = self._html.find(">", self._offset())
                self.spans.append((start, len(self._html) if close < 0 else close + 1))
            return

    def handle_data(self, data: str) -> None:
        if self._raw_text == "style":
            self.css.append(data)


RENDERER_MISSING = (
    "--fix needs markdown-it-py to verify its own rewrite before writing it: "
    "`pip install markdown-it-py` (or `pip install -e '.[dev]'`). "
    "--check needs nothing beyond the standard library."
)

# Printed after every --fix run. The verification is strong but not unbounded,
# and an unqualified claim is worse than a stated limit.
VERIFICATION_BOUNDARY = (
    "Each rewrite was rendered with markdown-it-py and compared to the original as a browser "
    "resolves whitespace. The guarantee stops there: it is one parser's reading of CommonMark+GFM, "
    "not GitHub's cmark-gfm, and a file whose rendering it cannot judge is refused, not written "
    "(ADR-0024)."
)


def load_renderer():
    """The CommonMark+GFM renderer used to verify a rewrite, or None if absent."""
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        return None
    # linkify is off: it rewrites bare URLs into links, which is a rendering
    # difference this comparison has no interest in.
    return MarkdownIt("gfm-like").disable("linkify")


def canonical_html(html: str, scan: HtmlScan | None = None) -> str:
    """Rendered HTML reduced to what a browser actually shows.

    Outside `<pre>` and friends every run of whitespace is one space, so a source
    newline and a source space are indistinguishable; inside them whitespace is
    significant and is kept exactly.
    """
    scan = scan if scan is not None else HtmlScan(html)
    parts: list[str] = []
    pos = 0
    for start, end in scan.spans:
        parts.append(" ".join(html[pos:start].split()))
        parts.append(html[start:end])
        pos = end
    parts.append(" ".join(html[pos:].split()))
    return " ".join(p for p in parts if p)


def _unescape_css(text: str) -> str:
    """`text` with CSS escapes resolved, so `white-spac\\65` reads as what it names."""

    def one(m: re.Match[str]) -> str:
        if m.group(1):
            point = int(m.group(1), 16)
            # Zero, a surrogate or a value past the last code point is U+FFFD,
            # which names no property and matches no value — as intended.
            unusable = point == 0 or 0xD800 <= point <= 0xDFFF or point > 0x10FFFF
            return chr(0xFFFD) if unusable else chr(point)
        return m.group(2) or ""

    return CSS_ESCAPE_RE.sub(one, text)


def css_declarations(block: str) -> list[tuple[str, str]]:
    """Every (property, value) pair a browser would read out of `block`.

    `block` is either a `style` attribute or the text of a `<style>` element, so
    this has to survive selectors, at-rules and nesting braces as well as
    declarations. It is a reader, not a CSS parser: it tokenises only as far as
    finding where one declaration ends and the next begins, which means tracking
    strings — a `;` inside `content: "a;b"` separates nothing — and parentheses,
    so the `:` inside `(max-width: 40em)` is not a declaration's colon.

    Comments are replaced by a space rather than removed, because that is what
    they are: `white-space/**/:pre` is the declaration and `white-spac/**/e:pre`
    is two idents and not a property name at all.
    """
    text = CSS_COMMENT_RE.sub(" ", block)
    declarations: list[tuple[str, str]] = []
    name: list[str] = []
    value: list[str] | None = None
    buf = name
    quote = ""
    escaped = False
    parens = 0

    def flush() -> None:
        nonlocal name, value, buf
        if value is not None:
            declarations.append(("".join(name), "".join(value)))
        name, value = [], None
        buf = name

    for ch in text:
        if escaped:  # the backslash is kept, for `_unescape_css` to resolve
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            buf.append(ch)
            escaped = True
        elif quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == "(":
            parens += 1
            buf.append(ch)
        elif ch == ")":
            parens = max(0, parens - 1)
            buf.append(ch)
        elif parens == 0 and ch == ":" and value is None:
            value = []
            buf = value
        elif parens == 0 and ch in ";{}":
            flush()
        else:
            buf.append(ch)
    flush()

    out = []
    for prop, val in declarations:
        text_value = CSS_IMPORTANT_RE.sub("", _unescape_css(val).strip().lower()).strip()
        out.append((_unescape_css(prop).strip().lower(), text_value))
    return out


def preserves_whitespace(block: str) -> bool:
    """True if this CSS could keep a source line break visible.

    An unrecognised value counts as could: `inherit` and `unset` take the value
    from a parent this cannot see, `var(--x)` from a custom property, and a typo
    is a value too. Refusing there costs a contributor a manual fix on a file
    `--fix` would probably have rewritten correctly; missing one writes a
    corrupted file over theirs, so the doubt resolves the same way every time.
    """
    for prop, value in css_declarations(block):
        if prop not in WHITESPACE_PROPERTIES:
            continue
        tokens = value.split()
        if not tokens or any(t in PRESERVING_VALUES for t in tokens):
            return True
        if not all(t in COLLAPSING_VALUES for t in tokens):
            return True
    return False


def unverifiable_reason(html: str, scan: HtmlScan | None = None) -> str | None:
    """Why this rendered HTML is outside what `canonical_html` can judge, or None."""
    scan = scan if scan is not None else HtmlScan(html)
    if any(preserves_whitespace(rule) for rule in scan.css):
        return (
            "a `white-space` CSS declaration can make a source line break visible here, "
            "and comparing rendered HTML cannot see that"
        )
    if scan.unbalanced:
        return (
            f"an unbalanced <{scan.unbalanced[0]}> in the rendered output — a browser preserves the "
            "whitespace after it, so this comparison would collapse a break the reader can see"
        )
    return None


def renders_the_same(before: str, after: str, renderer) -> bool:
    """True if `before` and `after` render to the same thing."""
    return canonical_html(renderer.render(before)) == canonical_html(renderer.render(after))


def unsafe_fix_reason(before: str, after: str, renderer) -> str | None:
    """Why writing `after` over `before` is unsafe, or None when it is safe.

    The two repair classes are checked differently because they promise
    different things. A class-A rejoin promises the rendered output does not
    change, so it is held to exactly that. The class-B repair changes it on
    purpose — a setext heading becomes a paragraph and a thematic break — so it
    is held to the structural rule that a setext heading may disappear but never
    appear.

    Both rest on `canonical_html`, so a file it cannot judge — one whose CSS
    preserves whitespace, or whose rendered HTML leaves a verbatim element open
    — is refused before either check runs.
    """
    joined = analyse(before, repair=(SPLIT_BLOCK,))[1]
    before_html, joined_html = renderer.render(before), renderer.render(joined)
    before_scan, joined_scan = HtmlScan(before_html), HtmlScan(joined_html)
    unverifiable = unverifiable_reason(before_html, before_scan) or unverifiable_reason(joined_html, joined_scan)
    if unverifiable is not None:
        return unverifiable
    if canonical_html(before_html, before_scan) != canonical_html(joined_html, joined_scan):
        return "rejoining its split blocks would change the rendered output"
    diffs = compare_structure(before, after)
    if diffs:
        return "; ".join(diffs)
    return None


# --------------------------------------------------------------------------
# File selection
# --------------------------------------------------------------------------


def write_atomically(path: Path, text: str) -> None:
    """Replace `path`'s contents in one step.

    `Path.write_text` truncates first, so an interruption between the truncate
    and the write leaves a half-written Markdown file — the one outcome this
    tool must never produce. Writing a sibling and renaming over the target
    cannot: the rename either happened or it did not.
    """
    tmp = path.with_name(f".{path.name}.md-wrap-tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


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
        description="Check or fix Markdown soft wrap per ADR-0024.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report violations (default)")
    mode.add_argument(
        "--fix",
        action="store_true",
        help="rewrite files in place, whitespace only; needs markdown-it-py to verify each rewrite",
    )
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument("--files", nargs="+", metavar="PATH", help="check exactly these paths")
    scope.add_argument("--changed", metavar="REF", help="check only the .md files this branch changes against REF")
    scope.add_argument("--allowlist", action="store_true", help="check the agent-context allowlist")
    p.add_argument("--equivalence", metavar="REF", help="compare each selected file against its version at REF")
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
    skipped = [p for p in paths if is_exempt(p)]
    paths = [p for p in paths if not is_exempt(p)]

    if args.equivalence:
        return _run_equivalence(args.equivalence, paths, root)

    renderer = None
    if args.fix:
        renderer = load_renderer()
        if renderer is None:
            print(f"error: {RENDERER_MISSING}", file=sys.stderr)
            return 2

    failures = 0
    fixed_files = 0
    refused = 0
    for rel in paths:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        violations, fixed = analyse(text)
        if args.fix:
            if fixed != text:
                reason = unsafe_fix_reason(text, fixed, renderer)
                if reason is not None:
                    refused += 1
                    print(f"{rel}: REFUSED, not rewritten — {reason}")
                    continue
                write_atomically(path, fixed)
                fixed_files += 1
                print(f"{rel}: fixed {len(violations)} violation(s)")
        else:
            for v in violations:
                print(v.format(rel))
            failures += len(violations)

    scope_name = "allowlist" if args.allowlist else (f"changed vs {args.changed}" if args.changed else "files")
    print(f"\n{len(paths)} file(s) checked ({scope_name}); {len(skipped)} exempt.", file=sys.stderr)
    if args.fix:
        print(f"{fixed_files} file(s) rewritten.", file=sys.stderr)
        print(VERIFICATION_BOUNDARY, file=sys.stderr)
        if refused:
            print(
                f"{refused} file(s) refused: the rewrite would have changed the rendered output, "
                "so it was not written. Soft-wrap those by hand and report the shape.",
                file=sys.stderr,
            )
            return 1
        return 0
    if failures:
        print(f"{failures} violation(s). Run with --fix to rewrite.", file=sys.stderr)
        return 1
    print("No violations.", file=sys.stderr)
    return 0


def _run_equivalence(ref: str, paths: list[str], root: Path) -> int:
    renderer = load_renderer()
    failures = 0
    compared = 0
    for rel in paths:
        path = root / rel
        if not path.exists():
            continue
        try:
            before = git("show", f"{ref}:{rel}")
        except subprocess.CalledProcessError:
            continue  # new file — nothing to compare against
        after = path.read_text(encoding="utf-8")
        compared += 1
        diffs = compare_structure(before, after)
        if renderer is not None:
            unverifiable = unverifiable_reason(renderer.render(before)) or unverifiable_reason(renderer.render(after))
            if unverifiable is not None:
                diffs.append(f"not verifiable by rendering: {unverifiable}")
            elif not renders_the_same(before, after, renderer):
                diffs.append("rendered output changed")
        for d in diffs:
            print(f"{rel}: {d}")
        failures += len(diffs)
    print(f"\n{compared} file(s) compared against {ref}.", file=sys.stderr)
    if renderer is None:
        print(f"Structural comparison only — {RENDERER_MISSING}", file=sys.stderr)
    if failures:
        print(f"{failures} structural difference(s) — the edit was not whitespace-only.", file=sys.stderr)
        return 1
    print("Structurally equivalent: prose, headings, code, links, list items and tables all match.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
