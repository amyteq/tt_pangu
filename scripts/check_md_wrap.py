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
backslash — is authored intent, so the line after it is left alone too.

`--fix` is whitespace only. It rejoins a split block onto the line above with a
single space, and inserts the missing blank line above a `---`. It never alters
words, punctuation, link targets or block structure, and on an already-compliant
file its output is byte-identical to its input.

Usage:
  python scripts/check_md_wrap.py --allowlist              # the agent-context set
  python scripts/check_md_wrap.py --changed origin/main    # only what this branch touches
  python scripts/check_md_wrap.py --files a.md b.md        # exactly these
  python scripts/check_md_wrap.py --fix --allowlist        # rewrite in place
  python scripts/check_md_wrap.py --equivalence origin/main --allowlist

Exactly one scoping mode is required. There is deliberately no "whole
repository" mode: ADR-0024's enforcement is scoped to changed files plus the
allowlist, and the historical backfill was declined (issue #210).

Exit codes:
  0 — no violations (or, with --fix, everything fixed)
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

FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
ATX_RE = re.compile(r"^ {0,3}#{1,6}(?: |\t|$)")
HR_DASH_RE = re.compile(r"^ {0,3}-{3,}[ \t]*$")
HR_OTHER_RE = re.compile(r"^ {0,3}(?:\*[ \t]*){3,}$|^ {0,3}(?:_[ \t]*){3,}$")
LIST_RE = re.compile(r"^ *(?:[-*+]|\d{1,9}[.)])(?: |\t|$)")
TABLE_RE = re.compile(r"^ {0,3}\|")
HTML_RE = re.compile(r"^ {0,3}<")
LINKDEF_RE = re.compile(r"^ {0,3}\[[^\]]+\]:")
QUOTE_RE = re.compile(r"^ {0,3}> ?")
HARD_BREAK_RE = re.compile(r"(?:  +|\\)$")

# CommonMark HTML blocks do not all end the same way. Types 1-5 run to their own
# terminator and may contain blank lines — an `<!-- ... -->` comment spanning a
# blank line is the common case here, and ending it early would let the engine
# reflow text it promised never to inspect. Types 6 and 7 end at a blank line.
HTML_CDATA_RE = re.compile(r"^ {0,3}<!\[CDATA\[")
HTML_COMMENT_RE = re.compile(r"^ {0,3}<!--")
HTML_PI_RE = re.compile(r"^ {0,3}<\?")
HTML_DECL_RE = re.compile(r"^ {0,3}<![A-Za-z]")
HTML_RAW_RE = re.compile(r"^ {0,3}<(script|pre|style|textarea)\b", re.IGNORECASE)


def html_block_terminator(content: str) -> str | None:
    """The string that closes this HTML block, or None if a blank line closes it."""
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


def indent_of(content: str) -> int:
    return len(content) - len(content.lstrip(" "))


def is_block_start(content: str) -> bool:
    """True if this line begins a new block rather than continuing the one above."""
    return bool(
        ATX_RE.match(content)
        or FENCE_RE.match(content)
        or HR_DASH_RE.match(content)
        or HR_OTHER_RE.match(content)
        or LIST_RE.match(content)
        or TABLE_RE.match(content)
        or HTML_RE.match(content)
        or LINKDEF_RE.match(content)
    )


def leaves_block_open(content: str) -> bool:
    """True if a following non-blank line would continue this line's block.

    Paragraph text, a list item and a table row are all continuable. A heading,
    a thematic break and a link reference definition are complete on their line.
    """
    if ATX_RE.match(content) or HR_DASH_RE.match(content) or HR_OTHER_RE.match(content):
        return False
    if LINKDEF_RE.match(content) or HTML_RE.match(content):
        return False
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


def analyse(text: str) -> tuple[list[Violation], str]:
    """Return (violations, fixed_text). `fixed_text` differs only in whitespace."""
    had_trailing_newline = text.endswith("\n")
    lines = text[:-1].split("\n") if had_trailing_newline else text.split("\n")

    out: list[str] = []
    violations: list[Violation] = []
    fence: str | None = None
    in_frontmatter = False
    prev_open = False
    prev_depth = 0

    i = 0
    while i < len(lines):
        raw = lines[i]

        # YAML frontmatter: only when it opens on the very first line.
        if i == 0 and raw.strip() == "---":
            in_frontmatter = True
            out.append(raw)
            i += 1
            continue
        if in_frontmatter:
            out.append(raw)
            if raw.strip() == "---":
                in_frontmatter = False
            i += 1
            continue

        depth, content = split_quote(raw)

        # Inside a fenced block: copy verbatim until the fence closes.
        if fence is not None:
            out.append(raw)
            if content.strip().startswith(fence):
                fence = None
            i += 1
            prev_open = False
            continue

        m = FENCE_RE.match(content)
        if m:
            fence = m.group("fence")
            out.append(raw)
            i += 1
            prev_open = False
            prev_depth = depth
            continue

        if not content.strip():
            out.append(raw)
            i += 1
            prev_open = False
            prev_depth = depth
            continue

        # An indented code block cannot interrupt a paragraph, so it only starts
        # where nothing is open. Copy it out until a blank line.
        if not prev_open and indent_of(content) >= 4:
            out.append(raw)
            i += 1
            prev_depth = depth
            continue

        # An HTML block is copied verbatim to its end condition.
        if not prev_open and HTML_RE.match(content):
            terminator = html_block_terminator(content)
            while i < len(lines):
                out.append(lines[i])
                body = split_quote(lines[i])[1]
                if terminator is None:
                    if not body.strip():
                        break
                elif terminator in body:
                    break
                i += 1
            i += 1
            prev_open = False
            prev_depth = depth
            continue

        # Class B — a thematic break that CommonMark will read as a setext H2.
        if HR_DASH_RE.match(content) and prev_open:
            violations.append(Violation(i + 1, "setext-rule", SETEXT_MSG))
            out.append("> " * depth if depth else "")
            out.append(raw)
            i += 1
            prev_open = False
            prev_depth = depth
            continue

        # Class A — a block continued on the next physical line.
        if prev_open and depth == prev_depth and not is_block_start(content):
            if HARD_BREAK_RE.search(out[-1]):
                # An explicit hard break is authored intent; joining would change
                # rendering. Leave it, and leave the line it introduces.
                out.append(raw)
                i += 1
                prev_open = True
                continue
            violations.append(Violation(i + 1, "split-block", SPLIT_MSG))
            out[-1] = out[-1].rstrip() + " " + content.strip()
            i += 1
            prev_open = True
            continue

        out.append(raw)
        prev_open = leaves_block_open(content)
        prev_depth = depth
        i += 1

    fixed = "\n".join(out)
    if had_trailing_newline:
        fixed += "\n"
    return violations, fixed


# --------------------------------------------------------------------------
# Structural equivalence
# --------------------------------------------------------------------------

INLINE_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)")
CODE_SPAN_RE = re.compile(r"`[^`]*`")


