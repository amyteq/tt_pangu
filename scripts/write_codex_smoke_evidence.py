#!/usr/bin/env python3
"""Commit a paired smoke-check answer set with a provenance header that is checked.

    python scripts/write_codex_smoke_evidence.py \
        --codex  <answer file> --codex-seconds  16 \
        --claude <answer file> --claude-seconds 17

The header it writes says which commit both harnesses read. That is only true if
the working tree matched that commit while they ran, so this script verifies it
instead of believing the caller — twice during review, evidence was recorded
against a commit whose files were not the ones the harnesses had read.

What is checked, and what is not:

* the named commit is HEAD;
* nothing outside the evidence directory is modified, staged, or **untracked** —
  an untracked `AGENTS.md` or skill is loader-visible, so `--untracked-files=no`
  would have missed exactly the case that matters;
* the evidence directory itself is exempt: it holds this run's outputs.

It cannot check that the answer files came from the run you think they did, or
that the harness identities in the header are accurate. Those stay attestations;
pass `--codex`/`--claude` explicitly so at least the provenance is visible at the
call site.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = REPO_ROOT / "docs" / "evidence" / "issue-189-codex-parity"
EVIDENCE_PREFIX = "docs/evidence/issue-189-codex-parity/"

CODEX_HARNESS = "codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`"
CLAUDE_HARNESS = "claude -p, `claude-opus-5[1m]`"


def fail(message: str) -> None:
    sys.exit(f"write_codex_smoke_evidence: {message}")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"`git {' '.join(args)}` failed: {result.stderr.strip()}")
    return result.stdout.strip()


def verify_tree_matches(commit: str) -> None:
    """The named commit must be HEAD, with nothing loader-visible uncommitted."""
    head = git("rev-parse", "HEAD")
    named = git("rev-parse", f"{commit}^{{commit}}")
    if head != named:
        fail(
            f"refusing to write: {commit} resolves to {named[:7]}, but HEAD is {head[:7]}.\n"
            "  The harnesses read the working tree, so the header would name a commit they did "
            "not see."
        )
    # Untracked files are included deliberately: a new, uncommitted skill under
    # `.agents/skills/` is loaded by Codex and would not appear in `git diff`.
    status = [line for line in git("status", "--porcelain").splitlines() if line.strip()]
    dirty = [line for line in status if EVIDENCE_PREFIX not in line]
    if dirty:
        fail(
            f"refusing to write: the worktree differs from {commit} outside the evidence "
            "directory, so the header would not describe what the harnesses read:\n  " + "\n  ".join(dirty)
        )


def write(name: str, harness: str, answer_path: Path, seconds: str, commit: str) -> None:
    if not answer_path.is_file():
        fail(f"no such answer file: {answer_path}")
    answer = answer_path.read_text(encoding="utf-8").strip("\n")
    if not answer:
        fail(f"{answer_path} is empty — the harness produced no answer")
    header = (
        f"{name} side of the paired smoke check (issue #189 AC5).\n"
        "\n"
        f"Harness:  {harness}\n"
        f"Repo:     {commit}, verified to be HEAD with a clean worktree when this was written\n"
        f"Prompt:   {EVIDENCE_PREFIX}smoke-prompt.txt, unedited\n"
        f"Elapsed:  {seconds} s\n"
        "\n"
        "--- answer ---\n\n"
    )
    out = EVIDENCE / f"smoke-{name.split()[0].lower()}.md"
    out.write_text(header + answer + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default="HEAD", help="commit both harnesses read (default: HEAD)")
    parser.add_argument("--codex", required=True, type=Path, help="file holding Codex's answer")
    parser.add_argument("--claude", required=True, type=Path, help="file holding Claude Code's answer")
    parser.add_argument("--codex-seconds", required=True)
    parser.add_argument("--claude-seconds", required=True)
    args = parser.parse_args()

    commit = git("rev-parse", "--short", args.commit)
    verify_tree_matches(commit)
    write("Codex", CODEX_HARNESS, args.codex, args.codex_seconds, commit)
    write("Claude Code", CLAUDE_HARNESS, args.claude, args.claude_seconds, commit)


if __name__ == "__main__":
    main()
