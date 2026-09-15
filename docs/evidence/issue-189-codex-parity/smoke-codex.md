Codex side of the paired smoke check (issue #189 AC5).

Harness:  codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`
Repo:     bdddf1a, clean worktree (checked before this file was written)
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited
Elapsed:  16 s

--- answer ---

1. Use `kg-run`; it creates `runs/arc-agi2/<run_id>/`.
2. The policy permits reading `~/.kaggle/kaggle.json` to use its credentials, but forbids printing, sharing, logging, or copying them externally.
3. Files: `AGENTS.md` and `.agents/skills/kg-run/SKILL.md`.
