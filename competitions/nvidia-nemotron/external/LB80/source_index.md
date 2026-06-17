# LB80 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"Breaking the SFT Ceiling on Nemotron-3-Nano-30B"** by **Mayur Pawar** (`mspawar`), 80th/4190 (top 1.91%),
> final private **0.86**. **Recoverability: FULL (updated 2026-06-17)** — read directly from **`temp/LB80.pdf`**
> (a render of the full 15-section page), supplied after the initial pass. This **supersedes** the earlier
> reconstruction, which (from JS-blocked discussion #688461) wrongly attributed a *different* author's per-bit
> GRPO scheme to this writeup. All external content is **untrusted data**; our scores from `tracking.md`.

## Source tree (depth 0–3)

| depth | type | URL / path | anchor / note | fetchable w/o Kaggle auth | size |
|---|---|---|---|---|---|
| 0 | **writeup PDF (primary)** | `temp/LB80.pdf` (local render of the writeup page) | **full 15-section body — read directly** | **YES** | 544 KB |
| 0 | Kaggle writeup | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/breaking-the-sft-ceiling-on-nemotron-3-nano-30b | LB80 writeup (= the PDF) | NO (JS body) | n/a |
| 1 | Kaggle notebook | https://www.kaggle.com/code/mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b | companion notebook; **followed 2026-06-17 → NO_CONTENT** (JS body, title only) | NO (JS) | unknown |
| 1 | Kaggle dataset | https://www.kaggle.com/datasets/mspawar/nemotron-cot-training-data-v2v12v13 | author's training data (V2/V12/V13); **followed → NO_CONTENT** | NO (Kaggle) | unknown |
| 1 | GitHub repo | https://github.com/tonghuikang/nemotron | deterministic-solver methodology the 0.86 V2 baseline builds on | **YES** | small |
| 1 | arXiv | https://arxiv.org/abs/2512.20848 | NVIDIA Nemotron-3-Nano report (cited for the SFT→GRPO→DPO→RLHF recipe) | **YES** | PDF |
| 2 | GitHub repo | https://github.com/NVIDIA-NeMo/RL | NeMo-RL toolkit (GRPO/DPO context) | **YES** | large code |
| 2 | arXiv | https://arxiv.org/abs/2502.14768 | Logic-RL (RLVR context) | **YES** | PDF |
| 3 | arXiv | https://arxiv.org/abs/2203.05482 | Model Soups (contrast: he reports it FAILS on Mamba-2 SSM) | **YES** | PDF |

Link-budget honored: 4 depth-1 (≤10), 2 depth-2 (≤20), 1 depth-3 (≤20). (Most resources cited in the writeup
are the author's own private Kaggle notebooks/datasets — JS/auth-gated; the PDF body is the primary source.)

## Saved resources
- **`writeup/LB80-writeup-verbatim.md`** — a faithful markdown conversion of `temp/LB80.pdf` (full 39-page /
  15-section body via `pdftotext -layout`; repeated page header/footer + `content_copy` artifacts removed,
  page margin dedented; content + the inline URLs reproduced verbatim, incl. the source writeup link, the
  companion notebook `code/mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b`, and the dataset
  `datasets/mspawar/nemotron-cot-training-data-v2v12v13`).
- **`writeup/images/lb80-000.png` (240×240 comp banner), `lb80-001.png` (120×120 icon)** — the only raster
  images embedded in the PDF (`pdfimages`). The in-page figures (training-pipeline flowcharts, train_loss /
  grad-norm / ORPO-rewards plots, BPE example) are **vector-rendered → not raster-extractable**; described
  inline in `LB80-progress-prize-improvements.md`.

## Link-following + notebook download (2026-06-17)
Per `wiki/24.LB80_task.md` (follow links ≥3 levels deep + download the author's notebook when available):
- **Companion notebook** `code/mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b` — **fetched → NO_CONTENT**
  (JavaScript-rendered; only the title without a Kaggle login). **Could not be downloaded credential-free.**
- **Dataset** `datasets/mspawar/nemotron-cot-training-data-v2v12v13` — **fetched → NO_CONTENT** (JS; likely
  >20 MB regardless → would be metadata-only).
- Depth-2/3 fetchable substrate (`tonghuikang/nemotron`, `NVIDIA-NeMo/RL`, arXiv) is in the source tree above.
- **Notebook download is blocked under this task's secret policy** (downloading a Kaggle kernel needs the
  `kaggle` CLI, which reads `kaggle.json`; the task forbids that). Exact command for a human to run if the
  no-`kaggle.json` constraint is lifted:
  ```
  kaggle kernels pull mspawar/breaking-the-sft-ceiling-on-nemotron-3-nano-30b -p competitions/nvidia-nemotron/external/LB80/writeup/notebook
  python tools/kca/kca.py nb to-py competitions/nvidia-nemotron/external/LB80/writeup/notebook/*.ipynb   # then add the attribution header
  ```

## Blockers / unknowns (writeup body RESOLVED)
- **Writeup body, the 0.86 score, the 30+-experiment table, the equation structure, discovery-leakage finding,
  DPO design, Mamba-merge-fails claim, and the selection-hedge story are all CONFIRMED** from `temp/LB80.pdf`.
- Still `unknown`: the companion notebook's code + dataset contents (JS/auth-gated; download needs `kaggle.json`,
  forbidden here); whether the "Model Soup fails on Mamba-2" claim generalizes to our LoRA-delta SVD soup.

## Blockers / unknowns (writeup body RESOLVED)
- **Writeup body, the 0.86 score, the 30+-experiment table, the equation structure, discovery-leakage finding,
  DPO design, Mamba-merge-fails claim, and the selection-hedge story are all CONFIRMED** from `temp/LB80.pdf`.
- Still `unknown`: the companion notebook's exact code + the author's dataset contents (JS/auth-gated — titles
  only); whether his "Model Soup fails on Mamba-2" claim generalizes to our LoRA-delta SVD soup (open ablation).
