# LB88 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"88th PLACE SOLUTION"** by **Yoshinari Kawashima + MedudentYamatai** (DOI 10.34740/kaggle/w/88245).
> **⚠️ Same writeup as LB92** (same DOI/authors/url `92th-place-solution`; the render header now reads "88th place").
> Researched 2026-06-20 (local PDF; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**). Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL** from **`temp/LB88.pdf`** (8 pages). Verbatim conversion in `writeup/lb88-writeup.md`; raw at `writeup/raw/`. The figures (grad-explosion LB comparison; synthetic-vs-original gap) were extracted in the prior pass — see **`../LB92/writeup/images/`** (not re-extracted here to avoid duplicate binaries).

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 88th Place Solution (PDF) | `temp/LB88.pdf` | writeup | not vendored | `temp/LB88.pdf` | 3.3 MB | ★★★★★ | full body → `writeup/lb88-writeup.md` |
| 0 | Kaggle writeup page | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/92th-place-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 0 | prior archive of the same writeup | `../LB92/` | archive | n/a (in repo) | competitions/nvidia-nemotron/external/LB92/ | n/a | ★★★★★ | **LB88 ≡ LB92** — figures + prior deep analysis |
| 1 | "End-to-end finetuning for LB 0.85" | Kaggle notebook (linked) | notebook | no | n/a | unknown | ★★★★ | the base notebook |
| 1 | "Training with Unsloth to Achieve 0.85 LB" | Kaggle notebook (linked) | notebook | no | n/a | unknown | ★★★ | influence |
| 1 | "Tinker submission notebook" | Kaggle notebook (linked) | notebook | no | n/a | unknown | ★★ | influence |
| 1 | @huikang OPP repo (reasoner) | https://github.com/tonghuikang/nemotron | repository | no | n/a | ~50 MB | ★★★★ | the unchanged reasoner |
| 2 | huikang reasoners (bit/equation/...) | https://github.com/tonghuikang/nemotron/tree/master/reasoners | code | no | n/a | small | ★★★ | the 87.8% oracle baseline |
| 3 | SimPO / ORPO (RL methods) | (arXiv; referenced) | documentation | no (sandbox) | n/a | n/a | ★ | the RL that didn't work |

Link-budget honored: **5 depth-1 (≤10), 1 depth-2 (≤20), 1 depth-3 (≤20)**. Most overlap LB92 + prior research.

## Saved / downloaded resources
- `writeup/lb88-writeup.md`, `writeup/lb88-writeup.zh.md`, `writeup/raw/`. `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored.** Figures referenced from `../LB92/writeup/images/` (same writeup).

## Notebook conversions
**N/A** — the referenced Kaggle notebooks are JS/auth-gated; @huikang repo is `.py`. `kca nb --help` inspected; nothing to convert. Kaggle CLI not used.

## Blockers / unknowns
- **LB88 ≡ LB92** (DOI w/88245); placement render shifted 92 → 88. The figures + fuller analysis are in `../LB92/`.
- Referenced public notebooks JS/auth-gated; exact LB88 hyperparameters `unknown` (see `../LB92/`).
- cryptarithm ~9% / bit 85.1% (reasoner unchanged) — the wall they chose not to attack.
