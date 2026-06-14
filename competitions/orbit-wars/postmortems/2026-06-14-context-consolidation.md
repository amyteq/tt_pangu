# Postmortem: context consolidation (orbit-wars, KCT-003, 2026-06-14)

> KCT-003: consolidated the long issue-#87 tracking context into English canonical docs under
> `competitions/orbit-wars/`. Builds on KCT-001. Chinese originals preserved as `_zh` sidecars.
> The original KCT-001 postmortem is preserved (English) in
> [`2026-06-14-kct-001-initial-consolidation.md`](./2026-06-14-kct-001-initial-consolidation.md).

## Sources read
- GitHub issue **#87** (body + 15 comments; Chinese strategy/tracking hub) — primary.
- `work/00.orbit.md` (A1/A2 analysis, zh); `competitions/orbit-wars/README.md` / `EPISODES.md` / `LEAGUE.md` / `VALIDATION.md`.
- `worklogs/orbit.md`, `worklogs/orbit2.md`; PRs #80 / #89 / #92.

## Key facts recovered
- $50,000 Featured; 1v1 μ-ladder (μ0=600, pairwise update); deadline 2026-06-15→**2026-06-23**; 5/day, latest-2 scored;
  id 138420. Engine pure-Python CPU-bound (GPU useless); torch usable eval-side.

## Decisions recovered
- D1–D5 confirmed 2026-06-12: D1=C; D2 freeze best-2 in last 3 days; D3 snorlax compute; D4 RL/distill via T10 gate; D5 inline marks.

## Open blockers
- Strong-tier cliff (0–15% vs evogen/multifocus/kuni05); 7 single-mechanism levers failed; v4 at parity not yet ahead.

## Active tasks recovered
- v4 Scheduler next cut (counter-attack window / cluster hammer / FM3 opponent-response); D2 final-2 freeze; T1 replay mining.

## Known submissions/results recovered (read-only refresh 2026-06-14)
- harrysun2006 latest-2: adapted-kuni05 1085.4 + v3.2 660.0; retired peaks kuni05 1151.0, v3 686.1, v2.1 555.8.
- firefly2006 latest-2: v3_2_coarr 648.8 + v3.2 636.7. Leaderboard top ~1746. Private LB not released. See `submissions.md`.

## Bugs recovered
- See `bugs.md` (self-play≠ladder, mirror null, terminal differential value, crash-safe, strong-tier cliff, BC shift, OMP threads, v4 iter1 shutter-crash).

## Reusable insights
- Ladder-predictive suite (not self-play); powered paired-seed A/B + bake gate; imitation ≠ playing; parallel CPU arena. See `insights.md` / `_shared/`.

## Chinese→English translations performed
- Issue #87 tables (D1–D5, T1–T14, §9, levers, agent-evolution) → `tracking.md` (EN). Key conclusions → EN in `tracking.md`/`strategy.md`/`insights.md`.
- Interim Chinese KCT-001 docs (rules/strategy/tasks/submissions/bugs/references/insights/postmortem) → rewritten English canonical (README kept; compact current-status block prepended).

## _zh sidecars created
- `tracking_zh.md` (verbatim issue #87 body, Chinese tables), `notes_zh.md` (zh source pointers + key excerpts).

## Kaggle read-only status commands run
- `kaggle competitions submissions orbit-wars` (harrysun2006 + firefly2006) and `kaggle competitions leaderboard orbit-wars --show`
  (creds read-for-use only, never printed). No submit/push/dataset.

## Uncertain or missing context
- Private/final-ladder μ (not released); exact submission IDs (API exposes none — date+description is the key).

## Proposed follow-up issues
- "orbit-wars: last-3-days final-2 freeze + post-deadline archival" (record final submitted 2/account; backfill final ladder + private LB; status → archived).
