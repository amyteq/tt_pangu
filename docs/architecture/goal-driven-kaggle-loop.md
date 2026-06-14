# Goal-driven Kaggle loop — architecture

Status: M14 (2026-06-10). Companion to
[`ADR-0020`](../adr/0020-goal-driven-kaggle-loop.md). T000 lands this
doc + the ADR; T001 lands migration 0011 + DB helpers; T002–T007 fill
the CLI + worker surfaces; T008 runs the live end-to-end; T009 is the
milestone close.

## Goals (recap)

Turn the platform from "one approved push" (M10) into "set a goal,
explore in parallel, push within Kaggle's rules, poll smartly, escalate
when stuck." Score-primary goals; rank best-effort. One real Kaggle
write surface (T008), per-batch human-approved, under a courtesy
concurrency + daily-budget gate. Never call real Kaggle from any
non-approved process (M10-T007 audit-grep sentinel inherited).

## ASCII data-flow

```
                 +----------------------------+
                 | experiments/<comp>/goal.md |  (human-readable mirror)
                 +-------------+--------------+
                               | kca goal init/update
                               v
   +-----------+        +------+------+        search-space.yaml
   | competit- |<--FK---|   goals     |        +----------------+
   |   ions    |        | (1 active   |        | axes: backbone |
   | max_*,    |        |  per comp)  |        |       img_size |
   | rules,    |        +------+------+        |       epochs   |
   | format    |               |              +-------+--------+
   +-----------+               | goal_id              | kca explore init
                               |                      v
                               |          +-----------+-----------+
                               |          | exploration batch     |
                               |          | (uuid; batch.yaml)    |
                               |          | init->fanout->screen  |
                               |          |   ->rank->promote      |
                               |          +-----------+-----------+
                               |                      | one experiment_runs
                               |                      | row per cell
                               |                      v
                               |          +-----------+-----------+
                               |          | experiment_runs       |
                               |          |  metrics jsonb:       |  <- holdout_accuracy,
                               |          |    (metric values)    |     macro_f1, train_seconds
                               |          |  analysis_jsonb (NEW): |  <- exploration_batch_id,
                               |          |   loop metadata        |     parent_run_id,
                               |          +-----------+-----------+     queue_time_seconds,
                               |                      | kca explore rank running_time_seconds,
                               |                      | (top-K qualify)  escalation_id
                               |                      v
                               |          +-----------+-----------+
                               |          | promote -> cmd_push   |
                               |          +-----------+-----------+
                               |                      | (1) creds pre-check
                               |                      | (2) concurrency gate
                               |                      | (3) daily-budget gate
                               |                      | (4) per-batch approval
                               |                      v
   +-----------+        +------+------+      +--------+---------+
   | submiss-  |<--FK---| goal_id     |      | smart poller     |
   |  ions     |  goal  +-------------+      | QUEUED: fib ramp |
   | public_lb |                             | RUNNING: 300s    |
   | _score    |<----------------------------| TERMINAL: size>0 |
   +-----+-----+   kca kaggle score          |   OR status      |
         |         --update-db               | _watch_many for  |
         |                                    |   >=2 slugs      |
         | LB delta vs goal                   +--------+---------+
         v                                             |
   +-----+-----------------+                           |
   | goal met? -----------yes--> close goal (status=reached)
   |   |                                                |
   |   no                                               |
   |   v                                                |
   | kca explore propose-next (T006)                    |
   |   forum/kernels/arxiv -> next_candidates.yaml      |
   |   (research-brief trust filter; source_url+trust)  |
   |   |                                                |
   |   +-- fresh candidates? --yes--> next batch -------+
   |   |                                                
   |   no (0 fresh) AND N non-improving                 
   |   v                                                
   | stuck detector (T007)                              
   |   write docs/escalations/<comp>-<ts>.md (redacted) 
   |   insert human_decisions(kaggle.exploration_stuck) 
   |   -> Approval Inbox (decision_api + UI)            
   |   <- human notes -> new seed -> resume             
   +----------------------------------------------------
```

## Table layouts

