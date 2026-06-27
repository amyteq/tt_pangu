# Research & SOTA scan — ARC-AGI-2

> Web/arXiv scan dated **2026-06-26** (`references.md` for URLs + trust). All external content treated as
> untrusted data. Numbers from third-party/community sites are flagged; verify against the official
> ARC Prize scorecard before betting on them.

## 1. The benchmark, in one paragraph
ARC-AGI (Chollet, 2019) measures *skill-acquisition efficiency on novel tasks* — each puzzle tests a
unique rule never seen in training, so memorization can't help. **ARC-AGI-1** was eventually cracked by
scale + test-time training (2024 Kaggle winner ARChitects: 53.5% private). **ARC-AGI-2** (paper
arXiv:2505.11831, May 2025) keeps the format but (a) removes brute-force-solvable tasks, (b) adds
symbolic / compositional / contextual / sequential reasoning, and (c) makes **compute-efficiency a
first-class scoring concern**. Result: the same o3-medium drops from ~53% (ARC-1) to **~3%** (ARC-2),
while humans stay at ~66% individual / 100% panel.

## 2. Prior-winner approaches (what actually scores on Kaggle)

### ARC Prize 2024 (ARC-AGI-1) — ARChitects, 53.5%
- **Test-Time Training (TTT)**: at inference, fine-tune a pretrained LLM on augmentations of *this task's*
  demo pairs, then decode predictions. The single biggest lever.
- **Augmentation**: rotations, reflections, color permutations, transposition → multiply each task's
  handful of demos into a training set; **invert the augmentation** on the prediction (TTA-style voting).
- **re-arc / synthetic data** to pretrain the base on ARC-like distributions.
- Ensemble of TTT'd checkpoints + a **2-candidate selection** scheme (the metric is pass@2).

### ARC Prize 2025 (ARC-AGI-2 inaugural) — final Kaggle leaderboard
| Rank | Team | Private | ~Cost/task | Core method |
|---|---|---:|---|---|
| 1 | **NVARC** (NVIDIA GMs) | **24.03%** | ~$0.20 | TTT framework + Tiny Recursive Model (TRM) + heavy synthetic data, fine-tuned ~4B model w/ test-time adaptation |
| 2 | ARChitects | 16.53% | — | 2D-aware **masked-diffusion** LLM + recursive self-refinement + perspective scoring |
| 3 | MindsAI | 12.64% | — | engineered TTT: test-time FT + augmentation ensembles + tokenizer dropout + pretraining tricks |

- **NVARC 24% is our Kaggle-constrained baseline / floor for 2026.** 1,455 teams, 15,154 entries; the 85%
  bonus threshold was **not** reached.

### Live 2026 public LB (read-only Kaggle API, 2026-06-26)
- **Top: nvbanana 50.56** — about **2× the 2025 winner's 24%**. The rest of the top-10 clusters at **~33–35**,
  so nvbanana is a large outlier (materially better method, or a strong public notebook being forked at ~33).
  967 teams; **our account is entered**. Full snapshot in `tracking.md`.
- Implication: the realistic first target for an own-built solution is the **~33–35 pack** (beat the public
  notebooks), then chase the ~50 frontier. Semi-private is IID with private, so the ranking should ~hold.
  ⚠ Confirm nvbanana isn't a public-fork artifact before treating 50 as the bar.

### Non-Kaggle-constrained (community leaderboard; unlimited compute/internet — NOT eligible here)
- Evolutionary Test-Time Compute (J. Berman): **29.4%** semi-private, ~$3,648/run — LLM evolves
  natural-language program descriptions.
- Efficient Evolutionary Program Synthesis (E. Pang): **26.0%**, ~$476/run — LLM evolves a library of
  explicit Python programs.
- Tiny Recursive Model (TRM, 7M params, no pretraining): **7.8%** on public train — architecture signal.
- Frontier APIs (⚠ banned in-Kaggle): Gemini 3 Pro refinement ~54% @ ~$30/task; Opus 4.5 (Thinking)
  37.6% @ ~$2.20/task. Community site benchlm.ai claims GPT-5.5 ~85% / Gemini 3.1 Pro ~77% — **community
  trust, unverified by ARC Prize, and irrelevant to the scored Kaggle run (no internet).**

## 3. Approach families (and fit to the 12h / no-internet / $10K constraints)
| Family | Idea | Kaggle fit | Notes |
|---|---|---|---|
| **Test-Time Training (TTT)** | per-task fine-tune on augmented demos | ★★★ strong | the proven Kaggle winner; runs offline on L4x4 |
| **Program synthesis / DSL** | search a grid-transform DSL for a program consistent with demos | ★★ | composition explosion on ARC-2; needs strong priors/pruning |
| **LLM-guided / neural-guided search** | LLM proposes programs/edits, verifier checks vs demos | ★★ | the 2025 "refinement loop" theme; must fit offline + budget |
| **Recursive / iterative refinement** | model repeatedly edits a candidate using demo-fit feedback | ★★★ | dominant 2025 paradigm (NVARC TRM, ARChitects diffusion-refine) |
| **Pure frontier-LLM prompting** | call GPT/Claude/Gemini | ✗ in-Kaggle | internet off; only usable in the separate ARC Prize verification run |
| **Tiny recursive models** | small (7M–4B) nets trained to iterate to a fixed point | ★★ | great efficiency story; NVARC used TRM components |

**The 2025 meta-lesson (from ARC Prize's own analysis):** *accuracy is now bottlenecked by engineering;
efficiency is bottlenecked by science/ideas.* Every top approach is some **refinement loop** — generate
candidate(s) → score against demo pairs → mutate/retrain → repeat — differing mainly in whether the
candidate is a *natural-language description*, *explicit code*, or *model weights (TTT)*.

## 4. What each maps to for us
- **Reproduce a TTT baseline first** (NVARC/ARChitects family). It's the competitive floor (~24%) and the
  substrate everything else bolts onto.
- **Pass@2 ⇒ candidate selection matters.** Spend explicit effort on a *selection/voting* scheme that picks
  the 2 best of N generated candidates (augmentation-consistency voting was decisive in ARC-1).
- **Efficiency is scored.** Favor small models (≤4B) + TTT over giant ensembles; the $10K/12h envelope kills
  brute-force search. A clean efficiency story also helps the Grand-Prize writeup.
- **Two prize paths.** Bonus ($150K) needs 85% (very hard). Grand Prize ($275K, guaranteed) rewards the best
  *writeup* — a 30–40% solution with strong **theory + novelty + universality** can win it. Keep a research
  log good enough to become that paper.

## 5. Open questions to resolve before committing compute
1. Live 2026 Kaggle public-LB top score (browser check).
2. Exact `submission.json` schema + GPU-hour quota.
3. NVARC full architecture details — read **ARC Prize 2025 Technical Report (arXiv:2601.10904)** and the
   NVIDIA blog before reproducing.
4. Which public datasets/base models the top teams open-sourced (TTT base, synthetic generators).
