# Orbit Wars — live agent status

> cycle **2026-06-17** (OW-LADDER-LOOP-001, prompt 07). New submits start `neutral` until episode
> evidence reclassifies them. μ values are this-session ListEpisodes (read-only); a **fresh** refresh
> is pending an API rate-limit (HTTP 429) cooldown — see account_status.md.

| account | slot | file | submissionId | public μ (session) | status |
|---|---|---|---|---:|---|
| harry | latest1 | `submission_kuni.tar.gz` (adapted-kuni05) | 53582503 | ~1077 (range 600–1103) | **anchor / keep** |
| harry | latest2 | `v4_scheduler.tar.gz` (v4) | 53730511 | ~700 (peak 843) | weak — retained (best own-agent, no >1200 replacement) |
| may | latest1 | `v3_2_coarr.py` | _tbd_ | ~644 | weak — retained |
| may | latest2 | `v3_forecast.py` | _tbd_ | ~678 | weak — retained |

- **episodes analyzed this cycle:** 60 cached real-ladder replays (execution-safety audit), incl. v4's
  tracked games; **new ladder episodes:** not fetched (API 429 — recorded blocker).
- **hard bugs detected: 0.** FlightOracle audit over 60 cached episodes / 10,648 of our launches:
  **0 strict-sun collisions**, 0 OOB self-loss confirmed. (The raw `first_hit` "oob" flag fires ~11%
  but is an oracle trace artifact on approximate-intercept launches — equal on winner (11.0%) and
  loser (10.8%) seats, so non-causal; the emission sanitizer correctly blocks 0. See bugs.md B11.)
- **early-stop:** no `fix_required` triggered (clean execution layer). kuni05 = keep anchor (<1200 but
  our best). v4 / v3 / coarr = `weak` by μ<950 policy but **retained** — no validated >1200 replacement
  exists (hybrid_v0 rejected, prompt 06).
- **submit decision: NO_SUBMIT** (no candidate beats the strong tier; see submit_plans.md).
- **cycle work:** built the **strong-tier-teacher corpus manifest** (1272 strong-vs-strong episodes,
  μ≥1200) — the data pipeline that unblocks a stronger hybrid. Fetch/build/train queued
  (parallel_work_queue.md), gated on the API cooldown.
