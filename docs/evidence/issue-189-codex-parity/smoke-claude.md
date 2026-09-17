Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     52b81cf, verified to be HEAD with the worktree matching it apart from
          the evidence outputs this writer and the probe renderer produce
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  19 s

--- answer ---

1. `kg-run` (`.claude/skills/kg-run/SKILL.md`) — `python tools/kca/kca.py run init --competition arc-agi2 --hypothesis "..." --json`.
2. It creates `runs/arc-agi2/<run_id>/` (run_id defaults to UTC `YYYYMMDD_HHMMSS`) holding `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` is gitignored, never committed.
3. Secret policy: I may read `~/.kaggle/kaggle.json` to pick up local Kaggle credentials for use ("read-for-use"), but must never echo/print them in session or copy them into web fetches, logs, public PRs, or comments ("not read-to-share").
4. Instruction file: `CLAUDE.md` § Environment configuration → "Dev-phase secret policy" (also mirrored in `AGENTS.md`).
5. Skill file: `.claude/skills/kg-run/SKILL.md`.
