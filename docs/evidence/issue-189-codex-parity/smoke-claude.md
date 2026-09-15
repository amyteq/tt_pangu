Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     bdddf1a, clean worktree (checked before this file was written)
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited
Elapsed:  17 s

--- answer ---

1. **kg-run** — `python tools/kca/kca.py run init --competition arc-agi2 --hypothesis "…" --json`.
2. Path shape: `runs/arc-agi2/<run_id>/` (run_id defaults to UTC `YYYYMMDD_HHMMSS`), containing `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` is gitignored.
3. Secret policy: I may **read** `~/.kaggle/kaggle.json` to pick up local Kaggle credentials for use — but never echo/print its contents in session, nor copy them into web fetches, logs, public PRs or comments ("read-for-use, not read-to-share").
4. Sources: `CLAUDE.md` → *Environment configuration → Dev-phase secret policy* (answer 2).
5. `.claude/skills/kg-run/SKILL.md` → *Layout* + *Commands* (answer 1).
