# LB109 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"Heuristics for bit, cryptarithm and equations"** by **Andrey Kulakov (jex398)**. 109th place; final ~0.82.
> Researched 2026-06-20 (local PDF; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**). Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL** from **`temp/LB109.pdf`** (8 pages). Verbatim conversion in `writeup/lb109-writeup.md`; raw at `writeup/raw/`. The writeup includes diagrams (the three bit cases) embedded as images in the PDF; the textual tables are preserved. Mostly an **ideas writeup** (most heuristics unshipped).

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | Heuristics for bit, cryptarithm and equations (PDF) | `temp/LB109.pdf` | writeup | not vendored | `temp/LB109.pdf` | 436 KB | ★★★★★ | full body → `writeup/lb109-writeup.md` |
| 0 | Kaggle writeup page | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/heuristics-for-bit-cypher-and-equations | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 1 | @huikang baseline | https://github.com/tonghuikang/nemotron | repository | no | n/a | ~50 MB | ★★★ | the baseline the heuristics build on |
| 1 | "Solved Bit Manipulation" team | @adityap97 / @prateekagnihotri / @shubham068 (Kaggle handles) | discussion | no | n/a | n/a | ★★ | referenced in a comment; bit approach unknown |
| 2 | huikang bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | no | n/a | ~36 KB | ★★ | the spot-finding LB109 broadened |
| 3 | (ANF / boolean function references) | — | documentation | n/a | n/a | n/a | ★ | algebraic normal form (the bit trick); no external link given |

Link-budget honored: **2 depth-1 (≤10), 1 depth-2 (≤20), 1 depth-3 (≤20)** — the writeup is largely self-contained heuristics.

## Saved / downloaded resources
- `writeup/lb109-writeup.md`, `writeup/lb109-writeup.zh.md`, `writeup/raw/`. `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored** (PDF stays in `temp/`; diagrams referenced in-place).

## Notebook conversions
**N/A** — no public `.ipynb` linked (reasoner code unreleased). `kca nb --help` inspected; nothing to convert. Kaggle CLI not used.

## Blockers / unknowns
- **Mostly unshipped ideas** — final ~0.82 (cryptarithm overfit); equation-guess (+50) was the only leaderboard mover.
- The **ANF "another approach"** (full-function ANF matching) was never implemented; the cryptarithm brute-force compression was unfinished.
- The "Solved Bit Manipulation" team's approach is `unknown` (a comment question). Reasoner code unreleased; exact training config `unknown`.
- Diagrams (three bit cases) are images in the PDF; not extracted (non-essential; textual tables preserved).
