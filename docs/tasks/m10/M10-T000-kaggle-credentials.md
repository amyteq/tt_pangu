# M10-T000: Kaggle credentials + competition registration (`tpu-getting-started`)

## Milestone
M10: live end-to-end regression test — Petals to the Metal (notebook-submission / kernel-push path).

## Goal
Confirm the agent can read Kaggle credentials without exposing them, run
READ_ONLY Kaggle calls against the kernel-runner path, and register
`tpu-getting-started` (Petals to the Metal) in the local control plane.
No real push, no submission, no dataset / model upload.

This task assumes **M9 is merged on main** (`docs/milestones/m9/final-review.md`
reports PASS) and that the M9-T000 deviation (AC #1 satisfied via
`kaggle.api.config_values` rather than the literal python-dotenv check)
is honoured here too.

## Read first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` §M10
5. `docs/engineering-practice.md`
6. `docs/milestones/m9/final-review.md` (M9-T000 deviation)
7. `docs/milestones/m9/handoff.md`
8. `env.example`
9. `tools/kca/competition.py`
10. `tools/kca/kg.py` — `cmd_list`, `cmd_watch`, `cmd_fetch`, `cmd_push` (header / args only — do NOT call), `add_parsers`
11. `.claude/settings.json` — verify Kaggle `submit/push/upload/datasets`
    are on `ask`
12. `.claude/hooks/guard_tool.py` — verify `kaggle.json` / `.env` reads
    are denied

## Scope

1. Verify Kaggle credentials are reachable WITHOUT printing them. Two
   accepted paths:
   - Preferred: `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.environ.get('KAGGLE_USERNAME')), bool(os.environ.get('KAGGLE_KEY')))"` prints `True True`.
   - Equivalent (per M9-T000 deviation): `python -c "from kaggle import api; api.authenticate(); cv = api.config_values; print(bool(cv.get('username')), bool(cv.get('key')))"` prints `True True`.
   Either is acceptable; the deviation exists because in some sandboxed
   views `.env` is bind-mounted to `/dev/null`. Booleans only — never
   the values.
2. Run `kca kaggle list --json` (READ_ONLY) to confirm credentials work.
   Capture only the count or slug presence, never the raw response.
3. Run `kaggle competitions files -c tpu-getting-started` (READ_ONLY) to
   confirm the kernel-runnable competition is reachable. **Do not run
   `kaggle kernels push`, `kaggle kernels init`, `kaggle datasets create`,
   or any write op.** Capture only the file-count and / or names; do
   not echo raw bytes.
4. Register Petals to the Metal via
   `kca competition register --slug tpu-getting-started --name "Petals to the Metal - Flower Classification on TPU"`
   (LOCAL_WRITE, gated on the local DB). If `cmd_register` errors due
   to the `competitions.repo_url` schema drift (M9 follow-up A, issue
   #14), document the workaround used and link issue #14 in the
   closeout; do not block the milestone on closing #14.
5. Run `kca competition info --slug tpu-getting-started --json` and
   confirm the entry is in the `competitions` table.
6. File or update the closing GitHub issue with the M10-T000 acceptance
   criteria, evidence links, and `ai:ready` once the decisions in issue
   #12 are `decision:confirmed` (they already are; recorded here for
   the audit trail).

## Non-goals

- Do not run `kca kaggle submit`, `kca kaggle push`,
  `kaggle competitions submit`, `kaggle kernels push`,
  `kaggle datasets create`, `kaggle datasets version`, or `kca kaggle upload`.
- Do not print credential values to stdout, logs, audit rows, or PR
  bodies.
- Do not change `.claude/settings.json` or `.claude/hooks/guard_tool.py`.
- Do not add a new `kca` subcommand for credential probing — use the
  existing READ_ONLY ones.

## Acceptance criteria

- Credentials are reachable per one of the two accepted paths in scope
  step 1 — produces `True True`, nothing else.
- `kca kaggle list --json` exits 0.
- `kaggle competitions files -c tpu-getting-started` exits 0 and
  reports a non-zero file count.
- `kca competition info --slug tpu-getting-started --json` exits 0
  with a matching row.
- No new lines added to `.env*` or any other file under the
  `docs/milestone-loop-protocol.md §6` denylist.
- All baseline validation still passes (pytest, ruff, pnpm where
  available).

## Permissions

- Local file reads (excluding the secret denylist) and `kca` READ_ONLY /
  LOCAL_WRITE commands are allowed.
- `git commit` and `git push` require explicit human approval (default
  per protocol §5 — overridden only by the milestone closeout).
- Any `kaggle.json` / `.env*` read is blocked at the hook layer; do not
  attempt to bypass.

## Closeout format

```
M10-T000 closeout
  Credentials reachable: YES | NO  (boolean assertion only — no values)
  Kaggle list: <count> competitions visible (no slugs in closeout)
  Files visible for tpu-getting-started: <count> files (no names in closeout)
  Competition row: tpu-getting-started — competitions.id=<uuid>
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M10-T001 ready to start
```

## Related issues

- #12 — M10 proposal (decision:confirmed, ai:ready). This task closes
  one bullet of the M10 entry-gate checklist on #12.
- #14 — `competitions.repo_url` schema drift. If `cmd_register` errors
  with `UndefinedColumn`, note the workaround in the closeout; do not
  block T000 on closing #14.

## Stop condition

Stop after 60 turns. If neither credential path produces `True True`,
halt and ask — do not write `.env` yourself. If Kaggle returns a
"competition rules not accepted" error for the READ_ONLY file list,
halt and ask — do not encode a click-through.
