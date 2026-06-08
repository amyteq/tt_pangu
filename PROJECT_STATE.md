# Kaggle Code Agent — Project State

_Last updated: 2026-06-09 (M12 close)_

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
- **M12**: Devpost / hackathon workflow ✓ (with T007 real-submit DEFERRED — see open items below)

See `docs/m8-final-review.md` for M8 validation results (all 28 non-SKIP
checks PASS), `docs/m8_5-final-review.md` for the M8.5 roll-up (all 26
non-SKIP checks PASS; three PRs landed on `main` as #4, #5, #6),
`docs/m9-final-review.md` for the M9 roll-up (30 PASS / 1 SKIP / 0 FAIL;
the SKIP is UI pnpm gates — M9 did not modify UI),
`docs/m9_4-final-review.md` for the M9.4 roll-up (17 PASS / 1 SKIP /
0 FAIL; the SKIP is the `design-archaeology` skill loader, deferred to
M9.3-T001 by design), and `docs/m12-final-review.md` for the M12 roll-up
(46 PASS / 0 SKIP / 0 FAIL / 1 DEFERRED — T007 real-submit pending 3
blocked artefacts).

M9 metrics snapshot:
- LR baseline (M9-T002): CV accuracy **0.79144 ±0.0086** (5-fold stratified, seed=42).
- HGB + FE (M9-T005): CV accuracy **0.81192 ±0.00753** (delta **+0.02048** vs LR).
- One approved real Kaggle submission (M9-T004): public LB **0.78676**
  (`external_submission_id=52955657`,
  `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`).
- New tests: `tests/test_m9_smoke.py` (4 DB-gated assertions),
  `tests/test_m9_e2e.py` (5 dry-run tests, 0 net / 0 DB / 0 creds).

## Current milestone: M13 — evaluation, reliability, and regression suite

_M12 exited 2026-06-09 with T007 real-submit deferred (pending 3 artefacts).
M11 (authorized CTF/lab workflow) and M10 (notebook-submission regression) may
be in flight in parallel; M13 does not depend on either completing first._

Status: planned (M12 exited 2026-06-09). See `docs/m13-loop-prompts.md` and
commit `c53bbaa` for the M13 planning docs (already landed on main).

### Open items at M12 exit

**T007 deferred real Devpost submit** (P0 — `policy:approval-required`):

- `human_decisions.id=754cadda-3e08-4072-8bd0-2a088dbd4a06` is pending.
- 3 blocked artefacts needed: demo video, Vercel deployment link, screenshots.
- Resume command once artefacts are ready:
  ```
  kca devpost submit --slug h01 --run-id r-20260608_154243 \
    --message "<your submit message>"
  ```
  then: `kca decisions approve --id 754cadda-3e08-4072-8bd0-2a088dbd4a06`
- Approval comment: #42#issuecomment-4650855888.
- File as a follow-up issue (`type:feature`, `area:tools`, `priority:P0`,
  `policy:approval-required`, `ai:blocked`) once artefacts are available.

Cross-cutting follow-ups carried forward from M9 (still open, tracked as their
own issues per `docs/handoffs/m9-handoff.md`):

- **A** — `competitions.repo_url` schema drift (`area:kaggle`, `type:bug`).
- **B** — Secrets-file hygiene in pytest subprocess (issue #11, P0).
- **C** — `decision_api`: no `GET /decisions` endpoint (`area:supabase`, `type:feature`).
- **D** — `reviewer_decision` literal event_type not emitted (`area:worker`, `type:docs`).
- **E** — Migration 0004 optional columns not applied (`area:supabase`, `type:bug`).

M12 ADR-0016 follow-ups (from `docs/adr/0016-generalized-competition-type.md`):

- **F1** — jsonb type-check for `submission_format` (P2 tech-debt).
- **F2** — `approved_by_user_id` FK on `human_decisions` (P1).
- **F3** — resolver `profile_fallback` event type in `permission_policy.py`.
- **F4** — ship `ctf-runner.yaml` permission profile (M11 task).

See `docs/handoffs/m12-handoff.md` for the M12→M13 read-first list.

## Open decisions
- **ADR-0016** (resolved, M12-T001, 2026-06-09): generalized
  `competition_type` enum on `competitions` — Alternative A (folded enum)
  picked. Enum literal `('kaggle', 'devpost', 'hackathon_devpost',
  'ctf', 'generic')`. ADR-0006 + ADR-0009 referenced, not superseded.
  Follow-ups F1–F4 listed in Open items above. See
  `docs/adr/0016-generalized-competition-type.md`.
- Decision API multi-user auth (per-user JWT via Supabase auth vs continued
  shared token).
- Artifact storage signed-URL strategy (Supabase storage vs local artifact
  service).
- Supabase queue/job mechanism for first use (SQS-style or Supabase Queues).
- First cloud deployment target: AWS vs GCP (still local-first until M11+).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis,
  Haiku/local for triage.
