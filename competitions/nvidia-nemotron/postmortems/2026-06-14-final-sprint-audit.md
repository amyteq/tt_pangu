# Nemo final-sprint audit — plan (`work/00.nemo.md`) vs actual work

> Read-only audit produced 2026-06-14 (~14:42 UTC, ~33h to the 2026-06-15 23:59 UTC deadline).
> Evidence: `competitions/nvidia-nemotron/{README,tracking,submissions,bugs,insights,strategy,tasks,rules,competition.yaml}`,
> `work/00.nemo.md`, committed kernels under `kernels/`. `unknown` = not in available evidence.
> Follow-up: per user direction this audit is followed by a last-window run of options B + C (see end).

## 1. Final recommendation (as written at audit time): hold 0.85
Two principled attempts to beat 0.85 both regressed (T7 merge 0.82, v15 synth 0.84); `insights.md`:
any augmentation on top of the clean replay recipe dilutes it. The one high-EV unbuilt lever
(bit/equation solver-distillation, `work/00.nemo.md` §10②) is high-risk. **LB keeps the max → 0.85 is
banked and safe.** (User subsequently approved a best-effort last-window swing at B + C — §10.)

⚠ Open verification: which submissions are selected for private scoring is `unknown`. Raw account public
max is **0.86** but from a **2026-05-15 public-fork (repack, not own training)** — touches the self-imposed
no-repack red line. Own-work best = **0.85 (v14)**.

## 2. Ground-truth score timeline
Source: `submissions.md` (read-only Kaggle API refresh 2026-06-14; all `COMPLETE`; private LB not released).

| Version | Idea | Push/submit evidence | Public LB | local/CV | Status | Lesson |
|---|---|---|---:|---|---|---|
| identity | untrained adapter | 06-09 23:45 harry | 0.47 | — | baseline | pipeline ok |
| v5 | answer-only SFT 120 steps | 06-10 02:27 harry | 0.61 | loss 1.48 | dropped | ptxas fix (B5) |
| v6/v6′ | CoT, loss over prompt+padding | 06-10 04:00 | 0.44/0.47 | — | bug | B2 response-only masking |
| v7 | CoT + response-mask 400 steps | 06-10 09:31 | 0.65 | — | ok | masking recovers |
| ctx4k (T1) | masked CoT seq4096 580 steps | 06-11 22:39 harry | 0.67 | unknown | ok | long CoT slight ↑ |
| ctx2k (T2) | same corpus seq2048 583 steps | 06-11 22:40 may | **0.42** | eval 0/8 (false) | neg-sample | B1 right-trunc cut `\boxed{}` |
| v10 (T4) | rule-CoT (4k rule + 4k long) | 06-12 09:53 may | 0.59 | held-out 3/4 | merge-pool | short rule-traces → shallow |
| **v14 (T10)** | **public replay recipe** | 06-12 23:36 harry; PR #90 | **0.85** | unknown | **best (+0.18)** | single biggest lever |
| t7 merge | SVD(1.0 v14 + 0.25 ctx4k + 0.25 v10) | 06-13 23:54 harry; PR #94 | 0.82 | ΔW reldiff 0.18–0.27 | route closed | strong+weak = dilution |
| v15 (T11) | v14 backbone + cryptarithm synth | 06-14 05:53 harry; PR #95 | 0.84 | CoT-answer 1930/1930 | did not exceed | single-cat ≠ total |

