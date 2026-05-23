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

## Current milestone: M10 — authorized CTF/lab workflow

Status: planned (M9 exited 2026-05-24). Support CTF-style challenges
only inside explicit authorization boundaries: challenge scope +
authorization metadata; local container/lab-only execution; solver
script generation and testing; writeup generation; hard policy blocks
for external scanning, real targets, credential theft, persistence, or
unsafe actions.

Entry-point note: five cross-cutting follow-ups (A–E) surfaced during
M9 and are recorded in `docs/handoffs/m9-handoff.md`. Each should be
filed as a GitHub issue under `.github/ISSUE_TEMPLATE/` before the
matching M10 (or earlier) work begins. Summary:

- **A** — `competitions.repo_url` schema drift (`area:kaggle`, `type:bug`).
- **B** — `.env` hygiene in pytest subprocess; live-DB run on a host
  with populated `.env` leaks Kaggle creds via
  `tools/kca/db.py::load_dotenv` (M8.5 carry-over;
  `type:test-gap`, `area:testing`).
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
- First cloud deployment target: AWS vs GCP (still local-first until M10+).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis,
  Haiku/local for triage.
