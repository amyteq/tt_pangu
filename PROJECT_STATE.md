# Kaggle Code Agent — Project State

_Last updated: 2026-05-16_

## Product intent
Build a hybrid human + AI competition engineering workbench. The first target is Kaggle-style competitions, with future support for authorized CTF/lab challenges. The system should research, discuss ideas with humans, edit code, run tests/evaluations, analyze results, iterate, and prepare submissions under human-approved guardrails.

## Chosen architecture direction
- Hybrid architecture.
- Claude Code Desktop/CLI for interactive project development and dogfooding.
- Claude Agent SDK for the production coding worker.
- Python-first worker for Kaggle/ML/CTF execution.
- TypeScript/Supabase/Lovable-compatible control plane and future UI.
- GitHub is the source of truth for code, project memory, agent instructions, decisions, and tooling contracts.
- Supabase is the control plane and audit database, not the primary code execution environment.

## Current MVP boundary
1. Local-first repository workflow with `CLAUDE.md`, skills, hooks, subagents, and GitHub.
2. Supabase schema for projects, sessions, jobs, messages, research notes, experiments, runs, submissions, artifacts, and approvals.
3. Kaggle baseline loop: understand competition, create validation, run baseline, record metrics, iterate, prepare submission.
4. Browser/research loop: fetch pages, summarize sources, track trust and citations.
5. Authorized CTF sandbox loop only for explicit challenge environments.

## Human approval gates
Require approval for:
- Kaggle competition submissions.
- Kaggle kernel/notebook pushes.
- Any remote write operation.
- Any operation touching credentials, secrets, or account settings.
- Any CTF action outside a declared sandbox/challenge scope.

## Current milestone: M0 — project baseline

Task `M0-T001` is in progress. Deliverables: repository docs distinguish platform-development coding agents from runtime competition code agents; GitHub files are documented as durable memory; branch/PR/secrets rules are documented; test commands or blockers are recorded.

Known M0 blockers:
- No `pyproject.toml` or test suite — `uv run pytest` will fail. Documenting as a M1 setup prerequisite.
- No `package.json` — TypeScript project not initialized. Expected in M2+.
- `tools/legacy/` scripts exist but are not yet wrapped — that is M1 scope.

## Open decisions
- Exact worker runtime: local Docker first, cloud runner later.
- Model routing policy thresholds: when to use Sonnet, Opus, GPT-5.5, GPT-5.5 Pro, or local models.
- Existing Kaggle scripts inventory and wrapper design (`tools/legacy/` contains kkp.py, kkr.py, nb2py.py, py2nb.py, nb2test.py, py2test.py, nb2md.py, jrun.py).
- Which competitions become the first regression suite.
