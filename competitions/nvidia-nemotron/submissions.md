# Submissions — nemo

> **PRIVATE LB RELEASED 2026-06-16.** Both team accounts finished **0.85 private**. harrysun2006 (`flyingfox`)
> public rank **150/4350** (0.86); private top 0.92. Public→private was robust (no shake-up). Key: **soup
> 0.86→0.85** (most robust 0.86, selected); **surgery 0.86→0.84** (−0.02, worst-aging — *not* selected, vindicated);
> **b2 0.84→0.85** (+0.01, the may hedge that paid off). Full analysis + per-submission private deltas:
> [`postmortems/2026-06-16-final-postmortem.md`](./postmortems/2026-06-16-final-postmortem.md).
>
> **Refreshed 2026-06-16 via read-only Kaggle API** (`kaggle competitions submissions`, both accounts;
> creds in `.vscode/.env.harry` / `.vscode/.env.may`, read-for-use only). All rows below are confirmed
> `SubmissionStatus.COMPLETE`. **Private LB is now released and backfilled** into every row below (no longer
> `unknown`). Kaggle's submissions API exposes no numeric submission ID; the (date + description) pair is the key.
> Quota: 5/team/day during the competition; **post-deadline late window = 100/team/day** (EQ campaign, below).

## T12 hard-val ranking (official-metric, min-logprob hardest 72; `harrysun2006/nemo-t12-hardval` v2, 2026-06-15)
Greedy decode (official `max_tokens=7680, temp=0`), `\boxed{}`/last-number extractor, exact-or-1e-2 match.
Hard-val = min-logprob hardest-N-per-category (16 each bit/equation/cipher, 8 each numeral/gravity/unit).
The final-sprint submissions themselves are listed in the campaign table below.

| adapter | hard-val acc | bit | equation | cipher | numeral/gravity/unit |
|---|---:|---|---|---|---|
| **soup** | **0.764** | 13/16 | 2/16 | 16/16 | 8/8 each |
| **v14** | **0.764** | 14/16 | 2/16 | 15/16 | 8/8 each |
| base (no adapter) | 0.389 | 0/16 | 0/16 | 8/16 | 8 / 7 / 5 |
| c1 | 0.389 | 1/16 | 0/16 | 3/16 | 8/8 each |
| v15 | 0.333 | 0/16 | 0/16 | 0/16 | 8/8 each |
| c2 | 0.278 | 1/16 | 0/16 | 2/16 | 7 / 3 / 7 |

**Findings:**
- **The 0.86 soup is robust, not diluted** — tied with v14 (0.764) and best overall; both ace hard cipher/bit.
- **Augmented adapters (c1/c2/v15) sit at/below the base model on the hardest cipher/bit** (c1 cipher 3/16 < base 8/16) despite being trained on cipher/bit CoT. The base anchor rules out a load artifact: they change behaviour (easy cats → 24/24) but *degrade* the hardest categories. Confirms "augmentation dilutes the clean replay recipe", amplified on the hard slice.
- **`equation` is unsolved by everyone (≤2/16)** — the only real frontier; cipher-heavy data does not touch it.
- **Decision (2026-06-15):** hold the 0.86 soup; stand down the cipher-heavy v11 stage-2 SFTs (a2 corpus was 94% cipher → same regression risk). Remaining daily slots left unused.

### Final-sprint extra submissions (2026-06-15, all scored)
| submission | account | public LB | note |
|---|---|---:|---|
| surgery `scale_1.15` | harrysun2006 | 0.86 | spectral surgery on the soup (×1.15 LoRA); **tied/duplicate** of soup → no hedge value |
| andy279 frontier | firefly2006 | **0.81** | v14 recipe + 1700 external-teacher solver-CoT (eq/bit) → **regressed** (dilution) |
| v11 self-distill | firefly2006 | **0.80** | v14 recipe + 261 rejection-sampled CoT → **regressed** |

None beat the 0.86 soup; the augmentation-dilutes / single-cat≠total lesson held even against external-teacher CoT.

### Final private-LB selection (lock before 23:59 UTC)
Select the **two** submissions that count for private scoring:
1. **soup — 0.86** (`2026-06-15 03:22`): best public + robust on hard-val.
2. **v14 — 0.85** (`2026-06-12 23:36`): equal public LB to c1 but **much stronger on hard-val (0.764 vs c1 0.389)** → safer second pick. **Pick v14, NOT the surgery 0.86** (a near-duplicate of soup = no hedge) and NOT andy279/v11 (regressed). Manually select to avoid the auto "2-highest-public" = soup+surgery no-hedge trap.

