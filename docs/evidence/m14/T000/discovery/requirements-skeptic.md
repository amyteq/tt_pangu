requirements-skeptic report for M14-T000 (goal-driven Kaggle loop; docs/milestones/README.md §M14 + docs/milestones/m14/loop-prompts.md)

hidden_constraints:
  1. Kaggle's *actual* per-competition concurrency limit is not a published
     constant — `competitions.max_concurrent_pushes` is a KCA-side guess. What
     is the source of truth, and what happens when KCA's count disagrees with
     Kaggle's enforcement (429/400)? — consequence if unanswered: T004's gate
     either over-blocks (wastes the daily budget) or under-blocks (Kaggle
     rejects the push and the loop stalls), and the rollback/stop criterion
     "concurrency enforcement permits a push that violates Kaggle's actual
     limit" (docs/milestones/m14/loop-prompts.md:552-554) cannot be evaluated.
  2. The "today's submissions" window — is it a calendar UTC day, a 24h rolling
     window from first submission, or Kaggle's own reset clock? CLAUDE.md's KCA
     strategy references "00:00 UTC roll-over" but the loop-prompt T005 says
     "24h rolling window" (docs/milestones/m14/loop-prompts.md:291). — consequence if
     unanswered: the daily-budget gate (T004) miscounts and either burns a slot
     after Kaggle reset or refuses a legal push.
  3. `goal.md`'s `target_lb_rank` requires knowing the current leaderboard size
     and the agent's current rank, which is a live read against Kaggle. Is rank
     refreshed on every loop tick, only on terminal LB write, or never (score
     only)? — consequence if unanswered: a rank-based goal can never be
     evaluated offline, and the stuck-detector's "monotone improvement" signal
     is ambiguous (rank can move without a new submission).
  4. The per-batch pre-approved push budget (decision 2 in
     docs/milestones/m14/loop-prompts.md:598-601) needs a cap and an expiry. How many
     pushes does one approval authorise, and does it expire at UTC midnight or
     persist across days? — consequence if unanswered: a stale batch approval
     could authorise pushes the human no longer intends, defeating ADR-0006's
     audit posture.
  5. The local GPU-screening fan-out (T003) assumes a GPU is present and has
     enough memory for `--max-concurrent N` processes. What is the behaviour on
     a CPU-only host, on OOM, and what bounds N? — consequence if unanswered:
     T003 either deadlocks on GPU contention or silently runs CPU-slow, and the
     "screen by holdout CV" step produces non-comparable metrics.

