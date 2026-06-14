# M10 → M11 Handoff Prompt

_Generated 2026-05-28 from `docs/milestones/m10/final-review.md` and `docs/milestones/README.md` §M11._

Paste this into a fresh session that is starting **M11 (authorized
CTF/lab workflow)** or picking up one of the M10-surfaced / still-open
follow-up issues listed below.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M10 are complete.** Your job is to start **M11** (authorized
CTF/lab workflow) or pick up a follow-up issue.

M10 was the platform's first **notebook-submission / kernel-push**
end-to-end Kaggle regression — Petals to the Metal — Flower
Classification on TPU (`tpu-getting-started`). It mirrored M9's
eight-Loop-Prompt structure (credentials + register → data discovery →
baseline notebook → `kernel_push` reviewer gate → ONE approved real
`kca kaggle push` → local-only second experiment → regression
assertions → dry-run e2e → exit/final review). The decision_api + UI
shell + worker + reviewer gate + audit tables all fired correctly under
the approval flow, the same way they did for `kaggle_submit` in M9.

**The one material deviation:** M10-T004's single approved real kernel
push **never produced a public LB score**. See the "State at M10 exit"
section — this is the key carry-forward.

## Read these files first

1. `PROJECT_STATE.md` — current state at M10 exit.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions.
4. `docs/milestones/README.md` — **especially §M11** (authorized CTF/lab
   workflow) plus a re-read of §M10 for what just landed.
5. `docs/milestones/m10/final-review.md` — what landed in M10 (26 PASS / 1 SKIP /
   0 FAIL matrix) and the deviation detail.
6. `docs/engineering-practice.md` — the GitHub interface model.
7. `docs/architecture/m8-ui-shell.md` — UI shell + decision_api layering
   (M11 will reuse the same approval surface for CTF actions).
8. `docs/architecture/kca-cli-architecture.md` — Command / Skill / Tool
   / Job layers.
9. Latest ADRs in `docs/adr/`.

## State at M10 exit

