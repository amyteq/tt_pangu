# LB13 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"13th Place Solution"** by **Haraguchi-T (haraguchit)**. (No final LB number given; teacher oracle 87.7% → 89.4%.)
> Researched 2026-06-20 (local PDF + read-only WebSearch; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**).
> Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL.** Recovered from **`temp/LB13.pdf`** (8 pages). Verbatim conversion in `writeup/lb13-writeup.md`; raw at `writeup/raw/lb13-pdftotext-layout.txt`. The live Kaggle page and the referenced notebooks (@konbu17, @dgxchen) are **JS/auth-gated**.

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 13th Place Solution (PDF) | `temp/LB13.pdf` | writeup | not vendored (precedent) | `temp/LB13.pdf` | 214 KB | ★★★★★ | full body → `writeup/lb13-writeup.md` |
| 0 | Kaggle writeup page | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/13th-place-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 1 | @huikang OPP repo (reasoner foundation) | https://github.com/tonghuikang/nemotron | repository | no (linked, not copied) | n/a | ~50 MB | ★★★★ | reasoners LB13 improved (bit 3-input, equation structure) |
| 1 | @konbu17 SFT notebook (original) | Kaggle (handle `konbu17`) | notebook | no | n/a | unknown | ★★★ | JS/auth-gated; LB13's SFT base |
| 1 | @dgxchen SFT notebook (improved) | Kaggle (handle `dgxchen`) | notebook | no | n/a | unknown | ★★★ | JS/auth-gated; LB13 adapted this |
| 1 | Unsloth | https://github.com/unslothai/unsloth | repository | no | n/a | n/a | ★★ | training framework |
| 2 | huikang equation_numeric solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/equation_numeric.py | code | no | n/a | ~23 KB | ★★★ | OPP baseline LB13 redesigned (category exclusivity + reversal symmetry) |
| 2 | huikang bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | no | n/a | ~36 KB | ★★★ | OPP baseline LB13 extended (3-input MAJ/XNOR verification) |
| 3 | Model Soups (Wortsman et al.) | https://arxiv.org/abs/2203.05482 | documentation | no | n/a | PDF | ★ | context (LB13 used multi-stage SFT, not merge) |

Link-budget honored: **5 depth-1 (≤10), 2 depth-2 (≤20), 1 depth-3 (≤20)**. See `links/depth0-3.md`. huikang substrate overlaps prior research; new for LB13: @konbu17 / @dgxchen notebooks (JS/auth-gated).

## Saved / downloaded resources
- `writeup/lb13-writeup.md`, `writeup/lb13-writeup.zh.md`, `writeup/raw/` (provenance).
- `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored** (PDF stays in `temp/`). @huikang code linked not copied.

## Notebook conversions
**N/A** — @konbu17 / @dgxchen Kaggle notebooks are JS/auth-gated; @huikang repo is `.py`. `kca nb --help` inspected; nothing to convert. Kaggle CLI not used.

## Link-following results (2026-06-20)
- **huikang repo + raw equation/bit solvers** — fetched OK in prior research; LB13's equation structural redesign (category exclusivity + reversal symmetry) and bit 3-input verification are LB13's additions.
- **@konbu17 / @dgxchen SFT notebooks** — JS/auth-gated (handles only); LB13's 3-stage decreasing-LR schedule is described in the prose.
- arXiv (Model Soups) for context; not fetchable from sandbox.

## Blockers / unknowns
- **No final LB number** in the writeup (only teacher oracle 87.7%→89.4%); 13th private.
- Reasoner code unreleased; oracle numbers (equation_deduce 95.3%, guess 50.7%, bit 89.7%) taken from the prose as sanity checks.
- `konbu17`/`dgxchen` notebook bodies JS/auth-gated.
- cryptarithm is **only ~10%** — the top-end lever LB13 lacks (vs LB1/LB3).
