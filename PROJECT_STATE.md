# Kaggle Code Agent — Project State

_Last updated: 2026-06-10 (M14 close — goal-driven Kaggle workflow; M13 close + M12 close + M11 partial close on 2026-06-09; M10 close on 2026-05-28)_

## Product intent
Build a hybrid human + AI competition engineering workbench. The first target is Kaggle-style competitions, with future support for authorized CTF/lab challenges. The system should research, discuss ideas with humans, edit code, run tests/evaluations, analyze results, iterate, and prepare submissions under human-approved guardrails.

## Chosen architecture direction

> **Superseded in part (2026-09-15, issue #189).** The "Claude Agent SDK for the production coding worker" line below predates the phase-1/phase-2 rewrite. `CLAUDE.md` → *Mission* is current: **KCA is not built on Claude Code or the Claude Agent SDK**; those are development harnesses and phase-1 drivers. Both `CLAUDE.md` and `AGENTS.md` win over this section, and both harnesses are told so. Full rewrite tracked in #188.

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

> **Partly superseded (2026-09-15, issue #189).** Read this list item by item — it is no longer wholly wrong or wholly right. The two **Kaggle** items are current policy: ADR-0022 §5 relaxes them only for a competition meeting activation conditions A1-A7, and none does, so ask. **"Any remote write operation"** and **"PR merges"** are superseded by the dev-phase policy in `CLAUDE.md` → *GitHub collaboration*, mirrored to `AGENTS.md`: non-destructive GitHub writes are auto-allowed, and in phase 1 you squash-merge your own feature-branch PR yourself once required checks are green — no separate approval. What does still need explicit human approval there is a **permanent deletion**; force-push is **denied outright — not approvable**. The **credentials/secrets** and **CTF scope** items stand as written. For **phase 2 / KCA** the list is wrong in the opposite direction: ADR-0021 §2 makes KCA's push and submit autonomous by default once `autonomy.screen` passes — design intent, not yet code, as the enforcement gaps below record.

Require approval for:
- Kaggle competition submissions. The relaxations in ADR-0021 §2 and ADR-0022 §5 are design intent awaiting the code that can evaluate their preconditions, so this gate is the policy today. **It is not enforced anywhere:** `tools/kca/kg.py:21-22` defaults `kaggle_submit` to *allow*, `.kca/permissions/*.yaml` is read only by `tools/kca/skill.py`, and `.claude/settings.json:91-92` allow-lists the direct submit commands. Follow it as a rule; nothing will stop you (`docs/adr/0022-long-run-competition-operating-model.md` §5, condition A5).
- Kaggle kernel/notebook pushes — same rule. Gated in the `kaggle kernels push` and `python tools/kca/kca.py kaggle push` forms only (`guard_tool.py:171,177`).
- Any remote write operation.
- Any operation touching credentials, secrets, or account settings.
- Any CTF action outside a declared sandbox/challenge scope.
- PR merges (create is allowed, merge requires approval).

Mutations from the UI flow through `services/decision_api/` (FastAPI) → `tools/kca/decisions.py` → DB. The browser bundle never holds a Supabase service-role key. The M7 permission policy resolution stays authoritative.

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
- **M9.3**: `memory-promotion` + `design-archaeology` skills (replaces unbuilt M9.1; retires `docs/milestones/m9_1/loop-prompts.md` with deferred-scope notice) ✓
- **M9.4**: Discovery / Debate Gate agents (planning + scaffolding) ✓
- **M10**: notebook-submission Kaggle regression — Petals to the Metal (kernel-push path) ✓ — one approved real `kaggle kernels push` attempted; no public LB recorded (queue stall + now-fixed kernelspec bug; single-push policy, "accept and continue"); issue #11 (dotenv-leak) closed during M10.
- **M11**: authorized CTF / lab workflow — PARTIAL (T000–T006 + T008 done 2026-06-09; T007 deferred pending human-supplied live-event credentials + approval)
- **M12**: Devpost / hackathon workflow ✓ (with T007 real-submit DEFERRED — see open items below)
- **M13**: evaluation, reliability, and regression suite ✓ — 6 suites (tool-smoke, kaggle-replay ×3, kernel-dryrun, reasoning), 5 routes, aggregator reports, nightly CI eval cron; 34 PASS / 4 SKIP / 0 FAIL; no paid LLM calls; no real Kaggle calls; `decision:confirmed` gate-bypass per `/goal` directive.
- **M14**: goal-driven Kaggle workflow ✓ — `kca goal {init,show,update}` + `goal.md`, `kca explore {init,run,rank,prune,propose-next}` local fan-out + screening, per-competition concurrency + daily-budget gate + creds pre-check, smart poller (Fibonacci QUEUED / stable RUNNING / batched `kernels list`), stuck detector + `kaggle.exploration_stuck` escalation, migration 0011 (`goals` + rule columns + `submissions.goal_id` + `experiment_runs.analysis_jsonb`). 21 PASS / 3 SKIP / 0 FAIL. **T008 live = PASS-WITH-DEVIATION**: 2 real kernel pushes (gate/poll/approval/audit all worked) but **0 new LB scores** — push ≠ leaderboard submission (#77) + push #2 alt-backbone kernel data-mount error; best-known LB stays 0.76505. T009 fixed 5 cloud-schema bugs the live run surfaced + added the eval-suite PR gate (#63). Follow-ups #77 (submit step), #78 (refresh-rules port).

See `docs/milestones/m8/final-review.md` for M8 validation results (all 28 non-SKIP checks PASS), `docs/milestones/m8_5/final-review.md` for the M8.5 roll-up (all 26 non-SKIP checks PASS; three PRs landed on `main` as #4, #5, #6), `docs/milestones/m9/final-review.md` for the M9 roll-up (30 PASS / 1 SKIP / 0 FAIL; the SKIP is UI pnpm gates — M9 did not modify UI), `docs/milestones/m9_4/final-review.md` for the M9.4 roll-up (17 PASS / 1 SKIP / 0 FAIL; the SKIP is the `design-archaeology` skill loader, deferred to M9.3-T001 by design), `docs/milestones/m12/final-review.md` for the M12 roll-up (46 PASS / 0 SKIP / 0 FAIL / 1 DEFERRED — T007 real-submit pending 3 blocked artefacts), `docs/milestones/m13/final-review.md` for the M13 roll-up (34 PASS / 4 SKIP / 0 FAIL), and `docs/milestones/m14/final-review.md` for the M14 roll-up (21 PASS / 3 SKIP / 0 FAIL; T008 live PASS-WITH-DEVIATION — 2 real pushes, 0 LB scores via the push≠submit gap #77).

M9 metrics snapshot:
- LR baseline (M9-T002): CV accuracy **0.79144 ±0.0086** (5-fold stratified, seed=42).
- HGB + FE (M9-T005): CV accuracy **0.81192 ±0.00753** (delta **+0.02048** vs LR).
- One approved real Kaggle submission (M9-T004): public LB **0.78676** (`external_submission_id=52955657`, `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`).
- New tests: `tests/test_m9_smoke.py` (4 DB-gated assertions), `tests/test_m9_e2e.py` (5 dry-run tests, 0 net / 0 DB / 0 creds).

## M10 metrics snapshot (see `docs/milestones/m10/final-review.md`, 26 PASS / 1 SKIP / 0 FAIL)

- Baseline transfer learning (M10-T002, MobileNetV2): local-slice holdout **0.4310** (full-dataset reference ~0.7707); `experiment_run_id=830fc32f-…`.
- Alt backbone (M10-T005, EfficientNetB0): local-slice holdout **0.3966** (−3.4pp vs baseline, within the 10pp guard); `experiment_run_id=c3339154-…`.
- One approved real Kaggle kernel push (M10-T004): **NO public LB recorded** — push #1 stalled QUEUED ~66 min; approved re-push #2 errored on a missing `metadata.kernelspec` (now fixed in `tools/legacy/py2nb.py`). `submissions.id=03b5d080-…` exists with `public_score` NULL. Single-push policy → "accept and continue". Re-push tracked by issues #34 / #35; notebook is push-ready.
- Issue #11 (dotenv-leak / Kaggle LB pollution; M9 follow-up B) CLOSED during M10: `tools/kca/db.py` guards repo-root `.env` auto-load behind `KCA_SKIP_DOTENV`.
- New tests: `tests/test_m10_smoke.py` (4 DB-gated assertions), `tests/test_m10_e2e.py` (dry-run e2e + 0-real-push audit sentinel).

## M13 metrics snapshot (see `docs/milestones/m13/final-review.md`, 34 PASS / 4 SKIP / 0 FAIL)

- Suites: 6 (tool-smoke, kaggle-replay-titanic, kaggle-replay-spaceship-titanic, kaggle-replay-house-prices, kernel-dryrun, reasoning).
- Routes: 5 (mocked, local_vllm, claude_haiku_4_5, claude_sonnet_4_6, gpt_4o).
- Canonical baseline snapshot: `runs/m13-eval/20260608T211005Z/report.{json,md}`; `run_id=b89f2f89-…`; 5 PASS / 0 FAIL / 20 SKIP / 0 ERROR; cost $0.00.
- Migration **0010_m13_eval.sql** (renumbered from 0008 after M11 took 0008 and M12 took 0009) — applied to cloud Supabase (eval_suites, eval_runs, eval_results).
- Nightly CI cron: `.github/workflows/eval.yml` at 03:30 UTC; `--route mocked`.
- New tests: `tests/test_m13_smoke.py` (6), `tests/test_m13_e2e.py` (6), `tests/test_m13_t006_routes.py` (16), `tests/test_m13_t007_report.py` (9).
- Post-merge pytest: **149 passed / 8 skipped / 0 failed** (cloud DSN).
- No paid LLM calls. No real Kaggle calls. Cost: $0.00.

## Current milestone: M15 in progress — goal-loop submit step (#77, #78) + ADR-0018 hardening (#59, #60, #61) + Docker retire/parity (#64)

_M10 closed 2026-05-28. M11 PARTIAL + M12 + M13 closed 2026-06-09. M14 closed 2026-06-10. All numbered milestones M0–M14 in `docs/milestones/README.md` are now ✓ done (M11 with T007 deferred; M12 with T007 deferred; M14 with T008's "≥ 2 LB scores" PASS-WITH-DEVIATION via the push≠submit gap #77). M15 planned 2026-06-17 — task specs + loop prompts drafted (`docs/milestones/m15/loop-prompts.md`, `docs/tasks/m15/M15-T000…T008-*.md`)._

M15 closes the goal loop on real LB signal and pays down the ADR-0018 tech-debt. The new submit step runs **autonomously under the KCA autonomy model** (`docs/adr/0021-kca-autonomy-model.md`): when `autonomy.enabled` is true in the file `competition.yaml:autonomy_config` names (ADR-0022 §5 **A1**) and `autonomy.screen` passes, KCA submits without per-action approval and persists a transactional intended-submission record in Supabase before dispatch — ADR-0022 §5's **A6**. Phase-1 drivers instead use `competitions/<slug>/submissions/<timestamp>-<intent-id>.yaml`; these are separate phase authorities, never dual writes. `.agent/kca/audit.jsonl` is supplementary evidence, not the record. Scenario-4 / over-budget / ambiguous-rules stay human-gated, as do final-submission selection and external-data decisions (ADR-0022 §5's seven-item floor). **Design intent, not current behaviour:** no code evaluates `autonomy.screen`, so this paragraph describes what M15 was aiming at, not what the tree does. Nor is the approval gate above enforced — see it for the `file:line` evidence. Until the gates in ADR-0022 §5's condition A5 are implemented, the submit step is neither autonomous nor gated: it is a human deciding, every time.

M15 task breakdown (full scope in `docs/tasks/m15/`):

- **T000** [`arch:`] — explicit-submit-step design + ADR-0020 addendum + the 8 downstream task specs.
- **T001 (#78)** — port `kca competition refresh-rules` off the removed `competition_view` onto kaggle 2.0.x; keep the degradation path.
- **T002 (#77)** — explicit submit step (push → terminal → submit → score) + ADR-0021 autonomy screen + `_check_budget_gates` counts the submit. **Headline.**
- **T003 (#59)** — JSON-Schema per `competition_type` for `submission_format` + read-time permissive validator (ADR-0018 F1).
- **T004 (#60)** — migration 0012 `human_decisions.approved_by_user_id` + populate + resolver (ADR-0018 F2).
- **T005 (#61)** — `profile_fallback` event in `permission_policy.py` (ADR-0018 F3).
- **T006 (#64)** — cloud Supabase parity check / retire local Docker.
- **T007** — live autonomous submit validation: ≥ 1 real LB score, closing the M14-T008 deviation.
- **T008** — regression tests + exit criteria + `docs/milestones/m15/final-review.md` + M16 handoff.

**Deferred to M16** (`decision:needed`, not pulled into `ai:ready`): #21 / #85 (cross-account quota pool + multi-account user pool), #83 (cheaper / free GPU compute), and the `approved_by_user_id` FK target (`auth.users`) finalised once Supabase auth lands.

Other prioritised work, in approximate order:

1. **M11-T007** — live CTFtime event submit (deferred pending human-supplied credentials + approval). See M11 unblock checklist below.
2. **M12-T007** — real Devpost submit (deferred pending 3 blocked artefacts: demo video, Vercel deployment link, screenshots). See M12 unblock below.
3. **M13.1** — CTF / lab eval cases (issue #48, `decision:needed`; now unblocked since M11 PARTIAL landed — CTF infrastructure exists).
4. **M13.2** — Hackathon / Devpost eval cases (issue #49, `decision:needed`; now unblocked since M12 landed — hackathon infrastructure exists).
5. Cross-cutting M9 / M11 follow-ups (still open; listed below).

### Open items

**M12-T007 deferred real Devpost submit** (P0 — `policy:approval-required`):

- `human_decisions.id=754cadda-3e08-4072-8bd0-2a088dbd4a06` is pending.
- 3 blocked artefacts needed: demo video, Vercel deployment link, screenshots.
- Resume command once artefacts are ready:
  ```
  kca devpost submit --slug h01 --run-id r-20260608_154243 \
    --message "<your submit message>"
  ```
  then: `kca decisions approve --id 754cadda-3e08-4072-8bd0-2a088dbd4a06`
- Approval comment: #42#issuecomment-4650855888.
- File as a follow-up issue (`type:feature`, `area:tools`, `priority:P0`, `policy:approval-required`, `ai:blocked`) once artefacts are available.

### M11 partial deliverables (shipped 2026-06-09)

- `supabase/migrations/0008_m11_ctf.sql` — 4 ctf_* tables; cloud applied.
- `src/db/ctf.py` — 6 DB helpers.
- `tools/kca/ctf.py` — 12 subcommands across 5 namespaces.
- `data/ctf/kca-fixtures-2026/` — web-1 (cookie-tamper) + crypto-1 (tiny RSA) bespoke fixtures.
- ADR-0016 (CTF data model) + ADR-0017 (CTF approval gates).
- `docs/architecture/m11-ctf-workflow.md` — 7-section workflow doc.
- `challenge_run`, `flag_submit`, `network_egress` in all 3 permission profiles.
- 3 test files: `test_m11_e2e.py` (8/8), `test_m11_smoke.py` (7/7 SKIP without DSN), `test_m11_db.py` (13/13).
- T005 local solves: web `flag_length=21`, crypto `flag_length=17`; 2 `ctf_attempts(accepted=true)` in cloud.
- T006 reviewer-gate: `challenge_run` + `flag_submit` approve round-trips; `network_egress` reject smoke.

See `docs/milestones/m11/final-review.md` (23 PASS / 1 SKIP-BLOCKED / 0 FAIL) and `docs/milestones/m11/handoff.md` for the full handoff.

### M11-T007 unblock (human action required)

1. Set `KCA_ALLOW_REMOTE=1`.
2. Register on a live CTFtime event + populate `~/.ctf/<slug>.json`.
3. Run `kca ctf event register` + `kca ctf scope set` for the live event.
4. Comment "approved to submit" on the T007 closing issue + add `decision:confirmed`/`ai:ready` labels.
5. Re-run M11-T007 Loop Prompt.

### Cross-cutting follow-ups from M11 (file as GitHub issues)

- **A** — `agent_jobs.competition_id` schema drift on cloud (`type:bug`, `area:supabase`, P2).
- **B** — `kca ctf flag submit` non-dry-run env-check before reviewer-gate (`type:bug`, `area:security`, P1).
- **C** — T004 fixture-authoring trail in `.agent/audit/tool-events.jsonl` contains deterministic crypto flag (`type:security`, `area:testing`, P1).
- **D** — `expected.sha256` web-1 churn — regenerates per solve harness run (`type:test-gap`, `area:ctf`, P2).
- **E** — gh CLI hook denial blocks `decision:confirmed` verification (`type:bug`, `area:security`, `area:ci`, P2).
- **F** — httpx-level `network_egress` interceptor for subprocess egress deferred (ADR-0017 §pinning) (`type:feature`, `area:security`, P1).
- **G** — per-challenge rate-limit column on `ctf_scopes` (`type:feature`, `area:ctf`, P3).

### M13-surfaced follow-ups

- **M13.1 (issue #48)** — CTF / lab eval cases (now unblocked — M11 PARTIAL landed; `decision:needed` for scoping).
- **M13.2 (issue #49)** — Hackathon / Devpost eval cases (now unblocked — M12 landed; `decision:needed` for scoping).

### M10-surfaced follow-ups (carried forward)

- **#34** — M10-T004 needs a future approved re-push to record a public LB score (notebook is push-ready after the py2nb kernelspec fix).
- **#35** — kernel-run queue-stall robustness + slug/title fix (kernelspec fix landed in the M10 PR).

### Cross-cutting follow-ups carried forward from M9 (unchanged after M10/M11/M12/M13)

- **M9-A** — `competitions.repo_url` schema drift (`area:kaggle`, `type:bug`) — still open.
- **M9-B** — Secrets-file hygiene in pytest subprocess (issue #11, P0) — **RESOLVED in M10** via `KCA_SKIP_DOTENV` guard in `tools/kca/db.py`; issue #11 CLOSED.
- **M9-C** — `decision_api`: no `GET /decisions` endpoint (`area:supabase`, `type:feature`) — still open.
- **M9-D** — `reviewer_decision` literal event_type not emitted (`area:worker`, `type:docs`) — still open.
- **M9-E** — Migration 0004 optional columns not applied to local DB (`area:supabase`, `type:bug`) — still open.

### M12 ADR-0018 follow-ups (from `docs/adr/0018-generalized-competition-type.md`)

- **F1** (#59) — jsonb type-check for `submission_format` (P2 tech-debt) — **scheduled M15-T003**.
- **F2** (#60) — `approved_by_user_id` FK on `human_decisions` (P1) — **scheduled M15-T004**.
- **F3** (#61) — resolver `profile_fallback` event type in `permission_policy.py` — **scheduled M15-T005**.
- **F4** — `ctf-runner.yaml` permission profile — **DONE in M11** (M11 shipped CTF permission-profile extensions; M12 ADR-0018 F4 is superseded).

See `docs/milestones/m13/handoff.md` for the M13→post-M13 read-first list, `docs/milestones/m12/handoff.md` for the M12→M13 handoff, and `docs/milestones/m11/handoff.md` for the M11 PARTIAL→M12 handoff (`docs/milestones/m10/handoff.md` and earlier preserved for history).

## Open decisions
- **ADR-0018** (resolved, M12-T001, 2026-06-09): generalized `competition_type` enum on `competitions` — Alternative A (folded enum) picked. Enum literal `('kaggle', 'devpost', 'hackathon_devpost', 'ctf', 'generic')`. ADR-0006 + ADR-0009 referenced, not superseded. Renumbered from 0016→0018 during PR #46 merge (M11 took 0016 + 0017). Follow-ups F1–F4 listed in Open items above. See `docs/adr/0018-generalized-competition-type.md`.
- Decision API multi-user auth (per-user JWT via Supabase auth vs continued shared token).
- Artifact storage signed-URL strategy (Supabase storage vs local artifact service).
- Supabase queue/job mechanism for first use (SQS-style or Supabase Queues).
- First cloud deployment target: AWS vs GCP (still local-first until M11+).
- Model routing policy thresholds: Sonnet for implement, Opus for eval/analysis, Haiku/local for triage.
