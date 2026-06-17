---
id: OW-LADDER-LOOP-001
title: Long-running Orbit Wars ladder iteration loop to strong-tier breakthrough
kind: claude-code-loop
status: ready
scope: authorized-orbit-ladder-iteration
competition_slug: orbit-wars
created: 2026-06-16
remote_side_effects: authorized-kaggle-submit-and-kernel-push
strong_tier_target_public_mu: 1200
loop_mode: bounded_cycles_not_infinite_sleep
allowed_credential_files:
  - .vscode/.env.harry
  - .vscode/.env.may
allowed_paths:
  - competitions/orbit-wars/**
  - competitions/README.md
  - competitions/_shared/insights.md
  - competitions/_shared/common-bugs.md
  - docs/tasks/competition-tracking/orbit-strong-tier/**
forbidden_paths:
  - .kca/**
  - tools/**
  - src/**
  - services/**
  - supabase/**
  - ui/**
  - tests/**
  - .github/workflows/**
  - .env
  - .env.*
  - kaggle.json
  - .kaggle/kaggle.json
  - secrets/**
---

# Loop: Orbit Wars ladder iteration to strong-tier breakthrough

## Mission

Run a long-term but bounded-per-cycle iteration loop:

```text
submit version
  -> mark neutral
  -> discover/download/analyze episodes
  -> classify version using first 10/20 episode early-stop policy
  -> if weak/fix_required, release slot with validated replacement
  -> if lessons found, create tasks and improve execution/model/rule engine
  -> train/update model in parallel on snorlax when possible
  -> validate candidate locally
  -> create account-aware latest-2 replacement plan
  -> autonomously submit/push when gates pass
  -> continue until μ >= 1200 or no runnable directions/tasks remain
```

This loop should use the existing `competitions/orbit-wars/ops/` live-loop tooling and strengthen it where needed. Do not rebuild everything from scratch.

## Authorization

This loop authorizes bounded autonomous Kaggle operations for Orbit Wars only:

Allowed when gates pass:

```text
kaggle competitions submit -c orbit-wars ...
kaggle kernels push ... for Orbit Wars only
python competitions/orbit-wars/submit.py ... --authorized-by-task OW-LADDER-LOOP-001
python competitions/orbit-wars/ops/submit_manager.py ... --submit-if-gated
```

Credentials allowed:

```text
.vscode/.env.harry
.vscode/.env.may
```

Never print, copy, commit, or write credential values. Usernames/profile names may be shown.

Forbidden:

```text
git push
gh pr create / merge
Kaggle dataset upload/create/version
any non-Orbit remote write
KCA core changes
```

## Read first

- `competitions/orbit-wars/README.md`
- `competitions/orbit-wars/tracking.md`
- `competitions/orbit-wars/tasks.md`
- `competitions/orbit-wars/submissions.md`
- `competitions/orbit-wars/EPISODES.md`
- `competitions/orbit-wars/VALIDATION.md`
- `competitions/orbit-wars/LEAGUE.md`
- `competitions/orbit-wars/ops/README.md`
- `competitions/orbit-wars/ops/live_loop.py`
- `competitions/orbit-wars/ops/track_submission.py`
- `competitions/orbit-wars/ops/episode_discover.py`
- `competitions/orbit-wars/ops/submit_manager.py`
- `competitions/orbit-wars/ops/account_manager.py`
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/early_stop_policy.yaml`
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/account_lane_policy.yaml`
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/promotion_gate.yaml`

## Loop target

Primary stop-success:

```text
A submitted agent reaches or is strongly trending toward public ladder μ >= 1200.
```

A version may be marked `strong` if:

```text
public μ >= 1200
OR public μ >= 1100 with positive slope and at least 2 strong-tier wins
OR first 20 episodes show sustained upward trend and no hard bugs, with human-worthy keep recommendation
```

## Per-cycle bounded behavior

Each invocation should run one bounded cycle unless explicitly invoked with `--max-cycles`.

Do not sleep indefinitely inside Claude Code.

Cycle outline:

1. Check clean worktree and credentials safety.
2. Refresh both accounts read-only.
3. Discover tracked submission episodes via `EpisodeService/ListEpisodes`.
4. Download/analyze at most a bounded number of new episodes per submission.
5. Update `track_<submission>.csv`, `EPISODES.md`, `agent_status.md`, `active_agents.yaml`, `submissions.md`, `tracking.md`.
6. Apply early-stop policy for first 10/20 episodes.
7. If an agent is `weak` or `fix_required`, find or build a validated replacement.
8. If idle, pick at most one high-priority implementable task from `tasks.md`/`tracking.md`.
9. If the task is foundation/model/data and can run parallel, spawn/report command for snorlax rather than blocking ladder loop.
10. If code changes, run local gates.
11. If candidate passes promotion gate, create account-aware submit plan.
12. Submit/push autonomously if and only if plan passes account/quota/gate policy.
13. Mark new submission `neutral` and initialize early-stop tracking.
14. Stop the cycle and report.

## Early stop policy

Use `configs/early_stop_policy.yaml`. Operational summary:

Immediate `fix_required`:

- strict sun collision by our fleet;
- invalid action / exception / timeout;
- repeated wrong first-hit target;
- repeated out-of-bounds self-loss;
- confirmed logic bug causing catastrophic self-loss.

After first 10 episodes:

Mark `weak` if any:

- hard bug triggered;
- two losses vs weaker opponents;
- 7+ losses in first 10;
- public μ delta <= -40;
- public μ < 800 and slope <= 0;
- 2p win rate < 35% and no strong-opponent win.

Continue if any:

- public μ delta >= +80;
- public μ >= 950 and slope > 0;
- at least one strong-opponent win;
- 2p win rate >= 50%.

After first 20 episodes:

Mark `weak` if any:

- public μ < 950 and slope <= 0;
- public μ < 1000 and latest 10 losses >= 6;
- public μ is 50+ below the incumbent it replaced;
- no strong-tier wins and public μ < 1000;
- any latest-5 window has 3+ losses and μ slope <= 0.

Mark `strong` if:

- public μ >= 1200;
- or public μ >= 1100, slope > 0, and strong-tier wins >= 2.

Do not mark weak from a single unlucky loss unless there is a hard algorithmic bug.

## Episode analysis requirements

For every analyzed episode:

- detect player count 2p/4p;
- map our seat using submission id / reward matching / profile identity;
- record initial and updated μ;
- record opponent profile/display names and, where possible, usernames;
- compute result and placement;
- scan strict sun collision, near-sun warning, wrong first-hit target, OOB;
- summarize winner reason;
- create follow-up tasks for new tactics, strategy gaps, or bugs.

If an episode is surprising or unexplained, flag it for manual review with direct replay and viewer links.

## Parallel work policy

The ladder loop may run while snorlax trains models.

Parallelizable:

- model training on snorlax;
- replay corpus indexing;
- live episode analysis;
- public source study;
- documentation synthesis.

Not parallelizable without coordination:

- editing `agent/main.py`;
- editing `core/geometry.py`, `core/oracle.py`, or `core/state.py`;
- editing `tasks.md`/`tracking.md` in multiple concurrent tasks;
- submitting from both accounts without a unified latest-2 plan.

When a parallel task should run, write a clear command to:

```text
competitions/orbit-wars/live/parallel_work_queue.md
```

Do not block the ladder loop waiting for a multi-hour training job unless the current cycle's only useful next step is the model result.

## Submit and account allocation policy

Use `configs/account_lane_policy.yaml`.

Default:

- `harry`: stable/final lane; preserve strong anchor; submit best validated candidates.
- `may`: experimental/probe lane; test promising candidates; avoid evicting strong harry slots.

Before any submit:

1. Build latest-2 state for both accounts.
2. Choose the account with lowest opportunity cost.
3. Prefer replacing `fix_required`/`weak` slots.
4. Avoid evicting `strong` slots.
5. Preserve a valuable other slot only if quota cost is justified.
6. Check budget and daily quota assumptions.
7. Record a submit plan.

Use:

```bash
python competitions/orbit-wars/ops/submit_manager.py --account auto --dry-run --candidate <file> --candidate-verdict <json>
python competitions/orbit-wars/ops/submit_manager.py --account auto --submit-if-gated --candidate <file> --candidate-verdict <json>
```

If `submit_manager.py` lacks a required feature, update it under `competitions/orbit-wars/ops/` and validate.

## Candidate validation before submit

Run gates from `promotion_gate.yaml`:

```bash
python -m py_compile competitions/orbit-wars/agent/main.py
python competitions/orbit-wars/arena/validate.py --games 10 --procs 4
python competitions/orbit-wars/arena/suite_gate.py main --games 12 --procs 4
python competitions/orbit-wars/arena/eval_4p.py --games 12 --procs 4
```

If candidate is a serious contender:

```bash
python competitions/orbit-wars/arena/league.py --games 30 --seed0 <fresh_seed> --procs 4
python competitions/orbit-wars/ops/evaluate_candidate.py --agent <candidate> --games 30 --seed0 <fresh_seed>
```

Ladder-probe exception:

Because local arena is known cluster-blind, a ladder-probe submit may be allowed if:

- candidate is crash-safe;
- no hard execution bug;
- no major 4p regression;
- it tests a qualitatively new integrated direction;
- it replaces a weak/replaceable slot;
- early-stop tracking is initialized.

Document the exception in `submit_plans.md`.

## Work selection when idle

Pick one task only.

Priority order:

1. P0 hard execution bugs: FlightOracle, landing target, sun/OOB/wrong first-hit.
2. P0/P1 BattlefieldState / ArrivalLedger / ThreatLedger.
3. Episode-derived bug or strategy gap from a current submitted version.
4. Dataset/model pipeline task if it unblocks hybrid.
5. Hybrid integration task if model + foundation ready.
6. Documentation cleanup only if it prevents wrong decisions.

Do not do speculative parameter sweeps unless tied to a task and gate.

## Success and stop conditions

Success stop:

- a submitted agent reaches public μ >= 1200;
- or first 20 episodes strongly indicate it is climbing past 1200 and the loop reports a keep recommendation.

Normal stop:

- no runnable tasks remain;
- all current versions are weak/fix_required and no replacement exists;
- snorlax training is running and ladder has no new episodes;
- cycle budget or submit budget reached;
- task requires human strategic decision.

Hard stop:

- secret value would be exposed;
- credentials are missing or tracked/staged;
- Kaggle/API behavior contradicts account compliance;
- forbidden paths would be modified;
- repeated hard bugs in execution layer;
- budget/quota would be exceeded;
- non-Orbit remote write would be required.

## Files to update

As appropriate:

```text
competitions/orbit-wars/live/agent_status.md
competitions/orbit-wars/live/active_agents.yaml
competitions/orbit-wars/live/account_status.md
competitions/orbit-wars/live/submit_plans.md
competitions/orbit-wars/live/push_submit_audit.md
competitions/orbit-wars/live/parallel_work_queue.md
competitions/orbit-wars/live/track_<submission_id>.csv
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/submissions.md
competitions/orbit-wars/EPISODES.md
competitions/orbit-wars/bugs.md
competitions/orbit-wars/insights.md
competitions/orbit-wars/README.md
```

## Validation commands per cycle

Always run:

```bash
git status --short
git diff --stat
git diff --name-status
python -m py_compile competitions/orbit-wars/ops/*.py
python -m py_compile competitions/orbit-wars/agent/main.py
```

Run local gates if code changed or before submit.

## Per-cycle acceptance criteria

A cycle is complete when:

- account status is refreshed or blocker recorded;
- tracked submissions have been checked for new episodes;
- at least one new episode is analyzed OR a no-new-episode state is recorded;
- early-stop statuses are updated;
- tasks/tracking/submissions docs are updated;
- if code changed, local validation results are recorded;
- if a candidate is submit-ready, submit plan is written and autonomous submit performed if gates/budget pass;
- if no submit, reason is recorded;
- parallel work queue is updated when applicable;
- final report summarizes exactly what happened.

## Final response requirements

Report:

- current active slots by account;
- submissions tracked and first 10/20 status;
- episodes discovered/downloaded/analyzed;
- hard bugs or strategy findings;
- agent status changes;
- tasks created/updated;
- code/model changes;
- validation results;
- submit/push actions performed, if any;
- quota/budget consumed;
- early-stop decisions;
- parallel work queued/running;
- whether strong-tier target is reached or current distance to μ 1200;
- next recommended cycle command.
