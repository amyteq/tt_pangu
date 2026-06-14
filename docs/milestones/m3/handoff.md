# M3 → M4 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/README.md` (M3 section) and `docs/milestones/m3/loop-prompts.md`. M3 predates the final-review file convention; there is no `docs/milestones/m3/final-review.md`._

Paste this into a fresh session that is starting **M4 (Kaggle competition workflow v0)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0–M3 are complete.** Your job is to start **M4**.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M4** section (M4-T000 through M4-T010).
5. `docs/milestones/m3/loop-prompts.md` — what M3 actually built (worker skeleton,
   workspace strategy, approval-gate plumbing).
6. `docs/milestones/m4/loop-prompts.md` — sequenced task prompts for M4.
7. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
8. Latest files in `docs/adr/`, especially `0006-approval-policy` and
   `0009-competition-repo-strategy` if present.

## State at M3 exit

- Worker can create an isolated workspace per job at `.workspaces/<job_id>/`
  (interim M3 layout, replaced by competition-repo worktrees in M4).
- Worker calls `kca` local tools through a structured tool loop.
- Job status, logs, artifacts, and metrics are recorded in Supabase.
- Budget limits enforced: max turns, max cost, max runtime.
- Approval gate fires for configured operations and writes a
  `human_decisions` row.
- `litellm.completion()` is the unified LLM provider interface (ADR-0004);
  Claude / GPT / local vLLM/Ollama selectable per job.
- Default policy: allow `kaggle_submit`, `kernel_push`, `git_push`;
  per-project/competition overrides per ADR-0006.

Carried into M4: full competition repo strategy (ADR-0009) — one git repo
per Kaggle competition, worktree-per-job inside it, `pyproject.toml` so
`pip install -e .` makes `kca` available from a competition repo.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

Start with **Prompt 0 of `docs/milestones/m4/loop-prompts.md`** — typically M4-T000
(make `kca` pip-installable) and M4-T001 (migration 0004: competition repo
columns + `experiments / experiment_runs / submissions` tables). Goal of M4:
the platform can run a Titanic loop end-to-end (research → implement →
experiment → prepare submission) with each competition in its own GitHub
repo and submissions gated through the configurable approval policy.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