personas_and_accounts:
  1. M14 ships the single-Kaggle-account primitive only (issue #21 deferred).
     Which env slot selects the account — `KAGGLE_USERNAME`/`KAGGLE_KEY` from
     `.vscode/.env.harry`, or `~/.kaggle/kaggle.json`, and what happens if both
     are present and disagree? — consequence if unanswered: a push could go to
     the wrong Kaggle owner, the exact kkr.py failure mode the gate exists to
     prevent.
  2. The stuck-escalation (T007) inserts a `human_decisions` row and references
     issue #60's `approved_by_user_id` FK "if present". Which user identity is
     written when the column exists, and who is the approver of record for an
     unattended nightly loop? — consequence if unanswered: the audit trail
     cannot attribute the resume decision to a human.
  3. T008's real multi-push series requires "a human comment explicitly
     approving the multi-push series" on the closing issue. Is that the same
     human as the reviewer-gate approver, and does the per-batch budget approval
     in the UI count as that comment? — consequence if unanswered: the approval
     provenance for the only live-write task is ambiguous.

side_effects:
  1. T004/T008 `cmd_push` → real `kaggle kernels push` (REMOTE_WRITE). What
     reverses a pushed kernel version? (Kaggle keeps every version; you cannot
     un-push.) — consequence if unanswered: a bad push pollutes the kernel
     history permanently; the only mitigation is the pre-flight gate, so the
     gate must be correct before the first push.
  2. `kca explore run` writes N new `experiment_runs` rows + N
     `experiments/<comp>/<run-id>/` directories per batch (LOCAL_WRITE +
     filesystem). What cleans up an abandoned or partially-failed batch? —
     consequence if unanswered: orphan run rows accumulate and the
     stuck-detector's "tried strategies" table (T007) double-counts failed
     fan-outs as real attempts.
  3. T006 `propose-next` reads competition forum threads / public kernels /
     arxiv (network egress, untrusted data). Can any fetched text reach a place
     where it is executed or interpreted as an instruction? — consequence if
     unanswered: an untrusted forum post could inject a search-space cell or a
     command, violating CLAUDE.md operating principle 1.
  4. T007 writes `docs/escalations/<comp>-<ts>.md` into the repo. Does the
     escalation doc ever contain a DSN, credential, or flag? — consequence if
     unanswered: a secret could be committed to git via the escalation doc
     (the rollback criterion at docs/milestones/m14/loop-prompts.md:558-559).

edge_cases:
  1. M10-T004 showed a push can stall QUEUED ~66 min and never run. With smart
     polling (T005), what is the QUEUED timeout, and is a never-running push
     counted against the concurrency limit forever? — consequence if
     unanswered: a stuck QUEUED kernel permanently consumes a concurrency slot
     and the loop deadlocks.
  2. The Kaggle `kernels status` API returned 500 for newly-pushed kernels
     (docs/milestones/m10/final-review.md:287-289 / kg.py:287-289). T005's state machine
     parses `kernels status` for QUEUED/RUNNING — what state is assumed on a
     500, and does the batched `kernels list` path have the same gap? —
     consequence if unanswered: the state machine misclassifies a 500 as
     terminal/non-terminal and either exits early or polls forever.
  3. Two batches in flight at once: does a `goal.md` allow one active batch or
     many, and how is `exploration_batch_id` disambiguated across overlapping
     batches in `experiment_runs`? — consequence if unanswered: `kca explore
     rank --batch <id>` mixes runs from two batches.
  4. The stuck-detector fires on "N consecutive submissions with no monotone LB
     improvement AND 0 fresh candidates". What if some submissions never
     produced an LB score (the M10-T004 NULL `public_lb_score` case)? Does a
     NULL count as "no improvement"? — consequence if unanswered: the detector
     either never fires (NULLs reset the counter) or fires spuriously.
  5. `experiment_runs.analysis` is `text` in the live schema
     (supabase/migrations/0004_m4_competition_repo.sql:61), but the loop-prompt
     repeatedly says `experiment_runs.analysis.exploration_batch_id` as if it
     were jsonb. Where do `exploration_batch_id` / `parent_run_id` /
     `queue_time_seconds` actually live — `analysis` (text→jsonb migration),
     the existing `metrics jsonb`, or a new column? — consequence if
     unanswered: T001's migration and T003/T005's writes disagree about the
     storage location and the data silently lands nowhere.

rollback:
  1. T001 adds columns to `competitions` and `submissions` and (per edge_case 5)
     possibly changes `experiment_runs.analysis`'s type. Is the migration
     reversible without dropping data already written by M10? — consequence if
     unanswered: a forward-only `analysis text → jsonb` cast could corrupt
     existing free-text analysis rows and block a clean revert.
  2. If T004's concurrency gate is found wrong mid-milestone (stop criterion),
     what state must be cleaned before re-enabling pushes — any in-flight
     watcher threads, any half-written `submissions` rows? — consequence if
     unanswered: a revert leaves dangling watchers polling Kaggle.
  3. The per-batch approval budget is stored where (goal.md? a human_decisions
     row? competitions.metadata)? Reverting T004 must invalidate any
     outstanding budget so a later push cannot consume a stale grant. —
     consequence if unanswered: rollback leaves a live authorisation.

explicit_unknowns:
  - The authoritative source for Kaggle's real per-competition concurrent-run
    limit and daily-submission reset semantics (UTC midnight vs 24h rolling) —
    needs a human decision pinned on the M14 proposal issue before T004.
  - Whether `target_lb_rank` is a first-class goal type in M14 or deferred to a
    score-only primitive (decision 1, docs/milestones/m14/loop-prompts.md:596-599) —
    human decision.
  - The per-batch push-budget cap default and expiry (decision 2) — human
    decision.
  - The storage location for the four `experiment_runs.analysis.*` keys given
    that `analysis` is currently `text` — an ADR-0020 decision the human must
    confirm (jsonb migration vs reuse `metrics`).
  - The stuck-threshold default N (decision 4 proposes 3) and whether a NULL
    `public_lb_score` counts toward "non-improving" — human decision.
  - The idea-sourcing trust model (decision 3): auto-incorporate vs
    human-approved `next_candidates.yaml` — human decision (default proposed:
    human-approved / write-only).

Output MUST contain ≥5 questions spread across ≥3 categories, and an
`explicit_unknowns:` section listing things the agent could not
answer without human input.
