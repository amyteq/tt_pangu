#!/usr/bin/env python3
"""The provenance check both issue-189 evidence writers run before they write.

Three consecutive review rounds found `docs/tooling/codex-parity.md` claiming a
guarantee the scripts did not implement: first neither writer compared its commit
argument to HEAD, then the probe renderer never checked the working tree at all
while the doc said "both writers check this". Two scripts meant two chances to be
wrong, so the check lives here once and both call it.

What a caller gets:

* `verify_commit_is_head` — the named commit is HEAD, so the evidence header
  describes the state the harness actually read;
* `verify_tree_matches_commit` — nothing differs from that commit except the
  evidence files the writers themselves produce. Untracked files count: a new
  `.agents/skills/<name>/SKILL.md` is loaded by Codex and inflates a measured
  skill count while never appearing in `git diff`.

`EVIDENCE_OUTPUTS` is an explicit list of the three files the writers emit, not
the evidence directory. Exempting the directory would exempt `smoke-prompt.txt`,
which is an *input* — the writers stamp "Prompt: … unedited" into their headers,
and a modified prompt is precisely the thing that claim must not survive.

What none of this can check: which binary produced a dump or an answer file, and
whether an answer file came from the run the caller believes it did.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_PREFIX = "docs/evidence/issue-189-codex-parity/"

EVIDENCE_OUTPUTS = frozenset(
    {
        EVIDENCE_PREFIX + "loader-probe.txt",
        EVIDENCE_PREFIX + "smoke-codex.md",
        EVIDENCE_PREFIX + "smoke-claude.md",
    }
)


def fail(tool: str, message: str) -> None:
    sys.exit(f"{tool}: {message}")


def git(tool: str, *args: str, root: Path = REPO_ROOT) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        fail(tool, f"`git {' '.join(args)}` failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _status_paths(tool: str, root: Path) -> list[tuple[str, str]]:
    """`(status, path)` for every difference from HEAD, untracked files included."""
    # Read porcelain unstripped: an unstaged modification is reported as " M path",
    # and stripping the output would eat that leading space and with it the first
    # character of the first path.
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(tool, f"`git status` failed: {result.stderr.strip()}")
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status, path = line[:2].strip(), line[3:]
        # A rename reads `old -> new`; the new name is the one on disk now.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        # git quotes paths containing spaces or non-ASCII bytes.
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        entries.append((status, path))
    return entries


def verify_commit_is_head(tool: str, commit: str, root: Path = REPO_ROOT) -> str:
    """Resolve `commit`, insisting it is HEAD. Returns the short SHA."""
    head = git(tool, "rev-parse", "HEAD", root=root)
    named = git(tool, "rev-parse", f"{commit}^{{commit}}", root=root)
    if head != named:
        fail(
            tool,
            f"refusing to write: {commit} resolves to {named[:7]}, but HEAD is {head[:7]}.\n"
            "  The harness read the working tree, so the header would name a commit it never saw.",
        )
    return git(tool, "rev-parse", "--short", commit, root=root)


def verify_tree_matches_commit(
    tool: str,
    commit: str,
    exempt: frozenset[str] = EVIDENCE_OUTPUTS,
    root: Path = REPO_ROOT,
) -> None:
    """Refuse unless the tree matches `commit` apart from the writers' own outputs."""
    dirty = [f"{status:>2} {path}" for status, path in _status_paths(tool, root) if path not in exempt]
    if dirty:
        fail(
            tool,
            f"refusing to write: the worktree differs from {commit} in files that are not "
            "evidence outputs, so the header would not describe what the harness read:\n  "
            + "\n  ".join(dirty)
            + "\n  (`"
            + EVIDENCE_PREFIX
            + "smoke-prompt.txt` is an input and is deliberately not exempt.)",
        )
