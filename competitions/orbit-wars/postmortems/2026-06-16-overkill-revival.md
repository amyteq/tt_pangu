# Experiment spec — OVERKILL revival (concentration → heavy-strike)

> Issue #87 follow-up, 2026-06-16. Branch `worktree-orbit-overkill`.
> Status: **round 1 (v4a/v4f) + round 2 (v4c/v4i) all FAILED.** See Results.

## Round 2 results (local HARRY-ARCH arena, 150 paired seeds vs evogen)

Two more sub-cuts requested after round 1, run locally on the reconstructed
gate (durable venv `~/.venvs/orbit-wars`, evogen fidelity 18.8% vs snorlax 17.3%).

| arm | evogen | Δ vs baseline | verdict |
|---|---|---|---|
| baseline | 17.3% (52-248) | — | |
| v4c (cluster hammer) | 17.0% (51-249) | **−0.3pt** | REFUTED (24-seed smoke +8.3pt was noise) |
| v4i (Isaiah band) @switch=200 | 17.3% (52-248) | +0.0pt | inert (byte-identical) |
| v4i @switch=120 | 17.0% (51-249) | −0.3pt | null |
| v4i @switch=80 | 16.3% (49-251) | −1.0pt | negative |

- **v4c — REFUTED.** Re-ranking the hammer toward the densest enemy/neutral
  cluster gives no win-rate. The 24-seed smoke (+8.3pt) was pure sampling noise.
- **v4i — REFUTED across all switch values.** Diagnostic (10 games): median game
  vs evogen is **~152 steps, only 2/10 reach step 200**, so Isaiah's faithful
  late-game half-drain band (switch 200) is inert — we don't survive to the
  endgame phase Isaiah's band is for. Forcing it earlier (switch 120/80) so it
  engages is null→negative: holding reserves / smaller hammers earlier hurts an
  agent that is already losing the ship race. Isaiah's band is an endgame
  point-defense optimization; it has nothing to optimize when you lose by step 152.

These are the 10th/11th refuted single-mechanism transplants — same H2 conclusion.
Note: the gate's "kuni05" column was a PHANTOM in round 2 (local kuni05 needs
`torch`; without it the agent errored → did nothing → v4 "won" ~96%). torch later
installed; evogen (17.3%, faithful) was always the real gate. All four gates
(`OW_V4A/V4F/V4C/V4I`) left default-OFF.

---


## Results (snorlax, 150 paired seeds vs evogen, +7pt bar)

Runner `arena/v4_overkill_ab.py`, seeds 21000+, 300 games/arm (±~3.5pt 95% CI).
Note: evogen (~18% v4 baseline) is the discriminating gate per the T2/t8 protocol;
kuni05 (~1240) floors at ~1% (v4 is still below that cliff → no gradient).

| arm | evogen (GATE) | Δ vs baseline | starter | kuni05 |
|---|---|---|---|---|
| baseline | 17.3% (52-248) | — | 91.0% | 1.0% |
| v4a (window) | 17.0% (51-249) | **−0.3pt** (null) | 92.0% | 1.0% |
| v4f (best-response) | 8.3% (25-275) | **−9.0pt** (regress) | 94.0% | 1.0% |
| both | 9.3% (28-272) | −8.0pt | 94.0% | 1.0% |

**Verdict:**
- **v4a — REFUTED (null, not untested).** −0.3pt, inside noise. The 6-seed +3.4pt
  smoke was sampling noise. **Diagnostic (10 games, env-step replay):** the
  counter-attack window OPENS on **36.9% of turns** (evogen commits ≥45% of its
  mass in transit; per-game max commit 0.84–1.00). So the lever fires abundantly
  and still produces zero win-rate — it is genuinely refuted, not unexercised.
  The policy-layer timing lever does not convert even when its precondition is
  richly met.
- **v4f — REFUTED (real regression).** −9.0pt, far outside CI. Legible mechanism:
  appending an enemy reinforcement to every target's arrival schedule makes the
  agent over-defensive — it beats weak `starter` MORE (94% vs 91%, holds instead
  of trading) but loses the ship-accumulation race vs evogen by going passive.
  This is the exact failure the conservation-correct frozen-opponent value avoids.
- **both** ≈ v4f (the regression dominates).

This is the 8th/9th refuted single-mechanism transplant — confirms H2
(`strategy.md`): strong play is an integrated system; isolated levers don't
transfer. The deeper read: the concentration insight was derived from the TOP
tier (Jake Will/Isaiah), but v4 sits at ~1% vs kuni05 — we can't reach the board
states where concentration matters, so the bottleneck is the cliff itself, not a
missing OVERKILL lever. Do NOT iterate on these knobs (= the refuted OW_* random
search). Both gates left default-OFF.