### `goals` (new — migration 0011)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | uuid pk | no | `gen_random_uuid()` |
| `competition_id` | uuid | no | FK → `competitions(id)` on delete cascade |
| `target_lb_score` | numeric(10,6) | yes | primary goal type |
| `target_lb_rank` | int | yes | secondary, best-effort |
| `target_rank_kind` | text | yes | check in (`percentile`,`absolute`) |
| `deadline` | timestamptz | yes | competition or self-imposed |
| `exit_strategy` | text | no | check in (`first_reached`,`all_required`,`score_only`,`rank_only`) |
| `max_total_pushes` | int | no | default 20 |
| `stuck_threshold` | int | no | default 3 |
| `status` | text | no | check in (`active`,`reached`,`closed`,`abandoned`); default `active` |
| `created_at` | timestamptz | no | default `now()` |
| `closed_at` | timestamptz | yes | |
| `closed_reason` | text | yes | |

Indexes: partial unique `(competition_id) where status='active'`;
`(competition_id)`.

### `competitions` (new columns — migration 0011, all `ADD COLUMN IF NOT EXISTS`)

`max_daily_submissions int` already exists
(`supabase/migrations/0001_init.sql:35`); T001 only ensures it. New:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `max_concurrent_pushes` | int | yes | KCA courtesy limit; Kaggle is the hard authority |
| `rules_summary_url` | text | yes | per #8 |
| `last_rules_fetch_at` | timestamptz | yes | per #8 |
| `submission_format` | jsonb | yes | per #7: `{kind: csv|notebook|kernel-output|zip, ...}` |
| `accelerators_allowed` | text[] | yes | e.g. `{tpu,gpu,none}` |
| `internet_allowed` | boolean | yes | |
| `deadline_at` | timestamptz | yes | competition close |

### `submissions` (new column — migration 0011)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `goal_id` | uuid | yes | FK → `goals(id)` on delete set null; nullable so M10 rows keep working |

Existing LB column is `public_lb_score numeric(10,6)`
(`supabase/migrations/0004_m4_competition_repo.sql:90`) — M14 reuses it,
does NOT add a `public_score`.

### `experiment_runs` (new column — migration 0011)

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `analysis_jsonb` | jsonb | yes | loop metadata; leaves `analysis text` untouched (ADR-0020 §3) |

`analysis_jsonb` documented keys (no per-key schema; documented here):

| Key | Type | Written by | Meaning |
|---|---|---|---|
| `exploration_batch_id` | uuid str | T003 `explore init` | which batch this run belongs to |
| `parent_run_id` | uuid str | T003/T006 | the run this cell was derived from (iteration lineage) |
| `queue_time_seconds` | number | T005 poller | QUEUED duration; feeds the queue estimator |
| `running_time_seconds` | number | T005 poller | RUNNING duration |
| `escalation_id` | uuid str | T007 | the `human_decisions` row that unblocked this run |

## Smart-polling state machine (T005)

```
        push ok + kernel_ref
                |
                v
        +----- QUEUED ----------------------------------+
        | cadence: Fibonacci [60,90,150,240,...]        |
        |   cap = (1/3) * estimated_queue_time          |
        |   estimated_queue_time = median(last 5 same-  |
        |     accelerator pushes) or 15min default      |
        | status==running? --------> RUNNING            |
        | output size>100? --------> TERMINAL           |
        | elapsed > max_poll_minutes? --> STALLED       |
        | status 500/503? --> stay QUEUED (no change)   |
        +-----------------------------------------------+
                |                          |
            RUNNING                     STALLED (release slot,
        +-- cadence: stable 300s --+     mark submission stalled,
        | output size>100? -> TERM |     exit non-terminal)
        | status 500/503? -> stay  |
        +--------------------------+
                |
            TERMINAL  (record queue_time_seconds + running_time_seconds
                       separately on analysis_jsonb; parse error_excerpt)
```

`_watch_many(kernel_refs)`: when ≥ 2 slugs are tracked, ONE
`kaggle kernels list -m --page-size 100` per tick, parsed per-slug. The
single-slug `cmd_push` auto-watch (`tools/kca/kg.py:268-275`) is
preserved verbatim. Terminal oracle stays the `kernels output` log-size
check (`tools/kca/kg.py:308-321`); `kernels status` only classifies
QUEUED vs RUNNING for cadence.

