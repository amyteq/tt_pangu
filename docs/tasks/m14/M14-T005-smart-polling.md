# M14-T005: Smart polling — Fibonacci backoff QUEUED, stable RUNNING, batched `kernels list` (issue #54)

## Milestone
M14: goal-driven Kaggle workflow.

## Goal
Revise `_watch_kernel_until_terminal` (`tools/kca/kg.py:280`) into the
three-state machine of ADR-0020 §6 — **without** regressing the
M10-discovered `kernels output`-size terminal oracle or the single-slug
auto-watch. Add `_watch_many` for ≥ 2 tracked slugs. Record
`queue_time_seconds` and `running_time_seconds` separately.

Assumes **M14-T000 / T001 / T004 closeouts are PASS**.

## Read first
1. M14-T000 / T001 / T004 closeouts.
2. `docs/adr/0020-goal-driven-kaggle-loop.md` §6 (state machine + stall release + 500-handling).
3. `docs/architecture/goal-driven-kaggle-loop.md` (poller diagram).
4. Issue #54 (acceptance criteria).
5. `tools/kca/kg.py::_watch_kernel_until_terminal` (M10 fixed-cadence baseline; `:280-363`).
6. `tools/kca/kg.py::cmd_push` (single-slug auto-watch entry; `:268-275`).
7. `docs/milestones/m10/final-review.md` (status API 500 history; output API fallback discovery).
8. `tools/kca/db.py` (T001 `set_run_analysis_jsonb`, queue-estimator read).

## Scope
1. **State machine in `_watch_kernel_until_terminal`:**
   - QUEUED → Fibonacci ramp `[60, 90, 150, 240, …]` capped at
     `⅓ × estimated_queue_time` (median of last 5 same-accelerator
     pushes for this comp from `analysis_jsonb.queue_time_seconds`;
     default 15 min if no history).
   - RUNNING → stable 300 s.
   - TERMINAL → exit.
   - STALLED → past `max_poll_minutes` (default 60) while still QUEUED:
     exit non-terminal, mark the submission `stalled`, release the
     concurrency slot.
2. **State detection:** parse `kaggle kernels status` when 200 to
   classify QUEUED vs RUNNING; **keep** the `kernels output` log-size>100
   check as the authoritative TERMINAL oracle; treat 500/503 as
   non-terminal, no state change (do NOT read a 500 as terminal or error).
3. **`_watch_many(kernel_refs)`:** ONE `kaggle kernels list -m
   --page-size 100` per tick, parsed per-slug; activates only at ≥ 2
   tracked slugs. The single-slug auto-watch path is preserved verbatim.
4. **Telemetry:** record `queue_time_seconds` + `running_time_seconds`
   separately on `experiment_runs.analysis_jsonb` so the estimator has data.

## Non-goals
- No concurrency-gate logic (T004 owns it; T005 only releases the slot on STALLED).
- No real Kaggle push (T008). All tests use a mocked clock + mocked CLI.

## Acceptance criteria
- On a synthetic kernel (mocked clock + mocked CLI responses), the cadence
  sequence in QUEUED follows the Fibonacci ramp up to the cap; RUNNING
  holds 300 s; TERMINAL exits.
- A 500 from `kernels status` does NOT change state and does NOT exit.
- The `kernels output` size>100 check still detects terminal when
  `kernels status` never returns 200 (the M10 case).
- A kernel still QUEUED past `max_poll_minutes` is marked `stalled` and
  the slot is released (assert via the T004 `count_active_pushes`).
- `_watch_many` issues exactly ONE `kernels list` per tick for ≥ 2 slugs
  and parses per-slug; single-slug still uses the 1-slug watcher.
- `queue_time_seconds` and `running_time_seconds` are written separately
  to `analysis_jsonb` on a synthetic kernel.
- Audit-grep: 0 lines reach `kaggle kernels push` / `kaggle competitions submit`.
- `ruff check .` / `ruff format --check .` clean; no pytest regressions.

## Allowed / forbidden paths
- ALLOWED: `tools/kca/kg.py` (`_watch_kernel_until_terminal`,
  `_watch_many`, `cmd_push` watch wiring), `tests/test_m14_*` (poller
  tests if added before T009).
- FORBIDDEN: `supabase/migrations/**`; `tools/kca/db.py` schema changes;
  `tools/kca/goal.py` / `explore.py`.

## Permissions
- No real Kaggle calls — mocked clock + mocked CLI only.
- LOCAL_WRITE (Supabase) for the telemetry write — ALLOWED.
- `git add` deferred to T009.

## Closeout format
```
M14-T005 closeout
  State machine: QUEUED fib-ramp -> RUNNING 300s -> TERMINAL; STALLED release at max_poll_minutes
  500-handling: non-terminal, no state change (verified)
  Terminal oracle: kernels output size>100 preserved (M10 fallback intact)
  _watch_many: ONE kernels list/tick for >=2 slugs; single-slug path preserved
  Telemetry: queue_time_seconds + running_time_seconds recorded separately
  Audit-grep: 0 real Kaggle lines
  pytest / ruff: <X> passed; clean
  Acceptance: PASS
  Next: M14-T006 (idea-sourcing + propose-next)
```

## Related issues
- #54 (smart polling).

## Stop condition
Stop after 60 turns. HALT and ask if:
- The mocked-clock seam cannot drive the cadence deterministically.
- Revising the cadence would require dropping the size>100 terminal
  oracle — it MUST be preserved (red-team dropped-capability).