- Validation matrix: **26 PASS / 1 SKIP / 0 FAIL** (see
  `docs/milestones/m10/final-review.md`). The 1 SKIP is `ruff format --check` on
  `scripts/exp_cc.py` — a pre-existing out-of-scope M9.x file that
  `main` reformatted (commit `cbbae93`, #39) *after* this worktree
  branched; the PR merge takes main's version.
- Local metrics:
  - Baseline (M10-T002, MobileNetV2): local-slice holdout **0.4310**
    (full-dataset reference ~0.7707); `experiment_run_id=830fc32f-3a09-…`
    (`830fc32f-2ea8-4309-9fa6-e9cd1e5877ec`).
  - Alt backbone (M10-T005, EfficientNetB0): local-slice holdout
    **0.3966** (−3.4pp vs baseline, within the 10pp guard; head still
    climbing at 3 epochs); `experiment_run_id=c3339154-944b-…`
    (`c3339154-944b-49aa-8322-f4a8607ad240`).
- **The kernel push (M10-T004) recorded NO public LB score.** The single
  human-approved real `kaggle kernels push` was executed (approval on
  issue #34 comment), but:
  - push #1 stalled in Kaggle's QUEUE ~66 min and never executed;
  - the approved re-push #2 errored on a missing `metadata.kernelspec`.
  Per issue #12 decision 4 (single-push policy) the human chose "accept
  and continue" rather than a third push. `submissions.id=03b5d080-1c05-4
  9b7e-…` (`03b5d080-1c05-47d7-9be1-abdb2ea31aff`) exists with
  `external_submission_id=harrysun2006/petals-baseline-transfer-learning/version-1`,
  `status=submitted`, **`public_score` NULL**. **No leaderboard
  pollution** (the stalled run never executed; the errored re-push
  produced no submission).
- **Root cause fixed:** `tools/legacy/py2nb.py` now emits
  `metadata.kernelspec` (`python3` / "Python 3" / `python`);
  `runs/tpu-getting-started/baseline-tl/baseline.ipynb` regenerated. The
  notebook is **push-ready** — a future approved re-push should run.
- DB rows: `competitions.id=4c69e842-eade-41e4-9143-b5d3966a9578`
  (`tpu-getting-started`); two `experiment_runs` with local metrics;
  one `submissions` row (NULL public_score); one `agent_reviews`
  (`a6f47954-…`, `target_op=kernel_push`); one `human_decisions`
  (`b47e2f16-…`, `tool_approval`/`approved`).
- New artifacts on disk:
  - `data/tpu-getting-started/manifest.json` — 193 entries, remote-only
    (raw TFRecords gitignored).
  - `runs/tpu-getting-started/{baseline-tl,alt-backbone-v1}/` — notebook
    artifacts + kernel-metadata.json.
  - `scripts/m10_t001_build_manifest.py`, `scripts/m10_t002_local_train.py`,
    `scripts/m10_t003_drive_reviewer_gate.py`, `scripts/m10_t005_local_train.py`.
  - `tests/test_m10_smoke.py` (4 DB-gated tests),
    `tests/test_m10_e2e.py` (dry-run e2e + 0-push audit sentinel),
    `tests/fixtures/tpu-getting-started/{baseline_stub.py, kernel-metadata.json}`.
- Test posture: sandbox-mode pytest 105 passed / 19 skipped; live-DB
  120 passed / 0 skipped; 0 failures; `ruff check .` clean.
- Branch model: per-milestone worktree `worktree-m10-petals-to-the-metal`
  per `docs/milestone-loop-protocol.md` §5. The closeout PR is opened by
  the `worktree-milestone-pr` step (not merged — merge is human-only).

## Issue #11 RESOLVED during M10 (M9 follow-up B)

`tools/kca/db.py` no longer re-injects repo-root `.env` secrets into
subprocesses when `KCA_SKIP_DOTENV=1` is set. This was the
leaderboard-pollution risk that motivated M9 follow-up B and was a hard
pre-req for M10-T007. Updated tests:
`tests/{test_m9_e2e.py, test_kca_smoke.py, test_m4_smoke.py}` now set
`KCA_SKIP_DOTENV=1` in their subprocess env. Issue #11 is **CLOSED**.

## Follow-ups carried into M11

### M10-surfaced

1. **#34 — M10-T004 needs a future approved re-push to record a public
   LB score.** The notebook is push-ready after the py2nb kernelspec
   fix. A re-push requires a fresh `decision:confirmed` issue + an
   in-session human approval recorded on the closing issue (single-push
   policy). When a score lands, decide whether to backfill the existing
   `submissions` row `03b5d080-…` or write a fresh one, and update
   `tests/test_m10_smoke.py::test_real_push_submission_row_exists` (it
   currently pins `public_score IS NULL` so a score landing forces a
   conscious test change).
2. **#35 — kernel-run queue-stall robustness + slug/title fix.** The
   kernelspec fix landed in the M10 PR. Still open: a poll-timeout
   policy for a kernel run that stays QUEUED (do not silently retry;
   surface to the human) and slug/title correctness for the kernel
   metadata.

### M9 follow-ups still open (B is resolved; A / C / D / E remain)

- **A** — `competitions.repo_url` schema drift (`area:kaggle`,
  `type:bug`): `cmd_register` expects a column the local DB lacks;
  M10/M9 worked around it via `db.ensure_competition()`.
- **C** — `decision_api`: no `GET /decisions` endpoint
  (`area:supabase`, `type:feature`): UI reads via supabase-js; CLI
  automation would benefit from a server-side list view.
- **D** — `reviewer_decision` literal event_type not emitted
  (`area:worker`, `type:docs`): worker tags `kernel_push` inside
  `event_data`, not as a dedicated `event_type`. M10's smoke test reads
  `event_data` accordingly.
- **E** — Migration 0004 optional columns
  (`submissions.public_lb_score`, `submissions.run_id`) not applied to
  the local DB (`area:supabase`, `type:bug`): LB lives in
  `submissions.public_score` when it exists.

The four M8 follow-ups (Decision API multi-user auth; artifact preview
via signed URLs; live-DB CI on fork PRs; OTEL collector wiring) also
remain open — not addressed by M10.

## Rules

- Treat GitHub repository files as the source of truth.
- Do not rely on hidden memory from any AI product.
- Make small, reviewable changes.
- Never expose or commit secrets. The agent may read project `.env` and
  `~/.kaggle/kaggle.json` for use (not for sharing); never SSH / AWS /
  gcloud / gh-token files.
- M10 used its single allowed real Kaggle push (which did not score).
  Any further Kaggle push needs a fresh `decision:confirmed` issue and
  an in-session approval recorded on the closing issue.
- Keep CTF work inside explicitly authorized local/sandbox challenge
  environments (M11's domain) — no third-party scanning, no real
  targets, no credential theft, no persistence.
- DB calls require `dangerouslyDisableSandbox=true` against the local
  Supabase container
  (`postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`; refresh the
  container IP with `docker inspect supabase-db --format '{{range
  .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`).
- Use a per-milestone worktree per `docs/milestone-loop-protocol.md` §5;
  no force-push, no merge without approval, no direct push to `main`.

## Current task

**Start M11 (authorized CTF/lab workflow).** Per `docs/milestones/README.md
§M11`. If `docs/milestones/m11/loop-prompts.md` does not yet exist, the first M11
task is to **write it** using `docs/milestones/m10/loop-prompts.md` /
`docs/milestones/m9/loop-prompts.md` as templates, then write the per-Loop-Prompt
`docs/tasks/m11/M11-T00N-*.md` specs. CTF scope (challenge metadata +
container lab + writeup) is unblocked now that M10 has closed.

Return:
- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
