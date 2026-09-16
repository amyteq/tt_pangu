Codex side of the paired smoke check (issue #189 AC5).

Harness:  codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`
Repo:     52b81cf, verified to be HEAD with the worktree matching it apart from
          the evidence outputs this writer and the probe renderer produce
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  11 s

--- answer ---

1. Use `kg-run`; it creates `runs/arc-agi2/<run_id>/` (default run ID: UTC `YYYYMMDD_HHMMSS`).
2. The dev policy permits reading `~/.kaggle/kaggle.json` to use its credentials, but forbids printing, sharing, logging, or copying them externally.
3. Instruction: `AGENTS.md`; skill: `.agents/skills/kg-run/SKILL.md`.
