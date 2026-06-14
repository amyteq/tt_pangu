# M9-T000: Kaggle credentials + competition registration

## Milestone
M9: live end-to-end regression test — Spaceship Titanic.

## Goal
Confirm the agent can read Kaggle credentials from `.env` without exposing
them, run READ_ONLY Kaggle calls, and register Spaceship Titanic in the
local control plane. No real submit, no kernel push, no dataset/model
upload.

This task assumes **M8.5 (T001, T002, T003) is merged on main**, CI is
green, and the 33 labels from `.github/labels.yml` are synced on `origin`.

## Read first

1. `PROJECT_STATE.md`
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/milestones/README.md` §M9
5. `docs/engineering-practice.md`
6. `docs/milestones/m8_5/final-review.md`
7. `env.example`
8. `tools/kca/competition.py`
9. `tools/kca/kg.py` — `cmd_list`, `cmd_watch`, `cmd_fetch`, `add_parsers`
10. `.claude/settings.json` — verify Kaggle `submit/push/upload/datasets`
    are on `ask`
11. `.claude/hooks/guard_tool.py` — verify `kaggle.json` / `.env` reads
    are denied

## Scope

1. Verify `.env` defines `KAGGLE_USERNAME` and `KAGGLE_KEY`. Do **not**
   `cat .env`, `head .env`, `awk` it, or print it. Use `python-dotenv` or
   `os.environ` after `load_dotenv()` and only assert presence
   (`bool(os.environ.get("KAGGLE_USERNAME"))`).
2. Run `kca kaggle list --json` (READ_ONLY) to confirm credentials work.
   Capture only the count or competition slugs, never the raw response.
3. Register Spaceship Titanic via
   `kca competition register --slug spaceship-titanic --name "Spaceship Titanic"`
   (LOCAL_WRITE, gated on the local DB).
4. Run `kca competition info --slug spaceship-titanic --json` and confirm
   the entry is in the `competitions` table.
5. File or update the closing GitHub issue with the M9-T000 acceptance
   criteria, evidence links, and `ai:ready` once the decisions in
   `docs/milestones/m9/loop-prompts.md#human-decisions-needed-before-starting-m9`
   are `decision:confirmed`.

## Non-goals

- Do not run `kca kaggle submit`, `kaggle competitions submit`,
  `kaggle kernels push`, `kaggle datasets create`, `kaggle datasets version`,
  or `kca kaggle upload`.
- Do not print credential values to stdout, logs, audit rows, or PR bodies.
- Do not change `.claude/settings.json` or `.claude/hooks/guard_tool.py`.
- Do not add a new `kca` subcommand for credential probing — use the
  existing READ_ONLY ones.

## Acceptance criteria

- `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.environ.get('KAGGLE_USERNAME')), bool(os.environ.get('KAGGLE_KEY')))"`
  prints `True True` — and nothing else.
- `kca kaggle list --json` exits 0.
- `kca competition info --slug spaceship-titanic --json` exits 0 with a
  matching row.
- No new lines added to `.env*` or any other file under
  `docs/milestone-loop-protocol.md §6` denylist.
- All baseline validation still passes (pytest, ruff, pnpm).

## Permissions

- Local file reads (excluding the secret denylist) and `kca` READ_ONLY /
  LOCAL_WRITE commands are allowed.
- `git commit` and `git push` require explicit human approval (default
  per protocol §5 — overridden only by the milestone closeout).
- Any `kaggle.json` / `.env*` read is blocked at the hook layer; do not
  attempt to bypass.

## Closeout format

```
M9-T000 closeout
  Credentials reachable: YES | NO  (boolean assertion only — no values)
  Kaggle list: <count> competitions visible (no slugs in closeout)
  Competition row: spaceship-titanic — competitions.id=<uuid>
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M9-T001 ready to start
```

## Stop condition

Stop after 60 turns. If `.env` is missing `KAGGLE_USERNAME` or
`KAGGLE_KEY`, halt and ask — do not write them yourself.
