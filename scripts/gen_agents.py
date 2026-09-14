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
0.152.1 consumes neither; see `docs/tooling/codex-parity.md` for the evidence.

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
    """`CLAUDE.md` with its H1 title line dropped (AGENTS.md supplies its own)."""
    lines = read_text(CLAUDE_MD).splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            return "\n".join(lines[index + 1 :]).strip("\n")
    fail("CLAUDE.md has no H1 heading to split on")
    return ""  # unreachable; keeps type checkers happy


def delta_parts() -> tuple[str, str]:
    """The preamble and appendix halves of the delta fragment."""
    text = read_text(DELTA_MD)
    for marker in (PREAMBLE_MARKER, APPENDIX_MARKER):
        if marker not in text:
            fail(f"{DELTA_MD.relative_to(REPO_ROOT)} is missing the marker {marker!r}")
    _, _, after_preamble = text.partition(PREAMBLE_MARKER)
    preamble, _, appendix = after_preamble.partition(APPENDIX_MARKER)
    return preamble.strip("\n"), appendix.strip("\n")


def mirrored_skills() -> list[str]:
    """Skill directory names to mirror, sorted, excludes applied."""
    if not CLAUDE_SKILLS.is_dir():
        fail(f"missing skills directory: {CLAUDE_SKILLS.relative_to(REPO_ROOT)}")
    names = [p.name for p in sorted(CLAUDE_SKILLS.iterdir()) if (p / "SKILL.md").is_file()]
    return [name for name in names if name not in SKILL_EXCLUDES]


def skill_description(name: str) -> str:
    """The `description:` front-matter line of a skill, for the README table."""
    text = (CLAUDE_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"')
            return description.split(". ")[0].rstrip(".")
    return ""


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

Phase 1 launches the same competition workflow from Claude Code and from Codex against the
same repo state (discussion #185, issue #189). Claude Code reads `CLAUDE.md` + `.claude/`;
Codex reads `AGENTS.md` + this directory.

Nothing here is hand-maintained. `python scripts/gen_agents.py` writes it, and
`python scripts/gen_agents.py --check` — asserted by `tests/test_instruction_parity.py` in
CI — fails if it drifts from `.claude/`.

## Mirrored — symlinks, never copies

`.agents/skills/<name>` is a relative symlink to `.claude/skills/<name>`, so a skill has
exactly one body on disk and both harnesses load the same bytes. Codex follows the symlink
and lists the skill under its front-matter `name`.

| Skill | Symlink target | What it is for |
|---|---|---|
{rows}

Claude-Code-only front-matter keys (`allowed-tools`, `argument-hint`) are tolerated by
Codex — a skill carrying them is still listed.

### Not mirrored

| Skill | Why |
|---|---|
{excluded}

## No Codex counterpart

| `.claude/` | Status in `.agents/` | Consequence |
|---|---|---|
| `agents/*.md` (sub-agent definitions) | **absent** — Codex 0.152.1 has no repo-level sub-agent format | Run the review in-session against the same checklist, and say it was not an independent agent. |
| `hooks/*.py` (`guard_tool`, `format_gate`, `audit_event`) | **absent** — Codex hooks are per-user config (`~/.codex/config.toml` / a managed dir), never repo-shipped | Real safety asymmetry: in Codex the deletion / force-push / secret rules are enforced only by reading them, and no `.agent/audit/tool-events.jsonl` trail is written. See *The safety asymmetry* in `AGENTS.md`. |
| `settings.json` (`permissions.allow` / `deny`) | **absent** — Codex approval policy and sandbox come from per-user config and CLI flags | The human sets Codex's approval mode; the repo cannot pre-approve commands for it. |

## Regenerating

```sh
python scripts/gen_agents.py          # rewrite AGENTS.md + .agents/
python scripts/gen_agents.py --check  # verify (what CI runs)
```

The Codex-side evidence and the two-harness smoke check are in
`docs/tooling/codex-parity.md`.
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
    changes: list[str] = []
    AGENTS_SKILLS.mkdir(parents=True, exist_ok=True)
    expected = mirrored_skills()
    for name in expected:
        link = AGENTS_SKILLS / name
        target = f"../../.claude/skills/{name}"
        if link.is_symlink() and str(link.readlink()) == target:
            continue
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target, target_is_directory=True)
        changes.append(f"linked .agents/skills/{name}")
    for entry in sorted(AGENTS_SKILLS.iterdir()):
        if entry.name in expected:
            continue
        if not entry.is_symlink():
            # Never delete real content that someone put here by hand; --check reports it.
            changes.append(f"left .agents/skills/{entry.name} alone (not a symlink — remove it by hand)")
            continue
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
