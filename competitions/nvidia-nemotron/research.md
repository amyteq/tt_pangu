# Research & post-competition directions — nemo

> Literature scan (2026-06-15) + design for the post-competition experiments. The competition
> finished with **own-work best 0.86** (`nemo-merge-soup`); quota was exhausted (5/5) before the
> deadline, so everything below is **post-competition** (measured via the local metric `eval/official_metric.py`
> + `eval/hard_val_ids.json`, and/or the still-open leaderboard which no longer counts for ranking).
> Citations are from a web/arXiv scan; full list in `references.md`.

## 1. Literature scan — and how each maps to our results
- **Model Soups** (Wortsman et al., 2203.05482) & **LoRA Soups / AdapterSoup** — averaging *same-base*
  fine-tunes (varied hyperparams/data) consistently beats the best individual. **This is exactly our 0.86
  result**: v14+c1+b1 are three 0.85 same-base fine-tunes on different data; their weighted SVD soup → 0.86.
  Confirms INS-004 and explains why T7 (strong+**weak**) failed while the soup of *comparable* members won.
- **Logic-RL** (2502.14768) — rule-based RL (RLVR) on ~5K synthetic logic puzzles generalizes to AIME/AMC.
  **Closest analogue to our hidden-rule task.** Suggests GRPO with a verifiable (exact-match/1e-2) reward
  could lift the categories SFT plateaus on (bit / equation-symbol).
- **LogicPuzzleRL** (2506.04821) — RL over logic puzzles cultivates transferable reasoning routines.
- **Tina: Tiny Reasoning Models via LoRA** (2504.15777) — strong reasoning from a small model with **LoRA +
  RL** specifically; directly compatible with our rank-32 LoRA constraint.
- **STaR / ReST / RFT (Rejection-sampling Fine-Tuning)** — sample → filter-by-correctness → SFT. Basis for
  v11. RFT = one round; STaR/ReST iterate. We have the verifier (ground-truth answers) for free.
- **SD-Zero** (2604.12002), **HDPO** (2603.23871) — newer self-distillation reportedly beating RFT/GRPO;
  HDPO mixes GRPO with privileged self-distillation for all-zero-reward prompts (useful for hard bit rows).

**Take-away:** the field says (a) soups of comparable fine-tunes are a reliable +; (b) verifiable-reward RL
on puzzles is the strongest path past an SFT plateau; (c) rejection-sampling is the cheap precursor to RL.

## 2. Top-4 post-competition tasks (picked from T5/v11, T6, T9, T12, GRPO/RL)
1. **T12 — local official metric + hard-val set — ✅ DONE this PR** (`eval/official_metric.py`,
   `eval/hard_val_ids.json`, `tests/test_official_metric.py`). Prerequisite for evaluating everything below
   without spending the 5/day quota. Highest leverage.
2. **v11 / T5 — rejection-sampling (STaR/ReST) self-distillation** — see §3. The untried distillation lever.
3. **GRPO / RLVR — verifiable-reward RL** — see §4. The literature's strongest lever for rule reasoning;
   run after v11 + a stable metric.
4. **T9 — elevate `kca-<slug>.yaml` + on-the-fly metadata + flat layout + scheduling into KCA core** (#85).
   ~70% done (PR #106). Promote `yaml_meta.py` into the `kca` CLI; add multi-account user-pool.

**Dropped — T6 (Unsloth seq8192):** superseded; v14 already trains at seq8192 with the full recipe, so the
marginal value is ~0.

## 3. v11 — rejection-sampling self-distillation (design)
Goal: lift the categories SFT plateaus on (bit, equation-symbol) by training on *verified* model-generated
CoT (richer than deterministic solver traces, on-policy with our best model).

Pipeline (why it was deferred: it is **multi-session**, sampling at 30B is the expensive part):
1. **Sample kernel** (per account, ~6–8h each): load base **+ v14 adapter** (on-policy), sample K=4–8 CoT
   per train prompt at `temp≈0.8` for the hard categories (bit/equation/cipher). Extract `\boxed{}`,
   **keep only rows where the answer matches the ground truth** (use `eval/official_metric.verify`). Save the
   kept (prompt, verified-CoT) corpus as a dataset. Split work across both accounts (different shards).
2. **Train kernel** (1 run): SFT on v14 backbone with the verified-CoT corpus mixed in at a modest dose
   (lesson: ≤~15%, like b1/c1 — high dose dilutes). Same CCE/MoE/seq8192 recipe + 7h guard.
3. **Evaluate** with `eval/official_metric` on `hard_val_ids` before any LB submit.
4. Optionally **soup** the v11 adapter into the v14+c1+b1 soup (it would be a 4th comparable member — the
   validated lever).
- Risk: sampling throughput (7680-token greedy is slow; use shorter sampling caps for generation, keep
  only short-correct traces). Budget ~2–3 GPU sessions (matches D2's estimate).

## 4. GRPO / PPO / RLVR — verifiable-reward RL (design, post-comp)
The task is ideal for RLVR: the reward is **programmatic and exact** (no reward model needed).
- **Reward** = `1.0` if `verify(gold, extract_final_answer(output))` else `0.0`; plus shaping:
  `+α` format reward (a single well-formed `\boxed{}`), small `−` length penalty (avoid runaway CoT under
  the 7680 cap), `−` invalid penalty (no/multiple boxed, dropped leading zeros).
- **Algorithm**: **GRPO** (group-relative, no value network — DeepSeek-R1/Logic-RL style) over a rank-32
  LoRA, initialized from v14 (or the soup). Group of G rollouts per prompt; advantage = reward − group mean.
- **Data**: the hard categories first (bit/equation), where SFT plateaus and RL has the most headroom
  (Logic-RL evidence). Curriculum from solver-solvable → solver-unsolvable rows.
- **Cost/risk**: online rollouts at 30B are heavy (GRPO needs G samples × many steps); a Kaggle kernel may
  be too small — likely needs the external GPU from #83. Consider **HDPO/SD-Zero** variants for all-zero
  prompts. Do this **only after** v11 + a stable local metric, and start tiny (few hundred prompts).
- Order (Raschka survey + our results): **strong SFT (v14) → local metric (T12) → rejection-sampling (v11)
  → small RLVR/GRPO → soup the survivors.**

## 5. Other ideas (post-competition backlog)
- **Soup sweep** (cheap, high-EV): now that the soup lever works, sweep members/weights — add v11 + b2 + c2 as
  members; try uniform vs score-weighted vs greedy "soup-growing" (add a member only if local metric improves).
  Evaluate with `eval/official_metric` locally; submit only the best.
- **Expand the real-prompt solver** (`lib/nemo_solver.py`): the equation/symbol solver matched only **0.4%**
  of real prompts (its fixed rule library is too small). Reverse-engineer the actual per-operator rewrite
  rules from train.csv → much higher coverage → more verified real-prompt CoT for c-style runs.
- **Teacher distillation**: use a strong external reasoner to generate CoT toward the known answers for
  bit/equation (⚠ verify competition rules permit external-model-generated training data first).
- **Per-category adapters → soup**: train one adapter per hard category, then soup — explicit specialization
  before averaging.
- **Answer-format RL/SFT**: a small pass purely on formatting edges (leading zeros, 2-dp, verbatim symbols)
  — "free" accuracy the metric rewards independently of reasoning.

## 6. Status
- T12 done (this PR). v11 / GRPO / T9 designed above; **not yet run** (post-competition; needs GPU sessions,
  likely the external compute from #83). Hold **0.86** to close the competition.
