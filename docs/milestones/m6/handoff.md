# M6 → M7 Handoff Prompt

_Backfilled 2026-05-22 from `docs/milestones/m6/final-review.md` and `docs/milestones/README.md` § M7._

Paste this into a fresh session that is starting **M7 (KCA CLI architecture — command / skill / tool / job / permission policy)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository. **M0–M6 are complete.** Your job is to start **M7**.

## Read these files first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` — especially the **M7** section (four-layer model,
   M7-T000 through M7-T010, permission policy design, recommended directory
   layout).
5. `docs/milestones/m6/final-review.md` — what landed in M6 (19 non-SKIP checks PASS).
6. `docs/milestones/m7/loop-prompts.md` — sequenced task prompts for M7.
7. `docs/meeting-notes/2026-05-21-r1.md` — full design rationale for the
   four-layer model (§1–3) and the KCA CLI command suggestions (§2).
8. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template.
9. Latest files in `docs/adr/`.

## State at M6 exit

- Migration `0006` applied: `agent_reviews` table (verdict, reviewer model,
  target op, decision link, OTEL span link), `agent_telemetry_spans` table
  (trace_id, span_id, parent_span_id, kind, name, attributes, status),
  `agent_jobs.otel_trace_id / otel_root_span_id` columns.
- Reviewer agent (`Reviewer.review`) fires before high-stakes ops
  (`kaggle_submit`, `supabase_migrate`, `git_force_push`, `dataset_upload`,
  `delete_artifact`); `approve` satisfies the matching approval gate
  without human intervention, `reject` escalates (default) or fails the
  job, `abstain` falls through to the existing human-decisions flow.
- Local-model layer (`src/worker/local_model.py`) talks to vLLM / Ollama
  via OpenAI-compatible HTTP; numbered-slot env config
  (`KCA_LOCAL_ENDPOINT_<n>_*`), priority ordering, TTL-cached probe, and
  `KCA_LOCAL_FALLBACK_MODEL` cloud fallback.
- Job types `log_triage` and `summarise` route to the local layer by default.
- `kca local probe / pick / triage` surfaces endpoint state.
- OTEL telemetry (ADR-0007) with three exporters: stderr (dev), SQLite
  (`.agent/telemetry.sqlite`), and Supabase (`agent_telemetry_spans`).
- TC-3 Spaceship Titanic: 8/8 checks, R1 LR `cv_auc=0.9032`, R2 HGB
  `cv_auc=0.9873`, reviewer auto-approved `kaggle_submit`, no pending
  decisions, pytest clean.
- 19/19 M6 validation checks PASS against the same live DB pattern as M5
  (`postgres@172.21.0.4:5432`); DB and local-endpoint calls require
  `dangerouslyDisableSandbox=true`.

Carried into M7: a four-layer CLI architecture (Command / Skill / Tool /
Job), a skill loader, a tool registry with permission labels, an
`allow | ask | deny` permission policy layer, `kca skill list/show/run`
with `--dry-run`, audit logging, four seed skills under `.kca/skills/`,
and an architecture doc.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human approval.
- Keep CTF work inside explicitly authorized local/sandbox challenge environments.

## Current task

Start with **Prompt 0 of `docs/milestones/m7/loop-prompts.md`** (CI repair / M7-T000),
then walk Prompt 1 → Prompt 10 sequentially. Goal of M7: ship a stable,
inspectable CLI scaffold that other workflows (M8 UI, M9 live submission)
can call into deterministically.

## Return

- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
