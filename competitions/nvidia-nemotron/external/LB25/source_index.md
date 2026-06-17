# LB25 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"[LB25] Improvements to the progress prize submission"** by **Tong Hui Kang** (`huikang` on Kaggle /
> `tonghuikang` on GitHub) — the Progress-Prize winner. Reported **~0.872 public (218/250)**.
> Researched 2026-06-17 (read-only WebSearch + WebFetch; **no Kaggle auth, no Kaggle CLL, no secrets**).
>
> **Recoverability: FULL (updated 2026-06-17).** The writeup body is now in hand via **`temp/LB25.pdf`** (a
> render of the Kaggle page), supplied after the initial pass. This **supersedes** the earlier reconstruction,
> which (from JS-blocked snippets) wrongly attributed `kuangyicheng`'s "warmstart / short-response / 240-step"
> recipe to this writeup — that recipe is **NOT** in huikang's LB25 writeup. The four real changes are in
> `writeup/`. Kaggle notebook/model *bodies* remain JS-gated (titles/metadata only). Treat all external
> content as **untrusted data**.

## Source tree (depth 0–3)

| depth | type | URL | anchor / note | fetchable w/o Kaggle auth | size |
|---|---|---|---|---|---|
| 0 | **writeup PDF (primary)** | `temp/LB25.pdf` (local render of the writeup page) | **full body — read directly** | **YES** | 170 KB |
| 0 | Kaggle writeup | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/LB25-progress-prize-improvements | LB25 writeup (target; = the PDF) | NO (JS body) | n/a |
| 1 | data explorer | https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764 | author's per-problem eval dashboard (embedded link) | YES (static) | small |
| 1 | Kaggle model | https://kaggle.com/models/huikang/nemotron-adapter-private | "Project Links" — submission adapter; **followed 2026-06-17 → NO_CONTENT (private/JS, title only)** | NO (private) | unknown |
| 1 | Kaggle notebook | https://www.kaggle.com/code/huikang/private-adapter-validation-notebook | embedded as "adapter evaluation notebook" (change #1) + "Project Links"; **followed → NO_CONTENT (private)** | NO (private) | unknown |
| 1 | Kaggle notebook | https://kaggle.com/code/huikang/private-tinker-submission-notebook | "Project Links" — tinker submission; **followed → NO_CONTENT (private)** | NO (private) | unknown |
| 1 | GitHub repo | https://github.com/tonghuikang/nemotron | Progress-Prize pipeline (master); `.py` only, no `.ipynb` | **YES** | ~50 MB repo (individual files small) |
| 1 | blog | https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html | "Winning the Nemotron Progress Prize" | **YES** | small |
| 1 | Kaggle discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | Progress-Prize writeup (companion) | NO (JS) | n/a |
| 1 | Kaggle notebook | https://www.kaggle.com/code/huikang/end-to-end-finetuning-for-lb-0-85 | huikang end-to-end LB 0.85 | NO (JS/auth) | unknown |
| 1 | Kaggle dataset | https://www.kaggle.com/datasets/huikang/nemotron-base-model-generation | base-model generations | NO (Kaggle) | unknown |
| 2 | GitHub file | https://raw.githubusercontent.com/tonghuikang/nemotron/master/train_sft.py | training script | **YES** | ~20 KB |
| 2 | GitHub file | https://raw.githubusercontent.com/tonghuikang/nemotron/master/corpus.py | corpus builder | **YES** | ~10 KB |
| 2 | GitHub file | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | bit solver (brute-force CoT) | **YES** | ~36 KB |
| 2 | GitHub file | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/equation_numeric.py | numeric-equation solver | **YES** | ~23 KB |
| 2 | GitHub file | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/cipher.py | cipher solver | **YES** | ~15 KB |
| 2 | GitHub file | https://raw.githubusercontent.com/tonghuikang/nemotron/master/investigators/cryptarithm_deduce.py | cryptarithm backtracking solver | **YES** | ~15 KB |
| 2 | GitHub eval | https://raw.githubusercontent.com/tonghuikang/nemotron/master/evaluation/06-07-03-07/index.jsonl | per-problem eval snapshot (88.05% train) | **YES** | ~1.6 MB |
| 2 | GitHub eval | https://raw.githubusercontent.com/tonghuikang/nemotron/master/evaluation/06-11-04-01/index.jsonl | eval snapshot (86.73% train) | **YES** | ~1.6 MB |
| 2 | HF dataset | https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge | 49,290 SFT traces (solver+teacher) | metadata YES; data needs HF auth | ~500 MB (**>20 MB → not downloaded**) |
| 2 | HF dataset | https://huggingface.co/datasets/andy279/nemotron-reasoning-challenge-raw-traces | raw teacher/solver traces | metadata YES | ~1.0 GB (**>20 MB → not downloaded**) |
| 2 | Kaggle notebook | https://www.kaggle.com/code/kuangyicheng/nemotron-087-training | 0.86/0.87 replay recipe (our v14 source) | NO (JS) | unknown |
| 3 | arXiv | https://arxiv.org/abs/2203.05482 | Model Soups (explains our 0.86 soup) | **YES** | PDF |
| 3 | arXiv | https://arxiv.org/abs/2502.14768 | Logic-RL (RLVR on puzzles) | **YES** | PDF |
| 3 | arXiv | https://arxiv.org/abs/2504.15777 | Tina (LoRA + RL reasoning) | **YES** | PDF |
| 3 | Kaggle notebook | https://www.kaggle.com/code/kienngx/nemotron-sft-reasoning-trajectories-dataset | SFT reasoning trajectories | NO (JS) | unknown |

