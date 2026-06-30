# Research brief — ARC-AGI-2 + prior ARC Prize winners (2026-06-26)

> Compiled by the `competition-researcher` agent for **cross-competition** strategy (the user is also
> running ARC-AGI-2). All external content treated as untrusted DATA. Kaggle pages were JS-rendered /
> login-walled; substantive facts from arcprize.org + arXiv technical reports. Sources: `references.md`.

## 1. ARC-AGI-2 competition basics

- **Goal**: 85% on the private eval (final year ARC-AGI-2 is used in an official Kaggle comp).
- **Metric**: submit **2 predictions per test input** (attempt_1, attempt_2); a task is correct if
  *either* is **pixel-perfect** (shape+color+position). Final = average over all test outputs.
  Submission file: `submission.json`.
- **Data (JSON, unchanged since AGI-1)**: each task has `train` (2–10 demo `{input, output}` pairs,
  median 3) and `test` (1–3 `{input}` to predict). Grids are list-of-lists of ints 0–9 (10 colors),
  1×1…30×30.
- **Splits**: 1,000 public train · 120 public eval · 120 semi-private (leaderboard) · 120 private (final).
  All eval sets difficulty-calibrated within ~1pp; every eval task solved by ≥ 2 independent humans.
- **Code**: Kaggle notebook, **no internet at eval**, **< 12h**, hardware 4× L4 (2025; 2026 TBA),
  Kaggle systems compute budget ≈ **$50 / 120 tasks** (~$0.42/task), cost-to-run cap **$10K**,
  agreement tolerance **±3pp** (much tighter than AGI-3's ±15pp). Open-source mandate (CC0/MIT-0).
- **Timeline**: same shell as AGI-3 — launch 2026-03-25, submissions close 2026-11-02, winners 2026-12-04.
- «⚠ 待确认» daily submission limit + team-size cap (Kaggle login needed; prior years ~2–5/day).

## 2. What changed AGI-1 → AGI-2

| Dimension | ARC-AGI-1 | ARC-AGI-2 |
|---|---|---|
| Brute-force-solvable | ~49% of private eval | intentionally minimized |
| Median human solve | near-instant for many | **2.7 min** |
| Compositional depth | single-rule common | **multi-rule, multi-step, contextual, in-context symbols** |
| Human success | 97–99% | **62%/attempt, 75%/task** (harder for humans too) |
| Frontier LLM (o3 medium) | 53% | **3%** |

**Four new reasoning patterns** in AGI-2: multi-rule (simultaneous interacting transforms),
multi-step (sequential, state-dependent), contextual (rule modulated by grid context), in-context
symbols (task-defined symbol meanings interpreted on the fly).

## 3. Scores — SOTA + humans (ARC-AGI-2)

Humans: 62%/attempt, 75%/task (no demographic predicts performance ⇒ measures general reasoning).

**Kaggle-constrained (the regime that matters for the competition):**

| Rank | Team | Score | Year | Cost/task |
|---|---|---|---|---|
| 1 | NVARC | **24.03%** | 2025 | $0.20 |
| 2 | ARChitects | 16.53% | 2025 | — |
| 3 | MindsAI | 12.64% | 2025 | — |

**Unconstrained / external leaderboards (NOT Kaggle-eligible; treat as claims):** Imbue (Gemini 3.1
Pro + code evolution) 95.1% @ $8.71/task; GPT-5.5 ~85%; Gemini 3.1 Pro ~77%; Poetiq (Gemini 3 +
meta-system) 54% @ $30.57/task (first past 50%); Opus 4.5 (thinking) 37.6% @ $2.20.
**Caveat**: external scores are self-/community-reported, not all ARC-Prize-verified; high-compute
systems (o3 High) were excluded for exceeding the $10K/task cap.

## 4. Winning techniques — the canon

### ARC Prize 2024 (ARC-AGI-1)
No static-inference solution scored > 10%. **Test-Time Training (TTT)** dominated:
- **MindsAI** 55.5% (ineligible): T5-series, pretrained on public eval + synthetic, TTT at test time.
- **ARChitects** 53.5% (1st): NeMo-Minitron-8B, TTT + data augmentation, selection by **solution
  stability under augmentations** (vote across augmented views).
- **Akyürek et al.** 47.5% (paper): 8B TTT — "The Surprising Effectiveness of Test-Time Training…".
- **Greenblatt** 42% (public): GPT-4o generates **thousands of Python programs/task**, iteratively
  debugs the best, scores vs demo pairs (LLM-guided program synthesis).
- **DSL brute-force search** lineage: icecuber 2020 (20%), Hodel DSL, da Vinci.
- **OmniARC/Barbadillo** 40% (2nd): **ensemble of transduction (TTT) + induction (program synth)** —
  key finding: each alone ~40%, only the ensemble competes at SOTA.

### ARC Prize 2025 (ARC-AGI-2)
**Refinement loops** became central — AGI-2's resistance to brute-force search killed exhaustive DSL.
- **NVARC** 24.03% @ $0.20/task (1st): 4B model + heavy **synthetic data** (BARC + Human-ARC, structured
  via Claude/GPT-4o into 5 components → ~2K structured summaries) + **TTT** + compact cost-efficient
  ensemble; no CoT/tools (Kaggle runtime). Used NVIDIA NeMo RL + NeMo Skills.
- **ARChitects** 16.53%: 2D-aware masked-diffusion LLM with recursive self-refinement.
- **MindsAI** 12.64%: TTT + TTFT + augmentation ensembles + tokenizer dropout.
- **Tiny Recursive Model (TRM)** (paper): 7M params, no pretraining, recursive latent refinement;
  ~8% AGI-2, 45% AGI-1.
- **CompressARC** (paper): 76K params, no pretraining/data; MDL / description-length minimization at
  test time, no branching search; ~20% AGI-1.
- **Imbue code evolution** (external, 95.1%): population of Python "organisms", fitness-scored,
  LLM mutation/crossover, NL explanation before code; works across model tiers.

## 5. The transferable skeleton (AGI-2 mental model)
AGI-2 is **one-shot pattern induction from demo pairs**. The winning recipe ≈
**strong small model → synthetic-data pretraining → TTT on the demo pairs (+ augments) → augmentation-
vote selection → ensemble transduction + induction → cost-efficient**. The meta-loop is
**propose candidate → verify against demo pairs → refine**.

## 6. Why this matters for AGI-3 → see `cross-competition.md`
AGI-3 has **no demo pairs**, so TTT / program synthesis / DSL search **do not transfer**. What
survives is the **refine-and-verify meta-loop**, plus RL / world-modeling / agent-architecture /
context-management — see the dedicated transfer doc.
