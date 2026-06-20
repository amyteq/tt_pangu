# LB3 / 3rd Place — Score-improvement tricks

> Evidence cites `../writeup/lb3-writeup.md` (= `temp/LB3.pdf`) unless noted. "reusable by us" judged vs our repo (notes.md / equation-frontier.md / submissions.md).
> Author rarely ran clean isolated ablations; impacts are qualitative except where a number is quoted.

| trick | description | evidence | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|
| **Two-stage training (memorize → execute)** | Stage 1: pretrain to recall lookup table (`<RECALL_DOMAINS>`/`<RECALL_ROWS>` drills, 16 packed per sample, request masked). Stage 2: init from stage-1 adapter, train on real traces; inject 3K drills to retain memory. | "12K: direct 0 solved, two-stage 7; direct needs 36K"; stage-1 recall overall-exact 97.1% | **High** — ~3× sample efficiency on cryptarithm; the standout idea | **Yes — top priority.** We have no memorize-pretrain stage. Modular (reuse stage-1 across format changes). | Medium-High |
| **CSP cryptarithm solver** | Mul-pattern lookup → per-symbol domains + candidate mappings → **intersect/join multiple MUL examples** → anchor mapping(s) → **bounded backtracking** (≤2 unknowns/eq, least-unknowns-first). Try (structure ∈ simple/reverse) × (mul ∈ a*b/a*b±1), reverse-first. | §Cryptarithm; solve 24.2% (deduce 27.8%, guess 9.8%) | **High** | **Yes** — lighter than LB1's full catalog | High |
| **Bit hex + tail-bit compression** | Encode output bit columns as `HEX|tail2bits` (keep last 2 bits literal — encoding them as hex hurt 9/10-example cases). −25% tokens. | §Bit "25% reduction" | **High** (enabler for MAJ) | **Yes — cheap.** We never compressed traces. | Low |
| **MAJ (majority) search** | The token budget freed by hex lets the bit solver also search the majority operation. | §Bit | **Medium** | **Yes** | Medium |
| **OR-NOT-first rule ordering** | Reorder bit rule trials so OR-NOT precedes plain OR/XOR. | §Bit "+0.6%" | **Low** (+0.6%) | **Yes** | Low |
| **Minimal 13-op numeric solver** | Exactly the ops needed (verified via the "peek" argument); deterministic ordering to resolve subtraction-family ambiguity. simple/reverse applied **globally** per problem. | §Numeric; deduce 93.79% | **Medium-High** | **Yes — re-check our EQ premise** | Medium |
| **Operation-family guessing** | Co-occurrence shows the generator samples op "families" and picks one per family; for unseen query operators, guess an op from an **unmapped family** (priority a-b, a+b, a*b). | §Numeric family table | **Medium** (guess subset) | **Yes** | Low |
| **Leakage-controlled local validation tracking private LB** | 10% stratified hold-out; exclude validation rows AND augmented samples derived from them. Tracks **private** (not public) LB. | §Validation strategy | **High** (decision-making) | **Yes — strong upgrade over our late T12** | Low-Medium |
| **Perfect-trace-rate metric** | Track exact-trace emission as a leading indicator (catches "right by luck, wrong trace"). Target >85% bit, >95% cipher/numeric. | §Additional metrics | **Medium** | **Yes** | Low |
| **Single-category iteration** | Train+validate on the target category alone to isolate a change; treat standalone as ceiling; promote only if it improves. | §Iterating | **Medium** | **Yes** — counters our B8 "single-cat gain ≠ total gain" trap | Low |
| **MoE tie weights OFF** | Disabling MoE tie weights gave better results. | §Modeling | **Medium** | **Test** — opposite of our v14 (MoE-128 tying) | Low (A/B) |
| **Small effective batch size (4)** | Large eff batch under-trains; 16→8→4 settled on 4. | §Modeling | **Medium** | **Test** | Low (A/B) |
| **Augment by resampling originals (not free-gen)** | Change operands/symbols of existing problems to avoid creating/removing hidden artifacts vs the official generator. | §Data augmentation | **Medium** | **Yes** — fixes our "synthetic dilutes" | Low-Medium |
| **Reuse llkh0a/huikang trivial+cipher traces** | Trivial categories + cipher reuse public traces; just add augmentation. | §Solver design | **Low** (already solved cats) | **Partly** (we have our own) | Low |

## Provenance / attribution
- **Built on:** llkh0a (starter notebook, trivial+cipher traces), **huikang** (CCE manual training loop, progress-prize solution), **kemshim** (symbolic equation solver ideas for cryptarithm), **youkinasa** (multi-example constraint intersection). See `../source_index.md`.
- **Novel to LB3 (vs the above and vs LB1):** the **two-stage memorize/execute decomposition** with masked drill packing, and the **CSP intersection-of-MUL-examples → anchor → bounded-backtracking** cryptarithm solver. (LB1 instead memorizes a full 22-rule signature catalog; both independently use hex bit compression.)
