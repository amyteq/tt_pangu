design-red-team report for docs/adr/0020-goal-driven-kaggle-loop.md (strawman) + docs/architecture/goal-driven-kaggle-loop.md

alternatives:
  1. metrics-jsonb-reuse — sketch: instead of migrating
     `experiment_runs.analysis` from `text` to `jsonb` (the strawman's plan to
     hold `exploration_batch_id`, `parent_run_id`, `queue_time_seconds`,
     `running_time_seconds`, `escalation_id`), write those keys into the
     EXISTING `experiment_runs.metrics jsonb`
     (supabase/migrations/0004_m4_competition_repo.sql:59) under a reserved
     `_loop` namespace, leaving `analysis text` untouched. key tradeoff vs
     proposal: zero risk of corrupting M10's existing free-text `analysis`
     rows on a `text→jsonb` cast and no destructive migration to reverse; but
     it overloads `metrics` (a metric-values column) with loop-control
     metadata, blurring the grain that M2/M9 deliberately kept clean.
  2. separate-exploration-tables — sketch: don't hang loop state off
     `experiment_runs` at all; add a dedicated `exploration_batches` table
     (id, goal_id FK, status, search_space_jsonb, created_at) and an
     `exploration_runs` join row, mirroring the three-table grain split M13
     chose for eval (`eval_suites`/`eval_runs`/`eval_results`, ADR-0019 §1).
     key tradeoff vs proposal: clean queryable batch lifecycle and no JSONB
     key-spelunking, at the cost of a wider migration (two tables + FKs) and a
     second place (besides `experiment_runs`) that T003/T005 must write — more
     surface for the two writers to drift.
  3. file-first-no-db-batch — sketch: keep the batch lifecycle entirely in
     `experiments/<comp>/<batch-id>/batch.yaml` + per-run dirs (the artefact
     layout M10 already uses, runs/<comp>/<id>/), and only write the SURVIVING
     pushed candidates to `submissions`; never create N speculative
     `experiment_runs` rows for screened-but-not-pushed cells. key tradeoff vs
     proposal: no orphan-run accumulation (skeptic side_effects.2) and a much
     smaller migration, but the screening cohort is invisible to any DB query /
     UI and the stuck-detector must re-read the filesystem to count "tried
     strategies".
  4. push-gate-in-worker-not-cli — sketch: enforce concurrency + daily budget
     in `src/worker/tools.py`'s `ToolExecutor` (which already owns the
     approval-policy resolution per ADR-0006 §"In src/worker/tools.py") rather
     than inside `tools/kca/kg.py::cmd_push`. key tradeoff vs proposal:
     single choke-point shared by worker-driven and CLI-driven pushes (no
     divergence), but it moves Kaggle-specific counting logic into the generic
     tool executor, coupling the worker to competition-rules columns.