## Late-submission window (post-deadline R&D — 2026-06-16+, 100/team/day)

Equation frontier (EQ-3 grid). Hypothesis: SFT on the **real** equation prompts woven into the v14 replay
backbone lifts the `equation` category (the only unsolved one, ≤2/16 hard-val for every adapter incl. the
0.86 soup). Risk per EQ-0: the equation is a **global strong-cipher function**, 61.6% of hidden query
symbols are unseen, so memorising the 1,555 train answers may not generalise; over-weighting may regress
bit/cipher (T12 gate). The LB is the verdict. Full design: [`equation-frontier.md`](./equation-frontier.md).

Full 2×2 (coverage × dose), all scored 2026-06-16:

| Date (UTC) | Account | Kernel | coverage | dose | Public LB | Private LB | Recipe |
|---|---|---|---|---|---:|---:|---|
| 06-16 09:22 | harrysun2006 | **nemo-eq-aug** | **rotated 7814** | **×1** | **0.86** | **0.86** | v14 replay + 7814 real input→output pairs (each in-context example rotated to a query), 498 steps |
| 06-16 06:00 | harrysun2006 | nemo-eq-spec | query 1555 | ×1 | 0.85 | 0.85 | v14 replay + 1555 equation **query answers** woven (~16%), 303 steps |
| 06-16 08:22 | firefly2006 | nemo-eq-hidose | query 1555 | ×3 | 0.84 | 0.84 | v14 replay + 1555 query answers ×3 |
| 06-16 10:02 | firefly2006 | nemo-eq-aug-hidose | rotated 7814 | ×2 | 0.85 | 0.82 | v14 replay + 7814 real pairs ×2 (overfit → priv −0.04) |
| 06-16 11:23 | harrysun2006 | nemo-merge-eqaug | — | — | 0.85 | 0.85 | **soup_v2** = SVD(0.86-soup ×0.6 + eq-aug ×0.4) rank32 — souping eq-aug **dilutes** (< both parents) |

**Grid verdict (2026-06-16): coverage helps, dose hurts — and eq-aug does NOT soup.**
- **Coverage is the lever:** eq-aug (7,814 *real* input→output pairs, via rotating each in-context example
  into a query target) → **0.86 / 0.86**, the **campaign's best private** (ties soup public 0.86, *beats* soup
  private 0.85). vs query-only eq-spec 0.85/0.85. The win is real (coherent across the grid, not noise): the
  rotation exposes ~5× more genuine cipher pairs to memorise, capturing the *seen-input* fraction of hidden
  equation queries (EQ-0: ~38% of hidden queries have all-seen symbols).
- **Dose hurts:** query-only ×3 (eq-hidose 0.84) and coverage ×2 (eq-aug-hidose **priv 0.82**) both regress —
  over-weighting equation data overfits (private drops more than public). **Sweet spot = single epoch over the
  full real-pair coverage.**
- **⚠️ Metric caveat (kept):** the T12 min-logprob hard-val ranked **eq-spec 0.167** vs its real LB 0.85 — it
  over-samples the hardest problems and understates adapters weak only on the hard tail (gap 0.68 vs ~0.07–0.10
  for soup/v14). **→ Trust the LB aggregate; hard-val is a hard-tail hint only.**
- **eq-aug does NOT soup.** `soup_v2 = SVD(0.86-soup ×0.6 + eq-aug ×0.4)` → **0.85 / 0.85**, *below both
  parents*. The model-soup lever needs **hard-tail-robust** members (the original v14+c1+b1 were all 0.76+
  hard-val); SVD-merging the hard-tail-*weak* eq-aug imports its shortcutting and averages out its equation
  coverage. So the coverage lever lives only in a **standalone** adapter, not a merge.
- **`equation` is *partially* addressable** (coverage-memorisation captures the seen-input fraction, +0.01
  aggregate) but **not solved** — the unseen-input majority stays uninferable (EQ-2′ strong cipher). **eq-aug
  standalone 0.86 / 0.86 is the practical ceiling** — best own-work private, not improvable by souping.

