Codex side of the paired smoke check (issue #189 AC5).

Harness:  codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`
Repo:     4d295d8, verified to be HEAD with a clean worktree when this was written
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited
Elapsed:  15 s

--- answer ---

1. Use `kg-run`; it creates `runs/arc-agi2/<run_id>/`.
2. The policy permits reading `~/.kaggle/kaggle.json` for credential use, but forbids printing, sharing, logging, or copying its contents externally.
3. Instruction: `AGENTS.md`; skill: `.agents/skills/kg-run/SKILL.md`.
