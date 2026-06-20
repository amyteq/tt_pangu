# LB13 / 13th Place — Score-improvement tricks

> Evidence cites `../writeup/lb13-writeup.md` (= `temp/LB13.pdf`). "reusable by us" judged vs our repo (notes.md / submissions.md / equation-frontier.md).

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **equation structural redesign (3 assumptions)** | 4 mutually-exclusive operator categories (add/mul/sub/concat); exclusivity (distinct symbols ≠ same category); **reversal symmetry shared across all examples**. Global reversal via majority vote; deduce verifies via target-operator examples; guess strictly picks an unused family (ties sub>add>mul>concat). | §3 equation; deduce 95.3%, **guess 50.7%** | **High** (equation; highest guess in batch) | **Yes — adopt for our EQ; re-check premise** | Medium |
| **Dataset rebalancing 1:1 correct:incorrect** | Rebalance teacher-correct vs teacher-incorrect traces to 1:1 (fallback overrepresented); keeps incorrect traces. | §2 cryptarithm | **Medium-High** | **Yes — challenges our c1/c2 verified-only** (echoes LB10) | Low |
| **Robust aggregation (match ≥1 example)** | An operation is a valid candidate if it matches ≥1 relevant example, not all — tolerates symbol transcription errors. | §2 cryptarithm | **Medium** | **Yes** | Low |
| **bit 3-input verification (MAJORITY/XNOR)** | Explicitly verify 3-input ops for unresolved bits; restrict search via input-bit-position from left/right operands; left-edge propagation fallback; drop parsing-display to free tokens. | §1 bit; 89.7% | **Medium-High** (bit) | **Yes** — our bit ~10% | Medium |
| **3-stage decreasing-LR SFT** | Stage1 LR 2e-4 linear 2ep (align); stage2 2e-5 cosine 1ep (smooth); stage3 5e-6 cosine 1ep (upsample bit+cryptarithm). | §SFT | **Medium** | **Yes — cheap A/B vs single-stage** | Low-Medium |
| **Aggressive/overfit-prone SFT for CoT fidelity** | Goal = better CoT trace generation, not zero-shot → use the entire dataset, overfit-prone. | §SFT | **Medium** | **Yes** (trace-fidelity framing) | Low |
| **cryptarithm output de-bracing + non-operator-symbol fallback** | Remove extra braces (syntax ambiguity); if concat/rev-concat non-unique, return first remaining non-operator symbol. | §2 cryptarithm | **Low-Medium** | **Yes** | Low |
| **equation augmentation as cryptarithm seeds** | Use equation_numeric problems as seeds to 3× cryptarithm samples. | §2 cryptarithm | **Low-Medium** | **Yes** | Low |
| **LoRA targets without lm_head** | Targets q/k/v/o + in/out + up/down (no lm_head). | §SFT | **Low** (vLLM ignores lm_head anyway) | **Yes** (consistent with LB5 note) | Low |

## Provenance / attribution
- **Built on @huikang OPP** (reasoner foundation) + **@konbu17** (original SFT notebook) + **@dgxchen** (improved notebook). Base: Nemotron-3-Nano-30B.
- **Novel to LB13:** the **equation reversal-symmetry + family-exclusivity model with majority-vote global reversal** (sharpest equation structure, highest guess 50.7%); **1:1 correct:incorrect rebalancing**; **robust aggregation**; the **3-stage decreasing-LR SFT**.
- **Cross-writeup convergence:** **keeping teacher-incorrect traces helps** — LB13 (1:1 rebalance) + LB10 (excluding them hurt). Directly relevant to our c1/c2 verified-only filter.
