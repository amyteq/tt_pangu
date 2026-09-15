Codex side of the paired smoke check (issue #189 AC5).

Harness:  codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`
Repo:     a4de031 (clean worktree)
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited
Elapsed:  16 s

--- answer ---

1. Use `kg-run`; it creates `runs/arc-agi2/<run_id>/` (default run ID: UTC `YYYYMMDD_HHMMSS`).
2. You may read `~/.kaggle/kaggle.json` to use its credentials locally, but must never expose or copy them into outputs, logs, web requests, PRs, or comments.
3. Instruction: `AGENTS.md`; skill: `.agents/skills/kg-run/SKILL.md`.
