# LB10 / 10th Place — Score-improvement tricks

> Evidence cites `../writeup/lb10-writeup.md` (= `temp/LB10.pdf`). "reusable by us" judged vs our repo (notes.md / submissions.md / insights.md).

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **"Improve the teacher, not the SFT"** | Score is bounded by the deterministic reasoner's oracle coverage; invest in trace coverage/learnability, not hyperparameters. | §Core idea, §Takeaways | **High (framing)** | **Yes — reframes our effort** toward solver coverage | n/a |
| **Rotate/shift key-table bit reasoner** | `out[i]=F(rotl(x,a),shl(x,b),shr(x,c))`; F read from examples as a 3-bit-key→bit table; recover (a,b,c) from boundary bits (bit0 shr=0, bit7 shl=0). | §bit update; 85.14%→98.75% | **High** (bit) | **Yes** — our bit ~10% coverage | Medium-High |
| **Trace compaction** | Remove per-example echoes + candidate `List:` enumeration; gate extra boundary scans by `_THRESH=24`; compact `key>value`. | §Trace efficiency | **Medium** (fewer loops, fits budget) | **Yes** | Low-Medium |
| **equation deduce candidate reorder** | Order by corpus frequency; `-` tries signed subtraction before abs diff. | §deduce; 541→555 | **Medium** | **Yes — re-check EQ premise** | Low |
| **equation guess two-axis rebuild** | Operation = conventional-if-free else first unused of {add, unsigned abs-diff, mul}; wrapper = pin from the most-example seen operator. | §guess; 21→56 | **Medium-High** (guess) | **Yes** | Medium |
| **alpha/r = 4 (high LoRA alpha)** | rank 32 / alpha 128 → adapter follows the deterministic CoT more strongly; improved CV. | §Additional / Training | **Medium** | **Yes — cheap A/B** | Low |
| **Add low-logprob problems + retrain** | Re-expose forgotten/fragile traces (not just volume); failure-mode demos mixed in. | §Additional | **Medium** | **Yes** | Low-Medium |
| **Priority 2× for fragile failure modes** | Duplicate fragile traces 2× (3× overfit). | §Training; 3× failed | **Medium** | **Yes** (cap at 2×) | Low |
| **Select by validation, not public LB** | Best private run had lower public (0.860) but higher val (0.904) → private 0.880. | §Results | **High (selection)** | **Yes** | Low |
| **Oracle-ceiling vs fidelity + learnability (logprob)** | Separate "reasoner wrong" from "model failed to imitate"; logprobs find hard traces. | §Validation | **Medium (diagnosis)** | **Yes — we lack this layer** | Medium |
| **Keep failed / low-confidence traces** (negative result) | Excluding them DECREASED accuracy → failure patterns carry signal. | §Attempts | **High (negative lesson)** | **Yes — challenges our c1/c2 verified-only filter** | Low |
| **LoRA merge** (negative result) | SVD merge + seed soup both FAILED to beat the single best (rank-32 can't extract complementarity; soup → worst member). | §Attempts | **Negative (for them)** | **Caution — tension vs our soup +0.01 / LB5 iterative soup** | n/a |
| **Curriculum / two-stage / 3× priority / cryptarithm add-sub-mul** | All failed or neutral. | §Attempts | **Negative** | Avoid | n/a |

## Provenance / attribution
- Built on the common deterministic-reasoner approach (huikang-style baseline implied). Base: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`. The writeup is largely self-contained (few external links).
- **Novel to LB10:** the **rotate/shift key-table bit reasoner with boundary-bit (a,b,c) recovery** (the 2-input flank trick a commenter highlighted), the **equation guess two-axis rebuild**, and the **negative results** (failed-trace exclusion hurts; LoRA merge fails) that are directly informative for us.
- **Cross-writeup tensions:** (1) bit hex/encoding — LB10 doesn't use hex (different approach), neutral. (2) **LoRA merge** — fails for LB10, "fails on Mamba-2" per LB80, **succeeds** as our soup (+0.01) and LB5 iterative soup → member/averaging-dependent. (3) **failed-trace value** — LB10 keeps them; our c1/c2 drop them.
