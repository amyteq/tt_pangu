# M4 → M5 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/m4/final-review.md` and `docs/milestones/README.md` § M5._

Paste this into a fresh session that is starting **M5 (research and browser workflow + M4 follow-ups)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0–M4 are complete.** Your job is to start **M5**.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M5** section (M5-T000 through M5-T010).
5. `docs/milestones/m4/final-review.md` — what landed in M4 and the 16-check validation matrix.
6. `docs/milestones/m5/loop-prompts.md` — sequenced task prompts for M5.
7. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
8. Latest files in `docs/adr/`, including `0009-competition-repo-strategy` and
   `0010-model-routing` (if present).

## State at M4 exit

- `pip install -e .` exposes `kca` on PATH; `pyproject.toml` declares the
  entry point and packages.
- Migration `0004_m4_competition_repo.sql` applied: adds
  `repo_url / default_branch / local_clone_path / competition_policy` on
  `competitions`, plus `experiments / experiment_runs / submissions` tables
  with RLS and indexes.
- `kca competition register / clone / list / info` available.
- `kca workspace init --repo <path>` creates worktrees at
  `<repo>/jobs/<job_id>` — replaces the M3 interim `.workspaces/` layout.
- `kca run init / record-metric / list` is FS-first; DB writes degrade to
  warnings when `SUPABASE_DB_URL` is absent.
- Real `kaggle` CLI is wired into `kca kaggle` commands with up-front
  credential checks and `--dry-run` on `push`.
- `JobPolicy.approval_gates` populated with the 7 ADR-0006 operations;
  `_check_approval_gate` raises `ApprovalRequired` on a gated op.
- `scripts/run_job.py` resolves policy (project → competition → CLI),
  clones the competition repo if needed, and commits agent changes on success.
- TC-1 Titanic loop completed end-to-end (8/8 checks, `cv 0.7912`,
  419-row `submission.csv`, no Kaggle calls).
- 16/16 M4 validation checks PASS — see `docs/milestones/m4/final-review.md`.

Carried into M5:
- Sha256 manifest for `kca kaggle download` + `--resume` + `kca kaggle verify`.
- Paused-job resume via `scripts/run_job.py --job-id` after `kca decisions approve`.
- Per-job-type model routing (Sonnet implement/experiment, Opus eval/analysis,
  Haiku triage; CLI override always wins).
- `.github/workflows/test.yml` (no-db + live-db + lint).

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

Start with **Prompt 0 of `docs/milestones/m5/loop-prompts.md`** (typically migration 0005
for `research_items` extensions + `research_citations`). Goal of M5: the agent
can fetch and read web pages through a safety-gated path, record cited /
trust-labelled research items, and exercise the multi-experiment regression
loop on TC-2 House Prices.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
