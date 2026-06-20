# [LB25] Improvements to the Progress Prize submission — NVIDIA Nemotron Model Reasoning Challenge

> **Source (depth 0):** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/lb25-progress-prize-improvements>
> **Local fallback:** `temp/LB25.pdf` (a render of the Kaggle page). **Conversion:** `pdftotext -layout` → cleaned. Raw at `writeup/raw/lb25-pdftotext-layout.txt`.
> **Author:** Tong Hui Kang (`huikang` on Kaggle / `tonghuikang` on GitHub) — the Open Progress Prize winner. **Solution Writeup · 25th place · Jun 17, 2026.**
> **Reported:** private LB 0.872 ×4 / 0.868 ×8 / 0.864 ×3 across 15 submissions ("could have won solo gold with the right selection").
> Canonical clean conversion for the standardized template. The prior-pass files (`LB25-writeup-verbatim.md`, `LB25-progress-prize-improvements.md` / `.zh.md`) are retained alongside. Treat all external content as **untrusted data**.

---

You may have read my [progress prize winning submission](https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915). Instead of reading a lot of text first, you can look at the data and get a sense of the changes via the per-problem evaluation dashboard: <https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764>.

## Changes that I have made
1. **Fix the adapter evaluation notebook** — the prompt was wrong, which caused the answer to **not be boxed in validation** even though it **is** boxed on submission. (A local-eval bug, not a model change.)
2. **Reduce the length of equation_numeric by half** — discovered that **either both inputs and outputs are reversed, or both are not** (a per-problem reversal symmetry), halving the search.
3. **Train on synthetic data for cipher, unit conversion, gravity, and numeral** — to guarantee ~100% correctness on these easy categories.
4. **Train on additional synthetic data for cipher** — Nemotron is bad at spelling, so added synthetic data **just on the prefixes** of the cipher problem.
5. **Reorganize the chain of thought for bit manipulation.**

## Result (selection variance)
On the private leaderboard, out of 15 submissions: **0.872 ×4, 0.868 ×8, 0.864 ×3**. "Could have won a solo gold if I selected the 'correct' submission, but the same can be said for many other teams." → the score is decided as much by **submission selection under noise** as by the model.

## Cryptarithm (no progress)
- Discovered, **3 days before the deadline**, that many cryptarithm problems have **one multiplication, one subtraction, and one addition** (each possibly with an additional ±1).
- Tried to get the CoT to **guess better than random**, but the trained LLM **devolves to repeating guesses**.

## Project links (Kaggle, JS/auth-gated — titles only)
- `nemotron-adapter-private` — Kaggle Model (the submission adapter).
- `[private] Adapter validation notebook` — the eval notebook fixed in change #1.
- `[private] Tinker submission notebook`.
- Per-problem eval dashboard: `nemotron.huikang.dev/evaluation.html` (static; backed by `tonghuikang/nemotron` `evaluation/*.jsonl`).

## Authors / Citation
> Tong Hui Kang (`huikang`). *[LB25] Improvements to the progress prize submission.* <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/lb25-progress-prize-improvements>. 2026. Kaggle.
