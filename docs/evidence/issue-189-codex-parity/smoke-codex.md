Codex side of the paired smoke check (issue #189 AC5).

Harness:  codex-cli 0.154.0, `gpt-5.6-sol`, `model_reasoning_effort=low`, `--sandbox read-only`
Repo:     083c8b7, verified to be HEAD with a clean worktree when this was written
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  13 s

--- answer ---

1. Use `kg-run`; it creates `runs/arc-agi2/<run_id>/`.
2. You may read `~/.kaggle/kaggle.json` to use Kaggle credentials, but must never echo, share, log, or exfiltrate its contents.
3. Instruction: `AGENTS.md`; skill: `.agents/skills/kg-run/SKILL.md`.
