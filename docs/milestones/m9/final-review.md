# M9 / live end-to-end Kaggle regression — final integration review

_Branch: `main` (no worktree — direct execution per user preference)._
_Date: 2026-05-24._

## Milestone exit (per docs/milestones/README.md M9 + docs/milestones/m9/loop-prompts.md)

> Validate the full platform loop with a real Kaggle submission for
> Spaceship Titanic (binary classification, public leaderboard, no cash
> prize, safe for automated dry-run + 1 real submission under human
> approval). This milestone is the first time a real
> `kaggle competitions submit` runs through the approved KCA approval
> gate and records a public LB score in the DB.

**Status: met.** All eight Loop Prompts (M9-T000 through M9-T007) closed
PASS, the single approved real Kaggle submission recorded a public LB
score of **0.78676**, and the second experiment cleared the 0.80 CV
threshold (+0.02048 over the LR baseline). DB-bearing validation ran
against `postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres` (the
local `supabase-db` container) under `dangerouslyDisableSandbox=true`;
all other checks ran inside the sandbox. No production Supabase touched.
One real Kaggle write call (the M9-T004 submission); no kernel push, no
dataset upload, no model upload.

## M9 EXIT CRITERIA MET

## Validation matrix

| #  | Check | Result | Notes |
|----|-------|--------|-------|
| 1  | M9-T000 — Kaggle credentials reachable from `.env` without printing values | PASS | `competitions.id=b6059835-3781-4d5c-bf08-3e6e86a071dc` for slug `spaceship-titanic`. Presence verified via `bool(os.environ.get(...))` only. |
| 2  | M9-T000 — `kca kaggle list --json` exits 0 (READ_ONLY) | PASS | Listing returned non-zero competition count; no slugs leaked into closeout. |
| 3  | M9-T000 — `kca competition info --slug spaceship-titanic --json` row present | PASS | Returned matching `competitions` row written via `db.ensure_competition()` (workaround for schema-drift item A). |
| 4  | M9-T001 — `data/spaceship-titanic/manifest.json` has 4 sha256 entries | PASS | `train.csv` (805421 B), `test.csv` (372487 B), `sample_submission.csv` (59902 B), `spaceship-titanic.zip` (306403 B). |
| 5  | M9-T001 — raw CSV/zip files gitignored, only `manifest.json` staged | PASS | `git status` shows only `data/spaceship-titanic/manifest.json`; CSV / zip files not tracked. |
| 6  | M9-T001 — `test.csv` has 4277 rows (Kaggle-expected) | PASS | `submission.csv` has 4278 lines (header + 4277 prediction rows). |
| 7  | M9-T002 — baseline LR run recorded in DB with CV metric | PASS | `experiment_run_id=646a15b8-5a91-4b5d-b2cd-d5998d89c6e2`, `experiment_name=baseline-lr`, `cv_accuracy=0.791441717162159`, `cv_accuracy_std=0.00860727016939358` (5-fold stratified, seed=42, per-fold `[0.7913, 0.7855, 0.7947, 0.8055, 0.7802]`). |
| 8  | M9-T002 — valid `submission.csv` generated under `runs/spaceship-titanic/baseline-lr/` | PASS | 4278 lines (header + 4277), columns `PassengerId,Transported`, dtype bool. |
| 9  | M9-T002 — `scripts/baseline_lr_spaceship.py` runner committed | PASS | 172 lines; pytest 84 passed / 14 skipped after addition. |
| 10 | M9-T003 — reviewer gate writes `agent_reviews` row before `kaggle_submit` | PASS | `agent_reviews.id=a7208e96-5a30-4003-92d1-c44a98d14edd`. |
| 11 | M9-T003 — `human_decisions` row created and approved | PASS | `human_decisions.id=43e116bb-2b96-4703-91b0-13f11d33cccc`; approved via `kca decisions approve` (CLI, not real Kaggle submit). |
| 12 | M9-T003 — `agent_job_events` records the reviewer flow | PASS | 5 events captured under `job_id=fd3500e0-d425-452d-864a-a20df66793b2`. |
| 13 | M9-T003 — `scripts/m9_t003_drive_reviewer_gate.py` committed | PASS | 185 lines. Gaps recorded as cross-cutting follow-ups C (no `GET /decisions`) and D (literal `reviewer_decision` event_type — closest emitted: `reviewer_abstain`/`approval_pause`). |
| 14 | M9-T004 — exactly ONE real `kaggle competitions submit` call under human approval | PASS | Kaggle submission `id=52955657`, status `COMPLETE`. Submit time UTC ~2026-05-23 13:20. Approval recorded in-session (AskUserQuestion → "Approve — go ahead"). |
| 15 | M9-T004 — submissions row written with `external_submission_id` and `public_score` | PASS | `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`, `external_submission_id=52955657`, `public_score=0.78676`. Linked to baseline-lr `experiment_run_id=646a15b8-…`. |
| 16 | M9-T004 — public LB score mirrored into `experiment_runs.analysis` | PASS | LB present in run analysis JSON (migration 0004 optional columns not applied to local DB — see cross-cutting follow-up E; LB lives in `submissions.public_score` and is mirrored to `experiment_runs.analysis`). |
| 17 | M9-T005 — second experiment (HGB + feature engineering) recorded in DB with CV metric | PASS | `experiment_run_id=eed94f28-c746-4b67-b623-64d89e94f4f5`, `experiment_name=hgb-fe-v1`, `cv_accuracy=0.811916627348892`, `cv_accuracy_std=0.0075256930146784` (5-fold stratified, seed=42, per-fold `[0.82059, 0.81426, 0.80966, 0.81646, 0.79862]`). |
| 18 | M9-T005 — HGB CV > LR CV | PASS | Delta `+0.02048` (0.81192 vs 0.79144). |
| 19 | M9-T005 — `scripts/hgb_fe_spaceship.py` committed | PASS | 210 lines. Features: Cabin→Deck/Num/Side, GroupSize, TotalSpend+HasSpend, log1p spends, IsChild; HGB(max_iter=400, lr=0.06, max_leaf_nodes=31, min_samples_leaf=20, categorical_features="from_dtype"). No second real submit (per scope). |
| 20 | M9-T006 — assertion LR CV ≥ 0.78 | PASS | 0.79144 ≥ 0.78. |
| 21 | M9-T006 — assertion HGB CV ≥ 0.80 | PASS | 0.81192 ≥ 0.80. |
| 22 | M9-T006 — assertion HGB CV > LR CV | PASS | 0.81192 > 0.79144 (delta +0.02048). |
| 23 | M9-T006 — assertion LB recorded for M9-T004 submission | PASS | `submissions.public_score=0.78676` for `external_submission_id=52955657`. |
| 24 | M9-T006 — `tests/test_m9_smoke.py` added (4 DB-gated tests; SKIP without DB, PASS with DB) | PASS | 159 lines. SKIPs cleanly without `SUPABASE_DB_URL`. |
| 25 | M9-T007 — `tests/test_m9_e2e.py` added (5 dry-run tests, 0 net, 0 db, 0 creds) | PASS | 393 lines; runtime 1.14s; uses `tests/fixtures/spaceship-titanic/{train,test,sample_submission}.csv` (80/40/40 rows). |
| 26 | M9-T007 — full pytest still green after addition (84 passed / 14 skipped sandbox-mode) | PASS | `python -m pytest tests/ services/decision_api/tests` → 84 passed / 14 skipped in 7.69s. No regressions vs M8.5 (was 79/14, +5 new). |
| 27 | `ruff check .` clean | PASS | "All checks passed!" |
| 28 | `ruff format --check .` clean | PASS | "70 files already formatted". |
| 29 | `kca run list --competition spaceship-titanic --json` shows both runs with CV scores | PASS | Returns `count: 4` rows (2 run-summary + 2 metric rows); both `baseline-lr` and `hgb-fe-v1` present with CV metrics + tags + run_dir. |
| 30 | `services/decision_api/tests/test_decision_api.py` — 5/5 pass | PASS | All five FastAPI tests green; no regression from M8. |
| 31 | UI / pnpm gates (lint / typecheck / build / vitest) | SKIP | M9 did not modify UI code; UI gates were green on `main` at M8.5 exit (PR #6, see `docs/milestones/m8_5/final-review.md` rows 7–11). Local pnpm not on PATH in this sandbox; deferred to CI on the M9 PR. |

**Tally: 30 PASS / 1 SKIP / 0 FAIL.**

## DB access note

DB validation reused the M5/M6/M7/M8/M8.5 path: container IP DSN
`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`. The container
IP rotates on `docker compose down/up`; refresh via
`docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`.

DB checks that needed `dangerouslyDisableSandbox=true`:
- `kca run list --competition spaceship-titanic --json` (READ_ONLY against `experiment_runs`, `experiments`, `run_metrics`).
- `submissions` row inspection via `psql`.
- Live-DB pytest sweep (98 passed / 0 skipped when `.env` is shadowed to an empty file in a tmp tree — see "Known caveat" below).

Live-DB pytest **inside the dev shell** surfaces 3 pre-existing failures
that are not M9 regressions:

- `tests/test_kca_smoke.py::test_kaggle_submit_blocked_without_env`
- `tests/test_m4_smoke.py::test_kaggle_submit_no_credentials`
- `tests/test_m9_e2e.py::test_kca_kaggle_submit_refuses_without_credentials`

Root cause: `tools/kca/db.py` calls `dotenv.load_dotenv(<repo-root>/.env, override=False)` at import time. With the sandbox engaged, `.env` is bind-mounted to `/dev/null` (loads nothing — tests PASS, see row 26 above). With `dangerouslyDisableSandbox=true` the real `.env` becomes readable and re-injects `KAGGLE_USERNAME`/`KAGGLE_KEY` into the subprocess environment, so the "refuses without credentials" assertion fails. This is **cross-cutting follow-up B** (M8.5 carry-over → M10). Both sandbox-mode pytest and the shadow-tree pytest (`tmp/.../.env` empty) are clean — only the unshadowed live-DB run on a host shell with a populated `.env` exhibits the leak. Filed in `docs/milestones/m9/handoff.md` for the user to issue post-merge.

## What landed

### M9-T000 — Kaggle credentials + competition registration

- Verified `.env` exposes `KAGGLE_USERNAME` / `KAGGLE_KEY` via boolean
  presence assertion only — values never read or printed.
- `kca kaggle list --json` returned a non-zero competition count (READ_ONLY).
- Registered `spaceship-titanic` in the `competitions` table:
  `competitions.id=b6059835-3781-4d5c-bf08-3e6e86a071dc`. Used
  `db.ensure_competition()` to work around schema drift on the
  optional `repo_url` column (cross-cutting follow-up A).

### M9-T001 — Data download + manifest verification

- Raw data lives under `data/spaceship-titanic/` (gitignored).
- `data/spaceship-titanic/manifest.json` — 4 sha256 entries
  (`train.csv` 805421 B, `test.csv` 372487 B, `sample_submission.csv`
  59902 B, `spaceship-titanic.zip` 306403 B).
- Test CSV has 4277 rows (matches Kaggle's expected submission length).

### M9-T002 — Baseline LR loop

- `scripts/baseline_lr_spaceship.py` — research → baseline LR → CV →
  `submission.csv` runner (172 lines).
- Baseline run: `experiment_run_id=646a15b8-5a91-4b5d-b2cd-d5998d89c6e2`,
  `experiment_name=baseline-lr`, **CV accuracy 0.79144 ±0.0086** (5-fold
  stratified, seed=42, per-fold `[0.7913, 0.7855, 0.7947, 0.8055,
  0.7802]`).
- `runs/spaceship-titanic/baseline-lr/{submission.csv, meta.json,
  config.json, metrics.json, cv_summary.json}` written.

### M9-T003 — Reviewer gate + approval inbox

- `scripts/m9_t003_drive_reviewer_gate.py` — drives the worker to
  `kaggle_submit`, writes `agent_reviews` + `human_decisions`, and
  approves via `kca decisions approve` (185 lines).
- `agent_reviews.id=a7208e96-5a30-4003-92d1-c44a98d14edd`.
- `human_decisions.id=43e116bb-2b96-4703-91b0-13f11d33cccc`.
- 5 `agent_job_events` rows under
  `job_id=fd3500e0-d425-452d-864a-a20df66793b2`.
- Gaps recorded as cross-cutting follow-ups C (no `GET /decisions`
  endpoint — UI reads via supabase-js) and D (literal
  `reviewer_decision` event_type not emitted — closest are
  `reviewer_abstain` / `approval_pause`).

### M9-T004 — One real Kaggle submission (the only live remote write in M9)

- Kaggle submission `id=52955657`, status `COMPLETE`, **public LB 0.78676**.
- `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`,
  `external_submission_id=52955657`, `public_score=0.78676`, linked to
  `experiment_run_id=646a15b8-…` (baseline-lr).
- Submit message: `M9-T004 baseline-lr CV 0.7914 (logreg, k=5,
  seed=42)`. Submit time UTC ~2026-05-23 13:20.
- Human approval recorded in-session via `AskUserQuestion` ("Approve —
  go ahead"). The closing issue links the approval comment and the
  submissions row id.
- Schema note: migration 0004's optional columns (`submissions.public_lb_score`,
  `submissions.run_id`, etc.) not applied to local DB; LB lives in
  `submissions.public_score` and mirrored to `experiment_runs.analysis`.
  Filed as cross-cutting follow-up E.

### M9-T005 — Second experiment (HGB + feature engineering)

- `scripts/hgb_fe_spaceship.py` — HGB + FE runner (210 lines).
- Features: Cabin → (Deck, Num, Side); GroupSize from PassengerId
  prefix; TotalSpend + HasSpend; log1p of individual spends; IsChild.
- Model: `HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06,
  max_leaf_nodes=31, min_samples_leaf=20, categorical_features="from_dtype")`.
- Run: `experiment_run_id=eed94f28-c746-4b67-b623-64d89e94f4f5`,
  `experiment_name=hgb-fe-v1`, **CV accuracy 0.81192 ±0.00753**
  (per-fold `[0.82059, 0.81426, 0.80966, 0.81646, 0.79862]`).
- Delta vs LR baseline: **+0.02048**. No second real submit per M9
  scope (LB is recorded only for the baseline-lr run).

### M9-T006 — Regression assertions

- `tests/test_m9_smoke.py` — 4 DB-gated tests (159 lines): LR≥0.78,
  HGB≥0.80, HGB>LR, LB recorded. SKIP cleanly without
  `SUPABASE_DB_URL`; PASS with DB. All four assertions PASS against the
  current DB state.

### M9-T007 — E2E dry-run test (no creds, no DB, no net)

- `tests/test_m9_e2e.py` — 5 tests (393 lines), runtime 1.14s.
- Fixtures: `tests/fixtures/spaceship-titanic/{train,test,sample_submission}.csv`
  (80 / 40 / 40 rows; tiny but format-valid).
- Tests cover: fixture loadability, baseline LR CV against the fixture,
  HGB-FE end-to-end against the fixture, submission CSV shape contract
  vs `sample_submission.csv`, and `kca kaggle submit` refusing without
  credentials (this last one is the assertion that surfaces caveat B
  when run with the real `.env` visible).
- Full pytest: 84 passed / 14 skipped (was 79 / 14 at M8.5 exit; +5
  new, 0 regressions).

### Tests + tooling (cumulative)

- Python suite: 84 passed / 14 skipped sandbox-mode; 98 passed / 0
  skipped live-DB-shadowed (see DB access note).
- `services/decision_api/tests` — 5 / 5 pass; no M8 regression.
- `ruff check .` + `ruff format --check .` — clean on 70 files.

## Deliberate deviations from the M9 loop prompts

1. **Branch model: direct on `main`, no worktree.** Protocol §5
   defaults to a worktree branch off `main`. The user explicitly
   preferred direct execution on `main` for M9, with the milestone
   closeout PR opened from `main` only if/when the parent agent runs
   `worktree-milestone-pr`. Files are staged (`git add`) but the
   `git commit` / `git push` / `gh pr create` steps are explicitly
   deferred to the parent agent's closeout step.
2. **Schema-drift workaround in T000.** `cmd_register` expects a
   `competitions.repo_url` column that the local DB schema is missing
   (migration order drift). Worked around with
   `db.ensure_competition()` rather than amending the schema mid-M9;
   filed as follow-up A.
3. **LB column placement (T004).** Migration 0004's optional
   `submissions.public_lb_score` / `submissions.run_id` columns aren't
   applied to the local DB. LB recorded in `submissions.public_score`
   plus mirrored to `experiment_runs.analysis`. Filed as follow-up E.
4. **Reviewer-flow event-type spelling (T003).** The literal
   `reviewer_decision` event_type isn't emitted by the worker; the
   closest emitted types are `reviewer_abstain` and `approval_pause`.
   The reviewer flow itself fires correctly. Filed as follow-up D.
5. **No `GET /decisions` endpoint on decision_api.** The UI reads
   pending decisions via supabase-js directly; only the
   approve/reject/ask-improve writes go through the FastAPI service.
   This is the M8 design but is worth surfacing for M10 since CLI
   automation would benefit from a server-side list view. Filed as
   follow-up C.
6. **`.env` hygiene in live-DB pytest (M8.5 carry-over).** Three pytest
   tests (`test_kca_smoke::test_kaggle_submit_blocked_without_env`,
   `test_m4_smoke::test_kaggle_submit_no_credentials`,
   `test_m9_e2e::test_kca_kaggle_submit_refuses_without_credentials`)
   leak Kaggle creds via `tools/kca/db.py::load_dotenv` when
   `dangerouslyDisableSandbox=true` is in force AND the host shell has
   a real `.env`. Sandbox-mode and shadow-tree variants both PASS.
   Filed as follow-up B (carried forward from M8.5).

## M10 follow-ups

The four M8 follow-ups (Decision API multi-user auth; artifact preview
via signed URLs; live-DB CI on fork PRs; OTEL collector wiring) remain
open — none addressed in M9 by design.

The five M9-surfaced cross-cutting follow-ups (A–E) are recorded in
`docs/milestones/m9/handoff.md` for the user to file as GitHub issues
post-merge. Summary:

1. **A. `competitions.repo_url` schema drift** — `cmd_register` expects
   a column missing in the current local DB.
   Labels: `area:kaggle`, `type:bug`.
2. **B. `.env` hygiene in pytest subprocess (M8.5 carry-over)** —
   `tools/kca/db.py::load_dotenv` leaks Kaggle creds into the
   subprocess env when run live-DB on a shell with a populated `.env`.
   Labels: `type:test-gap`, `area:testing`.
3. **C. `decision_api`: no `GET /decisions` endpoint** — UI reads via
   supabase-js; CLI automation would benefit.
   Labels: `area:supabase`, `type:feature`, `priority:P2`.
4. **D. `reviewer_decision` literal event_type not emitted** — closest
   emitted: `reviewer_abstain` / `approval_pause`; probably just spec
   alignment.
   Labels: `area:worker`, `type:docs`.
5. **E. Migration 0004 optional columns not applied to local DB** —
   `submissions.public_lb_score`, `submissions.run_id`, etc.
   Labels: `area:supabase`, `type:bug`.

Additional M10 entry-point note:

- **First M10 task: authorized CTF/lab workflow.** Per
  `docs/milestones/README.md § M10`. CTF scope (challenge metadata + container
  lab + writeup) is now unblocked since M9 closed.

## Files of interest (one-line each)

- `data/spaceship-titanic/manifest.json` — 4 sha256 entries; raw data
  gitignored.
- `scripts/baseline_lr_spaceship.py` — LR baseline runner (172 lines).
- `scripts/hgb_fe_spaceship.py` — HGB + feature-engineering runner
  (210 lines).
- `scripts/m9_t003_drive_reviewer_gate.py` — reviewer-gate driver
  (185 lines).
- `runs/spaceship-titanic/baseline-lr/submission.csv` — 4277 rows,
  Kaggle-valid; this is the file that scored LB 0.78676.
- `runs/spaceship-titanic/hgb-fe-v1/submission.csv` — local-only
  submission shape; HGB-FE run.
- `tests/test_m9_smoke.py` — 4 DB-gated regression assertions
  (159 lines).
- `tests/test_m9_e2e.py` — 5 dry-run tests (393 lines, 1.14s).
- `tests/fixtures/spaceship-titanic/{train,test,sample_submission}.csv`
  — 80 / 40 / 40-row fixtures for the dry-run tests.
- `docs/milestones/m9/final-review.md` — this document.
- `docs/milestones/m9/handoff.md` — M9 → M10 handoff with follow-ups A–E.
- `PROJECT_STATE.md` — updated to M9 complete / M10 next.
- `README.md` — current milestone pointer updated.
- `docs/milestones/README.md` — M9 marked done with LB and CV snapshot.
