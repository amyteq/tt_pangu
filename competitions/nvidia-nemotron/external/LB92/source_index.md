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

## Saved resources
- **`writeup/LB92-writeup-verbatim.md`** — faithful markdown conversion of `temp/LB92.pdf` (full body via
  `pdftotext -layout`; page header/footer + `content_copy` artifacts removed; content reproduced verbatim,
  incl. the reasoner accuracy table, the three pillars, "what did not work", and the DOI/BibTeX citation).
- **`writeup/images/lb92-000.png` … `lb92-005.png`** — the **6 raster figures embedded in the PDF**
  (`pdfimages`): comp banner; the Synthetic-Data-Improvement loop diagram; the `train_loss` curve; the
  BPE-vs-per-char tokenization example; the Grad-Norm spike plot (max≈25089 @ step 107); the ORPO
  chosen/rejected rewards plot. These are real content figures (≤1.4 MB each, all <20 MB).

## Link-following + notebook download (2026-06-17)
Per `wiki/24.LB92_task.md` (follow links ≥3 levels deep + download the author's notebook when available):
- The writeup links **three public base notebooks by other authors** — "Training with Unsloth to Achieve 0.85
  LB", "End-to-end finetuning for LB 0.85", "Tinker submission notebook" — and "Open Progress Prize Publication"
  (huikang). Their **hrefs were NOT extractable** from this PDF (Chrome-print compressed/malformed annotations;
  pypdf + raw-byte grep both empty), so the **link text is reproduced verbatim** without inventing URLs. All
  are Kaggle-hosted code → JS/auth-gated (not fetchable/downloadable credential-free).
- **No distinct "author's own notebook" is published** in this writeup — the team built on the third-party
  public notebooks above; the only first-party artifact is the writeup itself (DOI `10.34740/kaggle/w/88245`,
  captured). So there is no own-notebook to download.
- The kaggle CLI is **not used** (downloading any Kaggle kernel needs `kaggle.json`, forbidden by this task's
  secret policy). The reusable techniques (per-char tokenization, grad-clip 1.5, statistics-matched synth) are
  captured in `analysis/`.

## Blockers / unknowns (writeup body RESOLVED)
- **Writeup body, authors (Kawashima + MedudentYamatai), the 87.8% reasoner table, the statistics-matched
  synthetic generator + 2.5:1 ratio, the per-char tokenization trick, the grad-clip-1.5 fix, and the failed
  SimPO/ORPO RL are all CONFIRMED** from `temp/LB92.pdf`.
- Still `unknown`: their exact LB score (writeup gives rank 92, not a number — band ~0.86); the linked
  notebooks' code + exact hrefs (JS/auth-gated; hrefs not recoverable from the PDF).

## Blockers / unknowns (writeup body RESOLVED)
- **Writeup body, authors (Kawashima + MedudentYamatai), the 87.8% reasoner table, the statistics-matched
  synthetic generator + 2.5:1 ratio, the per-char tokenization trick, the grad-clip-1.5 fix, and the failed
  SimPO/ORPO RL are all CONFIRMED** from `temp/LB92.pdf`.
- Still `unknown`: their exact LB score (writeup gives rank 92, not a number — band ~0.86); the linked
  notebooks' code (JS/auth-gated).
