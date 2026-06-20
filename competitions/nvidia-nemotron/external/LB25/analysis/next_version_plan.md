# Next-version plan — borrowing from LB25 (post-Saturday GPU reset)

> Updated 2026-06-17 from the actual writeup (`temp/LB25.pdf`). Analysis/planning only (RTX PRO 6000 quota
> resets Saturday; **no GPU/submit/push in this task**). Borrows = huikang's four real LB25 changes; verify
> before trusting. Synthesises with our recipe (`tracking.md`, `insights.md`, `research.md`).

> **✅ EXECUTED 2026-06-20 (late window). RESULT: v16-evalfix = public 0.832 / private 0.828 — −0.018 pub / −0.012 priv vs v14 (0.85/0.84); below the 0.86 soup ceiling. Hypothesis NOT supported.** All three levers ran (`harrysun2006/nemo-v16-evalfix` v1): LEVER 1 eval/submission parity preflight (OK); LEVER 2 verified bit CoT (157 grader-faithful rows — our stricter `_bit_verify` dropped 1 poison row lib's lax numeric check kept); LEVER 3 min-logprob selective replay (scored 7987 non-replay → replayed hardest 1198 for 37 steps). **Verdict:** LEVER 1 is measurement-only (fixes local↔grader parity, can't move an LB the grader already scores right); LEVER 2+3 *diluted* (the dominant risk the plan flagged — b2/c1/c2/v15 lesson). No LB headroom. See `submissions.md` §LB25/LB80/LB92 + `tracking.md`.

## Version name
**v16-evalfix** — "eval/submission parity + targeted bit CoT + min-logprob replay" (v14 backbone).
(Renamed from `v16-mlp`: the headline lever is now the eval-bug fix, per the writeup.)

## Hypothesis
Our 0.86 ceiling is **not equation-bound** (cryptarithm is a confirmed ~8–9% wall — huikang failed too). The
recoverable headroom is **(a) eliminating any local-eval ↔ submission mismatch** (huikang's #1 lever: his
validation under-counted because the eval prompt differed from the submission prompt — *and we have the same
bug class*: B4 truncation, T12 mispredicting eq-spec), and **(b) the residual hardest bit rows** (better bit
CoT + min-logprob replay). Fixing (a) is ~free and may already be silently costing us accuracy; (b) is a low-
dose SFT change gated to avoid the dilution that sank b2/v15/c2.

