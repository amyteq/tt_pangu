# LB3 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"3rd Place Solution"** by **YS-L (liauys)**. Reported **Private LB 0.900** (local validation 90.46%).
> Researched 2026-06-20 (local PDF + read-only WebSearch/WebFetch; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**).
> Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL.** Recovered from **`temp/LB3.pdf`** (17 pages; an authored render of the Kaggle writeup page). Verbatim conversion in `writeup/lb3-writeup.md`; raw `pdftotext -layout` at `writeup/raw/lb3-pdftotext-layout.txt`. The live Kaggle writeup page and the referenced Kaggle notebooks/discussions are **JS-gated**. The cryptarithm example trace is an **attachment (`cryptarithm_example.txt`) not included** with the PDF; the writeup quotes its key sections, which are preserved in the conversion.

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 3rd Place Solution (PDF, primary) | `temp/LB3.pdf` | writeup | not vendored (LB25/80/92/LB1 precedent: PDFs stay in `temp/`) | `temp/LB3.pdf` | 533 KB | ★★★★★ | full body → `writeup/lb3-writeup.md` |
| 0 | 3rd Place Solution (Kaggle page) | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/3rd-place-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 1 | llkh0a's notebook (starter) | https://www.kaggle.com/code (handle `llkh0a`; exact slug not indexed) | notebook | no | n/a | unknown | ★★★★ | YS-L's starting point; trivial+cipher traces reused. JS-gated; slug not surfaced by WebSearch |
| 1 | huikang — Open Progress Prize repo | https://github.com/tonghuikang/nemotron | repository | no (linked, not copied) | n/a | ~50 MB | ★★★★ | CCE manual training loop; LB3 reuses it |
| 1 | huikang — progress-prize discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | discussion | no | n/a | n/a | ★★★ | JS-gated (NO_CONTENT) |
| 1 | youkinasa — pattern-matching discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/688461 | discussion | no | n/a | n/a | ★★★★ | JS-gated; source of LB3's multi-example **intersection** idea |
| 1 | kemshim — cryptarithm discussion | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion (JS-gated) | discussion | no | n/a | n/a | ★★★ | JS-gated; symbolic equation solver ideas |
| 2 | huikang bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | no | n/a | ~36 KB | ★★★ | per-output-bit search LB3's bit trace extends (hex+MAJ added by LB3) |
| 2 | huikang cryptarithm solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/investigators/cryptarithm_deduce.py | code | no | n/a | ~15 KB | ★★★ | backtracking DFS; LB3's CSP intersection/anchor + two-stage are LB3's additions |
| 2 | huikang training loop / corpus | https://github.com/tonghuikang/nemotron (train_sft.py, corpus.py) | code | no | n/a | small | ★★★ | the "manual training loop with CCE" LB3 praises |
| 3 | Model Soups (Wortsman et al.) | https://arxiv.org/abs/2203.05482 | documentation | no | n/a | PDF | ★ | context for our soup lever (LB3 did NOT soup) |

Link-budget honored: **6 depth-1 (≤10), 3 depth-2 (≤20), 1 depth-3 (≤20)**. See `links/depth0-3.md`. Most references overlap LB1's research (same competition); the new one is **llkh0a's notebook**.

## Saved / downloaded resources
- `writeup/lb3-writeup.md` (faithful Markdown of `temp/LB3.pdf`), `writeup/lb3-writeup.zh.md` (Chinese analysis), `writeup/raw/` (provenance).
- `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored** (PDF stays in `temp/`, matching precedent). @huikang code linked not copied (licensing).

## Notebook conversions
**N/A** — no reachable public `.ipynb` (llkh0a/huikang Kaggle notebooks JS/auth-gated; @huikang repo is `.py`). `kca nb --help` inspected; nothing to convert. Kaggle CLI not used (task forbids credentials).

## Link-following results (2026-06-20)
- **llkh0a notebook** — WebSearch did not surface a direct slug; handle-specific Kaggle notebook, JS-gated. Documented from the writeup's acknowledgement (trivial+cipher trace source).
- **huikang repo + raw solvers** — fetched OK in prior LB1 research; reused to confirm LB3's CSP/two-stage and hex/MAJ are LB3 additions atop @huikang's per-bit solver + backtracking DFS + CCE loop.
- **youkinasa / kemshim / huikang discussions** — JS-gated (NO_CONTENT), consistent with LB1/LB25/80/92 research.

## Blockers / unknowns
- Kaggle writeup body + llkh0a/huikang/youkinasa/kemshim discussion/notebook bodies are JS-gated. The cryptarithm full example trace (`cryptarithm_example.txt`) was an attachment not in the PDF.
- LB3's **code is unreleased**; CSP / two-stage / lookup-table sizes and the 24.2%/93.79% solve rates are taken from the prose and serve as **reproduction sanity checks**.
- `unknown`: exact GPU spec (single GPU, ~58 GPU-h total); the llkh0a notebook's exact URL/version.
- **Front-matter note:** `wiki/25.LB3_task.md` sets `notes_section_en: "LB3 / 1st Place Solution: What We Learned"` — a copy-paste typo (the rank is **3rd**, per `writeup_rank_label`/`writeup_display_name` and the zh section). We used the **correct "LB3 / 3rd Place Solution: What We Learned"** heading in `notes.md` to avoid a misleading canonical doc.
