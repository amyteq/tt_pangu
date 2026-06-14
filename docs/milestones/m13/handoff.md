# M13 → M14 Handoff Prompt

_Generated 2026-06-09 from `docs/milestones/m13/final-review.md` and `docs/milestones/README.md` §M11._

Paste this into a fresh session that is starting **M11 (authorized
CTF/lab workflow)** — the platform's next pending milestone — or picking
up one of the M13-surfaced / still-open follow-up issues listed below.

---

## Context

You are working on the `tt_pangu` / `kaggle-code-agent` repository.
**M0–M10 and M13 are complete.** M11 and M12 are still pending. Your
job is to start **M11** (authorized CTF/lab workflow) or pick up a
follow-up issue.

M13 was the platform's first **internal regression milestone** — it does
not chase a leaderboard or ship a user-visible feature. Its job was to
make every later platform change measurable. After M13, an arbitrary
code change on `main` can be evaluated against a fixed set of suites
and produce a metrics snapshot that future PRs can be graded against.

**Important sequencing note:** M11 (CTF/lab workflow) and M12 (Devpost /
hackathon workflow) were NOT prerequisites for M13 — M13 jumped ahead
by user prioritization. M11 and M12 are still planned but not yet started.

## Read these files first

1. `PROJECT_STATE.md` — current state at M13 exit.
2. `AGENTS.md` — agent contract for this repo.
3. `CLAUDE.md` — Claude Code project instructions.
4. `docs/milestones/README.md` — **especially §M11** (authorized CTF/lab
   workflow) and the updated §M13 (now ✓ done).
5. `docs/milestones/m13/final-review.md` — what landed in M13 (34 PASS / 4 SKIP /
   0 FAIL matrix) and the deviation detail.
6. `docs/milestones/m10/final-review.md` — M10 (kernel-push Kaggle regression).
7. `docs/engineering-practice.md` — the GitHub interface model.
8. `docs/architecture/eval-regression-suite.md` — M13's eval framework
   architecture (reuse as-is for M11 CTF eval cases once M11 lands).
9. `docs/adr/0019-eval-regression-suite.md` — ADR for the eval framework.
10. Latest ADRs in `docs/adr/`.

## State at M13 exit

- Validation matrix: **34 PASS / 4 SKIP / 0 FAIL** (see
  `docs/milestones/m13/final-review.md`). The 4 SKIPs are: pnpm UI gates (M13 did
  not touch `ui/`); one `kca eval list --json` offline check (cloud
  session verified); two checks absorbed into the cloud pytest sweep.
- Eval framework:
  - 6 suites: `tool-smoke`, `kaggle-replay-titanic`,
    `kaggle-replay-spaceship-titanic`, `kaggle-replay-house-prices`,
    `kernel-dryrun`, `reasoning`.
  - 5 routes: `mocked`, `local_vllm`, `claude_haiku_4_5`,
    `claude_sonnet_4_6`, `gpt_4o`.
  - Canonical baseline snapshot at
    `runs/m13-eval/20260608T211005Z/{report.json, report.md}`;
    `run_id=b89f2f89-7b7b-4842-ba4f-ccc2bd418c4e`; 5 PASS / 0 FAIL /
    20 SKIP / 0 ERROR; cost $0.00.
- New tables in cloud Supabase: `eval_suites`, `eval_runs`,
  `eval_results` (migration 0010 applied).
- New DB helpers in `tools/kca/db.py`: `register_eval_suite`,
  `start_eval_run`, `finish_eval_run`, `record_eval_result`,
  `list_eval_suites`, `list_eval_runs`, `get_eval_run`,
  `fetch_eval_results`.
- Nightly CI cron: `.github/workflows/eval.yml` at 03:30 UTC;
  `--route mocked`; uploads snapshot; posts diff to tracking issue #47
  ("M13 nightly eval — rolling diff", OPEN).
- New test files: `tests/test_m13_smoke.py` (6 tests),
  `tests/test_m13_e2e.py` (6 tests), `tests/test_m13_t006_routes.py`
  (16 tests), `tests/test_m13_t007_report.py` (9 tests).
- Test posture post-merge: **149 passed / 8 skipped / 0 failed** (cloud
  DSN, `dangerouslyDisableSandbox=true`); `ruff check .` and
  `ruff format --check .` both clean (96 files).
- No paid LLM calls executed in M13. No real Kaggle calls. Cost: $0.00.
- Branch model: per-milestone worktree `worktree-m13-execution` per
  `docs/milestone-loop-protocol.md` §5. The closeout PR is opened
  against `main` (not merged — merge is human-only).