---
## Original spec (pre-run)


## Hypothesis

The episode evidence (`EPISODES.md` #1/#2) that **少而重 > 多而小** is real, but the
standalone `OW_OVERKILL` sizing multiplier was correctly refuted (monotonic
negative): heavy strikes *emerge* from concentration **timed to the opponent's
commitment**, they are not an output sizing rule. The legitimate home for the
lever is the v4 hub-and-hammer, whose hammer currently fires only when the
*frozen-opponent, conservation-correct* terminal value is positive (`v4.py:846`
`if val <= gate`). Under conservation, concentration has zero marginal value
(red-team verdict `v4.py:114-121`) — so the value function is structurally blind
to the t100-125 decisive-exchange insight. Crediting that window is the real
OVERKILL lever.

## Two arms (each env-gated, default OFF, baseline-identical when off)

- **v4a — counter-attack-window hammer (`OW_V4A`)** — *policy layer*, does not
  touch the terminal value. When the enemy field army is committed in transit
  (`commit = enemy_inflight / enemy_total ≥ V4A_WINDOW`) AND the target is exposed
  (no enemy source can reinforce before our hammer lands, `_exposure > 0`):
  1. bump the drain band `+V4A_BAND_BONUS` (true overkill in-window);
  2. re-rank toward the most exposed target (`+V4A_RANK_BONUS·commit·expo·size`);
  3. let a conservation-neutral hammer through (`gate = -V4A_SLACK·need`).
  Knobs: `OW_V4A_WINDOW=0.45 OW_V4A_BAND_BONUS=0.08 OW_V4A_SLACK=0.15
  OW_V4A_RANK_BONUS=0.5`. Code: `v4.py` hub-and-hammer block.

- **v4f — FM3 opponent-response value (`OW_V4F`)** — *value-function fix*. Relax
  the frozen-opponent assumption: when valuing ANY strike (greedy menu + hammer),
  append the enemy's best single reinforcing launch (nearest source able to reach
  the target within H, sending `V4F_RESP_FRAC` of its garrison) to the target's
  arrival schedule. Strikes the enemy can cheaply parry lose value; strikes that
  land while no enemy can respond gain it — the insurance value, derived not
  knobbed. 1-ply / single responder so it does not over-suppress. Knobs:
  `OW_V4F_RESP_FRAC=0.8 OW_V4F_RESP_BUF=1`. Code: `_enemy_response()` in `v4.py`.

## Measurement (T2 power protocol)

- **GATE (discriminating):** v4 vs **kuni05~1240** (strong tier — the only tier
  that discriminates; v4 saturates evogen/pub_tactical/starter), ≥150 paired
  seeds (300 games, ±3.5pt 95% CI). Bake bar: **+7pt** over the v4 baseline arm
  (same bar that baked t14 and caught a would-be regression).
- **No-regress:** evogen + starter ≥ baseline − noise.
- **Runner:** `arena/v4_overkill_ab.py` (arms: baseline / v4a / v4f / both).
  Seed block **21000+** (18000s burned by original OVERKILL, 19000s by SUPPLY).
- **Compute:** snorlax (kuni05/evogen/multifocus suite agents are gitignored and
  live only there; local box has only starter/random/pub_tactical + our versions).

## Local sanity (this box, non-discriminating — opponents saturate)

`v4_overkill_ab.py`-equiv vs pub_tactical (60×2) + starter (60×2), seeds 21000+:

| arm | pub_tactical (60×2) | starter (60×2) |
|---|---|---|
| baseline | 96.7% (116-4) | 92.5% |
| v4a | 96.7% (116-4) | 93.3% |
| v4f | 96.7% (116-4) | 94.2% |
| both | 96.7% (116-4) | 93.3% |

**Informative null, not a failure.** All arms are identical vs pub_tactical and
within noise vs starter. By design the levers are *inert against weak opponents*:
v4a only triggers when the enemy commits its field army in transit (`commit ≥
0.45`) and v4f's response model only bites against opponents that actually
reinforce — neither weak bot does. So local confirms: (a) no crashes, valid moves
every game; (b) default-OFF byte-identical to v4 baseline; (c) **no regression vs
weak tier**; (d) within engine time budget. It does **not** validate the win-rate
effect — that needs kuni05.

## Decision gate

If any arm clears **+7pt vs kuni05** with no-regress, snapshot it to a named
version file (e.g. `v4a.py`) for the league/submit pipeline and propose a ladder
submission per the KCA strategy. Otherwise: record as the 8th refuted single-
mechanism transplant and keep v4 as-is. Do **not** re-run the standalone
`OW_OVERKILL` multiplier — already refuted.
