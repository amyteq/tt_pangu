# The `kg-*` skill contract

One contract, declared the same way by every `kg-*` skill, so that a work unit can be handed to either harness and produce the same record. Source: issue #192 (§3 of its task comment) and discussion #185 §12. The vocabulary it is written in is [ADR-0022](../adr/0022-long-run-competition-operating-model.md) — §3 for the state machine, §4 for the context pack, §5 for autonomy and the submission record, §6 for budgets.

## Why a contract rather than a house style

`kg-*` skills are not prose for one agent to read. They are the phase-1 implementation of the per-competition loop, and phase 1 runs that loop from **two** harnesses against one repo: Claude Code loads `.claude/skills/`, Codex loads `.agents/skills/`, and `scripts/gen_agents.py` makes the second a symlink mirror of the first. A skill that only works because a particular harness happens to behave a particular way is a fork of the loop, not a step in it.

So the rule is: **one documented contract, shared adapters, no per-harness implementation.** Where the two harnesses genuinely differ — hooks, sub-agents, approval policy — the skill names the difference instead of assuming one of them (`.agents/README.md` § *No Codex counterpart* is the inventory of what actually differs). Where a mechanical operation is needed, the skill calls the same `kca` subcommand from both, and the CLI is where harness-specific handling belongs.

The second reason is that the loop is designed to run across **fresh sessions** (ADR-0022 §4): model context is disposable, project state is not. A skill that leaves its result only in a session transcript has produced nothing. Every declared **Output** below is a file or a field that outlives the session.

## The nine declarations

Every `kg-*` skill carries a `## Contract` section with exactly these nine rows, in this order.

| # | Declaration | What it must say |
|---|---|---|
| 1 | **Inputs** | The slice of the ADR-0022 §4 context pack this unit is given, and nothing more. Name the files, not the topics. If a required input is absent the skill stops and says which one — it never proceeds on a guess. |
| 2 | **Output schema** | The exact artifact written, at an exact path, in a stated shape. Phase 1 writes it under `competitions/<slug>/`; phase 2's KCA writes the same payload to Supabase (§1). Named contract entities (`ResearchItem`, `Idea`, `Experiment`, `Run`, `Artifact`, `Submission`, `Score`, `Finding`) are **ADR-0023 / issue #191's** to define — a `kg-*` skill references the entity by name and does not invent a second shape for it. |
| 3 | **State transition** | The ADR-0022 §3 token this unit enters from and the token it leaves in, plus the side states it may land in. States are `UPPER_SNAKE_CASE`, no aliases. The transition is recorded by editing `competitions/<slug>/competition.yaml:state` — rank 1, the only writable authority — and the mirrors (ranks 2-4) in the same change. |
| 4 | **Allowed tools** | The tool classes the unit may use and the highest `docs/tooling/kca-side-effect-levels.md` level it reaches: `read-only`, `local-write`, `remote-write`, `submission`. A skill that declares `local-write` and pushes a kernel has broken its contract, not merely exceeded it. |
| 5 | **Budget** | Which ADR-0022 §6 dimensions the unit spends — GPU-hours, submission slots, wall-clock, subscription usage — and what it does when one is exhausted **or unconfirmable**. Unknown is never unlimited: an unconfirmable cap is `PAUSED_BUDGET`, not a proceed. |
| 6 | **Prerequisite approvals** | What must already be answered before the unit runs. The always-human floor is `CLAUDE.md` principle 6's seven items, and it is read there rather than re-listed here, because a copy drifts. A skill states only what is *additionally* required of it, and always says **which agent** each rule binds — the harness spending the human's credentials, or KCA under its competition's config plus ADR-0022 §5's activation conditions A1-A7. An unscoped approval sentence is read as binding both, which is issue #65's conflation. |
| 7 | **Idempotency** | What a second run does. Three answers are acceptable: *safe to re-run* (recomputes the same output), *resumable* (picks up a persisted intent and must not repeat the external half of it), or *single-shot* (a second run is a second external side effect and needs the reconciliation path, never a blind retry). |
| 8 | **Failure classes** | Each way the unit can fail, mapped to the ADR-0022 §3 side state it lands in — `RETRY_AT`, `NEEDS_RECONCILIATION`, `PAUSED_BUDGET`, `WAIT_HUMAN`, `FAILED` — together with the `resume_state` and `state_reason` written alongside it. A side state that does not record how to come back is not a side state; it is a stall. |
| 9 | **Acceptance tests** | How a reviewer checks the unit did its job, as observable facts — a file exists with these fields, this token is in `competition.yaml`, this command exits 0. Not "the analysis is good". |

