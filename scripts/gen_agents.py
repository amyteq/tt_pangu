#!/usr/bin/env python3
"""Generate `AGENTS.md` and the `.agents/` mirror from `CLAUDE.md` + a Codex delta.

Two harnesses run the same competition workflow against this repo (phase 1,
discussion #185 / issue #189): Claude Code reads `CLAUDE.md` + `.claude/`, Codex
reads `AGENTS.md` + `.agents/`. Two hand-maintained copies of the rule set is the
drift this script exists to prevent, so:

  AGENTS.md = docs/instructions/agents-delta.md   (PREAMBLE part)
            + CLAUDE.md body, verbatim            (the shared rules)
            + docs/instructions/agents-delta.md   (APPENDIX part)

  .agents/skills/<name> -> ../../.claude/skills/<name>   (symlink per skill)
  .agents/README.md                                      (generated inventory)

`.claude/agents/` and `.claude/hooks/` are deliberately NOT mirrored — Codex
consumes neither; see `docs/tooling/codex-parity.md` for the evidence and the
version it was checked against (CODEX_VERSION below).

Usage:
  python scripts/gen_agents.py            # write AGENTS.md and .agents/
  python scripts/gen_agents.py --check    # verify both are current; never writes

Exit codes:
  0 — generated, or --check found no drift
  1 — input error (a source file is missing or malformed)
  2 — --check found drift (regenerate and commit)
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
DELTA_MD = REPO_ROOT / "docs" / "instructions" / "agents-delta.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
AGENTS_DIR = REPO_ROOT / ".agents"
AGENTS_SKILLS = AGENTS_DIR / "skills"
AGENTS_README = AGENTS_DIR / "README.md"

PREAMBLE_MARKER = "<!-- part: preamble -->"
APPENDIX_MARKER = "<!-- part: appendix -->"

# The Codex release the claims in the delta and in `.agents/README.md` were verified
# against. Substituted for `{{CODEX_VERSION}}` so there is one place to bump after
# re-running the probe (`docs/tooling/codex-parity.md` § After a Codex upgrade).
CODEX_VERSION = "0.154.0"
VERSION_TOKEN = "{{CODEX_VERSION}}"
# Any literal version in the delta, not just the current one: a stale `0.153.0`
# beside a live token produces one file claiming two releases were probed. The
# delta is short, hand-written and Codex-specific, so a bare `x.y.z` there is a
# version claim — nothing else in it legitimately looks like one.
VERSION_LITERAL = re.compile(r"\d+\.\d+\.\d+")

# The only front-matter keys this script reads. Everything else in a skill's front
# matter (`allowed-tools`, `tags`, …) may take any shape YAML allows, because
# nothing here parses it.
READ_KEYS = ("name", "description")

# `CLAUDE.md`'s title block: everything above its first `## ` section. It is
# CLAUDE.md's own front matter ("this file is authoritative"), not a shared rule,
# so AGENTS.md supplies its own header instead. Matched exactly rather than by
# shape — a new safety rule written as a blockquote here would otherwise be
# dropped silently, which is exactly the failure this generator exists to prevent.
EXPECTED_TITLE_BLOCK = (
    "# tt_pangu — Agent Project Instructions",
    "> Canonical language: **English**. This file is authoritative; "
    "[`CLAUDE_zh.md`](./CLAUDE_zh.md) is a Chinese mirror for human reading only.",
)

# Skills that are NOT mirrored, with the reason shown in `.agents/README.md`.
# Everything else under `.claude/skills/` is mirrored automatically, so the
# `kaggle-* -> kg-*` rename (issue #192) needs no edit here.
SKILL_EXCLUDES: dict[str, str] = {
    "save-log": "Claude-Code-only — exports a Claude Code session transcript via `claude-code-log`.",
}

BANNER = """<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Sources: CLAUDE.md (shared rules) + docs/instructions/agents-delta.md (Codex delta).
     Regenerate: python scripts/gen_agents.py
     Verify:     python scripts/gen_agents.py --check   (also asserted by tests/test_instruction_parity.py)
-->"""

README_BANNER = """<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Sources: .claude/skills/ + the excludes in scripts/gen_agents.py.
     Regenerate: python scripts/gen_agents.py
     Verify:     python scripts/gen_agents.py --check   (also asserted by tests/test_instruction_parity.py)
-->"""

SHARED_HEADING = """# Shared rules

