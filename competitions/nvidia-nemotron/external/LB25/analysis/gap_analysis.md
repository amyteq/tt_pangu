# LB25 gap analysis — huikang's 0.872 vs our 0.86 (updated from the writeup PDF)

> Updated 2026-06-17 from the actual writeup (`temp/LB25.pdf`). The earlier version over-indexed on a
> "short-response format fix" that was a `kuangyicheng` conflation — **corrected here** to huikang's four real
> changes. External claims untrusted; our numbers from `tracking.md`/`submissions.md`.

## The four real LB25 changes vs us

| # | LB25 change | what it is | our status | gap / borrow |
|---|---|---|---|---|
| 1 | **Fix the adapter *evaluation*** | local validation used a *wrong prompt* → answers looked un-boxed in validation though boxed on submission; he aligned the eval prompt to submission | **WE HIT THE SAME CLASS OF BUG**: B4 (`EVAL_MAX_NEW 512` truncated CoT → 0/8) and T12 hard-val mispredicting eq-spec (0.167 hard-val vs 0.85 LB) | **HIGH-EV, ~free: audit that our local eval prompt == the submission prompt, exactly** |
| 2 | **Halve `equation_numeric`** | joint reversal symmetry — "inputs **and** outputs both reversed, or both not" → half the cases redundant | we didn't model `equation_numeric` separately (our equation slice was the base-36 cipher) | LOW direct EV (different sub-type); a data-efficiency idea |
| 3 | **Synthetic data → 100% on `cipher`/`unit`/`gravity`/`numeral`** | lock the easy/structured categories at ceiling | our easy cats are already strong (T12 numeral/gravity/unit 8/8, cipher 15–16/16 on v14/soup) | LOW-MEDIUM EV (we're near ceiling there); confirms "don't regress the easy cats" |
| 4 | **Reorganize bit-manipulation CoT** | better bit reasoning trace | our bit is strong (v14 14/16, soup 13/16 hard-val) but bit *train* ceiling ~86% | **MEDIUM EV: bit CoT quality is the shared headroom (also LB92's lever)** |
| — | **cryptarithm: NO progress** | "one mult, one sub, one add (each ±1)"; CoT devolves to repeating guesses | our EQ-2′: strong cipher, simple algebra eliminated; eq-aug 0.86 via coverage | **agreement: bounded wall; + a new composite-op lead (below)** |

## The biggest takeaways (corrected)
1. **The #1 LB25 lever was a LOCAL-EVALUATION BUG, not a model change.** His validation under-counted because the
   eval prompt differed from the submission prompt. **We have the identical failure mode twice** (B4 truncation;
   T12 hard-val mispredicting eq-spec). → The cheapest, highest-EV action for us is an **eval/submission parity
   audit**: assert our local validation uses byte-identical prompt + decode settings as the grader. "Free"
   accuracy that the metric was silently hiding.
2. **Selection variance is real at the top.** 0.872 was only **4 of 15** submissions (0.868 ×8, 0.864 ×3); he
   notes he "could have won solo gold if I selected the correct submission." This re-confirms our INS-005/INS-007
   (best + a *diverse* hedge; avoid near-duplicates — our surgery ×1.15 aged −0.02). Selection discipline ≈ a
   recipe lever at the top of the board.
3. **Equation/cryptarithm is a bounded wall for everyone** — the Progress-Prize winner explicitly failed on it,
   matching our EQ-2′ verdict. Do not over-invest.

## New, actionable EQ-2′ lead (from the cryptarithm note)
huikang: "many problems there is **one multiplication, one subtraction and one addition (each possibly ±1)**."
Our EQ-2′ eliminated *single* ops (`in mod M`, `floor(in/D)`, `A±B`, `A÷B`, `A·B`, `K·in mod M`) and one
positional split — but **never a 3-term composition `≈ A·B − C + D` with ±1 slack** under the secret σ. This is
a concrete, untested hypothesis class for a future crack round (a constraint/SAT solve over σ + the composite
form). ⚠ huikang **also failed** to crack it and our prompts are a single 5-char string (operand split unclear),
so it is a lead, not a likely win.

## Borrowable (ranked, all SFT / ~free)
1. **Eval/submission parity audit** (HIGH EV, ~free) — change #1; our recurring bug class.
2. **Bit-manipulation CoT reorganization** (MEDIUM EV) — change #4; shared with LB92; bit is our train-set headroom.
3. **Selection discipline** (free) — lock best + a diverse hedge; never two near-duplicates.
4. **(crack) test the composite `A·B−C+D ±1` hypothesis** for equation (low odds; one bounded constraint-solve).
5. **min-logprob selective replay** (still valid from the base pipeline / data explorer) — target under-fit rows.

## NOT worth borrowing / we're ahead
- **Model soup** (our 0.86; INS-004) — huikang ships a single adapter; keep souping.
- Heavy cryptarithm/equation effort — confirmed bounded ~8–9% both ways.