## DB access note at M13 exit

M13's DB-bearing validation ran against **Cloud Supabase** (`SUPABASE_DB_URL`
from `/home/harry/test/tt_pangu/.vscode/.env`), NOT the local container.
The local `supabase-db` container (`172.21.0.4:5432`) was not used in
M13 (it was used in M9 / M10). Memory file `reference_supabase_db.md`
has been updated. For future milestones, use the cloud DSN from
`.vscode/.env` unless the human explicitly re-enables the local container.

## issue #11 still CLOSED

`tools/kca/db.py` `KCA_SKIP_DOTENV=1` guard is intact post M13-merge.
Issue #11 ("dotenv-leak / Kaggle LB pollution") remains CLOSED.

## Follow-ups carried into M11+

### M13-surfaced (deferred-scope)

1. **M13.1 — CTF / lab eval cases (gated on M11).** Once M11 lands and
   ships a solver-script / writeup artefact path, add a `ctf_lab` suite
   to the M13 eval harness. File as a follow-up issue with labels
   `type:feature`, `area:eval`, `decision:needed`.

2. **M13.2 — Hackathon / Devpost eval cases (gated on M12).** Same
   deferral logic as M13.1. File as a follow-up issue with labels
   `type:feature`, `area:eval`, `decision:needed`.

3. **M14 — Gate PRs on eval score-deltas.** M13 baselines the metric
   values; M14+ can add pass/fail thresholds so a regression in, e.g.,
   the Titanic replay RMSLE blocks the PR.

4. **Cloud Supabase migration hygiene.** M13 applied migration 0010
   directly to cloud; the local container was not used. A future task
   should re-apply all migrations to the local container and verify
   parity, or retire the local-container workflow.

### M10-surfaced (still open from M10)

5. **#34** — M10-T004 needs a future approved re-push to record a
   public LB score. The baseline notebook is push-ready after the py2nb
   kernelspec fix. A re-push requires a fresh `decision:confirmed` issue
   and an in-session human approval. When a score lands, update
   `test_m10_smoke.py::test_real_push_submission_row_exists` (it
   currently pins `public_score IS NULL`).

6. **#35** — kernel-run queue-stall robustness + slug/title fix. The
   kernelspec fix landed in M10. Still open: a poll-timeout policy for a
   kernel run that stays QUEUED (do not silently retry; surface to the
   human) and slug/title correctness for the kernel metadata.

### M9 follow-ups still open (A / C / D / E; B resolved by M10)

- **A** — `competitions.repo_url` schema drift (`area:kaggle`,
  `type:bug`): `cmd_register` expects a column the local DB lacks.
- **C** — `decision_api`: no `GET /decisions` endpoint
  (`area:supabase`, `type:feature`).
- **D** — `reviewer_decision` literal event_type not emitted
  (`area:worker`, `type:docs`): worker tags `kernel_push` inside
  `event_data`, not as a dedicated `event_type`.
- **E** — Migration 0004 optional columns
  (`submissions.public_lb_score`, `submissions.run_id`) not applied to
  the local DB (`area:supabase`, `type:bug`).

The four M8 follow-ups (Decision API multi-user auth; artifact preview
via signed URLs; live-DB CI on fork PRs; OTEL collector wiring) also
remain open — not addressed by M10 or M13.

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
- DB calls require `dangerouslyDisableSandbox=true`. Use the cloud
  Supabase DSN from `.vscode/.env` (NOT the local container DSN).
- Use a per-milestone worktree per `docs/milestone-loop-protocol.md` §5;
  no force-push, no merge without approval, no direct push to `main`.
- M13's eval framework is live. After any significant code change,
  consider running `kca eval run --all --route mocked` to generate a
  regression snapshot and compare against the baseline in
  `runs/m13-eval/20260608T211005Z/`.

## Current task

**Start M11 (authorized CTF/lab workflow).** Per `docs/milestones/README.md
§M11`. If `docs/milestones/m11/loop-prompts.md` does not yet exist, the first M11
task is to **write it** using `docs/milestones/m10/loop-prompts.md` /
`docs/milestones/m9/loop-prompts.md` as templates, then write the per-Loop-Prompt
`docs/tasks/m11/M11-T00N-*.md` specs. CTF scope (challenge metadata +
container lab + writeup) is unblocked.

**M13.1 / M13.2 follow-ups** will unblock automatically once M11 / M12
land. Do not promote them earlier.

Return:
- Summary of intended change.
- Files to modify.
- Risks and approval needs.
- Patch or implementation.
- Suggested tests.
