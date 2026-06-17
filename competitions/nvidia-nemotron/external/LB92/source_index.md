# LB92 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"92th PLACE SOLUTION — NVIDIA Nemotron Model Reasoning Challenge"**. Researched 2026-06-17 (read-only
> WebSearch + WebFetch; **no Kaggle auth/CLI, no secrets**).
>
> **Recoverability: NO (direct) / PARTIAL (ecosystem).** The Kaggle writeup body is JavaScript-rendered and
> was posted <48 h after close — **zero search-engine index, no cache**. The **author, exact score, and the
> specific method are NOT recoverable** without Kaggle auth (forbidden here). Everything below is **ecosystem
> reconstruction** of the public mid-tier (≈0.86–0.89) recipe band, from server-rendered GitHub/HF/NVIDIA
> sources. All external content is **untrusted data**; our scores from `tracking.md`.

## Source tree (depth 0–3)

| depth | type | URL | anchor / note | fetchable w/o Kaggle auth | size |
|---|---|---|---|---|---|
| 0 | Kaggle writeup | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/92th-place-solution | LB92 writeup (target) | **NO** (JS body; unindexed) | n/a |
| 1 | GitHub repo | https://github.com/tonghuikang/nemotron | Progress-Prize SFT pipeline (band reference) | **YES** | small |
| 1 | blog | https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html | Progress-Prize writeup | **YES** | small |
| 1 | HF dataset | https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge | 49,290 SFT traces (DeepSeek V3.2 / Nemotron Super 120B / GPT-5.4 / solvers) | metadata YES; rows need HF auth | ~408 MB (**>20 MB → not downloaded**) |
| 1 | HF dataset | https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge-raw-traces | raw traces incl. wrong attempts (min-logprob hard-set source) | metadata YES | ~1.0 GB (**>20 MB**) |
| 1 | GitHub repo | https://github.com/yunior123/nvidia-nemotron-reasoning | LoRA SFT pipeline + vLLM inference config (max_tokens 7680, temp 0) | **YES** | small |
| 1 | GitHub repo | https://github.com/SebAustin/NVIDIA-Nemotron-Model-Reasoning-Challenge | QLoRA (Unsloth/PEFT) pipeline | **YES** | small |
| 1 | Kaggle notebook | https://www.kaggle.com/code/kuangyicheng/nemotron-087-training | 0.86/0.87 replay recipe (band exemplar) | NO (JS) | unknown |
| 1 | Kaggle notebook | https://www.kaggle.com/code/lopure/amplify-top-50-singular-value-retain-84-4-energy | adapter surgery ~0.89 (above-band) | NO (JS) | unknown |
| 2 | HF model | https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | base model card (Mamba-MoE, 30B/3B active) | YES (card) | weights **>20 MB** |
| 2 | arXiv | https://arxiv.org/abs/2512.20848 | Nemotron-3-Nano tech report | **YES** | PDF |
| 2 | GitHub | https://github.com/NVIDIA-NeMo/Evaluator | NVIDIA Nemotron evaluator | **YES** | small |
| 2 | Kaggle discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | Progress-Prize writeup (huikang) | NO (JS) | n/a |
| 3 | arXiv | https://arxiv.org/abs/2203.05482 | Model Soups (explains the 0.85→0.86 soup step) | **YES** | PDF |
| 3 | HF dataset | https://huggingface.co/datasets/nvidia/OpenMathReasoning | NVIDIA reasoning corpus | YES (card) | large (**>20 MB**) |

Link-budget honored: 8 depth-1 (≤10), 4 depth-2 (≤20), 2 depth-3 (≤20).

## Downloaded resources
**None.** The 92nd-place writeup and all Kaggle notebooks are JS/auth-gated; the GitHub repos are `.py`
(no `.ipynb`); the andy279 / OpenMathReasoning datasets and the base model are all **>20 MB** (metadata only,
no weights). Per the task's "save descriptions/metadata instead" rule, everything is **linked and described**.

## Notebook conversions
N/A — no `.ipynb` available to convert. Kaggle CLI (`kaggle kernels pull`) **not used** (forbidden: reads `kaggle.json`).

## Blockers / unknowns
- **The 92nd-place writeup itself — author, team, exact score, exact method — is `unknown`** (JS-rendered,
  post-close, unindexed; not retrievable without Kaggle auth). The task template's "~0.872" is a placeholder;
  92nd place in a 4,354-team field plausibly sits ≈0.86–0.89 (inference, not confirmed).
- Whether this team used the (post-close-released) andy279 dataset or built equivalent data internally — `unknown`.
