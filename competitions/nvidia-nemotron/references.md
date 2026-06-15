# References — nemo

> Each: title / URL or relative path / one-line note / relevance.

## Kaggle
- Competition page — https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge — Overview/Data/Code/Discussion — high.
- Base model `metric/nemotron-3-nano-30b-a3b-bf16` (Nemotron-3-Nano-30B-A3B, Mamba+MoE) — adapter base — high.

## Discussions
- Forum consensus: cryptarithm is the 0.86→0.89 lever (but single-category ≠ total) — issue #86 T11 / comment 4 — high.

## Notebooks / kernels (ours)
- `kernels/nemotron-lora-baseline.py` — LoRA SFT baseline (v5–v9) — high.
- `kernels/` (`firefly2006/nemo-rule4k-v10`) — rule-CoT, LB 0.59 — high.
- `kernels/` (`harrysun2006/nemo-replay-v14`) — replay recipe, **LB 0.85** — high.
- `kernels/` (`harrysun2006/nemo-synth-v15`) — cryptarithm synth, LB 0.84 — high.
- `kernels/` (`harrysun2006/nemo-merge-t7`) — SVD merge, LB 0.82 — medium.
- `lib/nemo_synth_gen.py`, `lib/svd_merge.py` — generators/tools — medium.

## Public notebooks / repos (external, attributed)
- `kuangyicheng/nemotron-087-training` — public 0.86/0.87 replay recipe (T10 source) — high.
- `tonghuikang/nemotron` (https://github.com/tonghuikang/nemotron · https://nemotron.huikang.dev) — Progress-Prize pipeline; per-problem rule-survey; hard-val source — high.
- `lopure/amplify-top-50-singular-value-retain-84-4-energy` — top-0.89 adapter surgery + embedded official metric + min-logprob hard set (T12 source) — high.
- `varianceofx/synthetic-dataset-generator-27k` — 10-category deterministic generator + CoT; finality line; unseen-symbol generalization (T11 reference) — high.

## Papers / arXiv (literature scan 2026-06-15; see `research.md` for how each maps to our results)
- **Model Soups** (Wortsman et al., arXiv 2203.05482) — averaging same-base fine-tunes beats the best individual — **directly explains our 0.86 soup (v14+c1+b1)** — high.
- **LoRA Soups / AdapterSoup** — weight-averaging / weighted-concatenation of LoRA adapters for skill composition + cross-domain generalization — high (validates merging only same-base members).
- **Logic-RL** (arXiv 2502.14768) — rule-based RL (RLVR) on ~5K synthetic logic puzzles → generalizes to AIME/AMC — **closest analogue to our hidden-rule task** — high (GRPO design input).
- **LogicPuzzleRL** (arXiv 2506.04821) — RL on logic puzzles cultivates transferable reasoning routines — high.
- **Tina: Tiny Reasoning Models via LoRA** (arXiv 2504.15777) — small reasoning models via LoRA + RL; directly relevant to a rank-32 LoRA + RL plan — high.
- **STaR / ReST / RFT (Rejection-sampling Fine-Tuning)** — sample → filter-by-correctness → SFT; the v11 design basis — high.
- **SD-Zero** (arXiv 2604.12002), **HDPO** (2603.23871) — newer self-distillation variants reported to beat RFT/GRPO; candidates for post-comp — medium.
- The State of RL for LLM Reasoning (Raschka) — survey: GRPO vs STaR/ReST tradeoffs — medium.
- `work/00.nemotron_3_versions.zip` — 3 ChatGPT scripts (inputs to v5/v10/T7) — medium.

## Internal notes
- `work/00.nemo.md` — ChatGPT competition analysis (zh): essence, data findings, 6 challenges, ideas A–F, techniques — high. (See `notes_zh.md` for an English digest.)
- `kernels/README.md` — recipe, gotchas, 0.47→0.61→0.65 progression — high.
- `docs/tooling/kaggle-kernel-ops.md` — kernel/version model, flat structure, concurrency/quota — medium.

## Worklogs
- `worklogs/nemo.md`, `worklogs/nemo2.md` — Chinese strategy hub mirror (three tables) + history — high.

## Issues / PRs / commits
- GitHub issue **#86** — strategy & tracking hub (body + 5 comments; Chinese) — high. (Historical; future updates here.)
- Sibling hub: issue **#87** (Orbit Wars).
- Decision issues (open): **#83** (external GPU), **#85** (per-comp YAML + user-pool), **#21** (multi-account quota pool).
- Known-gotcha issues (open): **#77** (kernel push ≠ LB submit), **#78** (`kca competition refresh-rules` broken on kaggle 2.0.x).
- PRs (merged): **#90** (v10 + v14 kernels + ruff pin), **#94** (T7 SVD merge), **#95** (v15 synth), **#81/#82/#84/#75** (tooling: kca kaggle submit, push lint gate, kernel/version model, input mount path).