### Competitor-writeup borrows: LB25 / LB80 / LB92 (2026-06-20)

Borrowing the four LB25 levers (v16-evalfix), the LB80 equation-discovery lever (v17-discovery), and the LB92
stability levers (v18-stable) onto the v14 backbone. Hypotheses + plans in `external/{LB25,LB80,LB92}/analysis/
next_version_plan.md`. **Verdict: none beats the 0.86 soup/eq-aug ceiling; all confirm their plans' own risk notes.**

| Date (UTC) | Account | Kernel | Public LB | Private LB | Recipe / verdict |
|---|---|---|---:|---:|---|
| 06-20 12:51 | harrysun2006 | **nemo-v16-evalfix** | 0.832 | 0.828 | LB25: eval-parity preflight (measurement-only) + verified bit CoT 157 + min-logprob replay (hardest 1198, 37 steps). **−0.018/−0.012 vs v14 → dilution** (dominant risk confirmed); LEVER 1 can't move the LB (it fixes local↔grader measurement parity, not the model). |
| 06-20 12:06 | firefly2006 | **nemo-v17-discovery** | 0.840 | 0.848 | LB80 A: equation discovery-CoT. **Cracked the equation cipher** = per-operator digit-string rules (operand-reverse × arith × ±1 × result-reverse, + concat); 180 verified plaintext-digit rows woven (dose 0.15). **−0.01/+0.008 vs v14 → equation bounded**: plaintext-subset rule-discovery does not transfer to the 82% glyph-ciphered queries. |
| 06-20 16:55 | harrysun2006 | **nemo-v18-stable** | 0.844 | 0.848 | LB92: grad-clip 1.5 (variance) + verified synth equation (cracked rule family, 800, ratio 0.1). **−0.006/+0.008 vs v14 → ~neutral** (least-harmful borrow; grad-clip didn't raise the mean). |

**Borrow-campaign verdict:**
- **v16 (LB25):** the bit-CoT + min-logprob replay levers *diluted* (the b2/c1/c2/v15 lesson again). The eval/submission **parity preflight is sound but measurement-only** — it can't lift an LB that the grader already scores correctly. No LB headroom there.
- **v17 (LB80):** the equation cipher is **per-problem per-operator transformation rules**, not the EQ-0 "single global function" — but cracking it for the *plaintext-digit* subset (~18% of equation rows) does **not** lift the LB, because the ~82% glyph-ciphered queries need a *joint cipher+op* crack (still open). **`rules24.py` (`versions/lb1-v1`, branch `exp/nemo-postlb1-v1`) is the superior 95%-deduce cracker — use it for a v17.1** (and reuse it as v18's synth generator). **v17-dpo deferred** (needs external sm_90+ GPU, #83).
- **v18 (LB92):** grad-clip 1.5 is the only sound, low-risk lever (variance, not mean); **per-char tokenization is infeasible** for an adapter-only submission (grader uses the base tokenizer — added tokens never reach inference). The synth-equation lever is now poison-free (cracked rule family) but still bounded by the same plaintext limitation as v17.
- **Bottom line: soup 0.86/0.85 + eq-aug 0.86/0.86 remain the held best.** The borrows reproduced the writeups' *methods* but not their LB — our 0.86 ceiling is robust, and equation stays the wall.

## Real-training campaign (own work — 2026-06-09 → 2026-06-15)

| Date (UTC) | Account | Version | Public LB | Private LB | Status | Description (kernel) |
|---|---|---|---:|---:|---|---|
| 2026-06-15 ~12 | harrysun2006 | **soup** | **0.86** | **0.85** | COMPLETE | **SVD model-soup of v14+c1+b1 (0.4/0.3/0.3) → rank-32 — new best, own real-training; most robust 0.86 (SELECTED)** |
| 2026-06-15 14:38 | harrysun2006 | surgery A | 0.86 | 0.84 | COMPLETE | spectral surgery on soup (×1.15 LoRA delta); −0.02 priv = worst-aging 0.86 (NOT selected, vindicated) |
| 2026-06-15 01:12 | harrysun2006 | c1 | 0.85 | 0.85 | COMPLETE | v14 backbone + verified real-prompt solver-CoT (balanced ~1800) |
| 2026-06-15 00:52 | harrysun2006 | c2 | 0.83 | 0.83 | COMPLETE | v14 backbone + verified solver-CoT (hard-cat emphasis ~1000) |
| 2026-06-15 01:02 | firefly2006 | b2 | 0.84 | **0.85** | COMPLETE | v14 backbone + cryptarithm+bit synth (~11%); +0.01 priv = the may hedge that paid off (SELECTED) |
| 2026-06-15 00:52 | firefly2006 | b1 | 0.85 | 0.84 | COMPLETE | v14 backbone + cryptarithm-only synth (~9%) (SELECTED) |
| 2026-06-15 21:36 | firefly2006 | v11 self-distill | 0.80 | 0.82 | COMPLETE | v14 recipe + 261 rejection-sampled verified CoT — regressed (dilution) |
| 2026-06-15 21:31 | firefly2006 | andy279 | 0.81 | 0.81 | COMPLETE | v14 recipe + 1700 external-teacher solver-CoT (eq/bit) — regressed (dilution) |
| 2026-06-14 05:53 | harrysun2006 | v15 (T11) | 0.84 | 0.84 | COMPLETE | v14 backbone + 2640 cryptarithm-weighted synth (60% crypt), seq8192, 337/337 steps |
| 2026-06-13 23:54 | harrysun2006 | t7 merge | 0.82 | 0.80 | COMPLETE | SVD merge v14@1.0 + ctx4k@0.25 + v10@0.25, per-module rank-32 |
| 2026-06-12 23:36 | harrysun2006 | **v14 (T10)** | **0.85** | 0.84 | COMPLETE | replay recipe: huikang corpus (7830) + replay-math (2.0M ans tok), seq8192, 254/254 steps, CCE + MoE tying + lm_head/in_proj/out_proj |
| 2026-06-12 09:53 | firefly2006 | v10 (T4) | 0.59 | 0.64 | COMPLETE | rule-CoT: 4000 rule traces (6 cat) + 4000 long CoT, seq4096, 558 steps |
| 2026-06-11 22:40 | firefly2006 | ctx2k (T2) | 0.42 | 0.46 | COMPLETE | response-masked LoRA, seq2048, 583 steps (eval 0/8 = truncation artifact) |
| 2026-06-11 22:39 | harrysun2006 | ctx4k (T1) | 0.67 | 0.66 | COMPLETE | response-masked LoRA, seq4096, 580 steps |
| 2026-06-10 09:31 | harrysun2006 | v7 | 0.65 | 0.66 | COMPLETE | response-masked LoRA, 400 steps, LR 2e-4 cosine |
| 2026-06-10 04:00 | harrysun2006 | v6 | 0.44 | 0.45 | COMPLETE | CoT 120 steps (loss over prompt+padding bug) |
| 2026-06-10 04:00 | harrysun2006 | v6′ | 0.47 | 0.46 | COMPLETE | CoT SFT 120 steps, submitted from Kaggle storage |
| 2026-06-10 02:27 | harrysun2006 | v5 | 0.61 | 0.66 | COMPLETE | bare-answer SFT, 120 steps (loss 1.48); ptxas fix validated |
| 2026-06-09 23:45 | harrysun2006 | identity | 0.47 | 0.52 | COMPLETE | untrained identity adapter (pipeline validation) |

## Earlier public-fork exploration (2026-05-15 — pre real-training; NOT our own training)

| Date (UTC) | Account | Public LB | Private LB | Status | Description |
|---|---|---:|---:|---|---|
| 2026-05-15 00:44 | harrysun2006 | 0.50 | 0.51 | COMPLETE | "NVIDIA Nemotron Submission Demo" notebook v1 |
| 2026-05-15 00:34 | harrysun2006 | 0.85 | 0.84 | COMPLETE | "THK public fork 2026-05-14 (v14 tinker-adapter)" — public fork |
| 2026-05-15 00:18 | harrysun2006 | **0.86** | 0.82 | COMPLETE | "[LB] [SCORE] [0.86]" — public fork (private 0.82 = worst-aging, vs own soup 0.85) |

## Best score — honest reading
- **Best own real-training submission: 0.86** (`nemo-merge-soup`, 2026-06-15) — an SVD **model-soup** of
  three own-trained, comparable+complementary 0.85 adapters (v14 replay + c1 verified-solver-CoT + b1
  cryptarithm-synth, weights 0.4/0.3/0.3, rank-32). Real training, no repack (D3-compliant). This broke the
  0.85 ceiling (+0.01).
- Earlier own-work best was 0.85 (`nemo-replay-v14`). The final-sprint individual runs tied or trailed it
  (b1 0.85, c1 0.85, b2 0.84, c2 0.83); only the **soup** exceeded it.
- **T12 hard-val (2026-06-15) confirms the soup is robust**, not a public-LB fluke: 0.764 on the hardest 72,
  tied with v14 and best of all candidates; the augmented adapters (c1/c2/v15) regress to at/below base
  there. → Final private-LB selection: **soup (0.86) + v14 (0.85)** (v14 is the strongest single adapter
  and far ahead of c1 on hard-val).
- Note: a 2026-05-15 **public-fork** submission also showed 0.86, but that was a repack (not own training);
  the soup now gives a **compliant own-work 0.86**.
- **Post-deadline (does NOT count for ranking):** `nemo-eq-aug` scored **0.86 public / 0.86 private** in the
  late window — the **best own-work private** (vs soup 0.85). It SFTs the v14 backbone on 7,814 *real* equation
  input→output pairs (rotate each in-context example into a query); coverage-memorisation captures the
  seen-input fraction of equation queries. Reusable lever for next time, but it landed after the 06-15 lock so
  it did not change the competition selection (soup + v14).
- Current leaderboard top: **~0.90** (refreshed 2026-06-15).

## lb1-v1 GPU run + guarded submit (2026-06-20) — SUBMITTED, Public 0.828 / Private 0.816

The full GPU pipeline ran end-to-end and the one guarded late-submission was
executed (post-LB1 method-validation; late window, no ranking effect).

- **Corpus:** 17,000 consistency-verified catalog-method records (cryptarithm 6,339
  signature-DFS + bit 2,346 HEX/repair + equation-numeric 8,315 24-rule), off-kernel
  by `versions/lb1-v1/synth_gen.py`; all 17k round-trip through the official
  extractor, none over the 7,680-token budget. Dataset `harrysun2006/nemo-lb1-v1-synth`.
- **Kernel run:** `harrysun2006/nemo-lb1-v1` v1 (RTX Pro 6000) — COMPLETE,
  `failureMessage: null`. Trained the v14 replay backbone + lb1-v1 synth to **step
  619/786** before the 7h B7 wall-clock guard saved (peak VRAM 96.8 GB, loss ≈ 0.14).
  In-run validation: "root files only, rank=32, alpha=32".
- **Artifact:** `submission.zip` **1.37 GB** rank-32 LoRA (large b/c `lm_head` in
  `target_modules` → `save_embedding_layers=True`; functionally rank-32, vLLM ignores
  lm_head; b1 precedent). Preflight PASS (exists/non-empty/root-structure/rank-32/
  no-secrets; hard-val unavailable = LB is the verdict).
- **Submit:** `… -k harrysun2006/nemo-lb1-v1 -v 1 -f submission.zip` 2026-06-20
  22:08 UTC → **Public 0.828 / Private 0.816** (COMPLETE; 1/100 daily late slots).

**Result reading (honest).** Below the held-best (soup 0.86/0.85, v14 0.85, eq-aug
0.86/0.86) — as predicted. The catalog method is **volume-bound**: LB1 used 360k
synth over a full epoch; this run had 17k (crypt under-weighted 6.3k) trained to only
619/786 steps — far short of where catalog recall stabilises (~80k crypt, LB1 Q&A),
so the lever could not "click" and the small eq-heavy synth mildly diluted the 0.85
backbone (b1/b2/v15 lesson, amplified by under-training). **Confirms volume is the
moat.** The *method* is reproduced + validated CPU-side (signature catalog 4,205
exact; eq-deduce 95.0%; HEX exact; repair verified). Held-best untouched; late window
= no ranking effect. Next: scale crypt ≥40k, drop `lm_head` (shrinks the 1.37 GB
adapter, no score effect), full epoch.

## lb3-v1 — guarded submit NOT performed (competition closed)

- **2026-06-20, `exp/nemo-postlb3-v1`:** the `/goal` task authorized one guarded Kaggle
  submit (`postlb3-v1: post-writeup implementation with guarded submit`,
  `require_preflight_pass_before_submit: true`). The submit was **correctly blocked by the
  preflight gate** and **no submission was attempted**. Reasons, in order:
  1. the competition **closed 2026-06-15 23:59 UTC** (no live ranking submission possible);
  2. the plan (`external/LB3/analysis/next_version_plan.md`) is explicitly **PLAN ONLY / no
     GPU / no submit** (`allow_* = false`) — a conflict with the task front matter, resolved
     in favor of repo-as-source-of-truth per the task's own conflict clause;
  3. no GPU two-stage training was run here, so **no `submission.zip` was produced** →
     preflight items "run completed successfully" and "submission.zip exists" fail.
- **Delivered instead:** the no-GPU CPU half of the plan under `versions/lb3-v1/` (CSP
  cryptarithm solver, hex bit compression, 13-op numeric solver, stage-1 drills,
  private-tracking validation, equation re-probe). See `tracking.md` lb3-v1 section.
- **For a future live competition**, the authorized flow (GPU train → package → preflight →
  submit, selecting on the private-tracking offline metric) is documented in
  `versions/lb3-v1/README.md`.

## lb5-v1 — guarded submit NOT performed (competition closed)

- **2026-06-20, `exp/nemo-postlb5-v1`:** the `/goal` task authorized one guarded Kaggle
  submit (`postlb5-v1: post-writeup implementation with guarded submit`,
  `require_preflight_pass_before_submit: true`). The guarded submit was **executed** via the
  real `kca kaggle submit` SUBMISSION command and **correctly BLOCKED by the preflight gate**
  — no upload reached Kaggle; the BLOCKED decision is recorded to `.agent/kca/audit.jsonl`.
  Block reasons: (1) competition **closed 2026-06-15**; (2) plan is PLAN-ONLY (`allow_*=false`);
  (3) no GPU 3-phase run → **no `submission.zip`** (preflight fails); (4) credentials unavailable
  (task forbids reading them). **0 of 100 submissions used**; held-best (soup 0.86/0.85, eq-aug
  0.86/0.86) untouched.
- **Delivered instead:** the no-GPU CPU half of the plan under `versions/lb5-v1/` (2-world/4-family
  equation solver, ternary raw-bit solver, no-leakage generator, tokenizer probe, private-tracking
  validation, equation re-probe). See `tracking.md` lb5-v1 section.

## lb6-v1 — guarded submit NOT performed (competition closed)

- **2026-06-20, `exp/nemo-postlb6-v1`:** the `/goal` task authorized one guarded Kaggle
  submit (`postlb6-v1: post-writeup implementation with guarded submit`,
  `require_preflight_pass_before_submit: true`). The guarded submit was **executed** via the
  real `kca kaggle submit` SUBMISSION command and **correctly BLOCKED by the preflight gate**
  — no upload reached Kaggle; BLOCKED decision recorded to `.agent/kca/audit.jsonl`. Reasons:
  competition **closed 2026-06-15**; plan PLAN-ONLY; no GPU run → no `submission.zip`;
  credentials unavailable. **0/100 submissions used**; held-best (soup 0.86/0.85, eq-aug
  0.86/0.86) untouched.
- **Delivered instead:** the no-GPU CPU half under `versions/lb6-v1/` (per-domain DUMMY-masking
  attribution probe — our B8 fix, template bit solver, DFS cryptarithm, maxmodmin equation
  solver, bit/cryptarithm trade-off CV, full-train-as-validation). See `tracking.md` lb6-v1 section.

## lb10-v1 — guarded submit NOT performed (competition closed)

- **2026-06-20, `exp/nemo-postlb10-v1`:** the `/goal` task authorized one guarded Kaggle
  submit (`postlb10-v1: post-writeup implementation with guarded submit`,
  `require_preflight_pass_before_submit: true`). The guarded submit was **executed** via the
  real `kca kaggle submit` SUBMISSION command and **correctly BLOCKED by the preflight gate**
  — no upload reached Kaggle; BLOCKED decision recorded to `.agent/kca/audit.jsonl`. Reasons:
  competition **closed 2026-06-15**; plan PLAN-ONLY; no GPU run → no `submission.zip`;
  credentials unavailable. **0/100 submissions used**; held-best (soup 0.86/0.85, eq-aug
  0.86/0.86) untouched.
- **Delivered instead:** the no-GPU CPU half under `versions/lb10-v1/` (rotate/shift key-table
  bit reasoner, frequency-deduce + two-axis-guess equation solver, oracle-vs-fidelity + logprob
  learnability diagnostics, keep-failures discipline, equation re-probe). See `tracking.md` lb10-v1 section.

## lb13-v1 — guarded submit NOT performed (competition closed)

- **2026-06-20, `exp/nemo-postlb13-v1`:** the `/goal` task authorized one guarded Kaggle
  submit (`postlb13-v1: post-writeup implementation with guarded submit`,
  `require_preflight_pass_before_submit: true`). The guarded submit was **executed** via the
  real `kca kaggle submit` SUBMISSION command and **correctly BLOCKED by the preflight gate**
  — no upload reached Kaggle; BLOCKED decision recorded to `.agent/kca/audit.jsonl`. Reasons:
  competition **closed 2026-06-15**; plan PLAN-ONLY; no GPU 3-stage run → no `submission.zip`;
  credentials unavailable. **0/100 submissions used**; held-best (soup 0.86/0.85, eq-aug
  0.86/0.86) untouched.
- **Delivered instead:** the no-GPU CPU half under `versions/lb13-v1/` (sharpest equation
  solver with global majority-vote reversal + robust aggregation, 3-input bit verifier,
  keep-failures 1:1 rebalance, validation, equation re-probe). See `tracking.md` lb13-v1 section.

## lb25-v1 — guarded submit EXECUTED (v16-evalfix artifact = the LB25 method)

- **2026-06-21, `exp/nemo-postlb25-v1` (PR #153):** the `/goal` task authorized one guarded
  Kaggle submit (`postlb25-v1: post-writeup implementation with guarded submit`,
  `require_preflight_pass_before_submit: true`). Initially deferred (the LB25 method was already
  realized as v16-evalfix, below best), then **executed on explicit human authorization** ("yes,
  submit all"). The submit re-uses the existing, already-grader-validated **v16-evalfix** adapter
  — which *is* the lb25-v1 method (the LB25 `next_version_plan`'s version is literally
  `v16-evalfix`); a real artifact, no fresh GPU run, honest label.
- **Preflight (PASS):** `harrysun2006/nemo-v16-evalfix` v1 kernel COMPLETE; its `submission.zip`
  already scored on the grader (0.832/0.828) — definitive proof of a valid rank≤32 adapter,
  correct zip structure, run completed; message set; 1 of 100 daily late-window slots.
- **Submit:** `kaggle competitions submit -c … -k harrysun2006/nemo-v16-evalfix -v 1
  -f submission.zip -m "postlb25-v1: post-writeup implementation with guarded submit"` →
  submitted **2026-06-21 02:39 UTC** → **Public 0.828 / Private 0.828** (COMPLETE).
- **Result reading:** below the 0.86 held-best, as predicted (the LB25 method = v16-evalfix
  underperforms; cryptarithm is the real wall, unsolved even by huikang). Note the **public
  0.828 vs v16-evalfix's original 0.832** on the *same artifact* — a live demonstration of LB25's
  own **temp=0 selection-variance** lesson (huikang saw 0.872↔0.864 across re-submits). Private
  0.828 is identical. Late window = no ranking effect; held-best (soup 0.86/0.85, v14 0.85,
  eq-aug 0.86/0.86) untouched. 1/100 daily slots used.
- **Delivered:** the clean reusable CPU packaging under `versions/lb25-v1/` — the headline
  `eval_parity.py` audit (LB25 lever #1, the boxed-prompt fix = our B4/INS-002), `eq_reversal.py`
  (lever #2: **96.1%** single-mode reversal symmetry / **47.6%** search cut on real train.csv),
  `bit_cot.py` (lever #5, grader-verified), `easy_cat_synth.py` (levers #3/#4, no-regression
  guard), min-logprob replay. See `tracking.md` lb25-v1 section + `versions/lb25-v1/README.md`.

## Submission checklist
- [ ] local validation passed (validate_kernel.py + fail-fast preflight)
- [ ] submission shape checked (submission.zip @ /kaggle/working; rank32/α32)
- [ ] no secrets
- [ ] runtime acceptable (≤8h wall-clock guard)
- [ ] approval obtained (remote submit needs human approval)
- [ ] result recorded (this table)
