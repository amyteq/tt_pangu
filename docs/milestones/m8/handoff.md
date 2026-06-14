# M8 → M9 Handoff Prompt

_Generated 2026-05-23 from `docs/milestones/m8/final-review.md` and `docs/milestones/README.md` § M9._

Paste this into a fresh session that is starting **M9 (live Kaggle
regression test — Spaceship Titanic)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M8 are complete.** Your job is to start **M9**.

M8 shipped the operator-facing UI shell + the M7 follow-ups (audit
table, schema gate, ToolSpec enforcement, decision_api). M9 is the
first end-to-end live regression: drive the worker + decision_api + UI
shell against a real Kaggle competition under the approval gates.

## Read these files first

1. `PROJECT_STATE.md` — current state at M8 exit.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions.
4. `docs/milestones/README.md` — **especially the M9 section** (planned
   capabilities + exit criteria).
5. `docs/milestones/m8/final-review.md` — what landed in M8 (28-check matrix) and
   the M9 follow-ups list.
6. `docs/architecture/m8-ui-shell.md` — the UI shell + decision_api
   layering, gate semantics, auth model.
7. `docs/architecture/kca-cli-architecture.md` — Command / Skill / Tool
   / Job layers that the UI calls into.
8. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template (this file
   already uses it).
9. Latest ADRs in `docs/adr/` — especially `0014-ui-stack.md`.

## State at M8 exit

- All 28 non-SKIP exit checks PASS (see `docs/milestones/m8/final-review.md`).
- New backend wiring: migration `0007_m8_tool_audit.sql`;
  `tools/kca/agent/skill_schema.py`; `src/worker/worker.py::_tool_call`
  with `PolicyViolation` + ToolSpec enforcement; `JobPolicy.tool_decisions`
  populated by `kca skill run --execute`; `services/decision_api/app.py`
  FastAPI service.
- New UI: `ui/` Vite + React + TS SPA with Dashboard, Run Timeline,
  Experiments, Research, Approval Inbox, Decision Gate, Artifacts. 13
  vitest cases + 4 Playwright cases.
- New tests: `tests/test_m8_smoke.py` (13), `tests/test_m8_worker_wiring.py`
  (3), `services/decision_api/tests/test_decision_api.py` (5).
- CI: `.github/workflows/test.yml` now has `no-db`, `live-db` (gated to
  push/main + same-repo PRs), `lint`, and `ui` jobs.

## M9 follow-ups carried forward

1. Decision API multi-user auth (per-user JWT via Supabase auth instead
   of the shared `KCA_DECISION_API_TOKEN`).
2. Artifact preview via Supabase storage signed URLs or a small
   `services/artifact_api/`.
3. Live-DB CI on PRs from forks (read-only secrets pattern).
4. OTEL collector wiring: the swim-lane currently reads
   `agent_telemetry_spans` directly; route through a collector once it
   lands.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- Never submit to Kaggle or push remote kernels without explicit human
  approval — for M9, every Kaggle submission goes through the
  decision_api → approval flow.
- Keep CTF work inside explicitly authorized local/sandbox challenge
  environments.
- DB calls require `dangerouslyDisableSandbox=true` against the local
  Supabase container (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`;
  refresh the container IP with `docker inspect supabase-db --format
  '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`).
- Playwright needs `PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium` in
  the local sandbox.

## Current task

Draft `docs/milestones/m9/loop-prompts.md` mirroring the structure of
`docs/milestones/m8/loop-prompts.md`, then run Prompt 0 of that file.

The first task of M9 (per `docs/milestones/README.md § M9`):

> Drive a live Kaggle regression test for Spaceship Titanic. Use the
> M3–M7 worker + the M8 decision gate UI: prepare a baseline, run CV,
> stage a submission, request approval through the inbox, and (on
> approve) submit via `kca kaggle submit`. Record metrics + LB score in
> Supabase and an artifact in `artifacts/spaceship-titanic/`.

When `docs/milestones/m9/loop-prompts.md` does not yet exist, the first M9 task is
to **write it** using the existing `docs/milestones/m8/loop-prompts.md` as a
template — the same Prompt 0 → Prompt N structure with a final
"exit criteria" prompt.

Return:
- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
