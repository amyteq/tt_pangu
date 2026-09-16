# Submissions — Orbit Wars

> **Refreshed 2026-06-14 via read-only Kaggle API** (`kaggle competitions submissions orbit-wars`, both accounts;
> creds in `.vscode/.env.harry` / `.vscode/.env.may`, read-for-use only). `publicScore` = ladder μ rating.
> All rows confirmed `COMPLETE`. Private LB empty in API → `unknown`. The competition keeps only the **latest 2**
> per account on the ladder. Kaggle's submissions API exposes no numeric submission ID.
>
> **Live-loop refresh 2026-06-15 (KCT-OW-LIVE-002, read-only):** harry latest-2 = `submission_kuni.tar.gz`
> **μ1086.5** + `main.py` v3.2 **μ655.7**; may latest-2 = `v3_2_coarr.py` **μ644.0** + `main.py` v3.2 **μ630.1**.
> Cycle decision **NO_SUBMIT** (no candidate beats an active slot; v4 = parity; budget/quota preserved).
> co-arrival (may) still ~+14 over its v3.2 twin on-ladder. Live state in `live/`; loop in `ops/`.
>
> **orbit5 cycle 2026-06-16 (Harry directive: submit shelved candidates to the REAL ladder; local arena
> under-discriminates at our tier; only an agent that climbs >1200 in reasonable time keeps a slot — both
> current agents replaceable).** Read-only refresh: harry [kuni05 **1079.7**, v3.2 640.4], may [coarr 640.7,
> v3.2 648.1]. **Submitted 2** (authorized-by-task KCT-OW-LIVE-002 + Harry 2026-06-16): harry ←
> `v4_scheduler.tar.gz` (keeps kuni05 anchor), may ← `v3_forecast.py` (keeps coarr). Rationale: arena
> calibration this cycle shows v4 is strongest of our line vs the discriminating mid-tier (evogen **20.0%**
> vs v3/v3.2 16.7%, supply 13.3%, v2.1 0%, kuni05 90%) but the arena CANNOT finely rank our cluster (v3 μ686
> and v3.2 μ640 BOTH 16.7% locally) — so the ladder is the right judge. `v3_2_supply` (T14) deliberately NOT
> submitted: weaker locally (13.3%) AND confounded (older lineage, lacks v3.2's comet/swept handling). v4
> crash-validated: tar.gz↔in-repo identity 24-0 vs starter, 4p no-crash (avg_rank 1.0 vs starter / 1.875 vs
> evogen, 0 elim@t50), import-smoke `agent({})→[]`, worst-case 18.55 ms/turn.

## harrysun2006

| Date (UTC) | Agent / file | Ladder μ (public) | Private | Status | Notes |
|---|---|---:|---:|---|---|
| 2026-06-16 04:11 | `v4_scheduler.tar.gz` (v4 Scheduler hub-and-hammer; main.py+forecast_sim.py) | _pending_ | unknown | PENDING | **latest-2** (orbit5); new-arch real-ladder test; best of our line vs evogen (20.0%) |
| 2026-06-11 23:17 | `submission_kuni.tar.gz` (adapted kuni05, **attributed**) | **1079.7** | unknown | COMPLETE | **latest-2** anchor (kept; drifting 1085→1079.7); strong-tier entry |
| 2026-06-11 23:17 | `main.py` v3.2 (t14) | **640.4** | unknown | COMPLETE | retired by orbit5 v4 submit (was latest-2) |
| 2026-06-10 05:02 | `main.py` v3 Forecast | 686.1 | unknown | COMPLETE | retired; own-agent peak |
| 2026-06-10 03:44 | `submission_kuni.tar.gz` (adapted kuni05) | **1151.0** | unknown | COMPLETE | retired; **attributed-entry peak** |
| 2026-06-10 03:17 | `main.py` v2.1 | 555.8 | unknown | COMPLETE | retired baseline |
| 2026-06-10 00:54 | `main.py` (romantamrazov-adapted, attributed) | 668.3 | unknown | COMPLETE | early adapted baseline |
| 2026-06-09 23:49 | `main.py` Interceptor v2c | 626.5 | unknown | COMPLETE | early |
| 2026-06-09 23:19 | `main.py` Interceptor v2 | 538.3 | unknown | COMPLETE | early |
| 2026-06-09 13:44 | `main.py` Value-targeting v1 | 385.3 | unknown | COMPLETE | early |
| 2026-06-09 13:44 | `main.py` Value-targeting | 279.0 | unknown | COMPLETE | first |

## firefly2006 (may — real registered teammate)

| Date (UTC) | Agent / file | Ladder μ (public) | Private | Status | Notes |
|---|---|---:|---:|---|---|
| 2026-06-16 04:11 | `v3_forecast.py` (v3 Forecast single-file; our peak line) | _pending_ | unknown | PENDING | **latest-2** (orbit5); re-measure 686 peak; upgrades may best while keeping coarr |
| 2026-06-11 23:49 | `v3_2_coarr.py` (v3.2 + co-arrival ON) | **640.7** | unknown | COMPLETE | **latest-2** kept (only +on-ladder lever); T8 experiment |
| 2026-06-11 23:45 | `main.py` v3.2 (t14) | **648.1** | unknown | COMPLETE | retired by orbit5 v3 submit (was latest-2) |

## Reading
- **orbit5 active slots (2026-06-16):** harry [`v4_scheduler` _pending_, `kuni05` 1079.7], may [`v3_forecast` _pending_, `v3_2_coarr` 640.7]. v4 + v3 are the live experiments; kuni05 + coarr are the kept anchors. Monitor μ via `ops/live_loop.py --once`; only >1200-in-reasonable-time keeps a slot.
- **Best own-agent ladder:** **703.9** — v4 Scheduler, sub `53730511`, settled at the 2026-06-16
  refresh (`tracking.md` "Active slots"), superseding the ~686 Forecast-v3 peak this line used to
  give. This is a historical measurement, not `competition.yaml:best.public_lb`, which is
  `null` because final eligibility/score are unknown (ADR-0022 §3). The `_pending_` rows
  above predate the refresh. The **last** own agents submitted are the
  2026-06-17 B11-rotfix pair (`53769740` / `53769744`), whose μ was never recorded — so 703.9 is
  the last *measured* own-agent μ of an entry that was later evicted, not the final one.
- **Best attributed entry:** 1151.0 peak (adapted kuni05, attributed) / 1069.9 at the 06-16 refresh
  (1079.7 at 06-14 — slow downward drift).
- co-arrival on the ladder (may): v3_2_coarr **648.8** vs v3.2 **636.7** → **+12** (mildly positive on-ladder,
  consistent with the offline +3pt evogen-layer finding).
- Leaderboard top **~1746** (2026-06-14; Isaiah @ Tufa Labs 1745.9, Jake Will 1740.8). Private LB not released.

## Submission checklist
- [ ] local validation passed (`VALIDATION.md` 6 gates + `arena/suite_gate.py` paired-seed protocol)
- [ ] submission shape checked (single-file stdlib-only or tar.gz; <1000 ms/turn; crash-safe)
- [ ] no secrets
- [ ] runtime acceptable
- [ ] approval obtained (Kaggle submit needs human approval; second account compliance-gated)
- [ ] result recorded (this table + LEAGUE.md)
