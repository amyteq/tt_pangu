# LB80 gap analysis — mspawar's 0.86 study vs our 0.86 (updated from the writeup PDF)

> Updated 2026-06-17 from the actual writeup (`temp/LB80.pdf`). The earlier version (per-bit GRPO from
> discussion #688461) was the **wrong author/method** — **corrected here**. External claims untrusted; our
> numbers from `tracking.md`/`equation-frontier.md`.

## The honest framing
LB80 (Mayur Pawar, 0.86, rank 80) and we (0.86 soup) **land at the same score from the same root** (both build
on Tong Hui Kang's deterministic-solver SFT). His writeup is mostly a **catalogue of what does NOT break 0.86**
(STaR, GRPO, DPO, weight-averaging) plus deep diagnoses of *why*. The gaps for us are therefore less "a lever
we missed" and more **"sharper diagnoses that redirect our equation + RL plans."**

## Side-by-side

| dimension | LB80 (mspawar) | us | gap / takeaway |
|---|---|---|---|
| base recipe | solver-CoT SFT, seq8192, all-linear LoRA r32, no gate_proj | v14 replay, seq8192, lm_head+attn+in/out_proj r32 | **parity** (independent convergence) |
| seq length | 4096→8192 = **0.46→0.77** | ctx2k 0.42 / ctx4k 0.67 → v14 0.85 | **agreement** (truncation is the big silent killer) |
| equation structure | **`A1A2 OP B1B2`, per-problem cipher; crackable 97.6% offline (answer-guided CP-SAT)** | EQ-0 "single global 5-char function"; EQ-2′ "uncrackable strong cipher" | **WE WERE MIS-FRAMED — revisit EQ-0/EQ-2′** |
| why equation still fails | **"discovery leakage"** — answer-guided CoT teaches *verify* not *discover*; 93–97% traces internally inconsistent | eq-aug = coverage-memorisation of seen pairs (also "verify", not "discover") → 0.86 | **same root cause; the fix is forward-executable discovery CoT** |
| RL | STaR 0% yield, GRPO advantage=0 (binary failure, no boundary problems) → **DPO with oracle** (still didn't beat 0.86) | never ran RL (designed binary-terminal GRPO, deferred) | **our designed GRPO would have failed too; DPO-with-oracle is the right shape** |
| merging | **"Model Soup FAILS on Mamba-2 SSM"** | **0.85→0.86 via SVD soup of LoRA deltas** | **tension — ablation needed (LoRA-delta SVD ≠ full-SSM averaging)** |
| eq_symbolic data | adding it is **actively harmful** (-0.01 to -0.04) | n/a (our equation slice was the cipher) | "not all correct data helps" (= our B8 / dilution) |
| selection | hedge V2 + V8-ckpt400 → **+397 ranks** under bimodal public↔private | INS-005/INS-007 (best + diverse hedge; surgery aged −0.02) | **strong agreement** |

## The three findings that matter most for us
1. **The equation cipher IS crackable offline (97.6%) and our EQ-0/EQ-2′ framing was wrong.** We searched for
   ONE global σ over a 5-char→1-4-char map and "proved" it uncrackable. mspawar shows the real structure is
   **`A1A2 OP B1B2`** — two 2-char operands + a 1-char operator under a **per-problem** symbol→digit bijection,
   with a finite operator family — and an **answer-guided permutation search** cracks 569/583 (the 14 failures
   genuinely have >10 distinct digit-symbols). **Action: re-run EQ-2′ with the per-problem `A op B` model + an
   answer-guided solver** (this belongs on the equation-frontier / PR #113 line, not here).
2. **"Discovery leakage" explains why our eq-aug capped at memorisation.** Answer-guided solver CoT presents
   the mapping as given (teaches *verify*), and 93–97% of such traces are internally inconsistent. At inference
   there is no answer, so the model must *discover* the mapping — which it was never taught. **The lever is a
   forward-executable, prompt-derivable cipher-discovery CoT** (show the constraint search, not the answer).
   Risk: it may exceed 8192 tokens; mspawar's step-by-step derivation scored only 0.84, but **top LB 0.90
   (rank 32) implies a working CoT formulation exists** — an open, high-value problem.
3. **Standard RL is the wrong tool here; DPO-with-oracle is the right shape.** Binary failure (0/8 or 8/8, no
   boundary) → STaR/GRPO get zero signal. Our previously-designed GRPO (binary terminal reward) would have
   failed identically. If we attempt RL post-Saturday, it must be **DPO** with solver-CoT *chosen* vs
   **greedy(temp=0) failure** *rejected* + SFT-mixing on easy cats. (Even so, mspawar did not beat 0.86 — set
   expectations.)

## Borrowable (ranked)
1. **(crack) Re-model equation as per-problem `A1A2 OP B1B2` + answer-guided solver** — corrects EQ-2′; the
   prerequisite for any real equation gain. CPU, free. *(→ feed back into PR #113 equation-frontier.)*
2. **Forward-executable cipher-discovery CoT** (the discovery-leakage fix) — the genuine path past eq-aug
   memorisation; length-budget permitting.
3. **DPO-with-oracle** (greedy-failure rejected, solver-CoT chosen, SFT-mix on easy cats, LoRA-toggle ref) —
   the correct RL shape for the binary-failure regime (replaces the dead dense-GRPO idea).
4. **Exclude `gate_proj` from LoRA** (avoid MoE expert collapse) — a free correctness check on our target set.
5. **Selection hedge discipline** — best + a diverse hedge; never two near-duplicates (already INS-005/007).

## Tension to resolve (don't over-trust either side)
- **"Model Soup fails on Mamba-2" vs our +0.01 SVD soup.** Likely reconciled by *what* is averaged (he:
  full SSM A/B/C/D recurrence; us: LoRA *deltas* on a frozen base + SVD rank-cap, small same-basin gain). **Run
  an explicit ablation** (LoRA-delta SVD merge vs full-weight averaging) before generalizing.

## NOT a gap
- Score paradigm — we're at the same 0.86 from the same root. The differences are diagnostic depth + the
  (still-open) discovery-CoT lever, not a missed SFT trick.
