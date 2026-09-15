Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     083c8b7, verified to be HEAD with a clean worktree when this was written
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  15 s

--- answer ---

1. `kg-run` — `python tools/kca/kca.py run init --competition arc-agi2 --hypothesis "..."` creates `runs/<competition>/<run_id>/` (i.e. `runs/arc-agi2/YYYYMMDD_HHMMSS/` by default), holding `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` is gitignored.
2. Permits reading `~/.kaggle/kaggle.json` locally to pick up Kaggle credentials for use; forbids echoing/printing them in session or copying them into web fetches, logs, public PRs, or comments ("read-for-use, not read-to-share") — as with SSH/AWS/gcloud/gh-token secrets, which may not be read at all.
3. Instruction file: `CLAUDE.md:65` (Environment configuration → Dev-phase secret policy). Skill file: `.claude/skills/kg-run/SKILL.md` (layout at lines 13–24).