## Which skill owns which states

The main path of ADR-0022 §3, with the skill that carries each stretch. `DISCOVER` and `SELECT` are the human's priority call (§2) and belong to the dashboard, not to a skill.

| State(s) | Skill | Priority |
|---|---|---|
| `ONBOARD` | `kg-onboard` | P1 |
| `BASELINE` | `kg-baseline` | P1 |
| `RESEARCH` | `kg-research` | P1 |
| `IDEA_GENERATION`, `IDEA_RANKING` | `kg-idea` | **P2 — named, not built** |
| `EXPERIMENT_PLAN` | `kg-plan-experiment` | P1 |
| `IMPLEMENT`, `TRAIN_VALIDATE`, `EVALUATE` | `kg-run-experiment` | P1 |
| `INDEPENDENT_AUDIT` | `kg-audit` | P1 |
| `SUBMISSION_ELIGIBILITY`, `PRE_SUBMIT_GATE`, `SUBMIT`, `WAIT_SCORE`, `SKIP_SUBMISSION` | `kg-submit` | P1 |
| `RESULT_ANALYSIS`, `FINDINGS` | `kg-evaluate` | **P2 — named, not built** |
| (drives the next stage from persisted state) | `kg-loop` | **P2 — named, not built** |

`HUMAN_DIRECTION` has no skill of its own: it is *applying* an answered direction decision, which lands in whichever skill consumes the answer — usually `kg-plan-experiment`. The waiting happens in `WAIT_HUMAN`, never in `HUMAN_DIRECTION` (ADR-0022 §3).

Until the P2 three exist, their states are worked by hand against this contract, and `kg-experiment` is the map that says which stage you are in. `RESULT_ANALYSIS` / `FINDINGS` work today has the `agent-iteration-review` skill for the continue/revert/stop call; that skill folds into `kg-evaluate` when it is built.

### Mechanical helpers, not stages

Two `kg-*` skills are CLI wrappers rather than loop stages, so they declare the contract but own no state transition of their own:

| Skill | What it wraps | Used by |
|---|---|---|
| `kg-nb` | `kca nb to-py` / `to-ipynb` | `kg-run-experiment`, `kg-submit` (kernels are authored as `.py`, pushed as `.ipynb`) |
| `kg-run` | `kca run init` / `record-metric` / `list` | `kg-run-experiment` — which supersedes it as the stage entry point |

## Not this contract's business

- **Defining the ledger entities.** ADR-0023 / issue #191 does that. A `kg-*` skill consumes the shape; where #191 has not landed, the skill references the entity by name and carries the wiring as a stated to-do rather than inventing a second shape.
- **Restating the always-human floor.** `CLAUDE.md` principle 6 holds it. Seven items, not configurable down.
- **Deciding how wide autonomy is.** ADR-0022 §5 does, per competition, gated on A1-A7. A skill reports what the conditions currently say; it does not widen them.

## Adding a `kg-*` skill

1. Front matter: `name:` identical to the directory name (`scripts/gen_agents.py` fails otherwise), and a `description:` that is one line and says *when to use it*, since that is all a harness sees before loading the body.
2. A `## Contract` section with the nine rows above, in order. A row you cannot fill is a design hole, not a formatting one.
3. Body: the steps, each naming the file it writes. Prefer a `kca` subcommand over prose describing the same operation.
4. Run `python scripts/gen_agents.py` so `.agents/skills/<name>` and `.agents/README.md` pick it up, then `python -m pytest tests/test_instruction_parity.py` — the pinned-mention guards will ask you to re-review any sentence the new skill adds about force-push, screened autonomy, or approvals.
5. Retiring one instead: `.claude/archive/skills/README.md`.
