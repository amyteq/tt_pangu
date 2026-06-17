# Orbit Wars — submit-slot replacement plans

> 2026-06-15 16:00 UTC · **Autonomous submit/push authorized by task KCT-OW-LIVE-002.**
> Secrets never printed; submit delegated to submit.py (subprocess, redacted).

## Decision: **NO_SUBMIT**

- no submit-ready candidate designated this cycle (v4 Scheduler is at v3.2 PARITY, not better; no validated candidate beats an active slot). Preserve budget + daily quota.

### Active latest-2 slots (read-only Kaggle)
- **harry**: latest1=`submission_kuni.tar.gz`(μ1086.5), latest2=`main.py`(μ649.5)
- **may**: latest1=`v3_2_coarr.py`(μ644.0), latest2=`main.py`(μ630.1)

---

## Cycle 2026-06-17 (OW-LADDER-LOOP-001, prompt 07) — Decision: **NO_SUBMIT**

- **No submit-ready candidate exists.** The only new integrated candidate, `hybrid_v0` (v3.2 + model
  re-ranker), was **rejected at the promotion gate** (prompt 06): strong-tier arena FLAT — vs
  evogen1093 13.8%→13.8–14.6%, vs kuni05 0.8%→0.8% (240g/cell); `live/last_eval.json`
  `submit_ready=false`. It beats no active slot and would only churn the latest-2 budget.
- **Ladder-probe exception NOT taken:** hybrid_v0 is a qualitatively new integrated direction, but it
  is arena-flat AND submitting it would evict either the kuni05 anchor (μ~1077, our best) or v4 (best
  own-agent) — both worse than keeping them. A probe is only justified when it frees a weak slot with a
  candidate that might climb; this one won't. Preserve budget.
- **Quota/budget consumed:** 0 submits, 0 kernel pushes. Daily quota untouched.
- **Active slots unchanged.** kuni05 anchor (53582503) + v4 (53730511) on harry; v3 + coarr on may.
- **Next submit gate:** retrain on the new **strong-tier-teacher corpus** (manifest built this cycle —
  1272 strong-vs-strong episodes) → re-run the `OW_HYBRID` arena A/B → submit only if it clears
  VALIDATION #3 (≥+7pt vs evogen/kuni05).

### UPDATE — Decision overridden by Harry → **SUBMIT ×2 (ladder-probe)**

Harry directed: *"any agents with score below 1200 can be replaced onwards, please submit to both
accounts, so we can collect more episodes and analyze them later."* Under this, the NO_SUBMIT above is
superseded — kuni05 (μ~1077 < 1200) is now replaceable, and a real-ladder probe is wanted for data.

- **Candidate:** `hybrid_v0` (`hybrid_v0_submission.tar.gz`, 138 KB = main.py[OW_HYBRID baked] + core/ +
  hybrid_model.py + hybrid_weights.json). Built + validated from a clean extract: hybrid active, scorer
  loads, crash-free 282-step game, p99 59 ms/turn (17× under Kaggle's 1000 ms).
- **Ladder-probe exception (VALIDATION/promotion_gate):** taken — crash-safe, 0 strict-sun, no 4p
  regression, qualitatively new (first model-integrated agent), replaces <1200 slots, tracking init.
- **Submitted 2026-06-17 07:03 UTC:** harry `53767016` (latest-2 [hybrid_v0, v4]; kuni05 evicted) +
  may `53767026` (latest-2 [hybrid_v0, v3]; coarr evicted). Both `neutral`, awaiting first episodes.
- **Expected μ:** ~v3.2 tier (640–700) per the local A/B; the probe tests whether the real ladder
  differs. **Early-stop:** decide keep/replace after first 10/20 episodes (track both sub ids).