dropped_capabilities:
  - `kernels output`-size terminal detection (the M10-T004-discovered fallback
    that works when `kernels status` 500s) — evidence:
    tools/kca/kg.py:308-321 (the watcher breaks on
    `log_path.stat().st_size > 100`, NOT on a parsed status). The strawman's
    T005 state machine "parse `kaggle kernels status` when it returns 200"
    risks replacing this size-based terminal check with a status-only check
    that regresses the exact 500-resilience M10 paid for. survives in:
    metrics-jsonb-reuse (unaffected) and any design that keeps the size>100
    fallback as the terminal oracle alongside the new QUEUED/RUNNING cadence.
  - `cmd_push` auto-watch on the SAME entry point (`getattr(args, "watch",
    True)`) — evidence: tools/kca/kg.py:268-275. The strawman's `_watch_many`
    batched path must not break the single-kernel auto-watch that M10 ships;
    if `_watch_many` becomes the only path it drops the 1-slug case. survives
    in: any design that keeps `_watch_kernel_until_terminal` as the 1-slug
    path and only switches to `_watch_many` at ">= 2 slugs"
    (docs/milestones/m14/loop-prompts.md:324-325).
  - `cmd_submit`'s existing `KAGGLE_USERNAME`/`KAGGLE_KEY` pre-check envelope —
    evidence: tools/kca/kg.py:145-162. T004 adds the same check to `cmd_push`
    (#62); if it invents a NEW error envelope shape instead of mirroring
    cmd_submit's `{"ok": false, "error": "...not set...", "competition": ...,
    "side_effect": ...}`, downstream test assertions and the M14-T009 test
    (docs/milestones/m14/loop-prompts.md:463-464, "matches cmd_submit's envelope shape")
    diverge. survives in: any design that copies the cmd_submit envelope
    verbatim.
  - The reviewer gate's flag-redaction discipline carried to the new
    `kaggle.exploration_stuck` decision — evidence: src/worker/reviewer.py:96-118
    (`_redact_tool_input` strips secret-shaped fields). The escalation payload
    (T007) and `docs/escalations/<comp>-<ts>.md` must inherit a redaction pass
    or risk leaking a DSN/credential into a committed doc (skeptic
    side_effects.4); the strawman does not yet name a redaction step for the
    escalation surface. survives in: a design that routes the escalation
    payload through the same `_redact_tool_input`-style filter.

long_term_costs:
  cognitive_load: A contributor must hold the goal→batch→run→submission FK
    chain AND remember whether loop metadata lives in `analysis`,
    `metrics._loop`, or a new table — the strawman's single biggest ambiguity;
    pinning ONE storage location in the ADR is what bounds this.
  ops_burden: At 3am a stuck QUEUED kernel (M10-T004's 66-min stall) that
    counts against the concurrency limit forever will silently deadlock the
    loop with no LB write and no escalation; the QUEUED-timeout + slot-release
    policy is the load-bearing on-call control and must be explicit, not
    implied by the Fibonacci cap.
  extensibility: The design must survive the next two likely expansions —
    next likely scope: (a) per-account quota pooling (issue #21 / M15+) and
    (b) dataset/model uploads reusing the concurrency+polling logic
    (docs/milestones/m14/loop-prompts.md:82-85). A CLI-local push gate
    (push-gate-in-worker-not-cli alternative names the tension) makes (a)
    harder because the counting logic is not where multi-account selection
    will live.
  blast_radius: If the concurrency/daily gate is wrong, the blast radius is a
    real Kaggle push that violates competition rules → leaderboard pollution
    that cannot be un-pushed (skeptic side_effects.1); if the escalation
    redaction is wrong, the blast radius is a committed secret. Both are
    irreversible, which is why the gate-correctness and redaction decisions
    are stop-criteria, not nice-to-haves.

open_disagreements:
  - The strawman migrates `experiment_runs.analysis text → jsonb`. The red-team
    disagrees: a forward-only cast risks M10's existing free-text rows and is
    hard to revert (skeptic rollback.1). next step: ask-human on the M14
    proposal issue to choose between metrics-jsonb-reuse (alternative 1) and a
    new nullable `analysis_jsonb` column that leaves `analysis text` intact;
    do NOT cast in place.
  - The strawman lets one `goal.md` run multiple overlapping batches without
    saying how `exploration_batch_id` disambiguates them (skeptic
    edge_cases.3). next step: write-a-spike — prototype `kca explore rank
    --batch <id>` against two synthetic overlapping batches and confirm the
    filter is batch-scoped before T003 implements fan-out.
  - The strawman's stuck-detector treats a NULL `public_lb_score` ambiguously
    (skeptic edge_cases.4; M10-T004 shipped exactly such a NULL row,
    docs/milestones/m10/final-review.md:54). next step: defer-to-follow-up-issue
    [type:feature area:kaggle priority:P2] OR pin in ADR-0020 that a NULL score
    is "no result, does not advance the non-improving counter" — the red-team
    recommends pinning it in the ADR since T007 cannot ship without a rule.
  - The strawman enforces the push gate in `cmd_push` only, leaving worker-
    driven pushes ungated if any exist. next step: research whether any
    worker job path reaches `kaggle kernels push` without going through
    `cmd_push`; if yes, the gate belongs in `ToolExecutor` (alternative 4),
    not the CLI.
  - The per-batch approval budget has no named expiry in the strawman (skeptic
    hidden_constraints.4, rollback.3). next step: ask-human — pin the budget
    cap default and whether it expires at UTC midnight, then store it where a
    revert can invalidate it (recommend a `human_decisions` row, not
    `goal.md`).

Output MUST include ≥3 alternatives, ≥1 dropped capability with
file:line evidence, all four long-term-cost axes, and ≥1
actionable `open_disagreements` entry.