Generated verbatim from `CLAUDE.md`. Do not edit here — edit `CLAUDE.md`."""


def fail(message: str) -> None:
    print(f"gen_agents: error: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(f"missing source file: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def claude_body() -> str:
    """`CLAUDE.md` from its first `## ` section onwards.

    The title block above it — the H1 and CLAUDE.md's own "this file is
    authoritative" language banner — is CLAUDE.md's front matter, not a shared
    rule: copied into AGENTS.md it would claim the generated file is the
    authority. AGENTS.md supplies its own header from the delta preamble.

    Skipping a prefix silently is how a rule goes missing, so the skipped lines
    must be `EXPECTED_TITLE_BLOCK` exactly. Matching by shape is not enough: a
    blockquote and an H1 are legal shapes for a new rule as well as for a title,
    so any edit above the first `## ` stops generation and asks a human whether
    the new line belongs in the delta preamble.
    """
    lines = read_text(CLAUDE_MD).splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## "):
            skipped = tuple(entry.strip() for entry in lines[:index] if entry.strip())
            if skipped != EXPECTED_TITLE_BLOCK:
                fail(
                    "CLAUDE.md's title block (everything above its first `## ` section) is not what\n"
                    "  this generator was told to drop, so generating AGENTS.md would silently change\n"
                    "  what Codex reads.\n"
                    f"    expected: {list(EXPECTED_TITLE_BLOCK)}\n"
                    f"    found:    {list(skipped)}\n"
                    "  If the new line is a rule, move it into a `## ` section — it then reaches both\n"
                    "  harnesses. If it is CLAUDE.md front matter, give AGENTS.md its equivalent in\n"
                    "  docs/instructions/agents-delta.md and update EXPECTED_TITLE_BLOCK here."
                )
            return "\n".join(lines[index:]).strip("\n")
    fail("CLAUDE.md has no `## ` section to split on")
    return ""  # unreachable; keeps type checkers happy


def delta_parts() -> tuple[str, str]:
    """The preamble and appendix halves of the delta fragment."""
    text = read_text(DELTA_MD)
    relative = DELTA_MD.relative_to(REPO_ROOT)
    for marker in (PREAMBLE_MARKER, APPENDIX_MARKER):
        count = text.count(marker)
        if count != 1:
            fail(
                f"{relative} contains the marker {marker!r} {count} times; expected exactly once.\n"
                "  With none the part is empty; with more than one only the first split is used and\n"
                "  the rest of that part is silently dropped."
            )
    if text.index(PREAMBLE_MARKER) > text.index(APPENDIX_MARKER):
        fail(
            f"{relative} puts {APPENDIX_MARKER!r} before {PREAMBLE_MARKER!r}.\n"
            "  The preamble is everything between them, so reversed markers would empty it."
        )
    # Everything before the first marker is dropped, exactly as the CLAUDE.md title
    # block is — and for the same reason it must be checked rather than assumed: a
    # Codex-only safety rule written above the marker would vanish from AGENTS.md
    # while generation and `--check` both stayed green.
    prefix = text[: text.index(PREAMBLE_MARKER)].strip()
    if not (prefix.startswith("<!--") and prefix.endswith("-->")):
        fail(
            f"{relative} has content before {PREAMBLE_MARKER!r} that is not the single HTML\n"
            "  comment header, so generating AGENTS.md would silently drop it:\n"
            f"    {prefix[:120]!r}\n"
            f"  Rules belong after {PREAMBLE_MARKER!r} (preamble) or {APPENDIX_MARKER!r} (appendix)."
        )
    if prefix.count("-->") != 1:
        fail(
            f"{relative} has more than one comment before {PREAMBLE_MARKER!r}; anything in the\n"
            "  gap between them would be dropped silently. Keep a single header comment."
        )
    # The single-source guarantee is only real if the delta asks for the version
    # instead of stating it. Both halves of the contract are checked, because a
    # silent bypass here regenerates cleanly and `--check` stays green.
    if VERSION_TOKEN not in text:
        fail(
            f"{relative} contains no {VERSION_TOKEN} token.\n"
            "  The Codex version AGENTS.md and .agents/README.md advertise comes from CODEX_VERSION\n"
            "  in this script; a delta that names no version has lost that link."
        )
    literal = VERSION_LITERAL.search(text)
    if literal:
        fail(
            f"{relative} hard-codes the version {literal.group(0)!r}.\n"
            f"  Write {VERSION_TOKEN} instead — a literal here survives a CODEX_VERSION bump and\n"
            "  quietly tells Codex it was verified against a release it was not. Beside a live\n"
            "  token it makes one file claim two different releases were probed.\n"
            "  If a non-Codex version genuinely belongs in the delta, narrow VERSION_LITERAL here."
        )
    _, _, after_preamble = text.partition(PREAMBLE_MARKER)
    preamble, _, appendix = after_preamble.partition(APPENDIX_MARKER)
    substituted = (part.strip("\n").replace(VERSION_TOKEN, CODEX_VERSION) for part in (preamble, appendix))
    return tuple(substituted)  # type: ignore[return-value]


def skill_front_matter(name: str) -> dict[str, str]:
    """The `name` / `description` keys of a skill's YAML front matter.

    Deliberately not a YAML parser: skills are a flat `key: value` block and a
    dependency here would have to be installed wherever `--check` runs, CI
    included. That makes the supported subset a contract, so anything outside it
    is reported rather than guessed at — a folded scalar read as the literal `>`
    would put that character in `.agents/README.md` and `--check` would agree.

    The subset is defined by what the *loaders* accept, not by what PyYAML does,
    and the two differ in one measured place: a plain scalar containing `: `
    (`description: Review: check files`) is a YAML `ScannerError`, yet Codex
    reads it and advertises exactly the value this reader extracts. Probed
    directly on codex-cli 0.154.0 with a fixture skill, and two shipped skills
    depend on it — `ctf-sandbox` and `kg-experiment` both carry a colon
    in their description and both appear in the committed loader dump. Rejecting
    that shape would stop generation for skills both harnesses load today, so it
    is accepted on purpose; `tests/test_instruction_parity.py` pins the evidence.
    The shapes Codex really does drop — a sequence or a nested mapping under a
    key that already has a scalar — are rejected below, and were probed the same
    way: neither fixture skill appeared in the dump at all.
    """
    relative = f".claude/skills/{name}/SKILL.md"
    lines = (CLAUDE_SKILLS / name / "SKILL.md").read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        fail(f"{relative} does not open with a `---` front-matter block")
    fields: dict[str, str] = {}
    previous_key = ""
    previous_value = ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        # A comment is never a continuation and never a key, at any indentation.
        if line.strip().startswith("#"):
            continue
        stripped = line.strip()
        if not stripped:
            continue
        # Classify by structure first. Testing for a colon before testing for a
        # continuation is what let `- Bash: true` through as a key named `- Bash`,
        # and what let an indented `child: value` through unexamined.
        is_continuation = line.startswith((" ", "\t")) or stripped.startswith("-")
        if is_continuation:
            # Under `name:`/`description:` a continuation means the value spans
            # lines, and reading only the first would truncate it.
            if previous_key in READ_KEYS:
                fail(
                    f"{relative} front matter continues `{previous_key}:` onto another line.\n"
                    f"    {stripped[:80]!r}\n"
                    "  This reader supports single-line values for that key — write it as one line."
                )
            # A sequence or nested mapping is only YAML under a key with no scalar
            # value of its own: `tags:` then `- logging` is a list, but
            # `allowed-tools: Read` then `- Bash` (or an indented `child: value`)
            # is a parse error, and Codex drops that skill while this reader
            # carried on and .agents/README.md advertised it.
            if previous_value:
                fail(
                    f"{relative} front matter continues `{previous_key}:`, which already has a "
                    "value on its own line.\n"
                    f"    {stripped[:80]!r}\n"
                    "  YAML cannot read a scalar and a nested block for one key, so Codex would "
                    "drop the skill entirely while this reader still advertised it."
                )
            if not previous_key:
                fail(f"{relative} front matter opens with a continuation, before any key.\n    {stripped[:80]!r}")
            continue
        # Not indented and not a list item, so it must be a mapping key.
        if ":" not in line:
            fail(
                f"{relative} front matter has a line that is not `key: value`, a list item, "
                "or a comment.\n"
                f"    {stripped[:80]!r}\n"
                "  YAML rejects a bare scalar between mapping keys, so Codex would drop the "
                "skill entirely while this reader still advertised it."
            )
        key, _, raw = line.partition(":")
        key = key.strip()
        value = raw.strip()
        previous_key = key
        previous_value = value
        if key in READ_KEYS:
            if key in fields:
                fail(
                    f"{relative} front matter defines `{key}:` twice.\n"
                    "  YAML loaders disagree about which wins; say it once."
                )
            if not value:
                fail(
                    f"{relative} front matter gives `{key}:` no value on its own line.\n"
                    "  Multi-line values are not supported here — write it as one line."
                )
            if value[0] in "|>&*!":
                fail(
                    f"{relative} front matter writes `{key}:` starting with YAML {value[0]!r} "
                    "(a block scalar, anchor, alias, or tag).\n"
                    "  This reader supports single-line plain or quoted values only — write it as one line."
                )
            closer = {"[": "]", "{": "}"}.get(value[0])
            if closer and not value.endswith(closer):
                fail(
                    f"{relative} front matter opens `{key}:` with {value[0]!r} and does not close it "
                    "on the same line.\n"
                    "  A real YAML parser rejects this outright; a skill Codex cannot load would "
                    "still be advertised in .agents/README.md."
                )
            if value[0] in "\"'" and not value.endswith(value[0]):
                fail(
                    f"{relative} front matter opens `{key}:` with {value[0]!r} and does not close it "
                    "on the same line.\n"
                    "  This reader supports single-line values only — write it as one line."
                )
        fields[key] = value.strip('"').strip("'")
    else:
        fail(f"{relative} front matter is never closed by a `---` line")
    for required in ("name", "description"):
        if not fields.get(required):
            fail(f"{relative} front matter has no `{required}:`")
    return fields


def mirrored_skills() -> list[str]:
    """Skill directory names to mirror, sorted, excludes applied.

    Also validates the inventory, because the mirror publishes it to Codex: a
    skill whose front-matter `name` disagrees with its directory is advertised
    under one identity and symlinked under another, and a stale exclude renders
    a phantom row in `.agents/README.md` that nothing else would catch.
    """
    if not CLAUDE_SKILLS.is_dir():
        fail(f"missing skills directory: {CLAUDE_SKILLS.relative_to(REPO_ROOT)}")
    present = [p.name for p in sorted(CLAUDE_SKILLS.iterdir()) if (p / "SKILL.md").is_file()]
    for stale in sorted(set(SKILL_EXCLUDES) - set(present)):
        fail(
            f"SKILL_EXCLUDES names {stale!r}, which is not a skill under .claude/skills/.\n"
            "  A renamed or retired skill leaves a phantom 'Not mirrored' row in .agents/README.md —\n"
            "  drop the entry, or point it at the new name."
        )
    declared: dict[str, str] = {}
    for name in present:
        declared_name = skill_front_matter(name)["name"]
        if declared_name != name:
            fail(
                f".claude/skills/{name}/SKILL.md declares `name: {declared_name}` but lives in {name}/.\n"
                "  Codex lists a skill under its front-matter name, so the two must agree."
            )
        if declared_name in declared:
            fail(f"two skills both declare `name: {declared_name}` ({declared[declared_name]}, {name})")
        declared[declared_name] = name
    return [name for name in present if name not in SKILL_EXCLUDES]


def skill_description(name: str) -> str:
    """First sentence of a skill's description, escaped for a markdown table."""
    description = skill_front_matter(name)["description"]
    return description.split(". ")[0].rstrip(".").replace("|", "\\|")


