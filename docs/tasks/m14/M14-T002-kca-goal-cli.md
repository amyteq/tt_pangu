# M14-T002: `kca goal {init, show, update}` + `goal.md` schema (issue #51)

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Implement the `kca goal` CLI surface and the `goal.md` workspace
artefact. The DB `goals` row (T001) is authoritative; `goal.md` is the
human-readable mirror for git history. The `kernel_push` reviewer gate
now surfaces `goal_remaining_delta` in the approval prompt.

Assumes **M14-T000 / M14-T001 closeouts are PASS**.

## Read first
1. M14-T000 / M14-T001 closeouts.
2. `docs/adr/0020-goal-driven-kaggle-loop.md` §1 (`goal.md` schema) + §2 (`goals`).
3. Issue #51 (acceptance criteria — pin to the issue body).
4. `tools/kca/competition.py` (existing register / info CLI pattern).
5. `tools/kca/db.py` (T001 helpers: `create_goal`, `get_active_goal`, `update_goal`, `close_goal`).
6. `tools/kca/COMMANDS.md` (subcommand documentation pattern).
7. `src/worker/reviewer.py` (where `goal_remaining_delta` is surfaced in the gate prompt).

## Scope
1. `tools/kca/goal.py` exporting `add_parsers(subparsers)`, registered
   from `tools/kca/kca.py`:
   - `kca goal init --competition <slug> --target-lb-score <f>
     [--target-lb-rank <int>] [--target-rank-kind percentile|absolute]
     [--deadline yyyy-mm-dd] [--exit-strategy first_reached|all_required|score_only|rank_only]
     [--max-total-pushes 20] [--stuck-threshold 3] [--json]` — creates
     the `goals` row (refuses if an active goal exists) and writes
     `experiments/<comp>/goal.md`.
   - `kca goal show --competition <slug> [--json]` — reads the active
     goal row; prints score/rank targets, exit_strategy, status,
     `goal_remaining_delta` (best current LB vs target).
   - `kca goal update --competition <slug> [--target-lb-score ...]
     [--deadline ...] [--stuck-threshold ...] [--close --reason <text>] [--json]`
     — updates fields or closes the goal; rewrites `goal.md`.
2. `goal.md` writer — YAML front-matter mirror of the row (ADR-0020 §1)
   plus a human-readable body; idempotent rewrite on update.
3. Reviewer-gate integration: the `kernel_push` gate prompt surfaces
   `goal_remaining_delta` so the approver sees how far the push could
   move the goal. (Read-only enrichment; does not change gate logic.)

## Non-goals
- No exploration / batch surface (T003).
- No concurrency / push changes (T004).
- No real Kaggle calls.

## Acceptance criteria
- `kca goal --help` lists `init`, `show`, `update`.
- `kca goal init ... --json` creates the `goals` row + `goal.md`; a
  second `init` on a competition with an active goal refuses cleanly
  (`{"ok": false, "error": "ACTIVE_GOAL_EXISTS"}`).
- `kca goal show --competition <slug> --json` returns the row +
  `goal_remaining_delta`, and works against the live cloud Supabase row.
- `kca goal update --close --reason ...` flips `status` and stamps
  `closed_at` / `closed_reason`; `goal.md` reflects the close.
- `goal.md` round-trips: re-reading the front-matter reconstructs the
  row fields.
- `ruff check .` / `ruff format --check .` clean; no regressions in pytest.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/goal.py`, `tools/kca/kca.py` (registration only),
  `tools/kca/COMMANDS.md`, `src/worker/reviewer.py` (goal_remaining_delta
  enrichment only), `experiments/<comp>/goal.md` (generated).
- FORBIDDEN: `tools/kca/kg.py`, `tools/kca/explore.py`,
  `supabase/migrations/**`, `tools/kca/db.py` schema changes.

## Permissions
- LOCAL_WRITE (Supabase) — ALLOWED; pooler needs `dangerouslyDisableSandbox=true`.
- No real Kaggle / LLM. `git add` deferred to T009.

## Closeout format
```
M14-T002 closeout
  CLI: kca goal init/show/update — registered; `kca goal --help` prints 3 verbs
  goal.md: experiments/<comp>/goal.md written + round-trips
  ACTIVE_GOAL_EXISTS refusal: verified
  goal_remaining_delta: surfaced in kernel_push gate prompt
  Live DB: `kca goal show --competition <slug> --json` works against cloud Supabase
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M14-T003 (kca explore + local screening)
```

## Related issues
- #51 (goal setting at start of competition).

## Stop condition
Stop after 60 turns. HALT and ask if:
- Issue #51's acceptance criteria conflict with ADR-0020 §1 — pin the
  conflict and ask before diverging.
- `goal_remaining_delta` requires a live Kaggle rank read that is not
  available offline — surface it; rank may be NULL per ADR-0020 §1.
