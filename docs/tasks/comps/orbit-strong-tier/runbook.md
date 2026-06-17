# Orbit Wars strong-tier execution runbook

## Branch/worktree pattern

Use one branch per task:

```bash
git checkout main
git pull --rebase
git checkout -b claude/orbit-p0-research
```

After the task finishes, review:

```bash
git status --short
git diff --stat
git diff --name-status
```

## Suggested parallel schedule

### Lane A — research/docs

```bash
claude --bg --name OW-P0-research --permission-mode auto \
  "/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/00-goal-research-kuni05-matchmaking-identity.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable."
```

### Lane B — foundation

Run after or alongside docs cleanup, but avoid concurrent edits to `agent/main.py`:

```bash
claude --bg --name OW-P0-flight-oracle --permission-mode auto \
  "/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/02-goal-flight-oracle-and-execution-zero-bug.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable."
```

Then:

```bash
claude --bg --name OW-P0-state-ledger --permission-mode auto \
  "/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/03-goal-battlefield-state-ledger-rule-engine.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable."
```

### Lane C — data/model on snorlax

Dataset index can start early; candidate labels should be re-run after FlightOracle:

```bash
claude --bg --name OW-P1-dataset --permission-mode auto \
  "/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/04-goal-replay-dataset-and-feature-pipeline.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable."
```

Training loop on snorlax:

```bash
claude --bg --name OW-P1-snorlax-model --permission-mode auto \
  "/loop Execute loop from docs/tasks/competition-tracking/orbit-strong-tier/prompts/05-loop-snorlax-model-training.md until one training cycle completes, no data is available, or stop conditions trigger. Read the loop file fully first. Treat the loop file as immutable."
```

### Lane D — online ladder loop

Run bounded cycles; review after each cycle:

```bash
claude --bg --name OW-LADDER-loop --permission-mode auto \
  "/loop Execute loop from docs/tasks/competition-tracking/orbit-strong-tier/prompts/07-loop-ladder-iterate-to-strong-tier.md until strong-tier breakthrough, no runnable tasks remain, or stop conditions trigger. Read the loop file fully first. Treat the loop file as immutable."
```

## Human review checkpoints

Review before merging:

- New `core/` geometry/oracle semantics.
- Any change to final action emission.
- Any real Kaggle submit/push audit.
- Any use of public `kuni05` source.
- Any model artifact embedded into `agent/main.py`.

## Release-slot policy

If a version is marked `weak` or `fix_required`:

1. Do not submit the same file again.
2. Keep tracking until a replacement plan exists.
3. If a validated replacement exists, use the account lane policy to replace the least valuable slot.
4. Record the reason in `submissions.md`, `tracking.md`, and `live/agent_status.md`.
