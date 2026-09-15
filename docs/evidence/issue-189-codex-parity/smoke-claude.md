Claude Code side of the paired smoke check (issue #189 AC5).

Harness:  claude -p, `claude-opus-5[1m]`
Repo:     92ab69b, verified to be HEAD with the worktree matching it apart from
          the evidence outputs this writer and the probe renderer produce
Prompt:   docs/evidence/issue-189-codex-parity/smoke-prompt.txt, verified unmodified against that commit
Elapsed:  15 s

--- answer ---

**1.** `kg-run` (`kca run init --competition arc-agi2 --hypothesis "…"`) → `runs/arc-agi2/<run_id>/` with `meta.json`, `config.json`, `metrics.json`, `logs/`, `artifacts/`; `run_id` defaults to UTC `YYYYMMDD_HHMMSS`, and `runs/` is gitignored.

**2.** It permits reading `~/.kaggle/kaggle.json` (read-for-use) to pick up local Kaggle credentials, and forbids echoing/printing those credentials in-session or copying them into web fetches, logs, public PRs or comments — as well as reading other secrets (SSH/AWS/gcloud keys, the `gh` token, `.netrc`, `./secrets/`, `.env.production`/`.env.test`).

**3.** (1) came from `.claude/skills/kg-run/SKILL.md`; (2) from `CLAUDE.md` § "Environment configuration" → *Dev-phase secret policy*.
