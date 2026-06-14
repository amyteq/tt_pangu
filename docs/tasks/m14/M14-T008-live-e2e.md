# M14-T008: Live end-to-end goal-driven loop on a Kaggle competition

## Milestone
M14: goal-driven Kaggle workflow.

## Tag / posture
`policy:approval-required` — this is the ONLY M14 task with real Kaggle
kernel pushes (typically 3–5 across one or two batches), under the
per-competition concurrency gate (T004) and the per-batch human approval
(ADR-0020 §8). Bounded by `competitions.max_daily_submissions` (today's
budget) and `goal.md::max_total_pushes` (default 20).

## Override note (protocol §2)
This Loop Prompt runs REAL Kaggle kernel pushes. It is the designated
live-write path. All other M14 tasks are offline. Needs
`dangerouslyDisableSandbox=true` (network out to `kaggle.com`) and the
cloud Supabase pooler.

## Pre-conditions (ALL must hold before any push)
- T002–T007 closed and PASS.
- `KAGGLE_USERNAME` / `KAGGLE_KEY` present (verify via `kca kaggle list
  --json` — presence only, never printed).
- A small open Getting Started competition picked (default:
  `tpu-getting-started`, re-using the M10 surface) with a goal of
  "top-30% LB rank OR score >= 0.85", `exit_strategy: first_reached`.
- The closing issue carries `policy:approval-required` AND a human
  comment explicitly approving the multi-push series (the per-batch
  budget grant; expires UTC midnight per ADR-0020 §8).

## Read first
1. All M14 closeouts T000–T007.
2. `docs/adr/0020-goal-driven-kaggle-loop.md` (full loop).
3. `docs/milestones/m10/final-review.md` (the M10 single-push surface + QUEUED-stall history).
4. The closing issue's approval comment.

## Scope (the loop)
1. `kca goal init` with the agreed goal (writes `goals` row + `goal.md`).
2. `kca explore init` with a search-space (3–5 backbones × 2 image sizes
   × 2 epoch counts).
3. `kca explore run` local screening; `kca explore rank`.
4. `kca kaggle push` the top K under the concurrency gate (T004); all
   pushes auto-watched by T005's smart-polling.
5. `kca kaggle score --update-db` per terminal kernel (writes
   `submissions.public_lb_score`).
6. If LB < goal: `kca explore propose-next` (T006), iterate to the next batch.
7. If stuck (T007 detector fires): write escalation, pause, await human
   decision, resume.
8. End when goal is reached OR `max_total_pushes` reached OR human says stop.

## Non-goals
- No dataset / model uploads.
- No competition portfolio beyond the one picked.
- No bypass of the per-batch approval or the concurrency / daily gate.

## Acceptance criteria
- ≥ 2 LB scores recorded under the goal-driven loop
  (`submissions.public_lb_score` non-NULL, linked to the `goals` row).
- At least one iteration step (initial batch → idea-source → next batch
  OR escalation).
- Every real push went through: creds pre-check → concurrency gate →
  daily-budget gate → per-batch approval (auditable in `human_decisions`
  + `agent_reviews`).
- No push violated `max_concurrent_pushes`, `max_daily_submissions`, or
  `max_total_pushes` (no Kaggle 429/400; if one occurred, the loop
  HALTED and the deviation is documented).
- The closing issue links: the approval comment, the `goals.id` row, all
  `submissions.id` rows from the batch, and the final LB delta.
- The DSN / credentials never appear in any log, audit row, escalation
  doc, or the closing issue.

## Allowed / forbidden paths
- ALLOWED (real write): `kca kaggle push` / `kca kaggle score` against
  the picked competition under the approved budget; `experiments/<comp>/**`,
  `runs/<comp>/**`, `docs/escalations/**` (generated).
- FORBIDDEN: any push beyond the approved budget; dataset/model uploads;
  any source edit (this is an exercise task, not an implementation task —
  fixes route back to the owning task T002–T007).

## Permissions (protocol §2 override)
- REAL Kaggle kernel push / score — ALLOWED, bounded by the budget +
  per-batch approval; `dangerouslyDisableSandbox=true`.
- LOCAL_WRITE (cloud Supabase pooler) — ALLOWED.
- `git add` deferred to T009.

## Closeout format
```
M14-T008 closeout
  Goal: <competition> target_lb_score=<f> / target_lb_rank=<r> exit=<strategy>; goals.id=<uuid>
  Batches: <n>; pushes used: <k> / max_total_pushes=<m>; daily budget honoured: yes/no
  LB scores recorded: <list of submissions.id + public_lb_score>
  Iteration steps: <initial -> propose-next -> next batch | escalation>
  Escalations: <count> (decision ids); time-to-resolution: <...>
  Queue/running time: <totals from analysis_jsonb>
  Final LB delta vs goal: <...>; goal status: reached | not-reached
  Kaggle errors: <none | 429/400 + HALT note>
  Closing issue: <url> links approval comment + goals.id + submissions.id[] + LB delta
  Acceptance: PASS | PASS-WITH-DEVIATION (documented) | HALT
  Next: M14-T009 (regression tests + exit criteria + final review)
```

## Related issues
- New (`policy:approval-required`). Cross-ref #51 #52 #53 #54 #55.

## Stop condition
Stop after 80 turns. HALT and ask (milestone stop criteria) if:
- A real push returns a Kaggle error (rate limit, bad metadata, rules
  violation) — fix is local; re-request approval; do NOT silently retry.
- The concurrency / daily gate permits a push Kaggle then rejects —
  halt T004's enforcement and fix before any further push.
- A stuck escalation goes ≥ 24h with no human response — halt and ask
  out-of-band.
- The DSN / credential is printed anywhere — stop and rotate.
