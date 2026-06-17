# Discussion & findings — fleet massing, inner-ring rotation, arena reliability (orbit5, 2026-06-16)

> Source-of-truth: `kaggle_environments/.../orbit_wars.py` (engine), our agents, and a rigorous
> swept-collision timing model. Every claim is engine-cited. Companion records: `tracking.md`,
> `tasks.md` (T19–T22 + PARK), `insights.md`, `submissions.md`.

## 0. Context — the orbit5 submission cycle
Harry directive: stop gating on the local arena (it under-discriminates our cluster) and test shelved
candidates on the REAL ladder; both prior agents replaceable; only an agent that climbs **>1200 in
reasonable time** keeps a slot. Submitted 2 (2026-06-16, authorized KCT-OW-LIVE-002 + Harry):
harry ← `v4_scheduler.tar.gz` (keeps kuni05 1079.7 anchor), may ← `v3_forecast.py` (keeps coarr 640.7).

## 1. Engine mechanics (verified, with line refs)
| # | Question | Answer (engine-grounded) |
|---|---|---|
| 1 | Inner planets rotate (clockwise), outer static? | ✅ A planet rotates iff `orbital_radius + radius < ROTATION_RADIUS_LIMIT(50)` (`:540-546`,`:145`). All rotating planets share ONE `angular_velocity = uniform(0.025,0.05)` rad/step (`:366`), same direction; `cur_angle = init_angle + ω·step`. The "clockwise" you see is the renderer's y-down convention; what matters is it's uniform & predictable (our intercept already models it). |
| 2 | Rotation's effect on launch/attack paths handled? | Predicted-arrival aiming: ✅ ON (`main.py:_predict_pos 386-401`, `_solve_intercept 404-423`). Exploiting rotation offensively (staging/relay): ❌ absent. |
| 3 | Production ∝ size? | Directionally yes, but the exact relation is `prod = randint(1,5)` (primitive) → `radius = 1 + ln(prod)` (`:80-81,:133-134`). Bigger ⇔ higher production, log-shaped (prod 1→5 ⇒ r 1.00/1.69/2.10/2.39/2.61). |
| 4 | Size ⟂ distance-to-sun? | ✅ `prod` (hence size) and `orbital_radius` are sampled independently (`:88`). Only constraint: `orbital_radius ≥ SUN_RADIUS(10)+r+10` (`:141`). |
| 5 | 少而重 ⇒ massing speeds fleets? | ✅ `speed = 1+(maxSpeed-1)(ln n/ln1000)^1.5`, cap ~6 (`:577`). 19→2.39, **76→3.48 (+46%)**, 200→4.36, 1000→6.0 (concave: small-fleet regime gains most). Plus the strict capture rule (`ships>garrison_at_arrival`, same-tick same-owner SUM) means a single big fleet punches through where sequential small ones get picked off. |

## 2. Rigorous relay/staging timing — PARK
Modeled 1-hop direct (O→T) vs 2-hop relay (O→inner I→T) with the exact engine swept-collision rule.
- **Rotation is NOT a free flight shortcut.** Max inner-planet radial closing speed = `orbital_r·ω ≈ 2.35 u/step`
  (edge of inner ring) — *below* even a 19-ship fleet's 2.39 u/step. So flying always beats riding the orbit;
  the **optimal relaunch delay computed to 0 in every tested geometry/ω**, and the orbital minimum-distance phase
  is **170–210 steps out** (games end ~150).
- **Honest 2-hop is strictly worse**: ship O→I then relaunch = **35–39 turns vs 27 direct** (the leg-1 + mandatory
  turnaround dwarfs leg-2 savings).
- **2-hop only "wins"** when the garrison is ALREADY on a held forward planet closer-in-flight-time to T — pure
  **geometry**, not rotation. The real value of 少而重 is the source-side massing speedup (no hop).
- **Verdict: PARK the rotation-conveyor/relay lever.** Same family as the PARKed T8 co-arrival / T16 / OVERKILL.

## 3. Code audit — what our agents do / lack
- Rotation-aware aiming: ✅ ON (both). Fleet massing: PARTIAL — only **v4 hub-and-hammer** is ON by default
  (`v4.py:813-949`); `main.py` (v3.2) is single-source minimal-capture (`:938-947`); `OW_MULTISRC`/`OW_COARRIVAL`
  default OFF. Inner-planet staging relay / waypoint routing / corner-then-outward / "send bigger because faster":
  ❌ all absent.

## 4. Arena reliability (calibrated this cycle)
Local win% vs evogen separates GROSS tiers (kuni05 **90%**/μ1083 ≫ our line ≤20%/μ640–686 ≫ v2.1 **0%**/μ556) but
is **blind within our cluster** (v3 μ686 & v3.2 μ640 BOTH **16.7%**; v4 best at **20.0%**). ⇒ gate vs the strong
tier locally, but use the **real ladder** for fine candidate selection. v4 crash-validated (tar.gz↔repo identity
24-0, 4p no-crash, import-smoke `[]`, ≤18.55 ms/turn).

## 5. Episode 80118852 — it's OUR game, and it confirms the weakness
🔴 **`flyingfox` = harrysun2006's profile name = US.** Submission 53582503 = our adapted-kuni05 (μ~1080). Episode
80118852 = our kuni05's 4p **WIN** (seat 1). The prior "flyingfox 205-episode" 4p finding was our OWN account's
history (finding stands; label corrected — re-tag EPISODES.md #3). Planet ids 0–35 (no 163/164 = viewer artifact).

**Our seat-1 launch profile BY PHASE (the substance):**
| phase | launches | size mean/median/max | from inner planets | our planets |
|---|---|---|---|---|
| early ≤80 | 74 | **24 / 20 / 95** | 45% | 1→7 (behind: 5 vs Lucky's 7 @ step40) |
| mid 81–160 | 140 | 67 / 36 / 368 | 39% | 7→15 |
| late >160 | 27 | **276 / 238 / 467** | 44% | 15→20 (win) |

⇒ Even our strongest agent plays **多而小 early** (median 20-ship launches), falls behind, and only masses
(少而重) late once rivals collapse. **The open lever is to mass EARLIER from the opening, not grind.** (vs the
strong tier — which doesn't implode — slow openings lose.)

## 6. Follow-up tasks (in `tasks.md`)
- **T19** ✅ resolved (this doc; flyingfox=us correction; EPISODES.md #3 re-tag pending).
- **T20** 🟢 early-game massing = the pinpointed lever; v4 live-ladder result is the test (must be HEAVY not just MORE — distinguish from refuted OW_MULTISRC/COARRIVAL/OPENING).
- **T21** forward-planet aggregation (pure geometry, measure-first; never a deliberate O→I detour).
- **T22** (optional) inner/outer target valuation.
- **PARK** rotation-conveyor/inner-planet relay (rigorously refuted).