## 3. Traceability matrix — `work/00.nemo.md` §5–11 → actual
| Plan section | Point | Landed? | Evidence |
|---|---|---|---|
| §5 hot directions | lm_head/MoE target, CoT/solver/synthetic, Progress-Prize pipeline | **partial** — lm_head+MoE target in v14 (most useful); pipeline not recreated but its corpus reused | T10 |
| §6 challenges | hidden generalization; bit/equation hardest; rank32; MoE target; LB misleads; submit compat | compat pitfalls all hit (B1/B3/B5/B6); bit/equation **not specifically cracked** | bugs.md |
| §7 Idea A solver-distillation | write solver→verify→trace | **no real solver**; v10 only computes numeral/gravity/unit/cipher; bit/equation = template | nemo-rule4k-v10.py:198–264 |
| §7 Idea B answer/short/long mix | three formats | partial (v5 / v7 / v14) | timeline |
| §7 Idea C per-category solver+gen | verifiable synth | partial — v15 generator (10 cats) is a **generator not a solver** | nemo_synth_gen.py:1088 |
| §7 Idea D bit candidate enumeration | enumerate fn library, keep f(xᵢ)=yᵢ | **not implemented** | grep: no solver/enumeration |
| §7 Idea E equation two tracks | numeric vs symbolic on real prompts | **only split in the synthetic generator**; v10 single "equation" bucket | nemo_synth_gen.py:927/1019/781; nemo-rule4k-v10.py:162 |
| §7 Idea F per-category local CV | category/template/answer-type CV | **not implemented**; T12 planned-not-run | tracking.md T12 |
| §8.1 data tricks | balancing, format, verified CoT, hard-neg | partial (v15 cryptarithm 60%; verified CoT; no hard-neg) | nemo_synth_gen.py:1103 |
| §8.2 LoRA tricks | rank32/alpha, LR grid, max_len/target ablation | partial; v14 target = broad (incl lm_head); no systematic ablation | §7 config audit |
| §8.3 loss/format | mask prompt, token weighting, boxed finality, binary leading-zeros | mostly (response-only mask; `\boxed{}` finality); no token weighting | insights.md |
| §8.4 merge/SVD | multi-adapter delta merge → SVD32 | **done & tested**: t7 = 0.82, route closed | PR #94 |
| §8.5 RL/GRPO | verifiable-reward RL | **not implemented** | — |
| §9 route (stages 1–6) | local metric → answer SFT → verified CoT → hard synth → multi-seed → merge | **skipped stage-1 local metric**; reached 0.85 via replay recipe — **diverged from plan** | global |
| §10 top-5 | ①verified CoT ②**bit/equation solver synth (biggest lever)** ③format ④merge ⑤per-cat CV | ① partial ② **not built** ③ done ④ done=regress ⑤ not built | combined |
| §11 matrix E0–E7 | E0…E6 merge…E7 RL | E0/E1/E2/E6 done; **E3/E4 (bit/equation synth), E5, E7 (RL) not done** | timeline |

**Core finding:** the scoring win (v14, 0.85) came from a direction the plan under-weighted (faithful replay of
the public recipe); the plan's most-touted lever (bit/equation solver synth) was never built; everything we did
build on top of v14 (v10/v15/t7) underperformed it.

## 4. Deep dive
### 4a. bit manipulation
- **Candidate-function enumeration solver: NOT implemented.** No solver searches a function library against
  example pairs (grep: no `def solve`/enumeration loop on real prompts).
- v10 emits a template for bit (`nemo-rule4k-v10.py:257-259`: "Compare each 8-bit example bitwise…") — no compute.
- v15 `make_bit_puzzle` (`nemo_synth_gen.py:178`) is a **generator** (`rng.sample(ops,2-4)` → known rule → CoT
  verifies the known ops), not a solver of an unknown rule.
- English prompts: yes (`ALICE_HEADER`, :17). Synth volume: bit only **150/2640 (~5.7%)** in v15 (`DEFAULT_MIX`).
- Validation: bit not in the exact-match consistency check (it is self-consistent by construction).
- Result: no per-category LB (`unknown`); v15 overall 0.84 < 0.85. **Plan called bit the biggest lever; it got the least.**

### 4b. equation / symbol
- Split exists **only in the synthetic generator**: `equation_numeric_deduce` (f(x)=ax+b/quadratic/floor/arith/geom,
  :927) + `_guess` (sequences, :1019); `make_symbol_puzzle` (5-char bijection, :521); `cryptarithm_deduce/guess`
  (:781/:805). **No real-prompt solver split** — v10 lumps all into one "equation" bucket (:162) with a template.
