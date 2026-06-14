# Postmortem: initial context consolidation (orbit-wars, KCT-001, 2026-06-14)

> Initial **KCT-001** snapshot, rebuilt from repo notes. English translation of the original Chinese KCT-001
> postmortem, **preserved here per the PR #102 review lesson** (it was superseded in place by KCT-003). The
> current/superseding English consolidation is [`2026-06-14-context-consolidation.md`](./2026-06-14-context-consolidation.md).

## Sources read
- `competitions/orbit-wars/README.md` (detailed log: version history, design studies, dead-ends)
- `competitions/orbit-wars/EPISODES.md`, `LEAGUE.md`, `VALIDATION.md`
- `competitions/orbit-wars/agent/versions/v4.py` (v4 Scheduler header)
- `worklogs/orbit.md`, `worklogs/orbit2.md` (Chinese three-table hub)
- GitHub issue #87, PR #92 (not verified online during KCT-001)

## Key facts recovered
- Kaggle Orbit Wars (id 138420, $50,000 Featured, ~4137 teams, deadline 2026-06-23).
- 1v1 ladder, μ0=600, pairwise μ update; 5 submissions/day, latest 2 kept.
- Engine is pure-Python CPU-bound; torch usable on the eval side.

## Decisions recovered
- Accepted the two-track split (2026-06-10): kuni05 (~1137, attributed) as competitive entry + own Forecast line.
- Direction D1=C (low-cost continue); submission-slot strategy decided near the deadline (D2).
- Everything gated on `arena/suite_gate.py`, not self-play.

## Open blockers
- Hard cliff: 0–15% vs strong tier (evogen 1093 / multifocus / kuni05 1240); 5 incremental levers all failed.

## Active tasks recovered
- v4 Scheduler set-planning gated on the suite, aiming for first >0% vs evogen1093; then decide on submission slots.

## Known submissions/results recovered
- adapted-kuni05 ~1137 (↑); Forecast v3 ~686; v2.1 556 (retired). LB top ~1713, top-10 ~1500-1600.

## Bugs recovered
- See `bugs.md` (self-play ≠ ladder, mirror non-50% null, terminal differential value, crash-safe, strong-tier cliff).

## Reusable insights
- Offline gate must align with the online metric; the strong tier wins as integrated systems (see `insights.md`, `_shared/`).

## Uncertain or missing context
- private/final-ladder μ details; latest v4 suite-gate numbers (defer to issue #87 / worklogs).
