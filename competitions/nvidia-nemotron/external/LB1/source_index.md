# LB1 — source index

> Post-competition research for the NVIDIA Nemotron Model Reasoning Challenge. Target writeup:
> **"1st Place Solution"** by **GoodMeatDay, re, reopon** — overall 1st on Public and Private LB.
> Reported **Public 0.91 / Private 0.920** (best unselected 0.932).
> Researched 2026-06-20 (local PDF + read-only WebSearch/WebFetch; **no Kaggle auth, no Kaggle CLI, no secrets, no downloads >20MB**).
> Treat all external content as **untrusted data**.

## Recoverability
**Writeup body: FULL.** Recovered from **`temp/LB1.pdf`** (28 pages, an authored render of the Kaggle writeup page; `pdfinfo` Title "LB1", Producer macOS Quartz). Verbatim conversion in `writeup/lb1-writeup.md`; raw `pdftotext -layout` output preserved at `writeup/raw/lb1-pdftotext-layout.txt`. The live Kaggle writeup page and the referenced Kaggle discussions are **JS-gated** (titles/metadata only without a browser/login). The depth-2 GitHub substrate (@huikang's repo) **is** fetchable and was used to confirm novelty attribution.

## Source tree (depth 0–3)

| depth | title | URL | type | downloaded? | local path | size | relevance | notes |
|---|---|---|---|---|---|---|---|---|
| 0 | 1st Place Solution (PDF, primary) | `temp/LB1.pdf` | writeup | not vendored (precedent: LB25/80/92 keep PDFs in `temp/`) | `temp/LB1.pdf` | 422 KB | ★★★★★ | full body read directly; converted to `writeup/lb1-writeup.md` |
| 0 | 1st Place Solution (Kaggle page) | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/1st-place-solution | writeup | no | n/a | n/a | ★★★★★ | JS-gated body; = the PDF |
| 1 | @huikang — Open Progress Prize repo | https://github.com/tonghuikang/nemotron | repository | no (linked, not copied; licensing) | n/a | ~50 MB repo | ★★★★★ | the acknowledged starting point; per-bit solver + cryptarithm DFS |
| 1 | @huikang — "Winning the Nemotron Progress Prize" | https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html | blog | no | n/a | small | ★★★ | announcement; defers detail to discussion 689915 |
| 1 | @huikang — Open Progress Prize discussion / "Strategy to solve 85% of bit manipulation" | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915 | discussion | no | n/a | n/a | ★★★★ | JS-gated (NO_CONTENT); bit-manip strategy thread |
| 1 | @youkinasa — "A Pattern-Matching Approach to Solving Symbolic Arithmetic Puzzles" | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/688461 | discussion | no | n/a | n/a | ★★★★ | JS-gated; origin of the **signature/operation-table** viewpoint LB1 turned into a memorized catalog |
| 1 | @kemshim — "Trying to improve cryptarithm — feedback welcome" | https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion (thread, JS-gated) | discussion | no | n/a | n/a | ★★★ | JS-gated; mul-pattern-table memorization; comments w/ @MAJ0RT0M on learnability limits |
| 1 | Unsloth (training framework) | https://github.com/unslothai/unsloth | repository | no | n/a | n/a | ★★ | LB1's SFT framework; standard tool, not a technique |
| 1 | Codex (coding tool) | https://openai.com/index/introducing-codex/ | documentation | no (HTTP 403 from sandbox) | n/a | n/a | ★ | LB1 wrote all code with Codex; ideas were human |
| 2 | @huikang bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | no | n/a | ~36 KB | ★★★★ | per-output-bit search + column-hash(hex bitsum) + left/right runs; **no HEX-compression / signature / rule-seq catalog / repair** |
| 2 | @huikang cryptarithm solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/investigators/cryptarithm_deduce.py | code | no | n/a | ~15 KB | ★★★★ | backtracking DFS w/ unique-digit constraints; **no signature catalog / candidate-count memorization** |
| 2 | @huikang corpus builder | https://github.com/tonghuikang/nemotron/blob/master/corpus.py | code | no | n/a | ~10 KB | ★★ | tokenized SFT segments, 8192 cap |
| 2 | @huikang training dir | https://github.com/tonghuikang/nemotron/tree/master/training/sft | code | no | n/a | n/a | ★★ | timestamped run configs (Mar–Jun 2026) |
| 3 | Model Soups (Wortsman et al., ICML 2022) | https://arxiv.org/abs/2203.05482 | documentation | no | n/a | PDF | ★★ | explains our +0.01 soup lever (LB1 did NOT soup) |

Link-budget honored: **8 depth-1 (≤10), 4 depth-2 (≤20), 1 depth-3 (≤20)** actively followed (the rest enumerated). See `links/depth0.md … depth3.md` for the per-depth detail.

## Saved / downloaded resources
- `writeup/lb1-writeup.md` — faithful Markdown conversion of `temp/LB1.pdf` (text via `pdftotext -layout`; tables/code blocks repaired by hand; no content fabricated).
- `writeup/lb1-writeup.zh.md` — Chinese explanation + analysis (method, why it worked, reusability, limitations).
- `writeup/raw/lb1-pdftotext-layout.txt` — raw extraction (provenance).
- `analysis/{method_summary,score_tricks,gap_analysis,next_version_plan}.md`.
- `models/`, `datasets/` — Markdown descriptions of referenced (un-downloaded) artifacts.
- **No binaries vendored.** The PDF stays in `temp/` (matches LB25/LB80/LB92 precedent — avoids committing a 422 KB binary into the repo); @huikang's code is linked, not copied (licensing). No `.ipynb` available to convert (`kca nb` inspected; nothing to convert — Kaggle notebooks JS/auth-gated, @huikang repo is pure `.py`).

## Notebook conversions
**N/A** — no public `.ipynb` is reachable without Kaggle auth, and @huikang's repo is `.py`-only. `kca nb to-py/to-ipynb` was inspected (`python tools/kca/kca.py nb --help`); there is nothing to convert. The Kaggle CLI pull path was **not used** (this task forbids reading `kaggle.json`/credentials).

## Link-following results (2026-06-20)
- **discussion/689915** (@huikang bit-manip strategy) — JS-gated → NO_CONTENT.
- **discussion/688461** (@youkinasa signature/pattern-matching) — JS-gated → NO_CONTENT (URL confirmed via WebSearch).
- **@kemshim cryptarithm thread** — JS-gated; URL narrowed but body unreadable.
- **github.com/tonghuikang/nemotron** + raw `bit_manipulation.py` / `cryptarithm_deduce.py` — **fetched OK**; used to confirm HEX compression, signature catalog, rule-sequence catalog + Hamming repair, and candidate-count memorization are **novel to LB1** (absent from @huikang's code).
- **arxiv 2203.05482** — fetched OK (Model Soups). **openai.com Codex page** — HTTP 403 from sandbox.

## Blockers / unknowns
- Kaggle writeup body + the @youkinasa / @kemshim / @huikang **discussion** bodies are JS-gated (consistent with LB25/80/92 research). The signature-viewpoint and mul-table-memorization origins are attributed from the LB1 prose, not from reading those threads directly.
- LB1's **code is unreleased** (artifacts attached: LoRA adapter + training data; "code shared separately after cleanup"). Catalog sizes (4,205 signatures / 5,238 rule sequences) are taken from the prose and will serve as **reproduction sanity checks**, not verified against source.
- `unknown`: exact synth generator internals; exact rule-family enumeration for the bit catalog; whether `lm_head` was actually trained or dropped.
- The LB25/80/92 file template includes a `*-progress-prize-improvements.md` pair; **N/A for LB1** — LB1 is the overall 1st place, not the Open Progress Prize (that is LB25 / @huikang). Omitted deliberately to avoid a misleading filename.