def structure(text: str) -> dict:
    """Extract wrap-invariant structure, for before/after comparison.

    The text stream drops `|` before comparing. Rejoining a split table row moves
    its tail from a prose line into a table cell, which is a repair rather than a
    content change, and only pipe-blindness makes the two states comparable.
    """
    lines = text.split("\n")
    fence: str | None = None
    in_frontmatter = False
    stream: list[str] = []
    headings: list[tuple[int, str]] = []
    code: list[str] = []
    links: list[str] = []
    list_items = 0
    tables: list[tuple[int, int]] = []
    table_rows: list[int] = []

    def close_table() -> None:
        if table_rows:
            tables.append((len(table_rows), max(table_rows)))
            table_rows.clear()

    for i, raw in enumerate(lines):
        if i == 0 and raw.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if raw.strip() == "---":
                in_frontmatter = False
            continue
        _, content = split_quote(raw)
        if fence is not None:
            if content.strip().startswith(fence):
                fence = None
            else:
                code.append(content)
            continue
        m = FENCE_RE.match(content)
        if m:
            fence = m.group("fence")
            close_table()
            continue
        if TABLE_RE.match(content):
            table_rows.append(len(content.strip().strip("|").split("|")))
        else:
            close_table()
        if not content.strip():
            continue
        stream.append(content)
        links.extend(m.group("target") for m in INLINE_LINK_RE.finditer(content))
        h = re.match(r"^ {0,3}(#{1,6})(?: +)(.*?)\s*#*\s*$", content)
        if h:
            headings.append((len(h.group(1)), " ".join(h.group(2).split())))
            continue
        if LIST_RE.match(content):
            list_items += 1
    close_table()

    return {
        "prose": " ".join(" ".join(stream).replace("|", " ").split()),
        "headings": headings,
        "code": "\n".join(code),
        "links": sorted(links),
        "list_items": list_items,
        "tables": tables,
    }


