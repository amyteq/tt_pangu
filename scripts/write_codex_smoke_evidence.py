#!/usr/bin/env python3
"""Commit a paired smoke-check answer set with a provenance header that is checked.

    python scripts/write_codex_smoke_evidence.py \
        --codex  <answer file> --codex-seconds  15 \
        --claude <answer file> --claude-seconds 16

The header says which commit both harnesses read and that they read the prompt
unedited. Both claims are verified in `scripts/evidence_provenance.py` rather
than believed: the named commit must be HEAD, nothing may differ from it except
the three evidence files the writers themselves produce, and `smoke-prompt.txt`
must exist as a regular file at that commit — not a directory, and not a symlink
whose target the commit does not contain. `smoke-prompt.txt` is an input, so it is not
exempt — an earlier version of this script exempted the whole evidence directory
and would have stamped "Prompt … unedited" over an edited prompt. The existence
check is separate because "nothing differs" is also true of a commit that never
contained the prompt, which would have stamped the same claim over a file that
was not there (#218).

It cannot check that the answer files came from the run you think they did, or
that the harness identities below are accurate. Those stay attestations; pass
`--codex`/`--claude` explicitly so at least the provenance is visible at the call
site.

Run it against the real working tree. Under a masking sandbox, paths the sandbox
hides are bind-mounted to `/dev/null` and `git status` reports them as untracked,
so the tree check refuses on files that do not exist outside the sandbox.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from evidence_provenance import (
    EVIDENCE_PREFIX,
    REPO_ROOT,
    fail,
    verify_commit_is_head,
    verify_paths_exist,
    verify_tree_matches_commit,
)

TOOL = "write_codex_smoke_evidence"
EVIDENCE = REPO_ROOT / "docs" / "evidence" / "issue-189-codex-parity"
SMOKE_PROMPT = EVIDENCE_PREFIX + "smoke-prompt.txt"

CODEX_HARNESS = "codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`"
CLAUDE_HARNESS = "claude -p, `claude-opus-5[1m]`"


def write(name: str, harness: str, answer_path: Path, seconds: str, commit: str) -> None:
    if not answer_path.is_file():
        fail(TOOL, f"no such answer file: {answer_path}")
    answer = answer_path.read_text(encoding="utf-8").strip("\n")
    if not answer:
        fail(TOOL, f"{answer_path} is empty — the harness produced no answer")
    header = (
        f"{name} side of the paired smoke check (issue #189 AC5).\n"
        "\n"
        f"Harness:  {harness}\n"
        f"Repo:     {commit}, verified to be HEAD with the worktree matching it apart from\n"
        f"          the evidence outputs this writer and the probe renderer produce\n"
        f"Prompt:   {EVIDENCE_PREFIX}smoke-prompt.txt, verified unmodified against that commit\n"
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

    commit = verify_commit_is_head(TOOL, args.commit)
    verify_tree_matches_commit(TOOL, commit)
    # After the tree check, not before. The tree check is the broader
    # precondition and the one an operator actually trips — harness scratch under
    # `.claude/` makes the tree dirty far more often than the prompt goes missing
    # — and it gives the better diagnosis for the overlapping case: a prompt that
    # is present on disk but absent from the commit is reported there as an
    # untracked file, which is what the operator has to fix. Only once the state
    # is otherwise sound does "the commit never held this input" become the
    # accurate thing to say.
    verify_paths_exist(TOOL, commit, [SMOKE_PROMPT])
    write("Codex", CODEX_HARNESS, args.codex, args.codex_seconds, commit)
    write("Claude Code", CLAUDE_HARNESS, args.claude, args.claude_seconds, commit)


if __name__ == "__main__":
    main()
