# Kaggle Code Agent — Project State

_Last updated: 2026-05-24 (M9 exit)_

## Product intent
Build a hybrid human + AI competition engineering workbench. The first target is Kaggle-style competitions, with future support for authorized CTF/lab challenges. The system should research, discuss ideas with humans, edit code, run tests/evaluations, analyze results, iterate, and prepare submissions under human-approved guardrails.

## Chosen architecture direction
- Hybrid architecture.
- Claude Code Desktop/CLI for interactive project development and dogfooding (primary development tool for all layers).
- Claude Agent SDK for the production coding worker.
- Python-first worker for Kaggle/ML/CTF execution.
- TypeScript/Supabase control plane and UI shell (developed in Claude Code, not Lovable).
- GitHub + Claude Code + CI + Supabase migrations are the source of truth. All decisions, architecture, task specs, and safety rules live in repo files.
- Supabase is the control plane and audit database, not the primary code execution environment.

## Current MVP boundary
1. Local-first repository workflow with `CLAUDE.md`, skills, hooks, subagents, and GitHub.
2. Supabase schema for projects, sessions, jobs, messages, research notes, experiments, runs, submissions, artifacts, approvals, and `agent_tool_audit` (M8).
3. Kaggle baseline loop: understand competition, create validation, run baseline, record metrics, iterate, prepare submission.
4. Browser/research loop: fetch pages, summarize sources, track trust and citations.
5. Multi-agent reviewer gate + OTEL telemetry + local GPU model layer.
6. Authorized CTF sandbox loop only for explicit challenge environments.
7. Operator-facing UI: Dashboard, Run Timeline (OTEL swim-lane), Experiments, Research, Approval Inbox + Decision Gate, Artifact Browser.

## Human approval gates
Require approval for:
- Kaggle competition submissions.
- Kaggle kernel/notebook pushes.
- Any remote write operation.
- Any operation touching credentials, secrets, or account settings.
- Any CTF action outside a declared sandbox/challenge scope.
- PR merges (create is allowed, merge requires approval).

Mutations from the UI flow through `services/decision_api/` (FastAPI) →
`tools/kca/decisions.py` → DB. The browser bundle never holds a
Supabase service-role key. The M7 permission policy resolution stays
authoritative.

## Completed milestones
- **M0**: project baseline and memory discipline ✓
- **M1**: local Kaggle tooling wrapper baseline ✓
- **M2**: Supabase/control plane foundation ✓
- **M3**: Python-first competition worker v0 ✓
- **M4**: Kaggle competition workflow v0 ✓
- **M5**: research and browser workflow ✓
- **M6**: multi-agent review + OTEL telemetry + local-model layer ✓
- **M7**: KCA CLI architecture (command / skill / tool / permission policy) ✓
- **M8**: product UI shell + M7 follow-ups (audit table, schema gate, ToolSpec enforcement, decision_api) ✓
- **M8.5**: pre-M9 hardening — CI repair + GitHub Issues/PR/labels interface + M9 planning ✓
- **M9**: live end-to-end Kaggle regression test — Spaceship Titanic ✓
- **M9.3**: `memory-promotion` + `design-archaeology` skills (replaces unbuilt M9.1; retires `docs/m9_1-loop-prompts.md` with deferred-scope notice) ✓

See `docs/m8-final-review.md` for M8 validation results (all 28 non-SKIP
checks PASS), `docs/m8_5-final-review.md` for the M8.5 roll-up (all 26
non-SKIP checks PASS; three PRs landed on `main` as #4, #5, #6), and
`docs/m9-final-review.md` for the M9 roll-up (30 PASS / 1 SKIP / 0 FAIL;
the SKIP is UI pnpm gates — M9 did not modify UI).

M9 metrics snapshot:
- LR baseline (M9-T002): CV accuracy **0.79144 ±0.0086** (5-fold stratified, seed=42).
- HGB + FE (M9-T005): CV accuracy **0.81192 ±0.00753** (delta **+0.02048** vs LR).
- One approved real Kaggle submission (M9-T004): public LB **0.78676**
  (`external_submission_id=52955657`,
  `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`).
- New tests: `tests/test_m9_smoke.py` (4 DB-gated assertions),
  `tests/test_m9_e2e.py` (5 dry-run tests, 0 net / 0 DB / 0 creds).

## Current milestone: M10 — notebook-submission regression (Petals to the Metal)

_Renumbered 2026-05-24: the old M10 (authorized CTF/lab) is now M11._
_Promoted to `ai:ready` on issue #12._

Status: planned (M9 exited 2026-05-24). Mirror M9's eight-Loop-Prompt
structure against [Petals to the Metal — Flower Classification on TPU](https://www.kaggle.com/competitions/tpu-getting-started)
to validate the **notebook-submission / kernel-push** end-to-end path,
the same way M9 validated the CSV-submission path on Spaceship Titanic.
Single approved real `kca kaggle push` (mirroring M9-T004's single-
submission policy); per-milestone worktree per
`docs/milestone-loop-protocol.md` §5; CV thresholds finalised in
`docs/m10-loop-prompts.md` at planning time.

Cross-cutting follow-ups carried forward from M9 (recorded in
`docs/handoffs/m9-handoff.md`), tracked as their own issues:

- **A** — `competitions.repo_url` schema drift (`area:kaggle`, `type:bug`).
- **B** — Secrets-file hygiene in pytest subprocess (issue #11, P0).
  Filed as a GitHub issue; **hard pre-req for M10-T007** so the new
  dry-run test cannot pollute the `tpu-getting-started` leaderboard.
- **C** — `decision_api`: no `GET /decisions` endpoint
  (`area:supabase`, `type:feature`).
- **D** — `reviewer_decision` literal event_type not emitted
  (`area:worker`, `type:docs`).
- **E** — Migration 0004 optional columns
  (`submissions.public_lb_score`, `submissions.run_id`) not applied to
  the local DB (`area:supabase`, `type:bug`).

See `docs/handoffs/m9-handoff.md` for the M9→M10 read-first list
(`docs/handoffs/m8_5-handoff.md` and `docs/handoffs/m8-handoff.md`
preserved for historical reference).

## Open decisions
- Decision API multi-user auth (per-user JWT via Supabase auth vs continued
  shared token).
- Artifact storage signed-URL strategy (Supabase storage vs local artifact
  service).
- Supabase queue/job mechanism for first use (SQS-style or Supabase Queues).
- First cloud deployment target: AWS vs GCP (still local-first until M11+).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis,
  Haiku/local for triage.
