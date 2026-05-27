# Kaggle Code Agent — Project State

_Last updated: 2026-05-28 (M10 close)_

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
- **M9.2**: `/save-log` Claude Code session-transcript skill ✓ — operator-tooling milestone; ran in parallel to M10 planning.
- **M9.3**: `memory-promotion` + `design-archaeology` skills (replaces unbuilt M9.1; retires `docs/m9_1-loop-prompts.md` with deferred-scope notice) ✓
- **M9.4**: Discovery / Debate Gate agents (planning + scaffolding) ✓
- **M10**: notebook-submission Kaggle regression — Petals to the Metal (kernel-push path) ✓ — one approved real `kaggle kernels push` attempted; no public LB recorded (queue stall + now-fixed kernelspec bug; single-push policy, "accept and continue"); issue #11 (dotenv-leak) closed during M10.

See `docs/m8-final-review.md` for M8 validation results (all 28 non-SKIP
checks PASS), `docs/m8_5-final-review.md` for the M8.5 roll-up (all 26
non-SKIP checks PASS; three PRs landed on `main` as #4, #5, #6),
`docs/m9-final-review.md` for the M9 roll-up (30 PASS / 1 SKIP / 0 FAIL;
the SKIP is UI pnpm gates — M9 did not modify UI), and
`docs/m9_4-final-review.md` for the M9.4 roll-up (17 PASS / 1 SKIP /
0 FAIL; the SKIP is the `design-archaeology` skill loader, deferred to
M9.3-T001 by design).

M9 metrics snapshot:
- LR baseline (M9-T002): CV accuracy **0.79144 ±0.0086** (5-fold stratified, seed=42).
- HGB + FE (M9-T005): CV accuracy **0.81192 ±0.00753** (delta **+0.02048** vs LR).
- One approved real Kaggle submission (M9-T004): public LB **0.78676**
  (`external_submission_id=52955657`,
  `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`).
- New tests: `tests/test_m9_smoke.py` (4 DB-gated assertions),
  `tests/test_m9_e2e.py` (5 dry-run tests, 0 net / 0 DB / 0 creds).

M10 metrics snapshot (see `docs/m10-final-review.md`, 26 PASS / 1 SKIP / 0 FAIL):
- Baseline transfer learning (M10-T002, MobileNetV2): local-slice holdout
  **0.4310** (full-dataset reference ~0.7707); `experiment_run_id=830fc32f-…`.
- Alt backbone (M10-T005, EfficientNetB0): local-slice holdout **0.3966**
  (−3.4pp vs baseline, within the 10pp guard); `experiment_run_id=c3339154-…`.
- One approved real Kaggle kernel push (M10-T004): **NO public LB recorded** —
  push #1 stalled QUEUED ~66 min; approved re-push #2 errored on a missing
  `metadata.kernelspec` (now fixed in `tools/legacy/py2nb.py`). `submissions.id=03b5d080-…`
  exists with `public_score` NULL. Single-push policy → "accept and continue".
  Re-push tracked by issues #34 / #35; notebook is push-ready.
- Issue #11 (dotenv-leak / Kaggle LB pollution; M9 follow-up B) CLOSED during M10:
  `tools/kca/db.py` guards repo-root `.env` auto-load behind `KCA_SKIP_DOTENV`.
- New tests: `tests/test_m10_smoke.py` (4 DB-gated assertions),
  `tests/test_m10_e2e.py` (dry-run e2e + 0-real-push audit sentinel).

## Current milestone: M11 — authorized CTF/lab workflow (planned)

_Renumbered 2026-05-24: the old M10 (authorized CTF/lab) became M11 to
make room for the notebook-submission regression M10, now ✓ done._

Status: planned (M10 exited 2026-05-28; see `docs/m10-final-review.md`,
26 PASS / 1 SKIP / 0 FAIL). M11 brings the platform's authorized
CTF/lab challenge workflow online — challenge metadata + container lab
+ writeup — inside explicitly authorized sandbox environments only (no
third-party scanning, no real targets, no credential theft). See
`docs/milestones.md §M11` and `docs/handoffs/m10-handoff.md` for the
read-first list and carried-forward items.

Cross-cutting follow-ups status after M10:

- **B** — Secrets-file hygiene in pytest subprocess (issue #11, P0):
  **RESOLVED** during M10 (`KCA_SKIP_DOTENV` guard in
  `tools/kca/db.py`); issue #11 CLOSED.
- **A** — `competitions.repo_url` schema drift (`area:kaggle`,
  `type:bug`) — still open.
- **C** — `decision_api`: no `GET /decisions` endpoint
  (`area:supabase`, `type:feature`) — still open.
- **D** — `reviewer_decision` literal event_type not emitted
  (`area:worker`, `type:docs`) — still open.
- **E** — Migration 0004 optional columns
  (`submissions.public_lb_score`, `submissions.run_id`) not applied to
  the local DB (`area:supabase`, `type:bug`) — still open.

M10-surfaced follow-ups:

- **#34** — M10-T004 needs a future approved re-push to record a public
  LB score (notebook is push-ready after the py2nb kernelspec fix).
- **#35** — kernel-run queue-stall robustness + slug/title fix
  (kernelspec fix landed in the M10 PR).

See `docs/handoffs/m10-handoff.md` for the M10→M11 read-first list
(`docs/handoffs/m9-handoff.md` and earlier preserved for history).

## Open decisions
- Decision API multi-user auth (per-user JWT via Supabase auth vs continued
  shared token).
- Artifact storage signed-URL strategy (Supabase storage vs local artifact
  service).
- Supabase queue/job mechanism for first use (SQS-style or Supabase Queues).
- First cloud deployment target: AWS vs GCP (still local-first until M11+).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis,
  Haiku/local for triage.
