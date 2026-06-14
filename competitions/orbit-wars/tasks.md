# Tasks — Orbit Wars

> Derived from issue #87 TODO/Plan table (T1–T14). Full English tracking in `tracking.md`.

## Now
- **v4 "Scheduler"** (hub-and-hammer, T9/T13): at parity with v3.2 (49.3% on 150 paired seeds); next cut =
  counter-attack window (hammer when opponent's main force is in transit) + cluster-targeted hammer + Isaiah
  mid-game sizing + FM3 opponent-response term in the value function.

## Next
- D2 last-3-days freeze: pick the best 2 versions per account and re-submit (latest-2 scored).
- T1 replay mining of the public episode dataset (top-bot behavior → heuristic params).
- T4 endgame + comet module (turns 450–500 score-positive only; comet payback gate).

## Backlog / background
- T12 RL/distillation (D4): de-prioritized to background after v0/v1/v2 (BC ≠ playing); next would be
  DAgger / value distillation / forward-sim features.

## Blocked
- None hard-blocking; constrained by deadline (06-23), 5/day quota, and the strong-tier cliff.

## Done
- T2 suite param optimization → **t14 → v3.2 baked (+7pt over baseline)**, 6/6 VALIDATION gates, submitted.
- T8 co-arrival (real +3pt evogen-layer; default OFF). T10 VALIDATION.md gate. T11 ledger (no-op).
- T6 confirm eval-side torch usable. T7 2p/4p split (rejected — ladder is 1v1).
- v1 → v2 → v2.1 (556) → v3 Forecast (686) → v3.1 → v3.2 (660 current) → v4 Scheduler (parity, iterating).
- Multi-account submit tool (`submit.py`, compliance-gated). Version league (`LEAGUE.md`). Episode pipeline.

## Proposed GitHub issues
> Not created in this task. Issue #87 is the hub. Suggested:
- "orbit-wars: last-3-days final-2 freeze decision + post-deadline archival" (acceptance: record final
  submitted 2 per account; backfill submissions.md with final ladder + private LB; status → archived).
