# M8.5 → M9 Handoff Prompt

_Generated 2026-05-23 from `docs/milestones/m8_5/final-review.md`, `docs/milestones/m9/loop-prompts.md`, and `docs/milestones/README.md` §M9._

Paste this into a fresh session that is starting **M9 (live Kaggle
regression test — Spaceship Titanic)** work.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M8.5 are complete.** Your job is to start **M9**.

M8.5 shipped pre-M9 hardening: CI was restored to green, a GitHub
Issues / PR / labels collaboration interface was added between humans
and Claude Code agents, the sandbox / hook policy was revised so
`git push` and `gh pr create` work under sandbox (while explicit
secret reads stay blocked), and `docs/milestones/m9/loop-prompts.md` plus nine
`docs/tasks/m9/M9-T*.md` specs were drafted. **No M9 code was implemented
in M8.5.**

M9 is the **first end-to-end live Kaggle regression** for this platform:
drive the M3 worker + M5 research + M6 reviewer + M7 permission policy
+ M8 decision_api + UI shell against Spaceship Titanic under the
approval gates. The acceptance criterion is **loop correctness under
the approval gates**, not LB score. Only **one** real
`kaggle competitions submit` happens across the entire milestone, and
only at M9-T004 under both the hook `ask` permission AND an explicit
human "approved to submit" comment on the closing GitHub issue.

## Read these files first

1. `PROJECT_STATE.md` — current state at M8.5 exit.
2. `AGENTS.md` — agent contract for this repo (includes the
   "GitHub collaboration interface" routing rules added in M8.5).
3. `CLAUDE.md` — Claude Code project instructions (includes the
   binding GitHub collaboration rules).
4. `docs/milestones/README.md` — **especially the M8.5 done section + the
   M9 section** (planned capabilities + exit criteria).
5. `docs/milestones/m8/final-review.md` — what landed in M8 and the M9 follow-ups.
6. `docs/milestones/m8_5/final-review.md` — what landed in M8.5 and additional M9
   follow-ups.
7. `docs/milestones/m9/loop-prompts.md` — the M9 Loop Prompts (M9-T000 → M9-T008).
8. `docs/tasks/m9/M9-T000-kaggle-credentials.md` — the first M9 task spec.
9. `docs/engineering-practice.md` — collaboration model, AI pickup
   rule, label semantics, PR closeout checklist.
10. `docs/architecture/m8-ui-shell.md` — UI / decision_api layering.
11. `docs/architecture/kca-cli-architecture.md` — Command / Skill /
    Tool / Job layers the worker calls into.

## State at M8.5 exit

- All 26 non-SKIP M8.5 exit checks PASS (see `docs/milestones/m8_5/final-review.md`).
- All 28 M8 exit checks remain PASS (see `docs/milestones/m8/final-review.md`).
- CI is green on `main@cade09f`.
- 33 labels are synced on `origin`; `scripts/sync_labels.py --dry-run`
  reports `0 update`.
- Two M9-related follow-up issues are open and `ai:blocked`:
  - **#7** — submission-format awareness (subset).
  - **#8** — competition-rules ingestion (broader; quota, accelerators,
    internet on/off, runtime limit, deadlines, format).

## M9 task sequence

| Task | Spec | Notes |
|---|---|---|
| M9-T000 | `docs/tasks/m9/M9-T000-kaggle-credentials.md` | Verify Kaggle credentials via presence-only; READ_ONLY `kca kaggle list`; register Spaceship Titanic locally. |
| M9-T001 | `docs/tasks/m9/M9-T001-data-download.md` | Download data; verify sha256 manifest; commit `manifest.json` only. |
| M9-T002 | `docs/tasks/m9/M9-T002-baseline-loop.md` | Worker baseline LR loop → CV + staged `submission.csv`. Spaceship Titanic uses CSV; format-awareness gap is #8. |
| M9-T003 | `docs/tasks/m9/M9-T003-reviewer-approval-gate.md` | Reviewer gate fires; UI Approval Inbox renders; `kca decisions approve` (no real submit). |
| M9-T004 | `docs/tasks/m9/M9-T004-real-submission.md` | **ONE** real Kaggle submit under explicit approval. Single-submission policy; no retry on failure. |
| M9-T005 | `docs/tasks/m9/M9-T005-second-experiment.md` | HGB + minimal feature engineering; local only. |
| M9-T006 | `docs/tasks/m9/M9-T006-regression-assertions.md` | CV ≥ 0.78 (LR), ≥ 0.80 (HGB); LB recorded. |
| M9-T007 | `docs/tasks/m9/M9-T007-e2e-dryrun-test.md` | `tests/test_m9_e2e.py` dry-run; no credentials, no network, no DB. |
| M9-T008 | `docs/tasks/m9/M9-T008-m9-exit-criteria.md` | M9 exit + `docs/milestones/m9/final-review.md` + M9 PR. |

## Human decisions needed BEFORE starting M9-T000

These block the first M9 Loop Prompt. Each should be recorded as a
`type:decision` GitHub issue with `decision:confirmed` before triage
may promote the corresponding M9 task to `ai:ready`.

1. **Submission policy for Spaceship Titanic.** Confirm: one real
   submission; no kernel push; no dataset / model upload; second
   experiment stays local.
2. **Kaggle credential source.** `.env` (recommended) vs Kaggle profile
   `~/.kaggle/kaggle.json`. The hook + sandbox already block direct
   `kaggle.json` reads.
3. **Public LB acceptance threshold.** CV thresholds are asserted; the
   planning docs do **not** assert an LB floor. Confirm we don't want
   one.
4. **M9-T004 failure handling.** If the single real submit fails, the
   plan is stop + follow-up issue (no silent retry). Confirm.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets — the `.env*`, `kaggle.json`,
  `id_rsa`, `id_ed25519`, `~/.aws`, `~/.config/gcloud`, `secrets/`
  paths are denied at the sandbox, permissions, AND hook layers.
- Never submit to Kaggle or push remote kernels without explicit human
  approval — for M9, the only real Kaggle submit goes through both the
  `ask` hook gate AND a "approved to submit" comment on the closing
  GitHub issue.
- Keep CTF work inside explicitly authorized local/sandbox challenge
  environments (M10 scope; not M9).
- DB calls require `dangerouslyDisableSandbox=true` against the local
  Supabase container
  (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`; refresh
  the container IP with
  `docker inspect supabase-db --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`).
- Playwright needs `PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium` in
  the local sandbox.
- Every PR uses `.github/pull_request_template.md`. The tests / docs /
  evidence / schema-RLS-secrets / remote-side-effects checklist is
  load-bearing.
- Every M9 task is filed as a GitHub issue using `feature-work.yml`
  (or `test-gap.yml` for T006 / T007). T004's issue starts
  `ai:blocked` + `policy:approval-required` + `decision:needed` and is
  only promoted to `ai:ready` after a human approval comment lands.

## Current task

Start with **M9-T000** (`docs/tasks/m9/M9-T000-kaggle-credentials.md`).
Open a `feature-work.yml` issue for it. Promote to `ai:ready` only
after the four pre-M9 decisions above are `decision:confirmed`.

Return:
- Summary of intended change.
- Files to modify.
- Risks and approval needs (especially anything that would surface
  a secret or trigger a remote write).
- Patch or implementation.
- Suggested tests.
