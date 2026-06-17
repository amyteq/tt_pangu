---
id: OW-P0-DOCS-LIVE-001
title: Normalize Orbit docs and live-loop baseline before strong-tier iteration
kind: claude-code-task
status: ready
scope: docs-and-small-ops-fixes
competition_slug: orbit-wars
created: 2026-06-16
remote_side_effects: read-only-kaggle-only
allowed_paths:
  - competitions/orbit-wars/**
  - competitions/README.md
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
allowed_credential_files_for_readonly_kaggle:
  - .vscode/.env.harry
  - .vscode/.env.may
---

# Task: Normalize Orbit docs and live-loop baseline before strong-tier iteration

## Mission

Make the Orbit Wars workspace internally consistent before deeper foundation/model work.

The current repo already has `ops/live_loop.py`, `ops/track_submission.py`, `ops/episode_discover.py`, two-account status, and autonomous submit tooling. This task should **not recreate them**. Instead it should verify and patch documentation/ops inconsistencies that would mislead the next tasks.

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

## Required checks

1. Check whether docs still say 4p is not scored or only 1v1 matters. If live evidence says 4p updates μ, update docs to say 2p + 4p are both relevant and gates must track both.
2. Check `flyingfox` identity. If `flyingfox == harrysun2006` is established, update old labels that treat it as an external competitor.
3. Check `submissions.md` latest-2 state and ensure it aligns with `live/account_status.md`, `live/active_agents.yaml`, and `track_<submission>.csv` files.
4. Check early-stop policy in `ops/track_submission.py`. If it is too weak for the 1200 target, update docs or small code thresholds to match `configs/early_stop_policy.yaml`.
5. Check live-loop commands and document the recommended daily commands.
6. Ensure `tasks.md` has next tasks for FlightOracle, BattlefieldState, replay dataset, model training, hybrid integration, and ladder iteration.

## Allowed read-only Kaggle refresh

If credentials are available and safe, refresh both accounts read-only:

```bash
python competitions/orbit-wars/ops/account_manager.py --status
kaggle competitions submissions orbit-wars
```

Do not submit or push.

## Desired documentation updates

Update as needed:

```text
competitions/orbit-wars/README.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/tasks.md
competitions/orbit-wars/submissions.md
competitions/orbit-wars/EPISODES.md
competitions/orbit-wars/VALIDATION.md
competitions/orbit-wars/LEAGUE.md
competitions/orbit-wars/live/agent_status.md
competitions/orbit-wars/live/account_status.md
competitions/orbit-wars/ops/README.md
```

Create a short postmortem if useful:

```text
competitions/orbit-wars/postmortems/YYYY-MM-DD-doc-consistency-and-live-loop-baseline.md
```

## Validation

Run:

```bash
git status --short
git diff --stat
git diff --name-status
python -m py_compile competitions/orbit-wars/ops/*.py
python -m py_compile competitions/orbit-wars/agent/main.py
```

## Acceptance criteria

- Docs consistently represent 2p/4p ladder relevance.
- Known profile-name mapping mistakes are fixed or explicitly marked historical.
- Current latest-2 slots are clearly documented or marked unknown.
- Early-stop policy references the 10/20 episode gates toward μ >= 1200.
- `tasks.md` contains a clean phase/task backlog for the next plan.
- Existing live-loop commands are documented and compile.
- No remote writes performed.
- No secrets exposed.

## Stop conditions

Stop if:

- current slot state cannot be determined and would require unsafe credential handling;
- fixing docs requires changing forbidden paths;
- a required operation would submit/push/upload;
- unrelated changes exist in the worktree.

## Final response requirements

Report:

- facts corrected;
- latest-2 state;
- live-loop readiness;
- files modified;
- validation results;
- remaining blockers.
