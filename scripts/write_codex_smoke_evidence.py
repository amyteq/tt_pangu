"""Write the committed smoke evidence with provenance headers.

Usage: write_smoke.py <commit> <codex-seconds> <claude-seconds>
"""

import subprocess
import sys
from pathlib import Path

base = Path("/home/harry/test/tt_pangu/.claude/worktrees/issue-189-agents-parity/docs/evidence/issue-189-codex-parity")
src = Path("/tmp/claude-1000/rev189")
commit, codex_s, claude_s = sys.argv[1], sys.argv[2], sys.argv[3]

# The evidence directory holds this run's *outputs*, not its inputs, so changes
# there do not invalidate the commit attribution. Anything else uncommitted does:
# it means the harnesses read something that is not in `commit`.
status = subprocess.run(
    ["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True
).stdout.splitlines()
dirty = [line for line in status if "docs/evidence/issue-189-codex-parity/" not in line]
if dirty:
    sys.exit(
        f"refusing to write: uncommitted changes outside the evidence directory, so {commit} "
        "would not describe what the harnesses read:\n" + "\n".join(dirty)
    )

headers = {
    "smoke-codex.md": (
        "Codex side of the paired smoke check (issue #189 AC5).\n"
        "\n"
        "Harness:  codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`\n"
        f"Repo:     {commit}, clean worktree (checked before this file was written)\n"
        "Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited\n"
        f"Elapsed:  {codex_s} s\n"
        "\n"
        "--- answer ---\n\n"
    ),
    "smoke-claude.md": (
        "Claude Code side of the paired smoke check (issue #189 AC5).\n"
        "\n"
        "Harness:  claude -p, `claude-opus-5[1m]`\n"
        f"Repo:     {commit}, clean worktree (checked before this file was written)\n"
        "Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited\n"
        f"Elapsed:  {claude_s} s\n"
        "\n"
        "--- answer ---\n\n"
    ),
}

for name, header in headers.items():
    answer = (src / name.replace("smoke-", "smoke3-")).read_text(encoding="utf-8").strip("\n")
    (base / name).write_text(header + answer + "\n", encoding="utf-8")
    print(f"wrote {base / name}")
