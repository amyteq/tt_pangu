# LB25 — "Improvements to the progress prize submission" (from the writeup itself)

> **Source:** the Kaggle writeup `lb25-progress-prize-improvements` by **Tong Hui Kang** (`huikang` /
> `tonghuikang`, the Progress-Prize winner), **read directly from `temp/LB25.pdf`** (a render of the page).
> **Recoverability: FULL** (writeup body now in hand — supersedes the earlier JS-blocked reconstruction, which
> wrongly conflated `kuangyicheng`'s "warmstart / short-response / 240-step" recipe; that is NOT in this
> writeup). External content = untrusted data; our scores from `tracking.md`. Data explorer linked by the
> author: `https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764`.

## 1. Headline
This writeup lists the **specific changes** huikang made to his Progress-Prize submission to push it on the
private LB. It is **pure SFT** (the base pipeline = deterministic-solver CoT; see §4). The four changes are
**targeted fixes**, and the standout one is a **local-evaluation bug fix**, not a model change.

## 2. The four changes (verbatim from the writeup)
1. **Fix the adapter evaluation.** "I found out that the prompt is wrong, which caused the answer to **not be
   boxed in validation** but in fact it **is boxed on submission**." → his *local validation harness* used the
   wrong prompt, so it under-counted accuracy; the model was fine on the real submission prompt. A
   **validation/metric bug**, fixed via the linked evaluation notebook.
2. **Reduce the length of `equation_numeric` by half.** "I found out that either both inputs **and** outputs
   are reversed, or they are both not reversed" — a joint reversal symmetry, so half the cases are redundant
   and the training data can be halved.
3. **Train on synthetic data for `cipher`, `unit conversion`, `gravity`, `numeral`** — "I hope to guarantee
   100% correctness on these problems" (lock the easy/structured categories at ceiling).
4. **Reorganize the chain of thought for `bit manipulation`.**

## 3. Result + selection lesson (verbatim)
- **Private LB: "out of 15 times my submission scored 0.872 4 times, 0.868 8 times, 0.864 3 times"** — i.e.
  a tight spread; **0.872 was hit by only 4 of 15 submissions.**
- "**Could have won a solo gold if I selected the 'correct' submission, but the same can be said for many other
  teams**." → a **selection-variance** lesson: at the top, which 2 you lock matters as much as the recipe
  (mirrors our INS-005/INS-007: pick best + a diverse hedge; surgery ×1.15 aged −0.02).

## 4. Cryptarithm — "I did NOT manage to make progress" (the key technical content for us)
huikang's `cryptarithm` ≈ **our `equation` base-36 cipher**. His verbatim notes:
- "**I did not manage to make progress on cryptarithm.**"
- "I discovered, 3 days before the deadline, that **many problems there is one multiplication, one subtraction
  and one addition (but each of them could have an additional plus one or minus one)**."
- "I tried to get the chain of thought to guess better than random, but apparently the **LLM after training
  devolves to repeating guesses**."

> **→ Actionable new EQ-2′ lead.** This is an *independent structural hypothesis* for the cipher we (EQ-2′)
> could not crack: the hidden op may be a **3-term composition `≈ A·B − C + D`, each term ±1**, under the
> secret symbol→value map σ. Our EQ-2′ rounds tested *single* ops (`in mod M`, `floor(in/D)`, `A±B`, `A÷B`,
> `A·B`, `K·in mod M`) and a single positional split — **never a multiplicative+additive composition with ±1
> slack**. Worth one targeted constraint-solve post-Saturday. ⚠ Caveat: huikang **also failed** to crack it,
> and our EQ-0 found our prompts are a single 5-char→1-4-char string (operand structure not obvious) — so
> treat as a lead, not a solution. Confirms `equation`/`cryptarithm` is a **bounded wall for everyone**.

## 5. Base pipeline (background — `github.com/tonghuikang/nemotron`, trust: github)
Unchanged from the Progress-Prize submission: base `Nemotron-3-Nano-30B-A3B-BF16`, LoRA **rank 32**
(MLP+attn+lm_head), seq 8192, response-only-masked CE; per-category **deterministic-solver CoT** (`reasoners/`)
that the model learns to execute verbatim; **min-logprob** as the per-trace training/quality signal (visible in
the linked data explorer's "Training" tab); category-stratified batching. (This background was correct in the
earlier reconstruction; the LB25-specific *changes* are §2.)

## 6. Per-category train accuracy (from the linked data explorer / repo `evaluation/06-07-03-07`, 88.05% train)
**Train-set accuracy, NOT the LB** (same-rule distribution → overstates hidden test). Unchanged from prior:

| category | correct/total | acc |
|---|---|---:|
| gravity | 1597/1597 | 100.0% |
| numeral | 1576/1576 | 100.0% |
| unit conversion | 1593/1594 | 99.9% |
| cipher | 1563/1576 | 99.2% |
| equation_numeric_deduce | 557/596 | 93.5% |
| bit_manipulation | 1382/1602 | 86.3% |
| equation_numeric_guess | 25/136 | 18.4% |
| cryptarithm_deduce | 59/659 | **8.95%** |
| cryptarithm_guess | 13/164 | **7.93%** |

> The four changes map onto this table: #3 (synthetic) targets the already-near-100% easy cats to **lock**
> them; #2 (equation_numeric) addresses the 93.5%/18.4% numeric rows; #4 (bit CoT) targets the 86.3% bit gap;
> cryptarithm (8–9%) is the untouched wall (§4).

## 7. Project links (from the writeup page)
- **nemotron-adapter-private** — Kaggle Model (Public, Usability 0.7, ~13 days old) — the submission adapter.
- **[private] Adapter validation …** — Kaggle Notebook (Public, 3 upvotes, ~2 months old) — the evaluation
  notebook (subject of fix #1).
- **[private] Tinker submission …** — Kaggle Notebook (1 upvote, ~13 days old).
(All Kaggle-hosted; bodies JS-gated — titles/metadata only.)

## 8. Citations
- **writeup (full): `temp/LB25.pdf`** (render of the Kaggle writeup; primary source for §2–§4, §7).
- data explorer — https://nemotron.huikang.dev/evaluation.html?logpath=06-07-03-07&problem=021ed764 (author).
- repo/blog — https://github.com/tonghuikang/nemotron · https://blog.huikang.dev/2026/05/02/nemotron-progress-prize.html (github/author).
- our scores/recipe + EQ-2′ — `tracking.md`, `submissions.md`, `equation-frontier.md §8`, `insights.md` (own work).