def compare_structure(before: str, after: str) -> list[str]:
    """Differences that mean the reflow changed more than whitespace."""
    a, b = structure(before), structure(after)
    diffs: list[str] = []
    if a["prose"] != b["prose"]:
        diffs.append("prose text changed (not a whitespace-only edit)")
    if a["headings"] != b["headings"]:
        diffs.append(f"heading sequence changed: {len(a['headings'])} -> {len(b['headings'])}")
    if a["code"] != b["code"]:
        diffs.append("fenced code content changed")
    if a["links"] != b["links"]:
        diffs.append("link targets changed")
    if a["list_items"] != b["list_items"]:
        diffs.append(f"list-item count changed: {a['list_items']} -> {b['list_items']}")
    if a["tables"] != b["tables"]:
        # Rejoining a split row legitimately repairs a table that was broken
        # before, so a dimension change is only a defect when the result is
        # still malformed. A well-formed table has one column count throughout.
        malformed_before = any(rows > 1 and cols_inconsistent for rows, cols_inconsistent in _table_health(before))
        malformed_after = any(rows > 1 and cols_inconsistent for rows, cols_inconsistent in _table_health(after))
        if malformed_after or not malformed_before:
            diffs.append(f"table dimensions changed: {a['tables']} -> {b['tables']}")
    return diffs


def _table_health(text: str) -> list[tuple[int, bool]]:
    """Per table: (row count, whether its rows disagree on column count)."""
    out: list[tuple[int, bool]] = []
    fence: str | None = None
    widths: list[int] = []
    for raw in text.split("\n"):
        _, content = split_quote(raw)
        if fence is not None:
            if content.strip().startswith(fence):
                fence = None
            continue
        m = FENCE_RE.match(content)
        if m:
            fence = m.group("fence")
            continue
        if TABLE_RE.match(content):
            widths.append(len(content.strip().strip("|").split("|")))
            continue
        if widths:
            out.append((len(widths), len(set(widths)) > 1))
            widths = []
    if widths:
        out.append((len(widths), len(set(widths)) > 1))
    return out


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
        description="Check or fix Markdown soft wrap per ADR-0024.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report violations (default)")
    mode.add_argument("--fix", action="store_true", help="rewrite files in place, whitespace only")
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

    failures = 0
    fixed_files = 0
    for rel in paths:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        violations, fixed = analyse(text)
        if args.fix:
            if fixed != text:
                path.write_text(fixed, encoding="utf-8")
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
        return 0
    if failures:
        print(f"{failures} violation(s). Run with --fix to rewrite.", file=sys.stderr)
        return 1
    print("No violations.", file=sys.stderr)
    return 0


def _run_equivalence(ref: str, paths: list[str], root: Path) -> int:
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
        for d in diffs:
            print(f"{rel}: {d}")
        failures += len(diffs)
    print(f"\n{compared} file(s) compared against {ref}.", file=sys.stderr)
    if failures:
        print(f"{failures} structural difference(s) — the edit was not whitespace-only.", file=sys.stderr)
        return 1
    print("Structurally equivalent: prose, headings, code, links, list items and tables all match.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
