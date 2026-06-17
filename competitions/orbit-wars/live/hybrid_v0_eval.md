# hybrid_v0 evaluation — NOT submit-ready (2026-06-17)

**Candidate:** `agent/versions/hybrid_v0.py` = v3.2 Forecast + model candidate re-ranker
(`OW_HYBRID=1`, `OW_HYBRID_BETA=0.5`), model `agent/hybrid_weights.json` (run `20260617-cs-ladder310`).

**Verdict: reject for ladder submission.** Integration is complete, safe, and non-regressive, but the
v0 model does not break the strong-tier cliff. Do NOT spend a submission slot on it.

## Gate results (arena, fresh seed block 9200+; 240 games/cell unless noted)

| gate | result | pass |
|---|---|---|
| Crash safety (8 games) | 0 crashes / 3650 steps | ✅ |
| Runtime | p50 9 ms / **p99 44 ms** per turn (<50 ms local; 20× under Kaggle 1000 ms) | ✅ |
| Fallback rules-only | `OW_HYBRID=0` **byte-identical** to v3.2 (499-turn replay) | ✅ |
| No torch online | pure-Python forward, matches numpy/torch 3e-16 | ✅ |
| Weak tier (pub_tactical) | 97.9% = 97.9% control | ✅ |
| 4p FFA | avg_rank 1.77/4 = control | ✅ |
| 2p vs incumbent (frozen v3.2) | net ≈even (111W/129L b0.5; tie-conversion only) | ⚠️ neutral |
| **Strong tier ≥ +7pt (VALIDATION #3)** | vs evogen 13.8%→13.8–14.6%; vs kuni05 0.8%→0.8% | ❌ **FAIL** |

## Why not submit

- The model imitates similar-skill ladder play (μ~1077) — which is what v3.2 already does — so it adds
  nothing against μ1093+ opponents. Offline AUC 0.88 did not translate (third confirmation of the
  imitation lesson; see `bugs.md` B7 / `insights.md`).
- The strong-tier gap is strategic; a re-ranker over v3.2's own candidates can't add missing strategy
  (B6: 13 levers refuted).

## Next

Retrain with genuine strong-tier teachers (top-player μ>1240 episodes), or move past imitation
(value/outcome distillation / search). Re-run this A/B harness as the gate. Full analysis:
`postmortems/2026-06-17-hybrid-v0.md`; model: `models/reports/model_card_20260617-cs-ladder310.md`.