- Pure symbol strings: operands are fixed **2 chars** (`_make_sym_operand`, :603); operators `+-*/` map to **8 fixed
  string-rewrite rules** (`_RULE_REGISTRY`, :574). **No variables / functions / arbitrary-length tokens.**
  `force_unknown` only injects unseen **chars** (:647).
- Exact-output risk: symbol/cryptarithm use exact string match (CoT-answer consistency 1930/1930 covers self-
  consistency, but the fixed small rule set may mismatch the hidden test distribution); numeric categories carry
  rounding risk (same family as B1).

## 5. Prompt / training-format audit
| Aspect | State | Evidence |
|---|---|---|
| answer-only | v5 (0.61) | timeline |
| short CoT | v7 response-masked (0.65) | timeline |
| long CoT | ctx4k seq4096 (0.67) | T1 |
| replay corpus | **v14**: huikang recording-order corpus (7830) + replay-math (2.0M ans tok) → **0.85** | T10 |
| English templates | yes — SUFFIX "Please put your final answer inside `\boxed{}`"; generator all-English | nemo_synth_gen.py:17 |
| `\boxed{}` finality | yes — assistant ends `…</think>\n\boxed{answer}` | insights.md; B1 |
| response-only masking | yes (prompt = -100); omitting it → 0.44 (v6) | B2 |
| truncation / seq len | seq2048 right-trunc destroyed `\boxed{}` tail → 0.42 (B1); seq4096 better; v14 seq8192 | B1; timeline |

## 6. Synthetic / solver audit
- Generated: 10 deterministic puzzle+long-CoT categories (`PUZZLE_MAKERS`, :1088); v15 used 2640, cryptarithm 60%
  (deduce 900 + guess 700), equation_numeric 200×2, bit/symbol 150, encrypt 100, numeral/unit/gravity 80
  (`DEFAULT_MIX`, :1103).
- Ratio: ~24% of v15 training (interleaved ~1 per 3).
- Verification: exact-category CoT-answer consistency **1930/1930** (`validate()`), but **generator self-consistency,
  not real-prompt solving**.
- Dilution: ~24% synth slightly diluted other categories (B8); single-cat ≠ total.
- Cryptarithm result: v15 = **0.84** < 0.85 — did not deliver.
- Real solver: **none** (Idea A/D/E solvers never built).

## 7. LoRA / config audit
| Item | Our SFT kernel (v7/ctx4k/v10) | v14 replay (best 0.85) | Evidence |
|---|---|---|---|
| rank / alpha | 32 / 32 | 32 / 32 | all rank≤32 |
| LR / schedule | 2e-4 cosine | **3.5e-4 linear** | submissions.md |
| seq | 4096 (ctx2k 2048 = bug) | **8192** | B1; T10 |
| target modules | `in/out/up/down_proj` (regex) | **+ q/k/v/o + lm_head** | T10 |
| CCE | no | **yes** | insights.md |
| MoE 128 expert tying | no | **yes** | T10 |
| lm_head/in_proj/out_proj LoRA | in/out only | **all incl. lm_head** | T10 |
| masking | response-only | response-only | B2 |
| steps | ctx4k 580 / v10 558 | 254 (1 epoch); v15 337 | submissions.md |
| LB | 0.59–0.67 | **0.85** | timeline |