## Concurrency + daily-budget gate (T004) — order of checks in `cmd_push`

```
cmd_push(args):
  1. creds pre-check    -> refuse {ok:false, error:"KAGGLE_USERNAME not set..."}  # mirrors cmd_submit kg.py:145-162
  2. concurrency gate   -> count active KCA-owned runs (latest version/slug, status != TERMINAL/stalled)
                           refuse if >= competitions.max_concurrent_pushes; emit active_runs[]
  3. daily-budget gate  -> count today's submissions (UTC calendar day)
                           refuse if >= competitions.max_daily_submissions
  4. per-batch approval  -> kernel_push gate fires once per batch (one human_decisions row);
                           budget expires UTC midnight
  5. real kaggle kernels push  (only past all gates; T008 only)
```

Kaggle's 429/400 is the hard authority; the gate is a courtesy guard.
On a Kaggle rejection the loop HALTS (milestone stop criterion) — no
silent retry.

## Escalation payload schema (T007)

`docs/escalations/<comp>-<ts>.md` and `human_decisions.payload` carry the
same structured content (the doc is the human-readable mirror, the row is
authoritative):

```yaml
decision_type: kaggle.exploration_stuck
competition: <slug>
goal:        {target_lb_score, target_lb_rank, exit_strategy}
current:     {best_public_lb_score, best_rank, pushes_used, max_total_pushes}
tried_strategies:                       # one row per screened/pushed run
  - {axes: {backbone, image_size, epochs}, holdout_accuracy, public_lb_score|null}
sources_consulted:                      # from T006 propose-next
  - {source_url, trust_label, summary}
ruled_out_hypotheses: [<text>, ...]
questions: [<concrete question for the human>, ...]
```

**Redaction:** the payload passes through a `_redact_tool_input`-style
filter (`src/worker/reviewer.py:96-118`) before being written to the doc
or the audit row — no DSN, credential, or flag is ever rendered. Resume:
`kca decisions approve --notes "<direction>"` (or the UI form) writes the
human direction; the loop reads it as a structured option or free text,
mints a new batch, and records the resolving `human_decisions.id` as the
new run's `analysis_jsonb.escalation_id`.

## Reuse vs replace (surfaces touched)

| Surface | Reuse / Replace | Evidence |
|---|---|---|
| `tools/kca/kg.py::cmd_push` approval+side-effect envelope | reuse; add gates in front | `tools/kca/kg.py:201-277` |
| `tools/kca/kg.py::cmd_submit` creds pre-check envelope | copy verbatim into `cmd_push` | `tools/kca/kg.py:145-162` |
| `_watch_kernel_until_terminal` | revise cadence; keep size-fallback | `tools/kca/kg.py:280-363` |
| `src/worker/reviewer.py` trigger ops | extend with `kaggle.exploration_stuck` | `src/worker/reviewer.py:20-34` |
| `_redact_tool_input` | reuse for escalation payload | `src/worker/reviewer.py:96-118` |
| `services/decision_api/app.py` + `ApprovalInbox.tsx` | reuse the inbox; new decision_type row | — |
| `tools/kca/research.py` + research-brief skill | extend for `propose-next` | — |
| `experiments/<comp>/<id>/` + `runs/<comp>/<id>/` artefact layout | reuse | ADR-0008 |

## Audit-grep sentinel inheritance (M10-T007)

Every M14 test path inherits the M10-T007 guard: **0 lines reach
`kaggle kernels push` / `kaggle competitions submit` / `kaggle datasets
create` from any non-approved process.** T003 (local screening), T005
(poller tests with a mocked clock), T004 (fixture-driven gate refusal),
and T007 (escalation) all run offline. T008 is the **only** task with a
real Kaggle write, gated by an explicit per-batch human approval comment
on its closing issue.

## Cross-references

- [`ADR-0020`](../adr/0020-goal-driven-kaggle-loop.md) — the decisions
  this doc illustrates.
- `docs/milestones/m10/final-review.md` — the single-push baseline; QUEUED-stall +
  `kernels status` 500 history.
- `docs/architecture/discovery-debate-gate.md` — the gate T000 exercises.
- `docs/milestones/m14/loop-prompts.md` — the milestone scope + per-task loop
  prompts.
