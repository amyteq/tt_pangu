# Kaggle Code Agent — Project State

_Last updated: 2026-05-23 (M8 exit)_

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

See `docs/m8-final-review.md` for M8 validation results (all 28 non-SKIP checks PASS).

## Current milestone: M9 — live Kaggle regression test

Status: planned. Drive the M8 surface end-to-end against a real
Kaggle competition (Spaceship Titanic) under the approval gates: baseline
training, CV scoring, submission preparation, human-approved submit,
leaderboard ingest. Reuse the worker + decision_api + UI shell. See
`docs/handoffs/m8-handoff.md` for the read-first list.

## Open decisions
- Decision API multi-user auth (per-user JWT via Supabase auth vs continued
  shared token).
- Artifact storage signed-URL strategy (Supabase storage vs local artifact
  service).
- Supabase queue/job mechanism for first use (SQS-style or Supabase Queues).
- First cloud deployment target: AWS vs GCP (still local-first until M10+).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis,
  Haiku/local for triage.