def render_agents_md() -> str:
    preamble, appendix = delta_parts()
    sections = [BANNER, preamble, "---", SHARED_HEADING, claude_body(), "---", appendix]
    return "\n\n".join(sections).rstrip("\n") + "\n"


def render_agents_readme() -> str:
    skills = mirrored_skills()
    rows = "\n".join(f"| `{name}` | `../../.claude/skills/{name}` | {skill_description(name)} |" for name in skills)
    excluded = "\n".join(f"| `{name}` | {reason} |" for name, reason in sorted(SKILL_EXCLUDES.items()))
    return f"""{README_BANNER}

# `.agents/` — the Codex-side mirror of `.claude/`

Phase 1 launches the same competition workflow from Claude Code and from Codex against the same repo state (discussion #185, issue #189). Claude Code reads `CLAUDE.md` + `.claude/`; Codex reads `AGENTS.md` + this directory.

Nothing here is hand-maintained. `python scripts/gen_agents.py` writes it, and `python scripts/gen_agents.py --check` — asserted by `tests/test_instruction_parity.py` in CI — fails if it drifts from `.claude/`.

## Mirrored — symlinks, never copies

`.agents/skills/<name>` is a relative symlink to `.claude/skills/<name>`, so a skill has exactly one body on disk and both harnesses load the same bytes. Codex follows the symlink and lists the skill under its front-matter `name`.

| Skill | Symlink target | What it is for |
|---|---|---|
{rows}

Claude-Code-only front-matter keys (`allowed-tools`, `argument-hint`) are tolerated by Codex — a skill carrying them is still listed.

### Not mirrored

| Skill | Why |
|---|---|
{excluded}

## No Codex counterpart

| `.claude/` | Status in `.agents/` | Consequence |
|---|---|---|
| `agents/*.md` (sub-agent definitions) | **absent** — Codex {CODEX_VERSION} has no repo-level sub-agent format | Run the review in-session against the same checklist, and say it was not an independent agent. |
| `hooks/*.py` (`guard_tool`, `format_gate`, `audit_event`) | **absent** — Codex hooks are per-user config (`~/.codex/config.toml` / a managed dir), never repo-shipped | Real safety asymmetry: in Codex the deletion / force-push / secret rules are enforced only by reading them, and no `.agent/audit/tool-events.jsonl` trail is written. See *The safety asymmetry* in `AGENTS.md`. |
| `settings.json` (`permissions.allow` / `deny`) | **absent** — Codex approval policy and sandbox come from per-user config and CLI flags | The human sets Codex's approval mode; the repo cannot pre-approve commands for it. |

## Regenerating

```sh
python scripts/gen_agents.py          # rewrite AGENTS.md + .agents/
python scripts/gen_agents.py --check  # verify (what CI runs)
```

The Codex-side evidence and the two-harness smoke check are in `docs/tooling/codex-parity.md`.
"""


