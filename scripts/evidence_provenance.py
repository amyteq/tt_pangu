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
  skill count while never appearing in `git diff`;
* `verify_paths_exist` — a file the header names as an *input* is actually there
  at that commit, as a **regular file**. The check above closes on "nothing
  differs", which a commit that never contained the file satisfies trivially, so
  a clean tree let the smoke writer stamp "Prompt: … verified unmodified" over a
  file that was not there at all (#218). A directory or a symlink does not count:
  git stores a symlink as a blob, so a committed symlink pointing outside the
  commit would pass an object-type test while its content stayed free to change
  under a clean worktree.

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
from collections.abc import Iterable
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


def _status_paths(tool: str, root: Path) -> list[tuple[str, tuple[str, ...]]]:
    """`(status, paths)` for every difference from HEAD, untracked files included.

    `paths` holds one path, or two for a rename — see the comment on the split below.
    """
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
    entries: list[tuple[str, tuple[str, ...]]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status, rest = line[:2].strip(), line[3:]
        # A rename reads `old -> new` and touches BOTH paths. Keeping only the
        # destination let `git mv AGENTS.md docs/evidence/…/smoke-claude.md` pass:
        # the destination is an exempt output, so the disappearance of AGENTS.md
        # went unreported and the check certified a tree without it.
        paths = tuple(part.strip() for part in rest.split(" -> ")) if " -> " in rest else (rest,)
        # git quotes paths containing spaces or non-ASCII bytes.
        paths = tuple(p[1:-1] if p.startswith('"') and p.endswith('"') else p for p in paths)
        entries.append((status, paths))
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


# What either harness actually loads. `git status` is blind to two things that
# live here: a **gitignored** file (an ignored `.agents/skills/ghost/SKILL.md` is
# loaded by Codex and reported by nothing), and a tracked file flagged
# `skip-worktree` or `assume-unchanged`, whose local edits git deliberately hides.
# Both were accepted by the first version of this check while it claimed the tree
# matched the commit.
LOADER_VISIBLE_FILES = ("AGENTS.md", "CLAUDE.md")
LOADER_VISIBLE_TREES = (".agents/", ".claude/skills/")


def _is_loader_visible(path: str) -> bool:
    return path in LOADER_VISIBLE_FILES or path.startswith(LOADER_VISIBLE_TREES)


def _hidden_loader_visible_differences(tool: str, root: Path) -> list[str]:
    problems: list[str] = []

    # Filtered in Python rather than by pathspec: `git status -- .agents` also
    # reports the unrelated ignored `.agent/`, and the check must not flag harness
    # scratch such as `.claude/.cc-writes/`, which no harness reads as instructions.
    ignored = subprocess.run(
        ["git", "status", "--porcelain", "--ignored=traditional"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    for line in ignored.stdout.splitlines():
        if line.startswith("!!") and _is_loader_visible(line[3:]):
            problems.append(f"ignored but loader-visible: {line[3:]}")

    flagged = subprocess.run(["git", "ls-files", "-v"], cwd=root, capture_output=True, text=True)
    for line in flagged.stdout.splitlines():
        # Lowercase tag = assume-unchanged; `S` = skip-worktree. Either hides edits.
        if (line[:1].islower() or line[:1] == "S") and _is_loader_visible(line[2:]):
            problems.append(f"changes hidden by `git update-index` ({line[0]}): {line[2:]}")

    return problems


def verify_tree_matches_commit(
    tool: str,
    commit: str,
    exempt: frozenset[str] = EVIDENCE_OUTPUTS,
    root: Path = REPO_ROOT,
) -> None:
    """Refuse unless the tree matches `commit` apart from the writers' own outputs."""
    hidden = _hidden_loader_visible_differences(tool, root)
    if hidden:
        fail(
            tool,
            "refusing to write: files the harnesses load differ from the commit in ways "
            "`git status` does not report:\n  " + "\n  ".join(hidden),
        )
    # An entry is exempt only if *every* path it touches is an output. A rename is
    # exempt only when it moves one output onto another.
    dirty = [
        f"{status:>2} {' -> '.join(paths)}"
        for status, paths in _status_paths(tool, root)
        if not all(path in exempt for path in paths)
    ]
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


# The tree-entry modes git gives a regular file. A blob is *not* enough: git
# stores a symlink as a blob too (mode 120000), and a committed symlink pointing
# outside the commit keeps the worktree clean while its content changes freely —
# so an object-type test would certify content the commit does not contain.
REGULAR_FILE_MODES = frozenset({"100644", "100755"})
_MODE_NAMES = {"040000": "a directory", "120000": "a symlink", "160000": "a submodule"}


def verify_paths_exist(
    tool: str,
    commit: str,
    paths: Iterable[str],
    root: Path = REPO_ROOT,
) -> None:
    """Refuse unless every path in `paths` is a regular file at `commit`.

    `verify_tree_matches_commit` asks whether anything *differs* from the commit,
    never whether a required input *exists* at it, and a clean tree matching a
    commit that never held `smoke-prompt.txt` passes it. The smoke header's
    "Prompt: … verified unmodified against that commit" then names a file that is
    not there (#218).

    Resolution is at the commit rather than on disk on purpose: the header names
    the commit, so a prompt that exists only in the operator's working tree is
    precisely the case the claim must not survive.

    The criterion is the tree entry's **mode**, not the object type. A directory
    is a tree and fails on type alone, but a symlink is stored as a blob and does
    not: a committed `smoke-prompt.txt` symlinked to a file outside the commit
    would satisfy a type test while the bytes the harness read stayed outside
    anything this module can verify, with `git status` reporting nothing.
    """
    missing: list[str] = []
    for path in paths:
        # Not through `git()`: it aborts with a generic "`git …` failed" on a
        # non-zero exit, and an unresolvable commit deserves the purposeful
        # refusal below. `ls-tree` rather than `cat-file`, because only the tree
        # entry carries the mode; `:(literal)` keeps a path containing pathspec
        # metacharacters from being read as a pattern. A path absent at the
        # commit is *no output and exit 0*, not an error.
        probe = subprocess.run(
            ["git", "ls-tree", "-z", "--full-tree", commit, "--", f":(literal){path}"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            missing.append(f"{path} — cannot resolve {commit}: {probe.stderr.strip()}")
            continue
        entry = probe.stdout.split("\0")[0]
        if not entry:
            missing.append(f"{path} — not present at {commit}")
            continue
        # "<mode> SP <type> SP <sha> TAB <path>"
        mode = entry.split(" ", 1)[0]
        if mode not in REGULAR_FILE_MODES:
            what = _MODE_NAMES.get(mode, f"mode {mode}")
            missing.append(f"{path} — {what} at {commit}, not a regular file")
    if missing:
        fail(
            tool,
            f"refusing to write: the header would claim an input was verified against {commit} "
            "that is not a regular file there:\n  " + "\n  ".join(missing),
        )