## What we borrow from LB25 (the four real changes)
1. **Eval/submission parity audit (change #1 — TOP priority, ~free).** Assert our local validation uses the
   **byte-identical prompt + decode settings** (greedy, `max_tokens=7680`, temp 0, same SUFFIX) as the Kaggle
   grader; confirm every answer is boxed under the *submission* prompt. This is exactly the bug huikang fixed.
2. **Bit-manipulation CoT reorganization (change #4).** Improve our bit trace quality (the shared headroom with
   LB92; bit train ceiling ~86%). Own-solver-verified traces only.
3. **Synthetic-to-lock the easy cats (change #3).** Low priority — our easy cats are already near ceiling
   (T12 numeral/gravity/unit 8/8, cipher 15–16/16); use only as a *no-regression guard*, not a gain source.
4. **(equation_numeric halving, change #2)** — N/A to our base-36 cipher slice; noted as a data-efficiency idea.

## What we add (ours, validated)
- Keep the **v14 replay recipe** backbone (biggest lever, 0.67→0.85) + the **SVD model-soup** (INS-004; huikang
  has no soup — our edge). Keep **eq-aug** standalone for equation (0.86 priv; doesn't soup).
- **min-logprob selective replay** of the hardest bit/cipher rows (huikang's base-pipeline signal; ≤15% dose).
- **Selection discipline** (his 0.872 was 4/15): lock best + a *diverse* hedge, never two near-duplicates
  (INS-005/INS-007; surgery ×1.15 aged −0.02).

## Data / corpus plan
- Backbone: existing v14 corpus (huikang recording-order + replay-math 2M answer tokens) — unchanged.
- Bit: reorganized, own-solver-**verified** bit CoT (answer == gold), woven at **≤15% dose** (b1/c1 lesson).
- min-logprob replay shard: hardest residual bit/cipher rows, one short extra pass.
- No external-teacher data (andy279 regressed to 0.81 at high dose).

## Prompt format
**Identical to the submission/grader prompt** (this is the point of change #1): chat template + the exact eval
SUFFIX, response-only mask, bounded CoT length so `\boxed{}` always lands < 7,680 tokens.

## Training config (single RTX PRO 6000 kernel, ≤8h guard)
- LoRA r32/α32; MoE-128 tying; lm_head/attn/in_proj/out_proj; CCE; seq 8192; LR 3.5e-4; micro 4 / global 32.
- Phase A: v14 backbone (~254 steps / 1 epoch). Phase B: bit-CoT + min-logprob replay (≤15%, ~+1 short epoch).
- 7h `TRAIN_DEADLINE_SEC` guard; fail-fast 1-example preflight (INS-001).

## Validation plan (incl. T12 hard-val) — gate BEFORE any submit
1. **Eval/submission parity check FIRST** (the LB25 lesson): local eval prompt + decode == grader, byte-for-byte;
   confirm 0 un-boxed / 0 truncated-before-`\boxed{}` on the hardest rows.
2. `validate_kernel.py` (ruff E9/F821 + masking); in-kernel fail-fast preflight.
3. **T12 local official metric** (`eval/official_metric.py` + `eval/hard_val_ids.json`): greedy 7680/temp 0,
   exact-or-1e-2, per category. Require **bit ↑, no regression on cipher/easy cats**, total hard-val ≥ 0.764.

## Submit / no-submit gate
- Submit only if the parity audit is clean AND T12 hard-val ≥ 0.764 with bit ↑ and no easy-cat regression.
- **Late-window submission needs explicit human approval** (this task is analysis-only).
- Soup-grow v16-evalfix into v14+c1+b1 only if the local metric improves; lock best + a diverse hedge.

## Risks
- **Dilution** (dominant): bit/replay over-weighting regresses (b2/v15/c2); mitigate ≤15% dose + T12 gate.
- **Parity audit finds nothing** — then there's no free win there and the gain is just the bit CoT (smaller).
- **Equation stays bounded** — don't target it; the gain is bit + eval-correctness.

## GPU estimate
- Parity audit + bit-CoT build + min-logprob shard: no extra Kaggle GPU (local/CPU).
- 1 training kernel ≈ **6–7 h** RTX PRO 6000 + 1 short soup kernel (CPU, ~20 min). Total ≈ **1 GPU session**.

## Implementation checklist
- [x] **eval/submission parity audit** — in-kernel `assert_eval_submission_parity`; preflight OK (change #1)
- [x] reorganized, own-solver-verified bit CoT corpus (change #4) — 157 grader-faithful rows (embedded solver)
- [x] min-logprob replay shard (hardest residual bit/cipher rows) — scored 7987 → hardest 1198, 37 replay steps
- [x] kernel = Phase A (v14) → Phase B (bit CoT + replay, ≤15%) — ran, 259 main + 37 replay steps
- [x] 7h guard + fail-fast preflight + `validate_kernel.py` — wall-clock guards per phase; ruff E9/F821 clean
- [ ] ~~T12 hard-val locally~~ — **not feasible (no local GPU for the 30B adapter)**; used the late-window LB as the measurement instead (public 0.832/priv 0.828 < v14)
- [ ] ~~soup-grow into v14+c1+b1~~ — **skipped: local metric did NOT improve (0.832 < v14 0.85)**, so no soup candidate
- [ ] ~~(optional) composite-op equation hypothesis~~ — superseded by v17-discovery's per-operator cipher crack (see LB80 plan)