def check_symlinks() -> list[str]:
    """Drift between `.agents/skills/` and the expected symlink set."""
    problems: list[str] = []
    expected = mirrored_skills()
    for name in expected:
        link = AGENTS_SKILLS / name
        target = f"../../.claude/skills/{name}"
        if not link.is_symlink():
            problems.append(f".agents/skills/{name} is missing or not a symlink")
        elif str(link.readlink()) != target:
            problems.append(f".agents/skills/{name} points at {link.readlink()}, expected {target}")
        elif not (link / "SKILL.md").is_file():
            problems.append(f".agents/skills/{name} does not resolve to a SKILL.md")
    if AGENTS_SKILLS.is_dir():
        for entry in sorted(AGENTS_SKILLS.iterdir()):
            if entry.name not in expected:
                problems.append(f".agents/skills/{entry.name} is stale (not in .claude/skills, or excluded)")
    return problems


def write_symlinks() -> list[str]:
    """Bring `.agents/skills/` to the expected symlink set.

    A real directory where a symlink belongs is never deleted — it may be
    someone's unmirrored work — but it is also never silently tolerated, since
    `--check` would reject it on the next run and the write would have exited 0.
    Both cases stop with a message naming the manual cleanup.
    """
    changes: list[str] = []
    AGENTS_SKILLS.mkdir(parents=True, exist_ok=True)
    expected = mirrored_skills()
    for name in expected:
        link = AGENTS_SKILLS / name
        target = f"../../.claude/skills/{name}"
        if link.is_symlink() and str(link.readlink()) == target:
            continue
        if not link.is_symlink() and link.exists():
            fail(
                f".agents/skills/{name} is a real {'directory' if link.is_dir() else 'file'}, not a symlink.\n"
                "  The mirror never deletes real content. Move or remove it by hand, then re-run."
            )
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target, target_is_directory=True)
        changes.append(f"linked .agents/skills/{name}")
    for entry in sorted(AGENTS_SKILLS.iterdir()):
        if entry.name in expected:
            continue
        if not entry.is_symlink():
            fail(
                f".agents/skills/{entry.name} is not a symlink and is not a mirrored skill.\n"
                "  The mirror never deletes real content. Move or remove it by hand, then re-run."
            )
        entry.unlink()
        changes.append(f"removed stale .agents/skills/{entry.name}")
    return changes


def diff(path: Path, expected: str) -> str:
    actual = path.read_text(encoding="utf-8") if path.is_file() else ""
    name = str(path.relative_to(REPO_ROOT))
    return "".join(
        difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=f"{name} (on disk)",
            tofile=f"{name} (expected)",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify the generated files are current; write nothing")
    args = parser.parse_args()

    targets = [(AGENTS_MD, render_agents_md()), (AGENTS_README, render_agents_readme())]

    if args.check:
        problems = [d for d in (diff(path, expected) for path, expected in targets) if d]
        problems += check_symlinks()
        if problems:
            print("gen_agents: --check failed — regenerate with `python scripts/gen_agents.py`:\n", file=sys.stderr)
            for problem in problems:
                print(problem, file=sys.stderr)
            return 2
        print("gen_agents: AGENTS.md and .agents/ are current.")
        return 0

    for path, expected in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.read_text(encoding="utf-8") == expected:
            continue
        path.write_text(expected, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    for change in write_symlinks():
        print(change)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
