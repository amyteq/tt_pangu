# Submissions — Orbit Wars

> **Refreshed 2026-06-14 via read-only Kaggle API** (`kaggle competitions submissions orbit-wars`, both accounts;
> creds in `.vscode/.env.harry` / `.vscode/.env.may`, read-for-use only). `publicScore` = ladder μ rating.
> All rows confirmed `COMPLETE`. Private LB empty in API → `unknown`. The competition keeps only the **latest 2**
> per account on the ladder. Kaggle's submissions API exposes no numeric submission ID.

## harrysun2006

| Date (UTC) | Agent / file | Ladder μ (public) | Private | Status | Notes |
|---|---|---:|---:|---|---|
| 2026-06-11 23:17 | `submission_kuni.tar.gz` (adapted kuni05, **attributed**) | **1085.4** | unknown | COMPLETE | **latest-2** re-submit (D2); strong-tier entry |
| 2026-06-11 23:17 | `main.py` v3.2 (t14) | **660.0** | unknown | COMPLETE | **latest-2**; own-agent current |
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
| 2026-06-11 23:49 | `v3_2_coarr.py` (v3.2 + co-arrival ON) | **648.8** | unknown | COMPLETE | latest-2; T8 ladder experiment |
| 2026-06-11 23:45 | `main.py` v3.2 (t14) | **636.7** | unknown | COMPLETE | latest-2 |

## Reading
- **Best own-agent ladder:** ~686 (Forecast v3 peak) / 660 (v3.2 current). 
- **Best attributed entry:** 1151.0 peak (adapted kuni05, attributed) / 1085.4 current re-submit.
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
