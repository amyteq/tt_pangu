# M2 → M3 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/m2/final-review.md` and `docs/milestones/README.md` § M3._

Paste this into a fresh session that is starting **M3 (Python-first competition worker v0)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0, M1, and M2 are complete.** Your job is to start **M3**.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M3** section.
5. `docs/milestones/m2/final-review.md` — what landed in M2 and the validation matrix.
6. `docs/milestones/m3/loop-prompts.md` — sequenced task prompts for M3.
7. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
8. Latest files in `docs/adr/`, especially `0008-artifact-storage-local-first.md`.
9. `docs/tooling/local-supabase.md` — local Supabase walkthrough.

## State at M2 exit

- Migration `0002_kca_run_alignment.sql` applied: adds `external_run_id`,
  `run_dir`, `tags[]`, `experiment_run_metrics`, bootstrap project, indexes.
- Local Supabase stack documented in `supabase/config.toml` and
  `docs/tooling/local-supabase.md`; `Makefile` exposes
  `supabase-up/down/reset/psql/status`.
- `tools/kca/db.py` is the psycopg3 access layer (13 public symbols).
- `kca run init / record-metric / list` are DB-first; FS becomes the cache.
- `kca kaggle submit` stays blocked without `KCA_ALLOW_REMOTE=1`; when DB is
  reachable a `pending` `human_decisions` row is recorded best-effort.
- ADR-0008 (artifact storage local-first, `local://` URI scheme) landed.
- All 16 M2 validation checks PASS; M1 smoke tests stay green and no test
  leaks DB state across runs.

Carried into M3: worker that creates an isolated workspace/worktree per job,
calls `kca` local tools, records job status/logs/artifacts/metrics, and
enforces budget + approval gates.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

Start with **Prompt 0 of `docs/milestones/m3/loop-prompts.md`** (or the first task in
`docs/milestones/README.md` § M3 if loop prompts haven't been written yet). Goal of
M3: a job runs locally end-to-end — prompt → workspace → LLM tool loop →
`kca` tool call → recorded result — with budget limits (turns, cost,
runtime) enforced and approval gates firing when configured.

Note: M3 creates worktrees inside the platform repo at `.workspaces/<job_id>/`
as a temporary simplification; the full competition repo strategy (ADR-0009)
lands in M4.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
