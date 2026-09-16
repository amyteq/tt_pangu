# Tracking — nemo

> English consolidation of GitHub issue **#86** ("Nemotron Model Reasoning Challenge — strategy & tracking hub").
> Original Chinese tables preserved verbatim in [`tracking_zh.md`](./tracking_zh.md). Future status updates
> live here, not in issue #86. `unknown` = not in available evidence.
>
> **Authority (ADR-0022 §3).** This file is rank 3: narrative, reasoning, experiment history
> and LB writeups. It is **not** where `state` / `status` / `best` live — those are rank 1,
> `competition.yaml`, and if this file disagrees with it, this file is stale. "Status updates
> live here, not in issue #86" means the *narrative* moved out of the issue; the state fields
> were always the YAML's.

## Current snapshot (updated 2026-06-15)
- Best **own real-training: 0.86 (`nemo-merge-soup` = SVD rank32 of v14(0.4)+c1(0.3)+b1(0.3))** — three comparable+complementary 0.85 adapters merged; broke the v14 0.85 ceiling (+0.01, compliant own-work, D3). Top **~0.90** (refreshed 2026-06-15), base ~0.47. Deadline **2026-06-15 23:59 UTC**. Quota 5/team/day.
- **T12 hard-val ranking (2026-06-15):** soup 0.764 = v14 0.764 (both ace hard cipher/bit) ≫ base 0.389 ≈ c1 0.389 > v15 0.333 > c2 0.278. The 0.86 soup is **robust, not diluted**; the CoT/synth-augmented adapters (c1/c2/v15) **regress the hardest cipher/bit to at/below base**; `equation` is unsolved by all (≤2/16). See `submissions.md`.
- Final-sprint individual runs ≤ soup: c1 0.85, b1 0.85, b2 0.84, c2 0.83; only the soup exceeded v14. Earlier strong+weak merge (T7=0.82) and high-dose synth (v15=0.84) regressed.
- **Decision: hold the 0.86 soup to close.** Final private-LB selection = **soup (0.86) + v14 (0.85)** (v14 ≫ c1 on hard-val despite equal public LB). Cipher-heavy v11 stage-2 SFTs stood down (a2 corpus 94% cipher → same regression risk). Remaining slots unused.
- **LB25/LB80/LB92 borrow campaign (2026-06-20, late window):** ran v16-evalfix (LB25), v17-discovery (LB80 A), v18-stable (LB92). **None beat 0.86** — v16 0.832/0.828 (bit-CoT+replay diluted), v17 0.840/0.848 (equation bounded), v18 0.844/0.848 (grad-clip 1.5 ~neutral). All confirm their plans' own dilution/bounded-equation risk notes; **soup/eq-aug 0.86 hold**. Two LB80 sub-results were genuine wins regardless of LB: (1) **cracked the equation cipher** = per-operator digit-string rules — but the team's `versions/lb1-v1/rules24.py` (95% deduce, branch `exp/nemo-postlb1-v1`) is the superior cracker, use it for a v17.1; (2) **v17-dpo deferred** (needs external sm_90+ GPU, #83). v18 LEVER 2 per-char tokenization **dropped as infeasible** (adapter-only grader uses base tokenizer).
- Last updated: 2026-06-20.

## Preserved issue tracking tables (translated → English)

### Table 1 — Open Discussions (all confirmed 2026-06-12)
| # | Topic | Decision / confirmation |
|---|---|---|
| D1 | Submit authorization for the B direction (firefly2006) after completion | ✅ Claude may submit directly as firefly2006 |
| D2 | GPU budget for v11 rejection-sampling self-distillation | ✅ approved |
| D3 | Scope of SVD merge (v13) | ✅ merge **only our own** adapters (avoid repack dispute) |
| D4 | Priority of v12 Unsloth route | ✅ confirmed (offline wheels → seq8192 + more steps) |
| D5 | External GPU resource selection | ✅ decided in #83 |
| D6 | Timing of #85 YAML + user-pool work | ✅ **do it post-competition** (scoring first) |
| D7 | Inline issue-update mechanism | ✅ edit comments inline; inplace-update the 3 tables; separate comment only for major results |
| D8 | T10 uses 4 third-party public Kaggle datasets (real fresh training, not repack) | ✅ approved |
| D9 | GPU allocation after A/B | ✅ A→T10 (public 0.87 replay), B→T4 v10; seq8192; keep ≤8h to avoid timeout |

### Table 2 — TODO / directions (T1–T13)
| ID | Direction | Current status | Evidence |
|---|---|---|---|
| T1 | A: nemo-cot-ctx4k (harrysun2006) — masked CoT, seq4096, 580 steps, loss 0.147 | ✅ **LB 0.67** | issue #86 comment 0 |
| T2 | B: nemo-cot-ctx2k (firefly2006) — seq2048, 583 steps, loss 0.186 | ✅ LB 0.42 (negative-sample lesson: right-trunc cut `\boxed{}`) | issue #86 comment 0 |
| T3 | Use daily 5-submission quota | 🟢 ongoing (per-day best banked) | issue #86 |
| T4 | v10: rule-aware CoT data (`firefly2006/nemo-rule4k-v10`) — 8000 ex, 558 steps, loss 0.93, held-out 3/4 | ✅ LB 0.59 (merge-pool member) | issue #86 T4 |
| T5 | v11: rejection-sampling self-distillation (`nemo-v11-sample-a2`/`-b`) | 🟡 stage-1 SAMPLE ran 2026-06-15 (vLLM via aimo-3-utils-0171; a2 → 404 verified CoTs, 94% cipher). Stage-2 SFT (`nemo-v11-sft-d`) **built but stood down** — T12 shows cipher-heavy augmentation regresses hard cats | issue #86 T5 |
| T6 | v12: Unsloth ~1 epoch / seq8192 | 📝 planned (superseded by v14) | issue #86 T6 |
| T7 | multi-adapter SVD merge (`harrysun2006/nemo-merge-t7`) — SVD rank32(1.0·v14+0.25·ctx4k+0.25·v10) | ✅ LB 0.82 (regression; **route closed**) | issue #86 comment 3; PR #94 |
| T8 | time-budget mechanism (v9 timeout fix) | ✅ done (in A/B) | issue #86 T8 |
| T9 | per-comp YAML + user-pool tooling (#85) | 🗓 post-competition (D6) | issue #86 T9 |
| T10 | **v14: public 0.86/0.87 replay recipe** (`harrysun2006/nemo-replay-v14`) — seq8192, 254/254 steps, CCE + MoE 128 tying + lm_head/in_proj/out_proj, loss ~0.05 | ✅ **LB 0.85 (best, +0.18)** | issue #86 comment 2; PR #90 |
| T11 | v15: cryptarithm synth + v14 backbone (`harrysun2006/nemo-synth-v15`) — 2640 ex (cryptarithm 60%), 337/337 steps, loss ~0.002, CoT-answer 1930/1930 | ✅ LB 0.84 (did not exceed v14) | issue #86 comment 4; PR #95 |
| T12 | official metric localization + min-logprob hard-val set (`harrysun2006/nemo-t12-hardval`) | ✅ **done 2026-06-15** — ported official scorer + min-logprob hardest-72 set; ranked adapters: soup/v14 0.764 ≫ base/c1 0.389 > v15 0.333 > c2 0.278. Basis for the hold-0.86 + soup+v14 selection | issue #86 T12 |
| T13 | fix held-out eval truncation (`EVAL_MAX_NEW` 512→7680 + `EVAL_TIME_CAP`=1800s) | ✅ done (in v10) | issue #86 T13 |

## Experiment / idea progress
- **Done & scored:** ctx4k (0.67), ctx2k (0.42), v10 (0.59), v14 (0.85), t7 merge (0.82), v15 synth (0.84), c1 (0.85), c2 (0.83), b1 (0.85), b2 (0.84), **soup v14+c1+b1 (0.86, best)**.
- **Done (eval):** T12 official-metric + min-logprob hard-val ranking — confirmed soup/v14 robust, augmented adapters regress hard cats.
- **Validated route:** **model-soup of comparable+complementary adapters** beats each member (0.85→0.86).
- **Stood down:** v11 stage-2 SFT (T5, cipher-heavy → T12 regression risk); v12 Unsloth (T6, superseded by v14); T9 tooling (post-comp, D6); GRPO/RL (not run).
- **Closed routes:** T7 strong+weak merge (dilutes, 0.82); high-dose category-weighted synth (single ≠ total); CoT/synth augmentation degrades the hardest cipher/bit (T12).


## Kernel push status
| Kernel | Account | LB | State |
|---|---|---:|---|
| nemo-cot-ctx4k | harrysun2006 | 0.67 | pushed + evaluated |
| nemo-cot-ctx2k | firefly2006 | 0.42 | pushed + evaluated |
| nemo-rule4k-v10 | firefly2006 | 0.59 | pushed + evaluated |
| nemo-replay-v14 | harrysun2006 | 0.85 | pushed + evaluated |
| nemo-merge-t7 | harrysun2006 | 0.82 | pushed + evaluated |
| nemo-synth-v15 | harrysun2006 | 0.84 | pushed + evaluated |
| nemo-solver-c1 | harrysun2006 | 0.85 | pushed + evaluated (2026-06-15) |
| nemo-solver-c2 | harrysun2006 | 0.83 | pushed + evaluated (2026-06-15) |
| nemo-synth-b1 | firefly2006 | 0.85 | pushed + evaluated (2026-06-15) |
| nemo-synth-b2 | firefly2006 | 0.84 | pushed + evaluated (2026-06-15) |
| **nemo-merge-soup** | harrysun2006 | **0.86** | pushed + evaluated (2026-06-15, **best**) |
| nemo-v11-sample-a2 / -b | harrysun2006 / firefly2006 | — | data-gen (verified-CoT corpus, vLLM); no submission |
| nemo-t12-hardval | harrysun2006 | — | eval harness (hard-val ranking); no submission |
| nemo-v16-evalfix | harrysun2006 | 0.832 | pushed + evaluated (2026-06-20, LB25 borrows; < v14) |
| nemo-v17-discovery | firefly2006 | 0.840 | pushed + evaluated (2026-06-20, LB80 Part A; equation bounded) |
| nemo-v18-stable | harrysun2006 | 0.844 | pushed + evaluated (2026-06-20, LB92; ~v14-neutral) |

> ✅ **Refreshed 2026-06-15** via read-only Kaggle API (`kaggle competitions submissions`, both accounts). All listed submissions are `COMPLETE`; private LB not released. See `submissions.md` for the full confirmed table + T12 ranking.

## Submission / LB status
- Best own-work public LB: **0.86** (`nemo-merge-soup`, 3-way SVD of own adapters — real training, no repack). Single-adapter best **0.85** (`nemo-replay-v14`). Leaderboard top **~0.90** (2026-06-15). Private LB `unknown` (not released). Final private-LB selection: **soup (0.86) + v14 (0.85)**. Full confirmed table: `submissions.md`.

## Version map
| LB | Version | Recipe summary |
|---:|---|---|
| 0.47 | identity | untrained adapter (base) |
| 0.61 | v5 | bare-answer SFT |
| 0.44 | v6 | CoT but loss over prompt+padding (bug) |
| 0.65 | v7 | CoT + response-only masking |
| 0.67 | ctx4k (T1) | masked CoT, seq4096 |
| 0.42 | ctx2k (T2) | masked CoT, seq2048 (truncation bug) |
| 0.59 | v10 (T4) | rule-aware CoT (rule + long-CoT mix) |
| 0.85 | v14 (T10) | public replay recipe: CCE + MoE tying + lm_head/Mamba LoRA + seq8192 + huikang corpus + replay-math |
| 0.82 | t7 | SVD merge v14+ctx4k+v10 → rank32 (strong+weak, regressed) |
| 0.84 | v15 (T11) | v14 backbone + cryptarithm-weighted synth (~24%) |
| 0.85 | c1 | v14 backbone + 1800 verified real-prompt solver CoT (hard-val 0.389) |
| 0.83 | c2 | v14 backbone + 1000 verified CoT (hard-cat emphasis; hard-val 0.278) |
| 0.85 | b1 | v14 backbone + cryptarithm-only synth (~9%) |
| 0.84 | b2 | v14 backbone + cryptarithm+bit synth (~11%) |
| **0.86** | **soup** | **SVD rank32 of v14(0.4)+c1(0.3)+b1(0.3) — comparable+complementary own-work model soup (BEST; hard-val 0.764)** |
| 0.83 | v16-evalfix | v14 backbone + eval-parity preflight + verified bit CoT (157) + min-logprob replay (hardest 15%) — **LB25 borrows; mild dilution** (2026-06-20) |
| 0.84 | v17-discovery | v14 backbone + equation discovery-CoT (cracked per-operator rule family, 180 plaintext rows) — **LB80 Part A; equation stays bounded** (2026-06-20) |
| 0.84 | v18-stable | v14 backbone + grad-clip 1.5 + verified synth equation (cracked rule family, 800) — **LB92; ~v14-neutral** (per-char tok dropped) (2026-06-20) |

## T12 hard-val per version (post-comp consolidation, 2026-06-16)

> The T12 official-metric + min-logprob hard-val harness (`harrysun2006/nemo-t12-hardval`) was **built
> 2026-06-15**, so it only ran on the *final-candidate* adapters; everything earlier is **not run** (the
> harness postdates them). Hard-val = hardest-72 (16 each bit/equation/cipher, 8 each numeral/gravity/unit),
> greedy decode `max_tokens=7680, temp=0`, `\boxed{}` extractor, exact-or-1e-2. `not run` ≠ a bad score.
> **The hard-val is a hard-TAIL proxy, not the LB** — it understates adapters weak only on the hardest slice
> (eq-spec 0.167 hard-val vs 0.85 LB). Trust the LB aggregate; treat hard-val as a hard-tail hint (INS-002).

| version | public LB | private LB | T12 hard-val | hard-val evidence |
|---|---:|---:|---|---|
| identity | 0.47 | 0.52 | not run | harness postdates |
| v5 | 0.61 | 0.66 | not run | harness postdates |
| v6 | 0.44 | 0.45 | not run | harness postdates |
| v6′ | 0.47 | 0.46 | not run | harness postdates |
| v7 | 0.65 | 0.66 | not run | harness postdates |
| ctx4k (T1) | 0.67 | 0.66 | not run | harness postdates |
| ctx2k (T2) | 0.42 | 0.46 | not run | harness postdates |
| v10 (T4) | 0.59 | 0.64 | not run | harness postdates |
| **v14 (T10)** | 0.85 | 0.84 | **0.764** | T12 v2 (bit 14/16, eq 2/16, cipher 15/16, n/g/u 8/8) |
| t7 merge | 0.82 | 0.80 | not run | route closed before T12 |
| v15 (T11) | 0.84 | 0.84 | **0.333** | T12 v2 (regresses hard cipher/bit to ≤ base) |
| c1 | 0.85 | 0.85 | **0.389** | T12 v2 (cipher 3/16 < base 8/16 — augmentation dilutes hard tail) |
| c2 | 0.83 | 0.83 | **0.278** | T12 v2 (hard-cat-weighted → worst hard-val) |
| b1 | 0.85 | 0.84 | not run | not in T12 v2 ranking |
| b2 | 0.84 | **0.85** | not run | not in T12 v2 ranking (the may hedge that aged +0.01) |
| **soup** | **0.86** | 0.85 | **0.764** | T12 v2 (tied v14, best+robust; SELECTED) |
| surgery A | 0.86 | 0.84 | unknown | a surgery-run note reported hard-val 0.744 vs soup 0.731 on a *separate* comparison set; not in the canonical T12 v2 ranking |
| andy279 | 0.81 | 0.81 | not run | external-teacher CoT; regressed on LB |
| v11 self-distill | 0.80 | 0.82 | not run | rejection-sampled CoT; regressed on LB |
| base (no adapter) | — | — | **0.389** | T12 v2 anchor (bit 0/16, eq 0/16, cipher 8/16) |
| **EQ1 = eq-spec** | 0.85 | 0.85 | **0.167** | EQ §8.4 (answer-shortcuts under hard-tail uncertainty; LB 0.85 ≫ hard-val — INS-002 lesson) |
| **EQ2 = eq-aug** | **0.86** | **0.86** | **0.194** | EQ §8.4 (best own private; still hard-tail-weak → can't soup) |
| **EQ3 = eq-hidose** | 0.84 | 0.84 | unknown | not separately hard-val'd |
| **EQ4 = eq-aug-hidose** | 0.85 | 0.82 | unknown | not separately hard-val'd |
| soup_v2 (eq-aug merge) | 0.85 | 0.85 | unknown | SVD(0.86-soup×0.6 + eq-aug×0.4); dilutes < both parents |
| **v16-evalfix** (LB25) | 0.832 | 0.828 | not run (no local GPU) | LB25 borrows: eval-parity preflight (measurement-only) + verified bit CoT 157 + min-logprob replay hardest 1198/37 steps; **−0.018 pub / −0.012 priv vs v14 → dilution (plan's dominant risk confirmed)** |
| **v17-discovery** (LB80 A) | 0.840 | 0.848 | not run (no local GPU) | equation discovery-CoT, cracked per-operator string-op family, 180 verified plaintext-digit rows (dose 0.15); ciphered 82% uncracked; **pub −0.01 / priv +0.008 vs v14 → equation bounded (no transfer from plaintext subset)** |
| **v18-stable** (LB92) | 0.844 | 0.848 | not run (no local GPU) | grad-clip 1.5 (variance) + verified synth equation (cracked rule family, 800, ratio 0.1); per-char tok dropped (infeasible, adapter-only grader); **pub −0.006 / priv +0.008 vs v14 → ~neutral; least-harmful borrow** |

## EQ1..EQ4 analysis (post-deadline equation-frontier grid, late window 100/team/day)

> The equation category was the only unsolved one (≤2/16 hard-val for *every* competition adapter incl. the
> 0.86 soup). EQ-0 proved `equation` is a single **global 5-char→1–4-char base-36 cipher**; 3 crack rounds
> (EQ-2′) eliminated the entire simple-algebraic space → **strong cipher, not closed-form-recoverable** from
> the 7,748 known pairs. So the empirical bet (EQ-3) was: SFT the v14 backbone on the *real* equation pairs and
> see how far coverage-memorisation goes. "EQ1..EQ4" below = the 4 SFT grid runs (coverage × dose). Best-own
> baseline for the delta column = the **0.86 / 0.85 soup** (selected competition best). Full: `equation-frontier.md §8`.

| run | hypothesis | change vs baseline (v14 replay) | hard-val | public LB | priv LB | Δ vs best own (soup 0.86/0.85) | likely reason LB didn't jump | lesson |
|---|---|---|---:|---:|---:|---|---|---|
| **EQ1 eq-spec** | SFT the 1,555 real equation *query answers* (~16% dose) teaches the global cipher | + 1,555 query→`\boxed{}` woven into v14 | 0.167 | 0.85 | 0.85 | pub −0.01 / priv 0.00 | only the *query answer* of each prompt is supervised (4 in-context examples are masked context); equation ≈ 1/9 of the test, and only the seen-input fraction is learnable | query-only coverage = no aggregate gain; equation stays at its cipher-bounded floor |
| **EQ2 eq-aug** | *Rotate* every in-context example into a supervised query → ~5× more real pairs (7,814) | + 7,814 rotated real input→output pairs (×1) | 0.194 | **0.86** | **0.86** | pub 0.00 / priv **+0.01** | coverage captures the ~38% of hidden equation queries whose symbols are all-seen; the unseen-input majority is a strong cipher (uninferable) → ceiling is partial, not full | **coverage is the lever** for a global-function/lookup category: SFT on *all* real pairs (rotate examples→targets), single epoch → best own private |
| **EQ3 eq-hidose** | More *dose* of the same 1,555 (×3) drills the cipher harder | 1,555 query answers repeated ×3 (~40%) | unknown | 0.84 | 0.84 | pub −0.02 / priv −0.01 | no new information (same 1,555 pairs reweighted); over-weighting equation crowds out the replay backbone → mild regression | **dose without coverage hurts** — repetition adds no signal, dilutes the recipe |
| **EQ4 eq-aug-hidose** | Max coverage **and** max dose (7,814 ×2) | 7,814 rotated pairs repeated ×2 | unknown | 0.85 | **0.82** | pub −0.01 / priv **−0.03** | over-dosing even the *good* coverage data overfits — private drops far more than public (classic overfit signature) | the **sweet spot = full coverage at a single epoch**; ×2 is past it |
| soup_v2 (eq-aug merge) | Soup eq-aug into the 0.86 soup to keep its robustness + add coverage | SVD(0.86-soup ×0.6 + eq-aug ×0.4) → rank32 | unknown | 0.85 | 0.85 | pub −0.01 / priv 0.00 | the soup lever needs **hard-tail-robust** members; eq-aug is hard-tail-weak (hard-val 0.194), so merging imports its shortcutting and averages out the equation coverage | **eq-aug does not soup** — the coverage gain lives only standalone |

**Verdict:** `equation` is **partially addressable, not solved**. The best lever — `eq-aug` (full real-pair
coverage, single epoch) — reaches **0.86 / 0.86** (best own private of the whole campaign) by memorising the
seen-input fraction, but the unseen-input majority is a strong cipher and stays uninferable. The frontier is
**bounded**, not open; nothing reaches the cipher's unseen tail without cracking the rule (proven intractable
from samples, EQ-2′). Why LB didn't jump: equation is ≈ 1/9 of the test and only a fraction of it is learnable,
so the maximum aggregate headroom from a perfect equation memoriser is small, and even that only covers seen inputs.

## lb1-v1 — post-LB1 method implementation (2026-06-20)

> Reproducible CPU implementation of the 1st-place method under
> `versions/lb1-v1/` (branch `exp/nemo-postlb1-v1`). The competition is closed
> for ranking; this is method-validation + reusable methodology. LB1 is a
> *training-data* method, so a real `lb1-v1` LB number needs a GPU-trained
> rank≤32 adapter — that training + the guarded late-submission are a documented
> handoff (the preflight gate blocks the submit until a completed run yields a
> valid `submission.zip`). Held-best protected: soup 0.86/0.85, v14 0.85,
> eq-aug 0.86/0.86.

| check | result | vs writeup |
|---|---|---|
| signature catalog (100×100 × 22 non-join rules) | **4,205 signatures — EXACT**; `ABCCCDD`→15 (add1/flip_add8/flip_add+1 6), slot strings byte-exact | 4,205 ✓ |
| **equation-numeric re-probe** (real train.csv) | **deduce 566/596 = 95.0%**, guess 65/136 = 47.8%; split 596/136 exact | 95.5% / 52.9% |
| HEX compression | `1101000001`→`341` exact; ~75% char cut | matches |
| bit rule-sequence catalog | pure enum **857,692 seqs / 115,826 functions** — overshoots; LB1's 5,238 is **train.csv-tuned**, not prose-reproducible. Repair (Hamming-NN) verified (recovers Hamming-3 corruption). | ≈5,238 (not reproduced) |

**Equation verdict qualified.** The EQ-0/EQ-2′ "global cipher = unsolvable"
conclusion is **over-generalized**: it holds for the *guess* (unseen-operator)
subset (~48–53%), but **equation-numeric *deduce* is 95% solvable per-prompt** via
the 24-rule inventory + Observation 1/2 — not one global function. This matches the
LB1 coverage table and refutes our frontier call for the deduce subset (cf.
`gap_analysis.md`, `equation-frontier.md`). The decisive remaining gap to 0.92 is
cryptarithm + bit *volume* (LB1: 220k+140k synth, ~170h single-GPU), reproducible
only as a down-scaled method-validation run post-comp.

## lb3-v1 — post-LB3 (3rd place) method implementation (2026-06-20)

> Reproducible **CPU** implementation of the 3rd-place method (Private 0.900) under
> `versions/lb3-v1/` (branch `exp/nemo-postlb3-v1`). **Competition closed 2026-06-15**
> → no live submission (preflight gate blocks: closed comp + no completed GPU run →
> no `submission.zip`). This validates the *mechanism* (CSP cryptarithm, hex bit
> compression, two-stage drills, private-tracking validation, equation-deduce
> premise), not LB3's full score. Held-best protected: soup 0.86/0.85, eq-aug 0.86/0.86.

| check | result | vs writeup |
|---|---|---|
| **equation-numeric re-probe** (real `train.csv`, 732 prompts) | **deduce 566/596 = 95.0%**, guess 65/136 = 47.8% | 93.3% / ~57% |
| **CSP cryptarithm** (synthetic, n=150; lookup→intersect→anchor→bounded backtracking) | `*` deduce **100%** (full-map recovery 100%); `+` 98%; `-` 94.7%; `*` guess 94% | mechanism ✓ (LB3 within-budget 24.2% on harder real cryptarithm) |
| **bit HEX+tail-2-bit** compression + solver (n=300) | solved **100%**; **−23.4%** trace tokens | ≈ −25% ✓ |
| **numeric 13-op** solver (n=300) | deduce **98.3%**; guess 11% (synthetic guess adversarial — no generator family co-occurrence) | deduce 93.8% ✓ |
| stage-1 **memorize drills** (16 packed/sample, request masked) | 28% chars masked; recall rows rendered as `(a,b)->p` tuples | masked-drill design ✓ |
| **private-tracking validation** self-check | PASS — stratified 10% hold-out (all cats), leakage exclusion, perfect-trace-rate, adapter rank=32≤32 + zip-root preflight | design ✓ |

**Equation premise — 2nd independent refutation.** The real-data re-probe (95.0% deduce)
confirms equation-numeric *deduce* is per-prompt-operator solvable, not a global cipher;
matches LB1 (95.5%) and LB3 (93.3%). Our `equation-frontier.md` EQ-0/EQ-2′ verdict is
over-generalized — it holds only for the *guess* (unseen-operator) subset (~48%). The
decisive remaining gap to 0.900 is the **two-stage memorize→execute training** + cryptarithm
**volume** (LB3 ~58 GPU-h), reproducible only as a down-scaled GPU method-validation run (handoff).

## lb5-v1 — post-LB5 (5th place) method implementation (2026-06-20)

> Reproducible **CPU** implementation of the 5th-place method (Private 0.900,
> *"infinite generator + iterative LoRA averaging"*) under `versions/lb5-v1/`
> (branch `exp/nemo-postlb5-v1`). **Competition closed 2026-06-15** → no live submit
> (preflight gate blocks; guarded-submit BLOCKED decision logged to `.agent/kca/audit.jsonl`).
> Validates the *mechanism* (no-leakage CV, ternary raw-bit lift, 2-world equation solver,
> soup-stability proxy). Held-best protected: soup 0.86/0.85, eq-aug 0.86/0.86.

| check | result | vs writeup |
|---|---|---|
| **equation re-probe** (real `train.csv`, 732 prompts) | **deduce 566/596 = 95.0%**, guess 65/136 = 47.8% | oracle ~95-96% / ~40% |
| **LB5 equation solver** (2-world/4-family/13-rule; synthetic n=300) | deduce **99.7%**; guess 20.7% (synthetic guess adversarial) | mechanism ✓ |
| **ternary raw-bit solver** (15 primitives = 8 binary + 7 ternary; n=300) | binary **100%**, ternary **100%**; **7-example cut loses nothing** | bit oracle 94.3% ✓ |
| **tokenizer probe** (HEX-vs-raw-bits merge risk) | flags merged `5A`/`AB` HIGH; spaced raw bits / spaced hex safe | LB5 negative lesson ✓ |
| **no-leakage generator** | fits train stats (bit 1602 / eq 1555); no-leakage PASS vs 9500 prompts; unique answers | honest-CV discipline ✓ |
| **private-tracking validation** self-check | PASS — no-leakage, oracle solvability, soup-stability proxy (deterministic), adapter rank=32≤32 + zip-root preflight | design ✓ |

**Equation premise — 3rd independent refutation.** The real-data re-probe (95.0% deduce)
is the 3rd confirmation (after LB1 95.5%, LB3 93.3%) that equation-numeric *deduce* is
per-prompt-operator solvable, not a global cipher; our `equation-frontier.md` verdict holds
only for the *guess* subset (~48%). LB5's distinct contribution vs LB1/LB3: it reaches 0.90
**without** cryptarithm (7.9%) by maxing bit (ternary) + equation + trivials and stabilizing
with **iterative LoRA averaging / multi-seed soup** (the 0.90→0.92 gap remains cryptarithm).

## lb6-v1 — post-LB6 (2nd public / 6th private) method implementation (2026-06-20)

> Reproducible **CPU** implementation of the LB6 method under `versions/lb6-v1/`
> (branch `exp/nemo-postlb6-v1`). **Competition closed 2026-06-15** → no live submit
> (preflight gate blocks; guarded-submit BLOCKED decision logged to `.agent/kca/audit.jsonl`).
> Validates the *mechanism* (per-domain DUMMY-masking attribution, template bit, DFS
> cryptarithm, bit/cryptarithm trade-off CV). Held-best protected: soup 0.86/0.85, eq-aug 0.86/0.86.

| check | result | vs writeup |
|---|---|---|
| **equation re-probe** (real `train.csv`, 732 prompts) | **deduce 566/596 = 95.0%**, guess 65/136 = 47.8% | guess 92.6% |
| **DUMMY-masking per-domain attribution** (signature lever; **fixes B8**) | isolates each domain's signal; non-target rows emit `\boxed{DUMMY}`; 0.01 LB ≈ 3 problems | attribution ✓ |
| **template bit solver** (shl/shr/rotr × pairwise/ternary; n=200) | pairwise+shift **99.5%**, ternary **100%** | bit 1508/1602 = 94.1% ✓ |
| **DFS cryptarithm** (reversed search + leading-zero/units/equation-sorting pruning) | `*` **100%**, `+` 93% (reversed pass = fallback for real reversed-structure) | deduce 240/654 = 37% |
| **LB6 equation solver** (add/sub/mul + **maxmodmin**; n=300) | deduce **100%**; guess 47.7% (synthetic) | guess 92.6% |
| **bit/cryptarithm trade-off CV** | predicts a +0.082 bit-CV drop when doubling cryptarithm → "double bit to hold CV" | LB6's selection regret ✓ |
| **validation** self-check | PASS — full-train-as-validation + DUMMY probe + perfect-trace-rate + rank=32≤32 preflight | design ✓ |

**Signature lever — DUMMY-masking attribution (B8 fix).** LB6 isolates a single domain's
signal by emitting that domain's real CoT and `I will ignore this problem\boxed{DUMMY}`
for all others. This is the per-domain attribution tool we've lacked (our recurring B8:
"single-category gain ≠ total gain"); run offline here since the comp LB is gone. The
equation re-probe (95.0% deduce) is another independent refutation of the global-cipher verdict.

## lb10-v1 — post-LB10 (Public 0.860 / Private 0.880) method implementation (2026-06-20)

> Reproducible **CPU** implementation of the LB10 method under `versions/lb10-v1/`
> (branch `exp/nemo-postlb10-v1`). **Competition closed 2026-06-15** → no live submit
> (preflight gate blocks; guarded-submit BLOCKED decision logged to `.agent/kca/audit.jsonl`).
> Validates the *mechanism* ("improve the teacher" oracle lift, rotate/shift key-table
> bit reasoner, oracle-vs-fidelity + logprob diagnostics). Held-best protected: soup 0.86/0.85, eq-aug 0.86/0.86.

| check | result | vs writeup |
|---|---|---|
| **equation re-probe** (real `train.csv`, 732 prompts) | **deduce 566/596 = 95.0%**, guess 65/136 = 47.8% | deduce 93.1% |
| **rotate/shift key-table bit reasoner** (single-operand; n=200) | 8-ex **96.5%**, 16-ex **100%**; **oracle ~98–100%** once all 8 keys covered | "improve the teacher" → ~98% ✓ |
| **LB10 equation solver** (frequency-deduce + two-axis guess; n=300) | deduce **99.3%**; guess 48.3% (synthetic) | deduce 93.1% ✓ |
| **oracle-vs-fidelity + logprob** diagnostics | split reported (imitation gap isolated from oracle ceiling); fragile-trace tail flagged for priority-2× | diagnostic design ✓ |
| **keep-failures + select-by-validation** | unsolved teacher traces retained (not filtered); validation self-check PASS (rank=32≤32 preflight) | data discipline ✓ |

**LB10's distinct contributions:** the **"improve the teacher"** discipline (raise per-category
oracle coverage first — the score ceiling), a **rotate/shift key-table bit reasoner**
(`out[i]=F(rotl(x,a),shl(x,b),shr(x,c))`, oracle ~98–100% once examples cover all 8 keys),
and the **oracle-ceiling-vs-model-fidelity + logprob-learnability** split that separates the
teacher ceiling from the imitation gap. Two A/Bs wired for a future GPU run: **keep-failures
vs verified-only** (challenges our c1/c2 filter) and **LoRA-merge** (LB10 reported merge failed).
The equation re-probe (95.0% deduce) is the 5th independent refutation of the global-cipher verdict.

## lb13-v1 — post-LB13 (13th place) method implementation (2026-06-20)

> Reproducible **CPU** implementation of the 13th-place method (teacher oracle 89.4%)
> under `versions/lb13-v1/` (branch `exp/nemo-postlb13-v1`). **Competition closed
> 2026-06-15** → no live submit (preflight gate blocks; guarded-submit BLOCKED decision
> logged to `.agent/kca/audit.jsonl`). Validates the *mechanism* (sharpest equation
> structure, robust aggregation, keep-failures rebalance, 3-input bit verify). Held-best
> protected: soup 0.86/0.85, eq-aug 0.86/0.86.

| check | result | vs writeup |
|---|---|---|
| **equation re-probe** (real `train.csv`, 732 prompts) | **deduce 566/596 = 95.0%**, guess 65/136 = 47.8% | 95.3% / 50.7% |
| **LB13 equation solver** (4-family excl. + global majority-vote reversal; synthetic n=300) | deduce **100%**; guess 84.7% (synthetic exclusivity cleaner than real) | mechanism ✓ |
| **robust vs strict aggregation under transcription noise** | **robust 100% vs strict 54%** — the LB13 keep-noisy-traces lever, demonstrated | robustness ✓ |
| **3-input bit verifier** (MAJ/XNOR3 + bit-pos search + left-edge fallback; n=300) | solved **100%** | bit oracle 89.7% ✓ |
| **keep-failures 1:1 rebalance** | 4.26:1 → **1.00:1** (all teacher-incorrect kept) | data discipline ✓ |
| **validation** self-check | PASS — teacher oracle, robust>strict, rebalance, perfect-trace-rate, adapter rank=32≤32 preflight | design ✓ |

**Equation premise — 6th independent refutation.** The real-data re-probe (95.0% deduce)
again confirms equation-numeric *deduce* is per-prompt-operator solvable (after LB1/LB3/LB5,
plus LB6/LB10). LB13's distinct contributions: the **global majority-vote reversal +
robust ≥1-match aggregation** equation model (batch-best guess 50.7%), **3-input bit
verification**, and **keeping teacher-incorrect traces (1:1 rebalance)** — which challenges
our verified-only c1/c2 filter (A/B is the recommended GPU follow-up).

## lb25-v1 — post-LB25 (huikang Progress-Prize improvements) method implementation (2026-06-20)

> Reproducible CPU packaging of the LB25 method under `versions/lb25-v1/` (branch
> `exp/nemo-postlb25-v1`). **Already realized:** the LB25 `next_version_plan`'s version is
> `v16-evalfix`, trained + submitted 2026-06-20 → **Public 0.832 / Private 0.828, below the
> 0.86 held-best ("hypothesis NOT supported")**; this dir is the clean reusable packaging of
> the five levers, not a new method expected to beat 0.86. Held-best untouched.

| LB25 lever | module | result |
|---|---|---|
| #1 eval/submission parity (headline) | `eval_parity.py` | reusable GPU-free audit of the boxed-prompt bug (= our B4/INS-002); measurement-only |
| #2 equation reversal symmetry | `eq_reversal.py` | **573/596 = 96.1%** single-mode (Obs.1) on real train.csv; **47.6% search reduction** — the earliest of 7 confirmations equation is per-problem-structured |
| #3/#4 easy-cat + cipher-prefix synth | `easy_cat_synth.py` | 240/240 extraction round-trip; no-regression guard only (easy cats already ceiling) |
| #5 reorganized bit CoT | `bit_cot.py` | own-solver-verified, grader-faithful `bit_verify`; the realized v16-evalfix solver |
| min-logprob replay (ours) | config | hardest-residual replay, ≤15% dose |

Shared pieces (`rules24`, `eq_reprobe`, `hex_compress`, `scorer`, `validate`,
`package_submission`) reused from the lb1-v1 batch. The LB25 method's real LB result already
exists (v16-evalfix); a fresh `lb25-v1` GPU run reproduces a known below-best number.

## Evidence links
- GitHub issue #86 (body + comments 0–4) — original hub.
- `tracking_zh.md` — original Chinese tables verbatim.
- `worklogs/nemo.md`, `worklogs/nemo2.md`; `work/00.nemo.md` (analysis); `notes_zh.md` (EN digest).
- PRs #90 (v10+v14), #94 (t7), #95 (v15); kernels under `./kernels/`.
