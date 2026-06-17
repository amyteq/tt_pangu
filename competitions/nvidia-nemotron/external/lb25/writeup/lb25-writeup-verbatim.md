<!--
Faithful conversion of `temp/LB25.pdf` (a Chrome print-to-PDF render of the Kaggle writeup
"[LB25] Improvements to the progress prize submission" by Tong Hui Kang / huikang).
Content and links are reproduced verbatim from the PDF (text via `pdftotext -layout`; hyperlink
targets via the PDF's embedded URI annotations). This is the raw source; the analytical summary is
in `lb25-progress-prize-improvements.md`. (The PDF's only embedded raster images were two thin
grayscale header strips — omitted as non-content.)
-->

# [LB25] Improvements to the progress prize submission

> **Source writeup:** https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/lb25-progress-prize-improvements
>
> Kaggle · Solution Writeup · by [Tong Hui Kang (`huikang`)](https://www.kaggle.com/huikang)

You may have read my [progress prize winning submission](https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/discussion/689915).

Instead of reading a lot of text first, you can look at the data and get a sense of the changes that I
have made

https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764

**Changes that I have made**

- Fix the adapter evaluation [notebook](https://www.kaggle.com/code/huikang/private-adapter-validation-notebook) (I found out that the prompt is wrong, which caused the
  answer to not be boxed in validation but in fact it is being boxed on submission)
- Reduce the length of equation_numeric by half (I found out that either both inputs are outputs are
  reversed, or they are both not reversed)
- Training on synthetic data for cipher, unit conversion, gravity and numeral (I hope to guarantee
  100% correctness on these problems)
- Reorganize the chain of thought for bit manipulation.

On the private leaderboard, out of 15 times my submission scored 0.872 4 times, 0.868 8 times,
0.864 3 times (could have won a solo gold if I selected the "correct" submission, but the same can
be said for many other teams).

I did not manage to make progress on cryptarithm.

- I discovered, 3 days before the deadline, that many problems there is one multiplication, one
  subtraction and one addition (but each of them could have an additional plus one or minus one)
- I tried to get the chain of thought to guess better than random, but apparently the LLM after
  training devolves to repeating guesses.

**Project Links**

- [nemotron-adapter-private](https://kaggle.com/models/huikang/nemotron-adapter-private) — Kaggle Model · Public — 13 days ago · Usability 0.7
- [[private] Adapter validatio…](https://kaggle.com/code/huikang/private-adapter-validation-notebook) — Kaggle Notebook · Public — 2 months ago · 3 upvotes
- [[private] Tinker submissio…](https://kaggle.com/code/huikang/private-tinker-submission-notebook) — Kaggle Notebook — 13 days ago · 1 upvote

---

<sub>Source: https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/lb25-progress-prize-improvements (page 1/1, printed 17/06/2026 17:21). Links below are the PDF's embedded URI annotations, reproduced unchanged.</sub>
