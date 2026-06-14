# M1 → M2 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/README.md` (M1 section) and `docs/milestones/m1/loop-prompts.md`. M1 predates the `docs/m{x}-final-review.md` convention; there is no M1 final-review file._

Paste this into a fresh Claude Code / Codex / ChatGPT session that is starting **M2 (Supabase / control plane foundation)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository — a hybrid human + AI code agent platform for Kaggle competitions and authorized CTF/lab challenges. **M0 (project baseline) and M1 (local Kaggle tooling wrapper baseline) are complete.** Your job is to start **M2**.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M2** section.
5. `docs/milestones/m1/loop-prompts.md` — what M1 actually built and which conventions it
   set (skill naming, `kca` CLI shape, side-effect levels, `runs/<competition>/<run_id>/`
   artifact layout).
6. `docs/milestones/_templates/handoff-prompt.md` — the canonical handoff template (this file is a
   per-milestone instance of it).
7. Latest files in `docs/adr/` — read every ADR present.

## State at M1 exit

- `tools/kca/` CLI skeleton is in place with stable subcommands (`kca nb`,
  `kca run`, `kca kaggle`, `kca eval`) and structured JSON output.
- 1–2 Python ↔ Jupyter notebook conversion scripts are wrapped under `kca nb`.
- Artifact layout is fixed at `runs/<competition>/<run_id>/`; created by
  `kca run init`, never by hand.
- `.claude/settings.json` hooks (`guard_tool.py` PreToolUse, `audit_event.py`
  PostToolUse) gate dangerous Bash patterns and audit every tool call.
- Kaggle submit / kernel push / data upload are blocked at the hook layer
  unless explicit human approval is provided.
- Smoke tests exist (`tests/test_kca_smoke.py`) and pass without DB / API
  credentials.

Open follow-ups carried into M2: persistent control plane (projects /
sessions / jobs / experiments / runs / approvals / artifacts), worker job
queue design, storage strategy for large artifacts.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

Start with the first task of M2 (Supabase / control plane foundation). Define
the schema and data model that supports MVP-1 artifacts and future worker
jobs; bring up a local Supabase stack and let a local/dev worker record run
events to it without needing a product UI. Pick the first task from
`docs/milestones/README.md` § M2 and confirm the plan with the human before writing
migrations.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
