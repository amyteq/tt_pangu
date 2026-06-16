# Strategy — Orbit Wars

> English canonical. Original Chinese discussion preserved in `tracking_zh.md` / `notes_zh.md` and issue #87.
> Full version history, design studies and dead-ends are in [`README.md`](./README.md) (detailed log).

## Current direction
**D1 = C (low-cost continue):** replay mining + suite-gated parameter optimization, plus the v4 "Scheduler"
rewrite — rather than (A) wind down or (B) a full multi-week coordinated-planner rewrite. Accept the
**two-track split**: an attributed adapted public agent (kuni05) as the competitive ladder entry, and our own
from-scratch Forecast line developed in parallel. **Everything is gated on the ladder-predictive opponent
suite (`arena/suite_gate.py`), never self-play.**

## Open discussions (issue #87 — all confirmed 2026-06-12)
- **D1 direction = C** (low-cost continue). 
- **D2 submission slots:** submit locally-validated improvements; in the last 3 days freeze and re-submit the
  best 2 (latest-2 scored). 
- **D3 compute:** snorlax (RTX 4090 box, 24-core CPU) approved for large-sample sweeps (PR #89). 
- **D4 RL/distillation:** allowed on snorlax; only submit if it beats the incumbent through the T10 gate. 
- **D5 inline comment-marking:** allowed.

> No discussions are currently open; the live question is the last-3-days final-2 freeze (D2).

## Orbit-specific strategy categories
- **Rules / engine facts:** deterministic orbits; exact capture rule (`ships > garrison_at_arrival`); first-hit
  fleet consumption; same-tick same-owner combat summing. See `rules.md` / `README.md`.
- **Geometry / simulation:** bit-exact forward simulator (0 error vs engine over 3,672 planet-step cells) —
  the core asset enabling differential terminal net-ship value.
- **Baseline agent design:** intercept-aim + exact capture math + in-flight cap + frontier garrison (v1→v2.1).
- **Local arena / eval harness:** parallel arena (`arena/pool.py`, ~30–40×, deterministic, 2p+4p);
  paired-seed A/B; **ladder-predictive suite gate** (the "self-play doesn't predict the ladder" product).
- **1v1 strategy:** the scored mode; all tuning targets it.
- **4-player FFA:** not scored; kept only as a robustness test (player-count-agnostic design, per Harry).

## Hypotheses
- **H1 (validated):** bit-exact forward sim + conservation-correct **terminal differential net-ship value** is
  the one big lever (556→686). Evidence: README; issue #87 levers table.
- **H2 (refuted, ×11):** single mechanisms transplanted from the strong tier transfer — consolidation,
  safe_drain, defense-reinforce (self-play only), multi-source salvo, opening-planner, PROJ_H scan, OW_* random
  search, plus the v4a counter-attack-window hammer, v4f best-response value, v4c cluster hammer, and v4i Isaiah
  two-band sizing (2026-06-16) all failed on the suite. Strong agents win as integrated systems. Evidence: issue
  #87; `postmortems/2026-06-16-overkill-revival.md`.
- **H3 (open, narrowed):** an integrated **hub-and-hammer scheduler (v4)** can convert the assembly machinery
  into wins — currently at parity with v3.2. Four scoped concentration/FM3 attacks all failed (2026-06-16):
  counter-attack window (v4a) null −0.3pt despite the window opening 36.9% of turns; 1-ply best-response value
  (v4f) −9pt (over-defensive); cluster hammer (v4c) null −0.3pt; Isaiah two-band (v4i) inert/negative (we don't
  reach the endgame it optimizes). No single bolt-on fixes it; the deeper blocker is the strong-tier cliff (v4
  ~1–2% vs kuni05), not a missing concentration lever — future work must be integrated, not another knob.
- **H4 (refuted):** behavior-cloning top players reproduces their play — T12 reached high imitation
  (recall@k 0.387) but **0% in arena** (BC distribution shift). Distillation de-prioritized.

## Rejected ideas
- Consolidation (long-range forwarding) ✗; safe_drain ✗; multi-source salvo (no ETA align) ✗; opening-sequence
  planner ✗; `PROJ_H` horizon scan ✗; OW_* random search ✗ (noise); OVERKILL multiplier ✗ (monotonic negative);
  T14 short-hop supply ✗ (mechanical forwarding); posture machine v1 ✗ (BRACE too often); T11 ledger constraint
  = no-op. co-arrival (T8): real but +3pt (evogen layer only) → default OFF (kept as `OW_COARRIVAL`).
  v4a counter-attack-window hammer ✗ (null −0.3pt; window opens 36.9% of turns but no conversion); v4f best-
  response value ✗ (−9pt, over-defensive); v4c cluster hammer ✗ (null −0.3pt); v4i Isaiah two-band ✗ (inert at
  switch 200 — games end ~step 152; null→−1.0pt when forced earlier) — all default-OFF
  (`OW_V4A/V4F/V4C/V4I`), 2026-06-16.
