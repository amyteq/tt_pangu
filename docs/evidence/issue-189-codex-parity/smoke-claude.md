Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     81c4709, verified to be HEAD with the worktree matching it apart from
          the evidence outputs this writer and the probe renderer produce
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  17 s

--- answer ---

1. **kg-run** — `python tools/kca/kca.py run init --competition arc-agi2 --hypothesis "..." --json`.
2. Path shape: `runs/<competition>/<run_id>/` → here `runs/arc-agi2/20260917_HHMMSS/` (default `run_id` = UTC `YYYYMMDD_HHMMSS`), holding `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` is gitignored.
3. Secret policy: I may **read** `~/.kaggle/kaggle.json` to pick up Kaggle credentials for local use.
4. It forbids echoing/printing those credentials in-session or copying them into web fetches, logs, public PRs or comments — read-for-use, not read-to-share.
5. Instruction file: `CLAUDE.md` (§ Environment configuration → "Dev-phase secret policy").
6. Skill file: `.claude/skills/kg-run/SKILL.md`.
