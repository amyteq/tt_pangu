# Bugs — Orbit Wars

> Mostly methodology pitfalls / rule-sim mismatches, not crashes. Detail in `README.md` / `VALIDATION.md` / issue #87.

| ID | Status | Severity | Area | Summary | Evidence | Next action |
|---|---|---|---|---|---|---|
| B1 | fixed | high | eval-methodology | self-play win% **does not predict the ladder** (v3 beat v2.1 91% offline yet ≈ on ladder) | README; issue #87 | gate on `arena/suite_gate.py` (strong-weak suite); never self-play |
| B2 | fixed | medium | eval-methodology | identical-mirror null is ~39% (2p) / ~57.5% (4p), not 50% | README | read decisive W-L / avg_rank |
| B3 | fixed | medium | eval-methodology | small-batch noise 8–27% (24–60 games) → false positives (T2-R1 "25%") | issue #87 | ≥150 paired seeds (±3.5pt) + ±7pt bake gate |
| B4 | fixed | high | value-fn | scoring net-ships over all k penalized in-transit ships → near-passive | README (Forecast bug) | terminal (k=H) differential value (conservation-correct) |
| B5 | fixed | medium | agent-robustness | any exception → return `[]` (passive but never forfeits/crashes) | README | crash-safe wrapper on all agents |
| B6 | open | high | strength-gap | strong-tier cliff: 0–15% vs evogen1093 / multifocus / kuni05 1240; 7 single-mechanism levers failed | issue #87 | v4 Scheduler integrated rewrite |
| B7 | wontfix | medium | ml | T12 BC reached high imitation (recall@k 0.387) but 0% in arena — distribution shift | issue #87 c (T12 v2) | de-prioritize BC; DAgger / value distillation if revisited |
| B8 | fixed | low | ops | torch opponents spawn ~24 OMP threads/worker → 24-core box load 269 (idle spin) | issue #87 worklog | `OMP_NUM_THREADS=1` (recorded in snorlax doc) |
| B9 | fixed | medium | agent-logic | v4 iter1 "shutter-crash" (mirror 13%): 83% empire in transit chasing a moving hub + 18–63-ship chip-hammers | issue #87 (C4 log) | iter2 guardrails (rear-only forwarding, supply cap 0.5, min hammer mass 80) → parity |
| B10 | infra | — | execution-safety | path/landing safety was spread across agents (each its own `_path_blocked`) — risk of moving-planet first-hit mismatch / wrong-first-hit / strict-vs-near-sun confusion | OW-P0-STATE-LEDGER-001 | **deterministic `core/oracle.py` FlightOracle** centralizes it (engine-verified swept collision; target/friendly/enemy/neutral/comet/sun/oob; strict-sun vs near-sun); `tests_orbit/test_flight_oracle.py` 6/6. **✅ wired (prompt 02):** `core/action_sanitizer.py` gates `agent/main.py` final emission (`_emit_gate`, import-guarded; blocks sun/oob, wrong-first-hit on intent); verified ACTIVE with **0 false-positives** on v3.2 (pure safety net, no regression); `test_action_sanitizer.py` 4/4. Activate on ladder via `main.py+core/` tar.gz. |
