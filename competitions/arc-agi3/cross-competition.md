# Cross-competition: ARC-AGI-2 ↔ ARC-AGI-3 — what transfers (跨赛互借)

> The user is running **both** ARC-AGI-2 and ARC-AGI-3. This doc is the honest answer to
> "可否互相借鉴?" — what transfers, what does **not**, and the few shared assets worth building once.
> Evidence: `research.md` (AGI-3) + `arc-agi2-research.md` (AGI-2). Both are 2026 Kaggle tracks of the
> same ARC Prize, same shell timeline, same Kaggle infra constraints.

## TL;DR
**The two share a domain (colored grids) and a philosophy (efficiency-scored, generalization-not-
memorization), but they are different problem classes** — AGI-2 is **one-shot pattern induction from
demo pairs** (a static map), AGI-3 is a **multi-turn POMDP / agentic exploration** (no demos, infer
the goal). So the *winning algorithms barely transfer*, but several *meta-patterns, infra assets, and
research insights* transfer well. Don't expect a shared solver; do expect a shared toolbox and brain.

## What does NOT transfer (be explicit so we don't waste effort)
| AGI-2 winning technique | Transfers to AGI-3? | Why not |
|---|---|---|
| Test-Time Training on demo pairs | ❌ | AGI-3 has **no demo pairs** to fine-tune on |
| Program synthesis from examples | ❌ | No static input→output to synthesize against |
| DSL exhaustive search | ❌ | No fixed transformation rule to search for |
| Ensemble of transduction + induction | ❌ | Both legs need demo pairs |
| Augmentation-vote selection | ❌ | Needs a static task to augment/vote over |

Implication: **AGI-2's #1 lever (TTT) is dead on AGI-3.** Anyone porting the AGI-2 stack directly will
score ~0 (this is exactly why frontier LLMs sit < 0.5% on AGI-3 — they reason but don't *explore/model*).

## What DOES transfer
| Asset / pattern | AGI-2 form | AGI-3 form | Transfer strength |
|---|---|---|---|
| **Refine-and-verify meta-loop** | propose candidate → check vs demo pairs → refine | propose action/plan → observe outcome → update world model → refine | ⭐⭐ partial (logic same, signal differs) |
| **RL / RLVR with a programmatic reward** | GRPO on verifiable answer match (cf. our nemo work) | RL on env reward / RHAE-shaped reward; **core** AGI-3 approach (StochasticGoose = CNN+RL) | ⭐⭐⭐ strong |
| **World/grid modeling** | implicit (learn the transform) | explicit — predict next frame from action (model-based RL) | ⭐⭐⭐ strong (new primary skill) |
| **Agent architecture (orchestrator + subagents)** | candidate-generation orchestration | exploration ↔ planning ↔ memory subagents (Arcgentica pattern) | ⭐⭐⭐ strong |
| **Context / history management** | long demo-set prompt packing | long action-frame history over many turns (Duke harness) | ⭐⭐⭐ strong |
| **Grid I/O & rendering tooling** | parse 30×30 int grids | parse 64×64 16-color frames | ⭐⭐ shared code, different dims |
| **Synthetic-data / self-play generation** | NVARC's synthetic ARC tasks | self-play episodes / curriculum over public envs | ⭐⭐ pattern transfers |
| **Cost-efficiency discipline** | $0.42/task, no-CoT under runtime | < 12h, no-internet, **RHAE punishes extra actions** | ⭐⭐⭐ both reward parsimony |
| **Kaggle infra**: notebook offline-pack, wheels, <12h guard, dual-account ops | reuse | reuse | ⭐⭐⭐ direct |

## The single most valuable shared insight
**Efficiency is scored, not just correctness.** AGI-2 caps you at $0.42/task and 2 attempts; AGI-3
*squares* the human/agent action ratio. Both punish brute force. A habit that pays in both: **minimize
exploration/compute per unit of correctness** — in AGI-2 that's cheap candidate generation + tight
verification; in AGI-3 it's *information-greedy* exploration (each action should maximally reduce
uncertainty about the world model), because every wasted action is quadratically expensive.

## Build-once, use-twice (concrete shared assets)
1. **Grid library** — a shared `lib/grid.py`: parse/encode/serialize colored grids (param the size:
   30×30 ints for AGI-2, 64×64×16 for AGI-3), diffing, symmetry/rotation ops, ASCII/RGB render. The
   Core-Knowledge priors (objectness, symmetry, topology, physics) are *identical* across both.
2. **Kaggle offline-pack tooling** — reuse the nemo `kca-<slug>.yaml` + on-the-fly metadata + flat
   `kernels/`+`lib/` + <12h guard + offline-wheels pattern (incl. the Blackwell vLLM offline recipe).
   Both comps are no-internet Kaggle notebooks.
3. **Local eval harness** — both need a *local* metric to avoid burning daily quota: AGI-2 →
   pixel-match over public eval (cf. nemo `eval/official_metric.py`); AGI-3 → RHAE over the 25 public
   envs via the SDK. Same discipline (INS from nemo: **offline gate must align with the online metric**).
4. **RL / GRPO scaffolding** — our nemo post-comp design already specs GRPO/RLVR with a programmatic
   reward. AGI-3 *is* an RL problem; AGI-2 can use RLVR on verifiable answer match. Shared verifier
   pattern, shared rollout plumbing.
5. **Core-Knowledge prior detectors** — object segmentation, symmetry detection, containment/topology,
   simple physics — useful as perception front-ends in *both* (features for AGI-2 induction, state
   abstraction for AGI-3 world model).

## Where the borrowing flows
- **AGI-2 → AGI-3**: synthetic-data discipline, augmentation thinking (as data-aug for a learned world
  model / frame predictor), cost-efficiency reflexes, our GRPO design, grid tooling.
- **AGI-3 → AGI-2**: agentic refinement loops and *active* candidate selection (treat AGI-2 solving as
  a short search episode: hypothesize rule → test on a held-out demo pair → refine — an "agent over the
  demo set" rather than one-shot). Imbue's **code-evolution** (population + LLM mutation + fitness) is
  itself a refinement-loop import from agentic thinking into AGI-2 and is currently SOTA there.

## Honest recommendation
- Keep **two separate solver stacks** — do not try to unify the cores; you'll compromise both.
- **Share the toolbox**: `lib/grid.py`, Kaggle offline-pack tooling, local-eval discipline, GRPO
  scaffolding, prior detectors. Put genuinely shared code in `competitions/_shared/` (it already exists).
- **Share the brain**: cross-post insights to `competitions/_shared/insights.md`. The efficiency-
  scoring lesson and the "offline gate must match online metric" lesson are universal.
- **Sequence effort by EV**: AGI-2 has a *known* winning recipe (TTT+synth+ensemble, 24% Kaggle SOTA)
  and our nemo experience maps onto it directly — higher near-term EV. AGI-3 is **wide open** (< 0.5%
  AI), higher variance, higher ceiling, and rewards RL/agent R&D — a longer bet. Decide split based on
  how much novel agent/RL research we want to fund vs. iterating a known recipe.
