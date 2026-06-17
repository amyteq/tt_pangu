# LB80 gap analysis — "Breaking the SFT Ceiling" vs our 0.86

> LB80's thesis is **go beyond SFT** (per-bit GRPO + champagne reward; discussion #688461). We never ran RL,
> so this is our **largest method gap**. External claims untrusted (`../source_index.md`); our numbers from
> `tracking.md`/`research.md`. Exact LB80 score is `unknown`.

## Side-by-side

| dimension | LB80 (reconstructed) | us | gap / verdict |
|---|---|---|---|
| paradigm | SFT cold-start **→ GRPO/RLVR** | SFT replay + SVD model-soup | **BIG GAP: we never ran any RL** |
| reward | **dense per-step verifiable** (column / op / per-bit / VER) + superlinear 8/8 "champagne" bonus | n/a (no RL); SFT cross-entropy only | **GAP: dense shaping is the claimed lever** |
| our RL design | — | `research.md §4`: GRPO with **binary terminal** reward (0/1) — designed, **never run**, deferred (GPU/time) | **GAP: wrong reward shape + never executed** |
| target categories | bit (cleanest reward) + equation/symbol | — | bit is where we have headroom (T12 14/16) |
| SFT ceiling | acknowledges 0.85–0.86 plateau, breaks it | **we are AT 0.86** (every augmentation diluted) | this writeup is the documented path past our wall |
| alt path | adapter surgery (lopure ~0.89, no RL) | SVD-cap **soup** 0.86 | **GAP: surgery = amplify top singular values (we only cap/merge)** |
| compute | external GPU (30B online rollouts) | Kaggle kernels + RTX PRO 6000 | RL likely needs external compute (#83) |
| score | `unknown` (likely 0.87–0.90) | 0.86 / 0.85 priv | gap exists but exact size unknown |

## What the SFT ceiling actually is (why RL is the lever)
SFT's answer-level signal is **sparse**: a near-correct 8-bit answer scores the same 0 as random, so the
hardest rows get vanishing gradient (our T12: equation ≤2/16 everywhere; bit caps ~14/16; augmentation
*regressed* the hard tail — c1 cipher 3/16 < base 8/16). A **dense per-step verifiable reward** gives gradient
on partial correctness; the **champagne bonus** shapes toward completing problems. This is the Logic-RL/RLVR
result and is exactly the headroom SFT cannot reach by adding more data.

## Borrowable (ranked by EV)
1. **GRPO with a DENSE per-step verifiable reward** (HIGH EV, HIGH cost). Upgrade `research.md §4` from binary
   terminal reward to per-step partial credit: reward layout + op-choice + per-bit correctness + a final-answer
   verify, plus a superlinear all-correct bonus. Start on **bit** (cleanest verifier), small (few hundred
   prompts), warmstarted from the **v14/soup** SFT prior. This is the single biggest untried lever.
2. **Adapter singular-value amplification** (MEDIUM EV, LOW cost, no RL). lopure's amplify-top-50%-SV (~0.89)
   is a post-training edit compatible with our `lib/svd_merge.py` — try amplifying the soup's top directions
   and gate on T12. Cheap to test; no GPU-rollout cost.
3. **Solver-guided teacher CoT cold-start** (MEDIUM EV). andy279-style (solver finds rule → teacher writes CoT)
   gives a stronger RL cold-start corpus than our replay alone, esp. for bit/equation.

## Gaps / risks of borrowing
- **RL at 30B is expensive and unstable.** Online GRPO rollouts likely exceed Kaggle kernels → external GPU
  (#83). Must warmstart from a strong SFT prior (cold-start GRPO is unstable). Reward hacking on the dense
  shaping is a real risk (model games partial credit without solving) — needs the final-answer verify to dominate.
- **Verifier coverage:** the dense per-bit reward is natural for **bit**; for **equation** (strong cipher) the
  per-step verifier is weak (we can't even check intermediate steps), so RL headroom there is small — consistent
  with equation being bounded.
- **Compute/quota:** out of scope for the Saturday RTX PRO 6000 unless rollouts are tightly bounded; may need #83.

## NOT a gap
- The model-**soup** (our 0.86) and **eq-aug coverage** are ours and orthogonal to RL — keep both; soup the RL
  survivor in as a new comparable member (INS-004).
