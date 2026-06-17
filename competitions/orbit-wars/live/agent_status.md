# Orbit Wars — live agent status

> cycle **2026-06-17** (OW-LADDER-LOOP-001, prompt 07). New submits start `neutral` until episode
> evidence reclassifies them. μ values are this-session ListEpisodes (read-only); a **fresh** refresh
> is pending an API rate-limit (HTTP 429) cooldown — see account_status.md.

**Updated after the 2026-06-17 ROTATION-FIX submit (×2).** Scored latest-2 per account now:

| account | slot | file | submissionId | public μ | status |
|---|---|---|---|---:|---|
| harry | latest1 | `v3_2_rotfix_submission.tar.gz` | **53769740** | tbd (awaiting eps) | **neutral — B11 fix (45% vs evogen)** |
| harry | latest2 | `hybrid_v0_submission.tar.gz` (buggy) | 53767016 | tbd | probe — superseded by 53769740 |
| may | latest1 | `v3_2_rotfix_submission.tar.gz` | **53769744** | tbd (awaiting eps) | **neutral — B11 fix** |
| may | latest2 | `hybrid_v0_submission.tar.gz` (buggy) | 53767026 | tbd | probe — superseded by 53769744 |

The **rotation-fix (53769740/53769744)** is the candidate to watch — fixes the planet-phase off-by-one
(B11) behind the fleet-into-sun report; validated 13.8%→45% vs evogen (+31pt). The buggy hybrid_v0
probes are now latest-2 (still scored until the next submit evicts them). Earlier evicted: v4
(53730511), v3 (53730517), kuni05 (53582503), coarr (53582925) — all <1200, replaceable.

- **episodes analyzed this cycle:** 60 cached real-ladder replays (execution-safety audit), incl. v4's
  tracked games; **new ladder episodes:** not fetched (API 429 — recorded blocker).
- **hard bugs detected: 0.** FlightOracle audit over 60 cached episodes / 10,648 of our launches:
  **0 strict-sun collisions**, 0 OOB self-loss confirmed. (The raw `first_hit` "oob" flag fires ~11%
  but is an oracle trace artifact on approximate-intercept launches — equal on winner (11.0%) and
  loser (10.8%) seats, so non-causal; the emission sanitizer correctly blocks 0. See bugs.md B11.)
- **early-stop:** no `fix_required` triggered (clean execution layer). Old slots all <1200 →
  replaceable (Harry's call). New probes `neutral`, tracking initialized (decide after 10/20 eps).
- **submit decision: SUBMIT ×2 (ladder-probe), Harry-authorized.** hybrid_v0 → harry `53767016` +
  may `53767026` (replaces <1200 slots; collect episodes for analysis). The earlier NO_SUBMIT was
  superseded by Harry's direction. Local A/B was flat vs the strong tier — this probes the real ladder.
  See submit_plans.md / push_submit_audit.md.
- **cycle work:** built the **strong-tier-teacher corpus manifest** (1272 strong-vs-strong episodes,
  μ≥1200) — the data pipeline that unblocks a stronger hybrid. Fetch/build/train queued
  (parallel_work_queue.md), gated on the API cooldown.
- **next:** after a few episodes accrue, track 53767016 / 53767026 (`ops/track_submission.py`); apply
  early-stop; if the probe underperforms, re-lock kuni05 by re-submitting its tarball.
