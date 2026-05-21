# Kaggle Code Agent — Project State

_Last updated: 2026-05-21 (M7 exit)_

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
2. Supabase schema for projects, sessions, jobs, messages, research notes, experiments, runs, submissions, artifacts, and approvals.
3. Kaggle baseline loop: understand competition, create validation, run baseline, record metrics, iterate, prepare submission.
4. Browser/research loop: fetch pages, summarize sources, track trust and citations.
5. Multi-agent reviewer gate + OTEL telemetry + local GPU model layer.
6. Authorized CTF sandbox loop only for explicit challenge environments.

## Human approval gates
Require approval for:
- Kaggle competition submissions.
- Kaggle kernel/notebook pushes.
- Any remote write operation.
- Any operation touching credentials, secrets, or account settings.
- Any CTF action outside a declared sandbox/challenge scope.
- PR merges (create is allowed, merge requires approval).

## Completed milestones
- **M0**: project baseline and memory discipline ✓
- **M1**: local Kaggle tooling wrapper baseline ✓
- **M2**: Supabase/control plane foundation ✓
- **M3**: Python-first competition worker v0 ✓
- **M4**: Kaggle competition workflow v0 ✓
- **M5**: research and browser workflow ✓
- **M6**: multi-agent review + OTEL telemetry + local-model layer ✓
- **M7**: KCA CLI architecture (command / skill / tool / permission policy) ✓

See `docs/m7-final-review.md` for M7 validation results (28/28 checks PASS).

## Current milestone: M8 — product UI shell

Status: planned. Expose the control plane through a React/TypeScript UI (Next.js or Vite) built in Claude Code: approval inbox, run timeline, experiment table, artifact browser. M7 follow-ups (skill → worker wiring, DB audit table, tool executor integration) tracked in `docs/m7-final-review.md` § M8 follow-ups.

## Open decisions
- TypeScript-only platform service vs TypeScript API + Python worker from day one (M8 concern).
- Supabase queue/job mechanism for first use (SQS-style or Supabase Queues).
- First cloud deployment target: AWS vs GCP (M8+ concern; local-first until then).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis, Haiku/local for triage.
