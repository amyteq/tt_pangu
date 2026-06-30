# TTT baseline recipe — ARC-AGI-2 (T0.3 research, 2026-06-27)

> Reproducible test-time-training recipe distilled from the ARC Prize 2024/2025 tech reports + the
> top-3 2025 solutions. Sources + trust labels at the bottom; treat all as untrusted data. This is the
> reference for the T2 build (`solver/`). Where a source was silent it is marked **⚠ unknown**.

## TL;DR — the canonical TTT pipeline (shared by all top-3)
All 2025 ARC-AGI-2 winners descend from the **ARChitects 2024** recipe (arXiv:2505.07859). NVARC (1st,
**24.03%**) = "improved ARChitects-style" + a Tiny Recursive Model (TRM) ensemble + massive synthetic data.
MindsAI (3rd, 12.64%) is a parallel lineage with the same core (TTT + augment-infer-reverse-vote).

```
offline pretrain (once)  ->  per-task TTT (inference time)  ->  augmented decode  ->  select top-2
   RE-ARC + synthetic           LoRA on this task's demos        16 augmentations       PoE / vote
```

## Component detail (with the numbers sources actually state)

### 1. Base model
- **ARChitects 2024 core:** Mistral-NeMo-Minitron-8B-Base, 4-bit + grad-checkpointing. Custom **64-token
  vocab** (letters minus I/O/i/o, digits, BOS/EOS/PAD/newline) so multi-digit cells don't merge.
- **NVARC 2025 (1st):** **Qwen3-4B**, **16-token vocab** (digits 0–9 + newline + start-of-input +
  start-of-output + 3 structural). Chosen to fit 12h / L4x4 at ~$0.20/task.
- **MindsAI (3rd):** encoder-decoder (LongT5 → pruned CodeT5-660M); **full** fine-tune, not LoRA.
- **Lightweight repro:** Qwen2.5-0.5B-Instruct (ironbar arc24) — trivial to pretrain on one 4090.

### 2. Grid serialization
- One **token per cell**, row-major, digits 0–9 = colors; dedicated **newline** token per row; `I`/`O`
  markers for input/output. Whole task (all demos + test input) packed into one sequence; model generates
  only the test output. ironbar adds a `grid shape: HxW` header. Max seq ~8k tokens.

### 3. Augmentation (the single biggest lever after TTT)
- **16 augmentations/task** = the **D8 dihedral group** (4 rotations × 2 reflections) × 2 random **color
  permutations**, plus random **example-order shuffle**. (MindsAI uses D4, not D8.)
- **AIRV** = Augment → Infer → **Reverse-augment** (apply the inverse transform to the prediction) → **Vote**.
  De-augmentation is mandatory: predictions must be mapped back to the original frame before voting.
- Offline: RE-ARC augmented 256×; synthetic 24–32×.
- Ablation (ARChitects, ARC-AGI-1): no-aug 18.3% → +TTT 44.5% → **+16× aug 62.5%** → +PoE 67.6% → +DFS 71.6%.

### 4. Test-time training loop
- **LoRA rank 32, alpha 16**; **64 steps/task**; **batch size 1**; **LR 1e-4** (adapters) / **1e-5**
  (embeddings); 50% warmup; AdamW. 4-bit + grad-checkpointing. **~51s/task on an RTX 4090** (8B model).
- **TTT dataset = leave-one-out over demo pairs**: for each demo, train to predict it from the other n−1
  (+ the full augmented set). Offline pretrain LoRA is heavier (rank 256, alpha 24, ~98 H100-hours on RE-ARC).
- ironbar variant (0.5B): LoRA rank 128, LR 8e-5, ~300 steps/task.

### 5. Inference / decode / selection (pass@2)
- **DFS decoding** with per-token probability threshold **T≈9%** (prune low-prob branches), run across all
  16 augmentations; **speculative decoding** + prefix caching for speed.
