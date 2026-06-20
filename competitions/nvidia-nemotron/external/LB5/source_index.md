# LB5 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"Jack of Trades, Loser of Cryptarithm" — 5th Place Solution** by Darren Amadeus Martin, Alwin Theodoric,
> Muhammad Yassir Ramadhan, Billy Anggara, Rinnnn_t. Reported **Private LB 0.900** (best, unselected; chosen 0.896).
> Researched 2026-06-20 (local PDF + read-only WebSearch; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**).
> Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL.** Recovered from **`temp/LB5.pdf`** (24 pages; authored render of the Kaggle writeup page). Verbatim conversion in `writeup/lb5-writeup.md`; raw `pdftotext -layout` at `writeup/raw/lb5-pdftotext-layout.txt`. The live Kaggle writeup page, the linked master notebook, the final-model dataset, and the referenced Kaggle discussions are **JS/auth-gated**. The writeup contains a full reference list with arXiv URLs (preserved).

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 5th Place Solution (PDF, primary) | `temp/LB5.pdf` | writeup | not vendored (LB25/80/92/LB1/LB3 precedent) | `temp/LB5.pdf` | 309 KB | ★★★★★ | full body → `writeup/lb5-writeup.md` |
| 0 | 5th Place Solution (Kaggle page) | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/domdolus-tolus-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 1 | @huikang — Open Progress Prize repo + trainer notebook | https://github.com/tonghuikang/nemotron | repository | no (linked, not copied) | n/a | ~50 MB | ★★★★★ | CoT generator + byte-level bit approach + training loop LB5 modified |
| 1 | @huikang — progress-prize discussion | https://www.kaggle.com/.../discussion/689915 | discussion | no | n/a | n/a | ★★★ | JS-gated |
| 1 | @donaldgalliano — per-bit 100%-solve post | https://www.kaggle.com/.../discussion (JS-gated) | discussion | no | n/a | n/a | ★★★ | per-bit (bit-level) claim LB5 **rejected** as not generator-intended |
| 1 | @citerne — Kaggle CLI tutorial | https://www.kaggle.com/.../discussion (JS-gated) | discussion | no | n/a | n/a | ★★ | Kaggle CLI training workflow LB5 relied on |
| 1 | LB5 master notebook | Kaggle (linked in writeup; JS/auth) | notebook | no | n/a | unknown | ★★★ | phases 1–3 compiled; JS/auth-gated |
| 1 | LB5 final-model dataset | Kaggle (linked in writeup; JS/auth) | dataset | no | n/a | ≫20 MB | ★★ | final LoRA; not downloaded |
| 2 | huikang bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | no | n/a | ~36 KB | ★★★ | byte-level per-bit search LB5 extended with ternary + memorized continuations |
| 3 | "It takes two: Your GRPO is secretly DPO" | https://arxiv.org/abs/2510.00977 | documentation | no (arxiv not fetchable from sandbox) | n/a | PDF | ★★ | basis for LB5's pseudo-GRPO-via-DPO (which failed) |
| 3 | ORPO | https://arxiv.org/abs/2403.07691 | documentation | no | n/a | PDF | ★ | planned, not run |
| 3 | KTO | https://arxiv.org/abs/2402.01306 | documentation | no | n/a | PDF | ★ | planned, not run |
| 3 | Smaug / DPOP | https://arxiv.org/abs/2402.13228 | documentation | no | n/a | PDF | ★ | planned, not run |
| 3 | DoRA | https://arxiv.org/abs/2402.09353 | documentation | no | n/a | PDF | ★ | tried; vLLM unsupported → rejected |

Link-budget honored: **7 depth-1 (≤10), 1 depth-2 (≤20), 5 depth-3 (≤20)**. See `links/depth0-3.md`. huikang substrate overlaps prior LB1/LB3 research; new for LB5: @donaldgalliano, @citerne, and 5 arXiv refs (with explicit URLs from the writeup's reference list).

## Saved / downloaded resources
- `writeup/lb5-writeup.md` (faithful Markdown of `temp/LB5.pdf`), `writeup/lb5-writeup.zh.md` (Chinese analysis), `writeup/raw/` (provenance).
- `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored** (PDF stays in `temp/`). @huikang code linked not copied (licensing).

## Notebook conversions
**N/A** — no reachable public `.ipynb` (LB5 master notebook + final-model dataset JS/auth-gated; @huikang repo is `.py`). `kca nb --help` inspected; nothing to convert. Kaggle CLI not used (task forbids credentials).

## Link-following results (2026-06-20)
- **huikang repo + raw bit solver** — fetched OK in prior research; LB5's ternary extension + memorized continuations + iterative LoRA averaging + no-leakage generator are LB5's additions on top.
- **@donaldgalliano / @citerne / @huikang discussions** — JS-gated (NO_CONTENT), consistent with prior research. @donaldgalliano's per-bit claim is summarized from LB5's description (and rejected by LB5).
- **arXiv refs (2510.00977 / 2403.07691 / 2402.01306 / 2402.13228 / 2402.09353)** — taken from the writeup's reference list (authoritative); arXiv pages are not reliably fetchable from the sandbox network (allow-list excludes arxiv.org).
- **LB5 master notebook + final-model dataset** — JS/auth-gated; not downloaded (and the model ≫ 20 MB).

## Blockers / unknowns
- Kaggle writeup body recovered; the **master notebook, final-model dataset, and discussion bodies are JS/auth-gated**.
- LB5's **per-category CoT samples** (linked "here" throughout the writeup) are JS/auth-gated; the prose describes them in detail (preserved).
- `unknown`: exact per-iteration token counts (author: "unclear"); exact GPU hours; the precise improvement attribution (author states this is unclear).
- LB5 explicitly **failed cryptarithm** (7.9%) — the 0.90→0.92 lever (vs LB1/LB3) is the cryptarithm capability LB5 lacks.
