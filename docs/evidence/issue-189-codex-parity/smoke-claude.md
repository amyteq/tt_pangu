Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     4d295d8, verified to be HEAD with a clean worktree when this was written
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, unedited
Elapsed:  16 s

--- answer ---

1. **`kg-run`** — it wraps `python tools/kca/kca.py run init --competition arc-agi2 --hypothesis "..."`.
2. Path shape: `runs/<competition>/<run_id>/` → `runs/arc-agi2/20260915_HHMMSS/` (`run_id` defaults to UTC `YYYYMMDD_HHMMSS`), containing `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` is gitignored.
3. Secret policy: I may **read** `~/.kaggle/kaggle.json` to pick up local Kaggle credentials for use, but must never echo/print it in-session or copy its contents into web fetches, logs, public PRs, or comments ("read-for-use, not read-to-share").
4. Sources: `CLAUDE.md:65` (Dev-phase secret policy) and `.claude/skills/kg-run/SKILL.md` (layout at lines 13–24, 35).
