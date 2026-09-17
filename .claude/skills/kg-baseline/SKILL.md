---
name: kg-baseline
description: Use after onboarding to build the first reproducible baseline: freeze a validation protocol with a split_id, produce one valid submission-shaped artifact, and record the numbers everything later is compared against.
---

# kg-baseline — freeze the ruler before measuring anything

Use this on entry to `BASELINE`: the competition is onboarded, and there is no reproducible score yet. The deliverable is not a good score. It is **a ruler that does not move** — a frozen validation protocol — plus one artifact that the competition actually accepts, so that the submission path is known to work before it matters.

Two failures this stage exists to prevent, both expensive later:

- **A moving ruler.** If the split changes between experiments, every comparison after it is meaningless and the whole loop's evidence is worthless. The split gets an id and is frozen here.
- **An unproven submission path.** Discovering at the deadline that the artifact shape is wrong is the same cost as having no model. Produce a valid artifact now, however weak the model behind it.

## Contract

| Declaration | This skill |
|---|---|
| **Inputs** | `competitions/<slug>/competition.yaml` (verified `metric`, `submission_mode`, `competition_type`, resource envelope, `budget`), `competitions/<slug>/rules.md`, the competition data at its real mount path, and `docs/experiment-discipline.md` for the per-experiment field floor. |
| **Output schema** | A frozen validation protocol recorded under `competitions/<slug>/` with a `split_id` that later work cites by name: the split scheme, the seed, the fold count, and any grouping or time ordering the data forces. Plus the baseline code (`competitions/<slug>/` — `.py`, reproducible, not notebook-only), a run record (`kg-run`, or the `Run` entity once ADR-0023 / issue #191 lands), and `best.cv_metric` / `best.cv_score` in `competition.yaml`. `best.public_lb` stays `null` until a submission is actually scored. |
| **State transition** | `ONBOARD` → `BASELINE` → `RESEARCH`. Leaves `BASELINE` only when the protocol is frozen, the score is reproducible from a recorded command, and a valid artifact exists. |
| **Allowed tools** | Read, Write, Edit, Glob, Grep, Bash for training and validation runs, `kca run init` / `record-metric` via `kg-run`, and `kca nb` via `kg-nb` where the artifact is a notebook or kernel. `local-write` — plus `remote-write` where `submission_mode` is `kernel` or `notebook` and the baseline must run on Kaggle to produce its artifact. A push is not a submission (issue #77); the submission itself belongs to `kg-submit`. |
| **Budget** | Spends `budget.compute.max_gpu_hours_per_cycle` and `budget.experiments.max_per_cycle`. Keep the baseline cheap on purpose: it is a ruler and a smoke test, not a contender. A null compute cap blocks the run — `PAUSED_BUDGET`, not a proceed (unknown is never unlimited). |
| **Prerequisite approvals** | Onboarding complete with a verified metric and submission mode. Training on anything beyond the competition's own data is an always-human item (`CLAUDE.md` principle 6) — a baseline uses competition data only. Any leaderboard submission of the baseline artifact goes through `kg-submit`, which says which agent each rule binds. |
| **Idempotency** | Safe to re-run *by construction*: same seed, same split, same command, same score. That property is the deliverable — if a second run gives a different number, the baseline is not finished. A re-run never silently re-freezes a different split; changing the protocol means a new `split_id` and re-baselining everything measured under the old one. |
| **Failure classes** | Data unreadable at the expected mount → fix the resolver (`docs/tooling/kaggle-kernel-ops.md` §6), never hardcode; `FAILED` with the listing of what *is* mounted. Score not reproducible across two runs → `FAILED`, `state_reason: unfrozen protocol` — do not proceed on an average. Compute cap exhausted or `null` → `PAUSED_BUDGET`, `resume_state: BASELINE`. Artifact rejected by the competition's format check → `FAILED` with the rejection text; that is exactly what this stage is for. |
| **Acceptance tests** | The recorded command re-run from a clean checkout reproduces the recorded score to the stated tolerance. A `split_id` exists and later experiment records cite it. A submission-shaped artifact exists and passed the competition's own format validation. `competition.yaml:best.cv_score` and `best.cv_metric` are set, and `best.public_lb` is `null` unless a submission was actually scored. |

## Freezing the protocol

Record these five, together, in one place that later stages cite:

1. **`split_id`** — a short stable name (`cv5-grouped-by-patient-s42`). Every later experiment record names it, and two scores under different `split_id`s are not comparable.
2. **The scheme and why** — k-fold, grouped, stratified, time-ordered. The data decides this, not convenience: a random split over grouped or time-ordered data leaks, and the leak flatters every experiment equally, so it never shows up as an anomaly.
3. **Seeds** — for the split and for training, separately.
4. **The metric and its direction**, matching `competition.yaml:metric` exactly. A local metric that is not the competition's is a different ruler.
5. **The exact command**, runnable from a clean checkout.

Then have `kg-audit` review it before it becomes the ruler for everything. A leak frozen into the baseline is the most expensive defect in the loop, because every later comparison inherits it and none of them contradicts it.

## Steps

1. **Resolve the data** with a glob, never a literal path — `docs/tooling/kaggle-kernel-ops.md` §6 has the resolver and the reason.
2. **Write the simplest honest model** for the competition type. The point is the pipeline, not the score.
3. **Freeze and record the protocol** as above. `kg-run` for the run directory and the metric record.
4. **Produce one valid artifact** in the competition's real shape and run its format validation. For `kernel` / `notebook` modes, that means the kernel runs to COMPLETE and emits the required file — `kg-submit` owns the submission itself.
5. **Write the numbers to rank 1** — `best.cv_metric`, `best.cv_score` in `competition.yaml` — and update the mirrors in the same change.
6. **Set `state: RESEARCH`.**

## Safety

- Heavy outputs stay out of git: weights, predictions, logs, raw data (`CLAUDE.md` principle 7). `runs/` is gitignored; artifacts go there, paths go in the record.
- Keep the baseline on competition data only. Expanding training data beyond the competition's own is an always-human decision.
