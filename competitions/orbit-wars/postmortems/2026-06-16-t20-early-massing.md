# Experiment postmortem — T20 early-game massing (OW_EM) → REFUTED

> orbit5, 2026-06-16. Branch `worktree-orbit5-submit-and-tasks`. Status: **REFUTED**
> (12th refuted single-mechanism massing lever). `OW_EM` kept env-gated default-OFF.

## Hypothesis
Episode 80118852 (our adapted-kuni05's 4p win, decoded via `ops/track_submission.py`)
showed our OPENING is **多而小**: early ≤step80 median launch ≈ **20 ships**, we trail in
planet count (5 vs 7 @ step40), and only mass (median 238) late once rivals collapse. So:
*sizing opening neutral captures for capture-AND-HOLD (heavier → faster flight via
`fleet_speed` + a surviving garrison) should win the early board vs the strong tier.*

Designed to be DISTINCT from the already-refuted levers: not a blanket all-game multiply
(`OW_OVERKILL`), not more-thin-grabs (`OW_OPENING`). `OW_EM` is **opening-only +
neutral-only**, adds a hold margin `needed += EM_HOLD·defender`, with a small value-gate
slack `EM_SLACK` so the frozen-opponent value fn (which under-credits the future retake
threat) doesn't suppress it. Default OFF → byte-identical to v4 baseline (confirmed: EM=0
reproduces 16-64 = 20.0% vs evogen exactly).

## Measurement (local HARRY-ARCH arena, fidelity-verified evogen, fresh seeds 40000+)
evogen = the discriminating gate (v4 ~20% baseline); starter = no-regress. 40 paired
seeds (80 games, ±~5.5pt 95% CI) per arm.

| arm | evogen | Δ vs baseline |
|---|---:|---:|
| baseline (EM=0) | 20.0% (16-64) | — |
| EM defaults (HOLD0.6 SLACK0.15 PHASE80) | 8.8% (7-73) | **−11.2** |
| HOLD0.3 SLACK0.0 | 12.5% (10-70) | −7.5 |
| HOLD0.3 SLACK0.05 | 11.2% (9-71) | −8.8 |
| HOLD0.6 SLACK0.0 | 6.2% (5-75) | −13.8 |
| MIN25 (pure min-launch floor) | 8.8% (7-73) | −11.2 |
| PHASE40 HOLD0.4 SLACK0.1 (gentlest) | 18.8% (15-65) | −1.2 (≈noise) |

vs starter: EM=1 100% vs baseline 95% (beats the weak tier MORE — the classic
over-defensive / over-commit tell, same as v4f).

## Verdict — REFUTED (mechanism, not just one config)
The response is **monotonic-negative with no positive region**: every EM variant is ≤
baseline, and the more EM does (higher hold, longer phase, min-floor), the worse it gets;
the gentlest config is merely neutral (−1.2pt, within noise). No arm approaches the +7pt
bake bar, so there is nothing to promote to a 150-seed confirm. Heavier opening neutral
grabs over-commit ships early and lose the accumulation race vs the strong tier — the exact
failure of `OW_OVERKILL` (monotonic-negative) and `v4f` (over-defensive). The "少而重"
insight is real at the mechanic level but, like the prior 11 transplants, does NOT transfer
as an isolated sizing lever: the strong tier wins as an integrated SYSTEM (opening-sequence
planning + which targets in what order + multi-wave + sim co-designed), not via bigger
opening fleets. Confirms `strategy.md` H2 and `insights.md`.

## Decision
- `OW_EM` left **default OFF** (env-gated, reproducible). v4 on the ladder (sub 53730511,
  settling ~700) is unaffected — keep it as the own-agent slot.
- Do NOT iterate these knobs (= the refuted OW_* random-search anti-pattern, INS-003 spirit).
- The on-target unexplored direction remains an INTEGRATED opening planner (sequence/target
  selection), not another sizing knob — a large, high-risk build, deferred. kuni05 (1079.7)
  + coarr stay as the competitive/anchor entries.