→ The 0.67→0.85 jump = CCE + MoE tying + lm_head/Mamba LoRA + seq8192 + huikang corpus + replay-math (insights.md #1).

## 8. Bug / failure lessons (`bugs.md`)
- **B1** seq2048 right-trunc cut `</think>\n\boxed{}` tail → 0.42.
- **B2** no response-only masking → 0.44.
- **B3** `apply_chat_template(tokenize=True)` BatchEncoding → `len()` on dict keys → 0 samples (public 0.87 notebook
  may never have run).
- **B4** held-out eval `EVAL_MAX_NEW=512` truncated → misleading local; → 7680 + EVAL_TIME_CAP=1800s.
- **B5** ptxas-blackwell non-executable → copy /tmp + chmod + monkeypatch.
- **B6** data at `/kaggle/input/competitions/<slug>/` → glob, no hardcode.
- **B7** v9 wall-clock overrun → TrainerCallback stop + guaranteed save/zip.
- **B8** (wontfix) cryptarithm single-cat gains ≠ total (8%→71% single, total still ~0.86).
- **B9** (obsolete) v7 NameError / v8 `.shape` each cost ~2h → push-gate ruff F821 + fail-fast preflight.

## 9. Last-~10h options table (at audit time)
| Option | Expected LB | Upside | Downside | GPU time | Quota | Impl risk | Recommend? |
|---|---:|---|---|---|---|---|---|
| A. hold 0.85 | 0.85 | none | none | 0 | 0 | none | ✅ (default) |
| B. half-dose cryptarithm-only synth (~8%) | ≤0.85 | low (single≠total) | 1 quota + ~6h | ~6h | 1 | low–med | ⚠ |
| C. bit/equation real solver-distillation | unknown (theoretical max) | medium (only untried high-EV) | build+run risk | ~7–8h | 1 | high | ❌ at audit (time) |
| D. different-weight re-merge | ≤0.85 | none (only one strong adapter) | 1 quota | ~0.5h | 1 | low | ❌ |
| E. v11 rejection-sampling self-distill | unknown | medium | multi-session sampling | many | many | high | ❌ |
| F. confirm/select v14 + archival | 0.85 | locks score | none | 0 | 0 | none | ✅ with A |

### 9b. Additional directions surfaced in PR #106 review
| Option | Idea | Assessment | Recommend? |
|---|---|---|---|
| G. **Mine real equation/cryptarithm rules → expand solver** | the C-solver's fixed rewrite library only matched **0.4%** of real `equation` prompts; reverse-engineer the actual per-operator rules from train.csv to lift coverage, yielding *verified real-prompt* cryptarithm CoT (vs synthetic) | The strongest untried cryptarithm angle: real, verified, on-distribution. Caveat B8 (single-cat ≠ total) still applies. ~3–4h build + 1 kernel | ⚠ worth a slot if C1/C2 don't beat 0.85 |
| H. **Better merge — only if a 2nd *strong* adapter appears** | T7 failed because it merged strong+weak (dilution, INS-003). A merge can only help among *comparable, complementary* members | We have exactly **one** strong adapter (v14). If an in-flight b/c kernel lands ≈0.85 on *different* data, a v14+that merge becomes worth trying. **NB: the submission is a SINGLE rank-≤32 LoRA — the eval loads one `lora_path`; "a collection of adapters" is only submittable by merging them into one (= T7), not as an ensemble.** | ⚠ conditional on a 2nd strong adapter |
| I. **Teacher-model distillation of CoT** | use a strong external reasoner to generate CoT toward the *known* train answers, SFT the Nemotron LoRA on it (richer than the base-model self-distill of T5/v11), esp. for bit/equation where the deterministic solver coverage is thin | Plausible higher-quality hard-category data. The adapter stays a Nemotron LoRA (you distill *outputs*, not weights). ⚠ verify comp rules permit external-model-generated training data; needs a capable teacher (local coder LLMs aren't strong puzzle reasoners) | ⚠ verify rules first; medium-effort |

## 10. Post-audit decision (user-directed)
With **~33h** actually remaining (clock 2026-06-14 14:42 UTC) — not ~10h — the timeline objection to option C
relaxes. User approved a best-effort last-window swing: **2 pushes per account (harry + may) attempting B and C**,
submit on completion. Safety: each is a fresh rank-32 LoRA on the v14 backbone (no repack); the C solver keeps only
prompts where its computed answer **matches the train.csv ground truth** (cannot poison); LB keeps the max so 0.85 is
never at risk. Variants + results tracked in `tracking.md` / `submissions.md`.