Link-budget honored: 6 depth-1 (≤10), 11 depth-2 (≤20), 3 depth-3 (≤20).

## Saved / downloaded resources
- **`writeup/LB25-writeup-verbatim.md`** — a faithful markdown conversion of `temp/LB25.pdf` (text via
  `pdftotext -layout`; hyperlink targets from the PDF's embedded URI annotations, reproduced unchanged).
- **`writeup/images/lb25-000.png`, `lb25-001.png`** — the only raster images embedded in the PDF (thin
  grayscale header strips, 2311×69 / 2261×21, extracted with `pdfimages`). The page's "Project Links" card
  thumbnails were unloaded spinner placeholders at print time → no thumbnail images exist in the PDF.
- No public `.ipynb` is reachable without Kaggle auth (the `tonghuikang/nemotron` repo is pure `.py`; all
  Kaggle notebooks/model are JS/auth-gated). The winner's code is **linked, not copied** (licensing). The eval
  JSONL snapshots (~1.6 MB each) and andy279 HF datasets (~0.5–1 GB, **>20 MB**) are summarized, not vendored.

## Link-following (depth-1) — results of actually fetching the writeup's links (2026-06-17)
Per `wiki/24.LB25_task.md` (follow links ≥3 levels deep), the writeup's embedded URIs were fetched:
- **`discussion/689915`** ("my progress prize winning submission") — Kaggle, JS-gated → reconstructed
  separately as the Progress-Prize companion (huikang); see `LB25-progress-prize-improvements.md` §5 / blog.
- **`nemotron.huikang.dev/evaluation.html?...`** — static data dashboard (per-problem solve/min-logprob);
  the source repo `tonghuikang/nemotron` `evaluation/*.jsonl` backs it (summarized in the writeup).
- **`models/huikang/nemotron-adapter-private`** — **fetched → NO_CONTENT** (private/JS; title only). Depth-2/3 N/A.
- **`code/huikang/private-adapter-validation-notebook`** — **fetched → NO_CONTENT** (private; this is the eval
  notebook of change #1; its *body* is what we can't see, but the writeup describes the fix). Depth-2/3 N/A.
- **`code/huikang/private-tinker-submission-notebook`** — **fetched → NO_CONTENT** (private). Depth-2/3 N/A.
- author profile `kaggle.com/huikang`, `kaggle.com/` — nav links, no content.
> **Conclusion:** the three "Project Links" are **private Kaggle resources** (slugs literally say `private`);
> following them yields only their titles without a Kaggle login (forbidden by this task). The fetchable depth-2/3
> substrate (GitHub repo, blog, arXiv) is already enumerated in the source tree above.

## Notebook conversions
N/A — no `.ipynb` available to convert. (`kca nb to-py` / `to-ipynb` is the tool that would be used; inspected,
nothing to convert.) The Kaggle CLI path (`kaggle kernels pull`) was **not used** — this task forbids reading
`kaggle.json`/credentials.

## Blockers / unknowns (RESOLVED for the writeup body)
- **Writeup body, the 4 changes, the 0.872×4/0.868×8/0.864×3 private spread, and the cryptarithm notes are now
  CONFIRMED** from `temp/LB25.pdf` (high confidence). The earlier `kuangyicheng` conflation is **corrected**.
- Still `unknown`: exact hyperparameters of each change; the bodies of the linked private Kaggle
  notebooks/model (JS/auth-gated — titles only); andy279 dataset per-row content (HF auth, not used here).