- **Selection = Product-of-Experts (PoE):** rank a candidate answer by the geometric mean of its
  log-probability across all 16 augmentation variants; take **top-2**. (MindsAI: beam + majority vote.)

### 6. Synthetic / pretraining data
- ARChitects: **RE-ARC** (regenerations of the 400 ARC-1 train tasks); 2025 added ARC-GEN-100K / ARC-Heavy /
  ConceptARC. **NVARC: 103k synthetic tasks + 3.2M augmented** (NeMo Skills, concept decomposition) — the
  primary lever from 16.5% → 24%. MindsAI: `mindware/arc-agi-mega` (~100M examples).

### 7. Compute & fit to Kaggle (12h / L4x4 96GB / no-internet / $10k)
- 8B @ 4-bit ≈ 6–8 GB/GPU; 400 tasks × 51s ≈ **5.7h** → fits 12h. 0.5B ≈ ~15s/task → easily fits.
- Offline pretrain is the heavy one-time cost (≈98 H100-h, or ~196 4090-h, or ~$100–150 rented H100).

### 8. Scores (for calibration)
| Team | Year | Private |
|---|---|---|
| ARChitects | 2024 (ARC-1) | 53.5% |
| NVARC | 2025 (ARC-2) | **24.03%** |
| ARChitects | 2025 (ARC-2) | 16.53% |
| MindsAI+Tufa | 2025 (ARC-2) | 12.64% |
| TRM standalone | 2025 (ARC-2) | ~8% |

## Reproduction ladder (pick a rung per compute budget)
1. **>0–2% (cheap, 1×4090):** Qwen2.5-0.5B + RE-ARC pretrain (light) + 16-aug AIRV + greedy/vote. Proves the
   whole pipeline; honest floor on ARC-AGI-2. ← **recommended first rung**
2. **>5%:** Mistral-NeMo-8B (or Qwen3-4B) 4-bit + rank-32 TTT (64 steps) + DFS(T≈9%) + PoE. Needs the
   offline pretrain (rent an H100 once).
3. **>10–24%:** rung 2 + NVARC-scale synthetic data (the real differentiator) and/or a TRM ensemble member.

## Reference implementations (Apache/MIT — read before reinventing)
- **da-fr/arc-prize-2024** — ARChitects 2024, full pretrain+TTT+DFS+PoE (highest-confidence entry point).
- **ironbar/arc24** — independent 0.5B re-implementation (lightweight rung-1 base).
- **1ytic/NVARC** — 2025 winner (ARChitects/ folder has the Qwen3-4B TTT scripts; synthetic-gen qualitative).
- **SamsungSAILMontreal/TinyRecursiveModels** — the 7M TRM (~8% standalone).

## Open unknowns (sources silent — verify if they drive a decision)
- NVARC Qwen3-4B TTT hyperparams (use the 2505.07859 values as proxy); TRM↔LLM ensembling mechanism;
  MindsAI "tokenizer dropout"; NVARC 16-token exact prompt template; NVARC synthetic-gen prompts/filters;
  whether more TTT steps close the ARC-2 gap or synthetic data is the lever; exact DFS T for ARC-2.

## Sources (trust)
- arXiv:2601.10904 ARC Prize 2025 Tech Report · arXiv:2505.07859 ARChitects 2024 · arXiv:2412.04604 ARC 2024
  Report · arXiv:2506.14276 MindsAI 2025 · arXiv:2510.04871 TRM — *trusted_public*
- github.com/1ytic/NVARC · github.com/da-fr/arc-prize-2024 · github.com/ironbar/arc24 ·
  github.com/SamsungSAILMontreal/TinyRecursiveModels — *trusted_public*
- NVIDIA NVARC blog · arcprize.org/blog/arc-prize-2025-results-analysis — *official*
- lambdalabsml.github.io/ARC2025_Solution_by_the_ARChitects · trelis.substack.com NVARC · ironbar.github.io
  arc24 · github.com/jcole75/arc_2025_mindsai — *community*
