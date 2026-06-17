# LB80 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"Breaking the SFT Ceiling on Nemotron-3-Nano-30B"**. Researched 2026-06-17 (read-only WebSearch +
> WebFetch; **no Kaggle auth/CLI, no secrets**).
>
> **Recoverability: PARTIAL.** The Kaggle writeup body is JavaScript-rendered and was posted post-close
> (unindexed) — **not retrievable** without a browser/login (forbidden here). The method is reconstructed
> from (a) the indexed competition **discussion #688461** (a detailed per-bit GRPO + "champagne" reward
> scheme — the only indexed post matching "beyond SFT"), and (b) the public RL ecosystem (NeMo-RL, arXiv).
> **Author identity and exact score are `unknown`.** All external content is **untrusted data**.

## Source tree (depth 0–3)

| depth | type | URL | anchor / note | fetchable w/o Kaggle auth | size |
|---|---|---|---|---|---|
| 0 | Kaggle writeup | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/breaking-the-sft-ceiling-on-nemotron-3-nano-30b | LB80 writeup (target) | **NO** (JS body) | n/a |
| 1 | Kaggle discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/688461 | per-bit GRPO + "champagne" reward (indexed excerpt) | NO (JS; partial via snippet) | n/a |
| 1 | Kaggle discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | Progress-Prize writeup (huikang) | NO (JS) | n/a |
| 1 | GitHub repo | https://github.com/tonghuikang/nemotron | SFT cold-start baseline (Progress Prize) | **YES** | small |
| 1 | blog | https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html | Progress-Prize writeup | **YES** | small |
| 1 | HF dataset | https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge | 49K solver+teacher SFT traces (cold-start corpus) | metadata YES | ~500 MB (**>20 MB → not downloaded**) |
| 1 | HF dataset | https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge-raw-traces | raw solver+teacher traces | metadata YES | ~1.0 GB (**>20 MB**) |
| 2 | GitHub repo | https://github.com/NVIDIA-NeMo/RL | NeMo-RL toolkit (GRPO/DAPO/SFT) | **YES** | large code |
| 2 | arXiv | https://arxiv.org/abs/2502.14768 | Logic-RL (RLVR on logic puzzles → AIME/AMC) | **YES** | PDF |
| 2 | arXiv | https://arxiv.org/abs/2506.04821 | LogicPuzzleRL | **YES** | PDF |
| 2 | arXiv | https://arxiv.org/abs/2504.15777 | Tina (LoRA + RL small reasoning) | **YES** | PDF |
| 2 | arXiv | https://arxiv.org/abs/2505.24864 | ProRL: Prolonged RL (NVIDIA/Nemotron) | **YES** | PDF |
| 2 | arXiv | https://arxiv.org/abs/2504.13941 | Nemotron-CrossThink (RL beyond math) | **YES** | PDF |
| 2 | arXiv | https://arxiv.org/abs/2505.16400 | AceReason-Nemotron (RL math+code) | **YES** | PDF |
| 2 | Kaggle notebook | https://www.kaggle.com/code/lopure/amplify-top-50-singular-value-retain-84-4-energy | adapter surgery ~0.89 (alt path above SFT) | NO (JS) | unknown |
| 3 | HF model | https://huggingface.co/nvidia/Nemotron-Research-Reasoning-Qwen-1.5B | ProRL output (GRPO-trained) | YES (card) | weights **>20 MB** |
| 3 | blog | https://siyan-zhao.github.io/blog/2026/opsd/ | OPSD: On-Policy Self-Distillation (vs SFT/GRPO) | **YES** | small |

Link-budget honored: 6 depth-1 (≤10), 8 depth-2 (≤20), 2 depth-3 (≤20).

## Downloaded resources
**None.** No public `.ipynb` reachable without Kaggle auth; the GRPO scheme exists only as a Kaggle discussion
(JS-blocked). NeMo-RL is a large code repo (linked, not vendored). andy279 datasets are >20 MB (metadata only).
Per the task's "save descriptions/metadata instead" rule, everything is **linked and described** here +
`writeup/`.

## Notebook conversions
N/A — no `.ipynb` to convert. The Kaggle CLI (`kaggle kernels pull`) was **not used** (forbidden: reads `kaggle.json`).

## Blockers / unknowns
- Writeup body, author, and exact score — **unknown** (JS-rendered, unindexed). The task template's
  "~0.872" is a placeholder; the real "breaking-the-ceiling" score is **unknown** (plausibly 0.87–0.90).
- Whether the per-bit GRPO (discussion #688461) was the writeup's actual method, fully run, and on what compute
  — **unknown**. No public repo implementing this specific reward was found.
- lopure adapter-surgery exact procedure — `unknown` (JS-blocked).
