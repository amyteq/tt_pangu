# M9 → M10 Handoff Prompt

_Generated 2026-05-24 from `docs/milestones/m9/final-review.md` and `docs/milestones/README.md` § M10._
_Amended 2026-05-24 post-merge: M10 is now the **notebook-submission regression
on Petals to the Metal** (issue #12, decisions confirmed, `ai:ready`).
The old M10 (authorized CTF/lab) is renumbered to M11._

Paste this into a fresh session that is starting **M10
(notebook-submission regression — Petals to the Metal)** or any of the
M9 follow-up issues listed below.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M9 are complete.** Your job is to start **M10** (or one of the
M9-surfaced cross-cutting follow-ups before M10 begins; issue #11 is a
hard pre-req for M10-T007).

M9 shipped the first live end-to-end Kaggle regression test — Spaceship
Titanic (binary classification) — with one approved real CSV submission,
two local CV runs (LR baseline + HGB-FE), regression assertions, and a
dry-run e2e test path. The decision_api + UI shell + worker + reviewer
gate + audit table all fired correctly under the approval flow. **M10
extends that pattern to the notebook-submission / kernel-push path**
against Petals to the Metal — Flower Classification on TPU
(`tpu-getting-started`). Single approved real `kca kaggle push`
(mirroring M9-T004's single-submission policy); per-milestone worktree
per `docs/milestone-loop-protocol.md` §5.

## Read these files first

1. `PROJECT_STATE.md` — current state at M9 exit.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions.
4. `docs/milestones/README.md` — **especially the M10 section** (planned
   capabilities + exit criteria) plus a re-read of § M9 for what just
   landed.
5. `docs/milestones/m9/final-review.md` — what landed in M9 (30-check matrix) and
   the M10 follow-ups list.
6. `docs/engineering-practice.md` — the GitHub interface model used in
   M8.5 → M9 and inherited by M10.
7. `docs/architecture/m8-ui-shell.md` — UI shell + decision_api
   layering (M10 will reuse the same approval surface).
8. `docs/architecture/kca-cli-architecture.md` — Command / Skill / Tool
   / Job layers; M10 will register new tools and skills under this.
9. `docs/milestones/_templates/handoff-prompt.md` — canonical handoff template (this file
   already uses it).
10. Latest ADRs in `docs/adr/`.

## State at M9 exit

- All 30 non-SKIP exit checks PASS (see `docs/milestones/m9/final-review.md`). One
  SKIP: UI pnpm gates — M9 did not modify UI; relied on M8.5 green
  state on `main`.
- Live Kaggle metrics: **LR baseline CV 0.79144**, **HGB-FE CV 0.81192
  (+0.02048)**, **public LB 0.78676** for the M9-T004 baseline-lr
  submission (`external_submission_id=52955657`,
  `submissions.id=b4607ada-c78a-4d78-80b3-2a5887582472`).
- New M9 artifacts on disk:
  - `data/spaceship-titanic/manifest.json` — 4 sha256 entries (raw
    CSV/zip files gitignored).
  - `runs/spaceship-titanic/{baseline-lr,hgb-fe-v1}/submission.csv`
    plus run metadata under the same folders.
  - `scripts/baseline_lr_spaceship.py`, `scripts/hgb_fe_spaceship.py`,
    `scripts/m9_t003_drive_reviewer_gate.py`.
  - `tests/test_m9_smoke.py` (4 DB-gated tests),
    `tests/test_m9_e2e.py` (5 dry-run tests),
    `tests/fixtures/spaceship-titanic/{train,test,sample_submission}.csv`.
- Test posture: sandbox-mode pytest 84 passed / 14 skipped;
  decision_api 5 / 5 PASS; ruff clean.
- DB state: `competitions.id=b6059835-3781-4d5c-bf08-3e6e86a071dc` for
  `spaceship-titanic`; two `experiment_runs` with CV + LB; 1
  `submissions` row with public score; 1 `agent_reviews` + 1
  `human_decisions` row; 5 `agent_job_events` under the M9-T003 job
  id.
- Branch model: M9 was executed directly on `main` (no worktree, per
  user preference). Files were staged via `git add` mid-prompt; the
  milestone-closeout PR is opened by the parent agent's
  `worktree-milestone-pr` step.

## Cross-cutting follow-ups from M9 (file as GitHub issues post-merge)

These came up during M9 but are out of scope for the M9 PR itself.
Each should be filed using `.github/ISSUE_TEMPLATE/`, labelled per
M8.5's `.github/labels.yml`, and triaged into M10 (or later) by the
`github-issue-triage` agent before any AI session picks one up.

### A. `competitions.repo_url` schema drift

- **Type:** bug.
- **Labels:** `type:bug`, `area:kaggle`, `area:supabase`,
  `priority:P2`.
- **Symptom:** `tools/kca/competition.py::cmd_register` expects a
  `competitions.repo_url` column that the current local DB schema
  doesn't have. The workaround in M9-T000 was to call
  `db.ensure_competition()` directly.
- **Suggested fix:** check the migration order — either
  `0004_m4_competition_repo.sql` isn't fully applied to the local DB
  (see also follow-up E), or `cmd_register` should treat `repo_url`
  as optional / nullable and probe column existence first.
- **Acceptance:** `kca competition register --slug <slug>` works on a
  fresh DB built only from `supabase/migrations/*.sql` without manual
  fixup.

### B. `.env` hygiene in pytest subprocess (carried from M8.5)

- **Type:** test-gap.
- **Labels:** `type:test-gap`, `area:testing`, `area:security`,
  `priority:P1`.
- **Symptom:** Three tests
  (`tests/test_kca_smoke.py::test_kaggle_submit_blocked_without_env`,
  `tests/test_m4_smoke.py::test_kaggle_submit_no_credentials`,
  `tests/test_m9_e2e.py::test_kca_kaggle_submit_refuses_without_credentials`)
  leak `KAGGLE_USERNAME` / `KAGGLE_KEY` into the test subprocess via
  `tools/kca/db.py::load_dotenv(<repo-root>/.env, override=False)`.
  Sandbox-mode (`/.env` bind-mounted to `/dev/null`) PASS. Live-DB
  mode on a shell with a populated `.env` FAIL — the assertion
  expects a credentials-gate refusal, but `kaggle competitions submit`
  actually succeeds because the env is re-injected.
- **Suggested fix:** make `load_dotenv` opt-out via an env var
  (`KCA_SKIP_DOTENV=1`) and set that in the failing tests' subprocess
  env. Belt-and-suspenders: also point the subprocess at an empty
  shadow `.env` and verify dotenv reads from that path explicitly.
- **Acceptance:** all three tests PASS with
  `dangerouslyDisableSandbox=true` and a populated `.env` on the host.

### C. `decision_api`: no `GET /decisions` endpoint

- **Type:** feature.
- **Labels:** `type:feature`, `area:supabase`, `area:cli`,
  `priority:P2`.
- **Symptom:** The decision_api ships POST handlers
  (`/decision/{id}/{approve,reject,ask-improve}`) only. The UI reads
  pending decisions via supabase-js directly. CLI automation
  (`kca decisions list`) reads the DB directly too. There's no
  HTTP-surface list endpoint for non-DB callers.
- **Suggested fix:** add `GET /decisions?status=pending&limit=N` to
  `services/decision_api/app.py`, gated by the same
  `KCA_DECISION_API_TOKEN`. Mirror the response shape used by the UI's
  supabase-js call.
- **Acceptance:** new endpoint returns the same rows the UI Approval
  Inbox renders, under token auth, with pagination.

### D. `reviewer_decision` literal event_type not emitted

- **Type:** docs (probably) or worker bug (if the literal was
  promised).
- **Labels:** `type:docs`, `area:worker`, `priority:P3`.
- **Symptom:** The M9-T003 task spec mentions a `reviewer_decision`
  `agent_job_events.event_type`. The worker actually emits
  `reviewer_abstain` and `approval_pause` (plus the matching
  `reviewer_approve` / `reviewer_reject` for verdicts). The reviewer
  flow itself works — only the spec wording is off.
- **Suggested fix:** either update `docs/tasks/m9/M9-T003-…` and the M9
  loop prompt to reference the actually-emitted event types, OR add a
  unified `reviewer_decision` event type that subsumes the others.
- **Acceptance:** spec wording and worker emission agree; a smoke test
  asserts the event type literal.

### E. Migration 0004 optional columns not applied to local DB

- **Type:** bug.
- **Labels:** `type:bug`, `area:supabase`, `priority:P2`.
- **Symptom:** `supabase/migrations/0004_m4_competition_repo.sql`
  defines optional columns `submissions.public_lb_score`,
  `submissions.run_id`, etc. (used by M4 to track per-submission LB +
  link back to a run). The local DB doesn't have these columns
  applied. M9-T004 wrote the LB to `submissions.public_score` and
  mirrored it to `experiment_runs.analysis` as a workaround.
- **Suggested fix:** verify the migration runner state; re-apply
  `0004` idempotently if needed; if the columns are intentionally
  unused, drop the workaround and migrate `submissions.public_score`
  → the canonical column.
- **Acceptance:** `psql ... -c "\d submissions"` shows all 0004
  columns; M9-T004's LB lives in the canonical `public_lb_score`
  column without a mirror write.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets.
- M9 used its single allowed real Kaggle submit. Any further Kaggle
  submit needs a fresh `decision:confirmed` issue and an in-session
  approval recorded on the closing issue.
- Keep CTF work inside explicitly authorized local/sandbox challenge
  environments (M11's domain after renumbering — no third-party
  scanning, no real targets, no credential theft).
- DB calls require `dangerouslyDisableSandbox=true` against the local
  Supabase container
  (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`; refresh
  the container IP with `docker inspect supabase-db --format '{{range
  .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`).
- Playwright needs `PLAYWRIGHT_CHROMIUM_PATH=/usr/bin/chromium` in
  the local sandbox.

## Current task

Either:

(a) **Triage and file follow-ups A–E** as GitHub issues using
`.github/ISSUE_TEMPLATE/`. Triage agent should set labels per the
suggested label sets above and add `ai:triage`. Promote to `ai:ready`
only after acceptance criteria are clear and a human picks them up.

(b) **Start M10 (notebook-submission regression — Petals to the
Metal).** Issue #12 is `ai:ready` with all four planning decisions
confirmed. Draft `docs/milestones/m10/loop-prompts.md` mirroring the M9 layout
(Loop Prompt 0 → 8 + exit prompt), then write
`docs/tasks/m10/M10-T00N-*.md` per non-trivial loop prompt. Use
`docs/milestones/m9/loop-prompts.md` as the template.

The first M10 task (per `docs/milestones/README.md § M10` + issue #12):

> Validate the full platform loop with a real Kaggle **kernel push**
> (notebook submission) for Petals to the Metal — Flower Classification
> on TPU. Mirror M9's eight-Loop-Prompt structure: credentials +
> register, data discovery, baseline notebook, reviewer-gate for
> `kernel_push`, ONE approved real `kca kaggle push`, second
> experiment (local only), regression assertions, dry-run e2e test,
> exit + final review. Hard pre-req for M10-T007: issue #11 (dotenv
> leak) must be merged so the new e2e test cannot pollute the
> `tpu-getting-started` leaderboard.

When `docs/milestones/m10/loop-prompts.md` does not yet exist, the first M10 task
is to **write it** using `docs/milestones/m9/loop-prompts.md` as a template.

The CTF/lab workflow (the previous M10 topic) is renumbered to M11;
the Devpost/hackathon topic moves to M12; the evaluation /
reliability / regression suite moves to M13. See
`docs/milestones/README.md` for the updated numbering.

Return:
- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
