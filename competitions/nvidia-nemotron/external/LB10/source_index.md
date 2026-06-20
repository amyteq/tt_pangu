# LB10 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"10th Place Solution"** by **Rick (rikitomo0526), neilus, eikichi**. **Public 0.860 / Private 0.880.**
> Researched 2026-06-20 (local PDF + read-only WebSearch; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**).
> Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL.** Recovered from **`temp/LB10.pdf`** (12 pages). Verbatim conversion in `writeup/lb10-writeup.md`; raw at `writeup/raw/lb10-pdftotext-layout.txt`. The writeup is **largely self-contained** (no attachment links in the body; the reasoner code is not publicly linked). The live Kaggle page is JS-gated.

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 10th Place Solution (PDF) | `temp/LB10.pdf` | writeup | not vendored (precedent) | `temp/LB10.pdf` | 215 KB | ★★★★★ | full body → `writeup/lb10-writeup.md` |
| 0 | Kaggle writeup page | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/10th-place-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 1 | Base model (Nemotron-3-Nano-30B-A3B-BF16) | https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 | model | no | n/a | ≫20 MB | ★★★ | the single base model (30B MoE, ~3B active) |
| 1 | Competition page | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge | documentation | no | n/a | n/a | ★★ | task / grader context |
| 2 | @huikang OPP repo (implied baseline) | https://github.com/tonghuikang/nemotron | repository | no (linked, not copied) | n/a | ~50 MB | ★★ | the common deterministic-reasoner baseline (LB10 rewrote bit + equation) |
| 3 | Model Soups (Wortsman et al.) | https://arxiv.org/abs/2203.05482 | documentation | no | n/a | PDF | ★ | context for LB10's FAILED merge / seed-soup result |

Link-budget honored: **2 depth-1 (≤10), 1 depth-2 (≤20), 1 depth-3 (≤20)** — the writeup is unusually self-contained, so few external links exist to follow. See `links/depth0-3.md`.

## Saved / downloaded resources
- `writeup/lb10-writeup.md`, `writeup/lb10-writeup.zh.md`, `writeup/raw/` (provenance).
- `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored** (PDF stays in `temp/`).

## Notebook conversions
**N/A** — no public `.ipynb` linked (reasoner code unreleased). `kca nb --help` inspected; nothing to convert. Kaggle CLI not used.

## Link-following results (2026-06-20)
- The writeup body contains **no attachment/code links** — it is self-contained prose + tables (all preserved).
- **Base model HF page** and **competition page** are the only depth-1 references; the **@huikang OPP repo** is the implied baseline (fetched in prior research) that LB10's bit (key-table) and equation (candidate-ordering) reasoners replaced/improved.
- arXiv (Model Soups) referenced for context of LB10's failed merge; not fetchable from sandbox.

## Blockers / unknowns
- Reasoner **code is unreleased**; oracle/coverage numbers (bit 98.75%, equation_deduce 93.1%, etc.) are taken from the prose as reproduction sanity checks.
- `unknown`: exact compute/runtime; whether the base was loaded with a specific trainer (huikang-style implied but not stated).
- LB10's cryptarithm is **only ~9%** (add/sub/mul traces too jumpy to learn) — the top-end lever it lacks vs LB1/LB3.
