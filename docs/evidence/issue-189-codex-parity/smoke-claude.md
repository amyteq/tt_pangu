Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     f3876cc, verified to be HEAD with the worktree matching it apart from
          the evidence outputs this writer and the probe renderer produce
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  16 s

--- answer ---

1. **`kg-run`** — `python tools/kca/kca.py run init --competition arc-agi2 --hypothesis "..." --json`.
2. Path shape: `runs/<competition>/<run_id>/` (here `runs/arc-agi2/<run_id>/`, `run_id` defaulting to UTC `YYYYMMDD_HHMMSS`), containing `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `runs/` is gitignored.
3. Secret policy: I may **read** `~/.kaggle/kaggle.json` to pick up local Kaggle credentials for use, but must never echo/print it in session or copy its contents into web fetches, logs, public PRs or comments (read-for-use, not read-to-share).
4. Sources — (1)/(2): `.claude/skills/kg-run/SKILL.md` ("Layout" + "Commands").
5. Sources — (3): `CLAUDE.md` → "Environment configuration" → "Dev-phase secret policy".
