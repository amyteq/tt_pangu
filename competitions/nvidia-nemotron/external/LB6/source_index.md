# LB6 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"[2nd public / 6th private] place solution"** by **Yurnero, Alehandreus**.
> Researched 2026-06-20 (local PDF + read-only WebSearch; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**).
> Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL.** Recovered from **`temp/LB6.pdf`** (7 pages). Verbatim conversion in `writeup/lb6-writeup.md`; raw `pdftotext -layout` at `writeup/raw/lb6-pdftotext-layout.txt`. The live Kaggle writeup page, the linked reasoning-trace attachments, and the per-domain LB-probe result figures are **JS/auth-gated** (numeric tables preserved).

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 6th-place (2nd public) Solution (PDF) | `temp/LB6.pdf` | writeup | not vendored (precedent) | `temp/LB6.pdf` | 514 KB | ★★★★★ | full body → `writeup/lb6-writeup.md` |
| 0 | Kaggle writeup page | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/2nd-public-6th-private-place-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated; = the PDF |
| 1 | @huikang OPP repo (baseline solvers) | https://github.com/tonghuikang/nemotron | repository | no (linked, not copied) | n/a | ~50 MB | ★★★★ | LB6 reused numeral/unit/gravity/cipher solvers ~unchanged |
| 1 | @huikang OPP discussion | https://www.kaggle.com/.../discussion/689915 | discussion | no | n/a | n/a | ★★★ | JS-gated |
| 1 | LB6 bit reasoning-trace attachment | Kaggle (linked "here") | code/trace | no | n/a | unknown | ★★★ | JS/auth-gated; trace example |
| 1 | LB6 cryptarithm reasoning-trace attachment | Kaggle (linked "here") | code/trace | no | n/a | unknown | ★★★ | JS/auth-gated |
| 1 | Unsloth | https://github.com/unslothai/unsloth | repository | no | n/a | n/a | ★★ | training framework |
| 1 | Tinker | (referenced; late-stage fast adapter training) | tool | no | n/a | n/a | ★ | named, no URL given |
| 2 | huikang bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | no | n/a | ~36 KB | ★★★ | OPP bit baseline LB6 extended (templates + hex + ternary) |
| 2 | huikang cryptarithm solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/investigators/cryptarithm_deduce.py | code | no | n/a | ~15 KB | ★★★ | OPP cryptarithm baseline; LB6 = DFS + reversed search |
| 3 | Model Soups (Wortsman et al.) | https://arxiv.org/abs/2203.05482 | documentation | no | n/a | PDF | ★ | context for two-seed shipping |

Link-budget honored: **7 depth-1 (≤10), 2 depth-2 (≤20), 1 depth-3 (≤20)**. See `links/depth0-3.md`. huikang substrate overlaps prior LB1/LB3/LB5 research; new for LB6: Tinker (named, no URL).

## Saved / downloaded resources
- `writeup/lb6-writeup.md` (faithful Markdown of `temp/LB6.pdf`), `writeup/lb6-writeup.zh.md` (Chinese analysis), `writeup/raw/` (provenance).
- `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`; `models/`, `datasets/` descriptions.
- **No binaries vendored** (PDF stays in `temp/`). @huikang code linked not copied.

## Notebook conversions
**N/A** — no reachable public `.ipynb` (LB6 attachments JS/auth-gated; @huikang repo is `.py`). `kca nb --help` inspected; nothing to convert. Kaggle CLI not used (task forbids credentials).

## Link-following results (2026-06-20)
- **huikang repo + raw solvers** — fetched OK in prior research; LB6's template bit solver (hex+skips+ternary), DFS cryptarithm with reversed search, per-domain DUMMY probing, and full-train-as-validation are LB6's additions.
- **LB6 reasoning-trace attachments + per-domain result figures** — JS/auth-gated (NO_CONTENT).
- **Tinker** — named as a late-stage fast adapter-training tool; no URL given in the writeup.

## Blockers / unknowns
- Kaggle writeup body recovered; **attachments (bit/cryptarithm traces) and per-domain LB-probe figures are JS/auth-gated**.
- `unknown`: exact final private score (writeup says "6th private"; the ~0.90 class is inferred from the field and the 0.25B-dataset CV); exact Tinker setup; the precise bit-CV drop estimate that caused the selection regret.
- LB6's cryptarithm is **weak (~17% in the shipped 0.25B set)** — the 0.5B set would have doubled it (potential 2nd-3rd) but mis-estimated the bit cost.
