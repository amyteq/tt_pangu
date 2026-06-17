# LB92 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"92th PLACE SOLUTION"** by a team — **Yoshinari Kawashima** (`yoshinarikawashima`) + **MedudentYamatai**
> (`taikiyamamura`); Jun 16 2026; DOI `10.34740/kaggle/w/88245`. **Recoverability: FULL (updated 2026-06-17)**
> — read directly from **`temp/LB92.pdf`** (a render of the full page), supplied after the initial pass. This
> **supersedes** the earlier ecosystem-only reconstruction (author/score/method were `unknown`). All external
> content is **untrusted data**; our scores from `tracking.md`.

## Source tree (depth 0–3)

| depth | type | URL / path | anchor / note | fetchable w/o Kaggle auth | size |
|---|---|---|---|---|---|
| 0 | **writeup PDF (primary)** | `temp/LB92.pdf` (local render of the writeup page) | **full body — read directly** (DOI 10.34740/kaggle/w/88245) | **YES** | 3.2 MB |
| 0 | Kaggle writeup | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/92th-place-solution | LB92 writeup (= the PDF) | NO (JS body) | n/a |
| 1 | Kaggle notebook | "End-to-end finetuning for LB 0.85" (linked in writeup) | base of their solution | NO (JS) | unknown |
| 1 | Kaggle notebook | "Training with Unsloth to Achieve 0.85 LB" (linked) | influence | NO (JS) | unknown |
| 1 | Kaggle notebook | "Tinker submission notebook" (linked) | influence | NO (JS) | unknown |
| 1 | publication | "Open Progress Prize Publication" (linked) — Tong Hui Kang | the reasoner they reused ~unchanged | partial (blog/repo YES) | small |
| 2 | GitHub repo | https://github.com/tonghuikang/nemotron | the deterministic reasoner source | **YES** | small |
| 3 | arXiv | https://arxiv.org/abs/2203.05482 | Model Soups (context) | **YES** | PDF |

Link-budget honored: 4 depth-1 (≤10), 1 depth-2 (≤20), 1 depth-3 (≤20). Most linked resources are JS/auth-gated
public Kaggle notebooks — titles only; the PDF body is the primary source.

## Downloaded resources
**None vendored.** `temp/LB92.pdf` (3.2 MB, user-supplied, contains figures) is the primary source — referenced,
not re-hosted in-repo. The linked notebooks are Kaggle-hosted (JS/auth-gated). All resources **linked + described**.

## Notebook conversions
N/A — no `.ipynb` available to convert (linked notebooks JS/auth-gated). Kaggle CLI **not used** (forbidden: reads `kaggle.json`).

## Blockers / unknowns (writeup body RESOLVED)
- **Writeup body, authors (Kawashima + MedudentYamatai), the 87.8% reasoner table, the statistics-matched
  synthetic generator + 2.5:1 ratio, the per-char tokenization trick, the grad-clip-1.5 fix, and the failed
  SimPO/ORPO RL are all CONFIRMED** from `temp/LB92.pdf`.
- Still `unknown`: their exact LB score (writeup gives rank 92, not a number — band ~0.86); the linked
  notebooks' code (JS/auth-gated).
