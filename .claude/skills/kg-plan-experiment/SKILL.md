---
name: kg-plan-experiment
description: Use to design exactly one competition experiment before any code is written — one hypothesis, one changed variable, a stated acceptance rule and a budget, so the result can be attributed when it arrives.
---

# kg-plan-experiment — one hypothesis, one changed variable, decided in advance

Use this on entry to `EXPERIMENT_PLAN`: there is a ranked idea (or a human direction that has been answered) and the next step is a design. The output is an `Experiment` — the *design*, not an execution. `kg-run-experiment` executes it, and one plan may produce several runs across folds, seeds and resource configurations.

The discipline this stage enforces is `CLAUDE.md` principle 4: **one meaningful change at a time.** Two changed variables in one experiment produce one number and two explanations, and nothing later can separate them. If two things must move together, say so explicitly and record it as a deliberate compound change with its own reason.

The second discipline is that **acceptance is written before the result is known.** A threshold chosen after seeing the number is not a threshold.

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | The idea or answered direction, the context-pack slice (ADR-0022 §4): frozen `split_id` and validation protocol, baseline and current best under that same `split_id`, known dead ends, the budget envelope from `competition.yaml:budget`, and the `rules.md` constraints that bound what may be tried. |
| **Output schema** | One `Experiment` record (ADR-0023 / issue #191 defines the entity and its field list — id, idea_id, strategy_id, parent_experiment, hypothesis, changed variables, `code_commit`, `data_version`, `config_hash`, `split_id`, seeds, metric with direction, results, resource cost, log and artifact paths, status, conclusion, lessons). Until that ADR merges, write those fields into `competitions/<slug>/tasks.md` and the tracking narrative under a stable experiment id, and do not invent a competing shape. At plan time the result fields are empty by design — `kg-run-experiment` fills them. |
| **State transition** | `IDEA_RANKING` or `HUMAN_DIRECTION` → `EXPERIMENT_PLAN` → `IMPLEMENT`. A plan whose cost exceeds the remaining budget does not leave this state: it is re-scoped or it waits. |
| **Allowed tools** | Read, Write, Glob, Grep. `local-write`. It writes a design and runs nothing. |
| **Budget** | Spends nothing itself; it *reserves conceptually* by declaring the run's expected cost in GPU-hours and wall-clock, and checks that against `budget.compute.max_gpu_hours_per_cycle` and `budget.experiments.max_per_cycle` **before** the plan is accepted. A cap that is `null` blocks the dimension: `PAUSED_BUDGET`, `resume_state: EXPERIMENT_PLAN`. |
| **Prerequisite approvals** | A direction change is the human's, and it arrives by a different route than a gate: the agent *proposes* one and waits in `WAIT_HUMAN` (ADR-0022 §5). So a plan that changes direction rather than continuing it is a proposal, not a plan. A plan that would use external or expanded training data is an always-human item and cannot be accepted here. Otherwise no approval: planning spends nothing and dispatches nothing. |
| **Idempotency** | Safe to re-run. Re-planning the same idea produces a new experiment id with `parent_experiment` set, never an edit that overwrites a design a run was executed against — the old design is what that run's result means. |
| **Failure classes** | The idea is a recorded dead end without new evidence → refuse and say which record refutes it. Cost exceeds the remaining budget → re-scope, or `PAUSED_BUDGET`. Direction change required → `WAIT_HUMAN`, `resume_state: EXPERIMENT_PLAN`, with the proposal written out. No frozen `split_id` → back to `kg-baseline`; there is nothing to compare against. |
| **Acceptance tests** | The plan names exactly one changed variable (or states explicitly why a compound change is deliberate). Acceptance is a number and a direction, written before any run. The plan cites a `split_id` that matches the frozen protocol. Expected cost is stated and is within the remaining budget. The experiment id is stable and is what the run record will cite. |

## What a plan must contain

| Field | Test for it |
|---|---|
| **Hypothesis** | One sentence naming the change and the expected effect. `"add target-encoded categorical features; expect +0.005 CV vs baseline"` passes. `"try new features"` does not — it cannot be compared to anything later. |
| **Changed variable** | Exactly one, stated as a diff against a named parent: which experiment it builds on, and what is different. |
| **Held constant** | The split (`split_id`), the seed policy, the data version, the metric. If one of these moves, the comparison is gone. |
| **Acceptance** | A number and a direction, plus what happens on each side of it: adopt, revert, or investigate. Decided now. |
| **Budget** | Expected GPU-hours and wall-clock, and the cap it is checked against. |
| **Risks** | What could make the result uninterpretable — leakage, a fold that is too small, an unstable metric, a run that cannot finish in the accelerator's time cap. |
| **Falsification** | What result would make you drop the underlying idea rather than tune it. An experiment that cannot fail is not testing anything. |

## Steps

1. **Read the dead ends first.** Refusing a re-proposal is cheaper than running it, and the refusal cites the record.
2. **Name the parent** — baseline, or the experiment this builds on — and the single variable that moves.
3. **Write acceptance as a number**, and say what happens above and below it.
4. **Cost it** against `competition.yaml:budget`. Over budget means re-scope, not "try and see".
5. **Check it against `rules.md`** — a plan that the competition forbids is not a plan, and finding that out now is free.
6. **Write the record** under a stable experiment id, and set `state: IMPLEMENT`.

## Safety

- Do not plan around a submission slot. Whether a result deserves one is `kg-submit`'s question, decided after the result exists, under the rules that skill states.
- Do not plan external or expanded training data. Record it as a proposal for the human.
