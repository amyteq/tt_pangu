# LB92 gap analysis — the mid-tier (~0.86–0.89) band vs our 0.86

> The 92nd-place writeup body is unrecoverable (author/score/method `unknown`); this compares the **public
> mid-tier recipe band** it sits in against our work. External claims untrusted (`../source_index.md`); our
> numbers from `tracking.md`. Our 0.86 is already in this band — the gaps are *corpus-quality* levers, not paradigm.

## Side-by-side (band vs us)

| dimension | mid-tier band (reconstructed) | us | gap / verdict |
|---|---|---|---|
| base / recipe | Nemotron-30B, r32 LoRA, seq8192, response-masked SFT | same (v14 replay) | parity |
| corpus | often the **andy279 multi-teacher** set (DeepSeek V3.2 + Nemotron Super 120B + GPT-5.4 + solvers, 49K) | huikang corpus + our own synth/solver-CoT | **GAP: multi-teacher distillation breadth** |
| bit CoT | solver-discovers-rule → prepend → teacher writes CoT | partial solver coverage; cryptarithm synth | **GAP: solver-prepend bit CoT** |
| hard-row handling | min-logprob rebalancing (huikang) | fixed replay dose | **GAP (also flagged in LB25)** |
| merge | sometimes single adapter | **3-way SVD soup → 0.86** | **we are AHEAD here** |
| equation | strong-cipher wall ~8–9% | eq-aug coverage 0.86 (seen-input fraction) | parity (bounded both ways) |
| above-band | adapter surgery (lopure ~0.89) / RL | not yet | gap (covered by LB80 plan) |
| score | ~0.86–0.89 (band; 92nd `unknown`) | 0.86 / 0.85 priv (eq-aug 0.86 priv) | **we are IN the band** |

## Where the marginal headroom is (consistent with LB25/LB80)
Our 0.86 already sits in this band, so 92nd place is **not above us by paradigm** — the differences are
**corpus quality** (multi-teacher breadth, solver-prepend bit CoT) and **hard-row targeting** (min-logprob
rebalancing). The category that separates the band is **bit-manipulation**; equation/cryptarithm is a shared
~8–9% cipher wall that caps everyone.

## Borrowable (ranked by EV; the LB92 contribution is the CORPUS lever)
1. **Solver-prepend bit CoT** (MEDIUM-HIGH EV). Our `lib/nemo_solver.py` covers bit only partially; adopt the
   andy279/huikang pattern: deterministic solver finds the bit rule → prepend the discovered rule → generate a
   clean step-by-step trace. Bit is the band's separator and where we have the most train-set headroom.
2. **Min-logprob rebalancing** (HIGH EV, cheap) — same lever as the LB25 plan; converges across all three writeups.
3. **Multi-teacher corpus breadth** (MEDIUM EV, ⚠ rules). The andy279 set used multiple external teachers; our
   prior single external-teacher run (andy279-style) *regressed* at high dose (0.81) — so use as **low-dose
   cold-start only**, and **verify competition/data rules permit external-model-generated traces** first.
4. **Keep our edges:** the **3-way model-soup** (we're ahead of the single-adapter band) and **eq-aug** coverage.

## NOT a gap
- Paradigm — we're already in the band (0.86). No need to copy the standard recipe; we have it + the soup.
- Equation — confirmed bounded ~8–9% both ways.

## Unknowns
- The actual 92nd-place author/score/method — `unknown` (JS-blocked, unindexed).
- Whether this team used andy279 (post-close release) or internal equivalent — `unknown`.
