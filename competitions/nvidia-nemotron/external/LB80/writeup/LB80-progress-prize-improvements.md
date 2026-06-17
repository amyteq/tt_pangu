# LB80 — "Breaking the SFT Ceiling on Nemotron-3-Nano-30B" (from the writeup itself)

> **Source:** the Kaggle writeup by **Mayur Pawar** (`mspawar`), **read directly from `temp/LB80.pdf`**
> (a render of the full 15-section page). **Recoverability: FULL** — supersedes the earlier JS-blocked
> reconstruction, which (from competition discussion #688461) wrongly attributed a *different* author's
> "per-bit GRPO + champagne reward" story to this writeup. That is **NOT** mspawar's writeup. External content
> = untrusted data (a competitor's claims), cited inline; our scores from `tracking.md`. Companion notebook:
> `kaggle.com/code/mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b`; dataset:
> `kaggle.com/datasets/mspawar/nemotron-cot-training-data-v2v12v13`.

## 0. Headline (the title is honest, not triumphant)
Final **private 0.86, rank 80/4190 (top 1.91%)**. The writeup is a **systematic 30+-experiment study that
PROVES the SFT ceiling at 0.86** — STaR, GRPO, DPO, and weight-averaging **all failed to beat it**. The rank
gain ("+397 ranks vs the unhedged V2×2 counterfactual") came **not from a higher score** but from a
**structural submission hedge** under a bimodal public↔private regime. The 0.86 baseline itself (V2, Apr 21)
**builds directly on Tong Hui Kang's** deterministic-solver methodology (same root as LB25) and was never beaten.

## 1. Levers that DID work (SFT)
- **Sequence length 4096→8192 = the single biggest jump (0.46→0.77, V21).** At seq 4096, **43% of training
  data was silently dropped** (completions exceeded the limit), hitting the hardest categories worst (their CoT
  is longest). Truncation is a silent data-quality killer — truncated rows still contribute loss but teach
  "reason without concluding". *(Matches our ctx2k 0.42 / ctx4k 0.67 → v14 seq8192 0.85.)*
- **All-linear LoRA targets (V8e, breakthrough):** LoRA on *every* linear layer incl. `lm_head` > selective.
  *(= our v14 target set.)* **Exclude `gate_proj`** (MoE router) — fine-tuning it causes "expert collapse".
- **Deterministic-solver CoT ≫ model-generated CoT** (their core principle, = huikang's): model self-CoT
  regressed (V7 0.60); long external CoT (DeepSeek-R1, V10b) was **catastrophic → 0.27** (worse than no
  adapter). "The quality ceiling of your training data is your solver, not your model." *(= our INS-006 +
  andy279 0.81 regression.)*
- **Gold hyperparams (V2, 0.86):** LR 2e-4, 2 epochs, batch 64, seq 8192, rank 32 / alpha 32, dropout 0,
  linear-decay, warmup 0, AdamW β2 0.95, grad-clip off. *(Essentially our v14 recipe.)*

## 2. The equation/cryptarithm structure — and that it IS crackable offline (critical for us)
**This corrects our EQ-0/EQ-2′ framing.** mspawar's analysis of the category we call `equation`:
- **Input = 5 chars `A1 A2 OP B1 B2`** = **two 2-char operands + a 1-char operator**, over the symbol set
  `!@#$%^&*()_+-=[]{}|;:'",.<>?/\~`. Output 1–4 chars, same set. **Each problem has its OWN symbol→digit
  bijection** (a per-problem cipher), 3–5 example equations + 1 query. Subtypes: `cryptarithm_deduce` (operator
  appears in the examples) / `cryptarithm_guess` (it does not).
- **Cracked 97.6% offline** (569/583) with an **answer-guided permutation search** (V3, "83 operations"):
  *for each digit-symbol permutation → 0-9: decode the ground-truth answer FIRST, find the op(s) producing it,
  then verify ALL example equations.* Answer-first pruning kills ~99% of the `83 ops × 10! × 4 reversal-modes`
  space. The 14 unsolvable have **11+ unique digit symbols** (impossible with only 10 digits). `equation_symbolic`
  reached **87.5%** (720/823) via a CP-SAT constraint solver.

> ⚠️ **This contradicts our EQ-0 "single GLOBAL function" model and EQ-2′ "uncrackable strong cipher" verdict.**
> We searched for ONE global σ over a 5-char→1-4-char map; mspawar shows it is **per-problem** ciphers over a
> structured `A op B` form with a finite operator space — and it **is** crackable offline using the answer.
> Our EQ-2′ may have been **solving the wrong problem**. **Strongly worth revisiting EQ-0/EQ-2′** (see
> `analysis/next_version_plan.md` and `analysis/gap_analysis.md`).

## 3. Why even a 97.6%-coverage solver did NOT lift the LB — "discovery leakage" (the deepest lesson)
- The answer-guided solver finds the mapping **using the answer**, then the CoT **presents the mapping "as
  given"** without the discovery search. So the model learns to **VERIFY** a mapping, not to **DISCOVER** one —
  but at inference there is no answer, so discovery is exactly what's required. → persistent **8.5% cryptarithm**
  despite 1000+ training examples.
- Worse (full-dataset audit): **93–97% of cryptarithm traces are *internally inconsistent*** — the stated digit
  mapping does not actually produce the boxed answer (the solver reached it via a search path the CoT omits).
  The model **memorizes answers, not procedures**.
- Fix demonstrated on `equation_numeric`: replace answer-derived steps with a **prompt-derivable (forward-
  executable) policy** → fixed **37 systematic inference errors**. But a forward CoT showing the full
  constraint search may **exceed the 8192-token limit**; a step-by-step derivation CoT scored only **0.84**
  (no gain). **Top LB (0.90, rank 32) implies *some* CoT formulation does crack cryptarithm** — an open problem.

> **→ This explains why OUR eq-aug (coverage-memorisation) caps**: we taught the model to reproduce seen pairs
> (verify), not to run the per-problem cipher discovery. The real lever is a **forward-executable** cipher-
> discovery CoT, length permitting.

## 4. Why SFT plateaus + why standard RL fails here (binary failure modes)
- **SFT ceiling = 0.86, proven by 6 independent experiments** (more data, new category, model-CoT, hparams,
  more training, category focus — all matched or regressed V2). SFT's cross-entropy only says "make this output
  more likely", never "make that wrong output less likely" → wrong reasoning paths stay probable, and adding
  categories dilutes a fragile equilibrium.
- **Binary failure phenomenon:** at temp 0.7, N=8 — **3,157 hard problems scored 0/8, ~6,343 easy scored 8/8,
  ZERO scored 1–7/8.** No "boundary" problems exist.
  - **STaR** yield = **0%** (nothing correct to filter on hard problems).
  - **GRPO** advantage = **0** (no within-group reward variance → zero gradient). "GRPO requires a minimum
    density of boundary problems to function." *(This is the real reason RL failed — NOT a missing dense
    per-bit reward; my earlier reconstruction was wrong.)*

## 5. The DPO pipeline (the actual "beyond-SFT" attempt — still did not beat 0.86)
DPO sidesteps the binary-failure wall by using an **external oracle** (solver CoT) as *chosen* vs the model's
own *greedy failure* as *rejected* — no boundary problems needed. Design:
- **Dual-temperature generation:** greedy `temp=0, N=1` to capture the **exact eval-time failure** as the
  rejected (eval uses greedy, so this is the highest-probability wrong output) + `temp=0.7, N=8` for diversity.
- **Pairs:** outliers → chosen = solver CoT, rejected = greedy-wrong; boundary → chosen = model's shortest
  correct (none existed); inliers skipped. ~2,000–2,500 pairs.
- **Loss:** length-normalized DPO margin + **SFT-mixing on the easy cats** (cipher/gravity/numeral/unit) to
  prevent forgetting; **reference model = same base with LoRA disabled** (toggle → saves ~60 GB VRAM).
- **Result:** V12 (audit-fix dataset) / V13 (V12 + consistency regen) **plateaued at 0.84–0.86** — the SFT
  ceiling held even under improved data integrity.

## 6. Weight averaging FAILS on Mamba-2 (tension with our INS-004)
"**First documented evidence that Model Soup fails on hybrid SSM architectures.**" The Mamba-2 SSM parameters
(A, B, C, D recurrence matrices) encode **temporal dynamics**; naive averaging across checkpoints destroys
them. *(V9 merge of V8d+V8e gave only a small gain at lower scores.)*

> ⚠️ **Tension with our INS-004** (we got **0.85→0.86 from an SVD model-soup** of v14+c1+b1). Reconciliation
> hypotheses (to verify): (a) our soup averaged **LoRA *deltas* on a frozen base** + an **SVD rank-cap**, NOT
> the full SSM recurrence matrices, so the SSM dynamics were less perturbed; (b) it was a same-basin, low-weight
> (0.4/0.3/0.3) merge of *comparable* members and the gain was small (+0.01, within ±0.04 eval variance). Our
> soup may be a narrower, gentler operation than the full-weight averaging he found toxic — **worth an explicit
> SSM-vs-LoRA-delta merge ablation** before over-trusting either claim.

## 7. The rank gain = a SELECTION HEDGE, not a score jump
Final picks: **V2 original (primary) + V8 ckpt-400 (structural hedge)**. Under a **bimodal failure regime**
where the **public set (n≈250) is not predictive of private**, the hedge carried the private draw and gained
**+112 positions / +397 ranks** vs the same-researcher **unhedged V2×2** counterfactual. *(Strong
selection-discipline evidence — = our INS-005/INS-007 and LB25's "0.872 was 4/15 / could've won solo gold".)*

## 8. Infra / process (brief)
Min viable GPU = **95.6 GB VRAM, sm_90+** (RTX PRO 6000 Blackwell / H200); Kaggle T4×2 and Colab A100-40GB
**fail** (7 failure modes / OOM). ~**335 GPU-h, ~$2,000** (Vast.ai + Colab Pro+; GCP quota was denied).
vLLM-generation and HF-training run as **separate processes** (never share GPU mem) to fit N=8×7680 in 95.6 GB.
Notebooks authored/debugged **with Claude Code**.

## 9. Citations
- **writeup (full): `temp/LB80.pdf`** (render of the Kaggle writeup; primary source for all sections above).
- companion notebook / dataset (Kaggle, JS-gated) — `mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b`,
  `mspawar/nemotron-cot-training-data-v2v12v13`.
- builds on `tonghuikang/nemotron` (deterministic-solver methodology); NVIDIA Nemotron-3-Nano report arXiv 2512.20848.
- our scores/recipe + EQ-0/EQ-2′ — `tracking.md`, `submissions.md`, `equation-frontier.md §8`, `insights.md` (own work).
