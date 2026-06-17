# Prompt/task files

All files in this directory are intended to be executed with Claude Code as task specs.

## One-shot goals

```bash
/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/00-goal-research-kuni05-matchmaking-identity.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable.

/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/01-goal-doc-consistency-and-live-loop-baseline.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable.

/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/02-goal-flight-oracle-and-execution-zero-bug.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable.

/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/03-goal-battlefield-state-ledger-rule-engine.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable.

/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/04-goal-replay-dataset-and-feature-pipeline.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable.

/goal Execute task from docs/tasks/competition-tracking/orbit-strong-tier/prompts/06-goal-hybrid-policy-integration.md until its acceptance criteria pass or stop conditions trigger. Read the task file fully first. Treat the task file as immutable.
```

## Loops

If `/loop` is available:

```bash
/loop Execute loop from docs/tasks/competition-tracking/orbit-strong-tier/prompts/05-loop-snorlax-model-training.md until one training cycle completes, no data is available, or stop conditions trigger. Read the loop file fully first. Treat the loop file as immutable.

/loop Execute loop from docs/tasks/competition-tracking/orbit-strong-tier/prompts/07-loop-ladder-iterate-to-strong-tier.md until strong-tier breakthrough, no runnable tasks remain, or stop conditions trigger. Read the loop file fully first. Treat the loop file as immutable.
```

Fallback if `/loop` is not available:

```bash
/goal Execute one bounded cycle from docs/tasks/competition-tracking/orbit-strong-tier/prompts/05-loop-snorlax-model-training.md until its per-cycle acceptance criteria pass or stop conditions trigger.

/goal Execute one bounded cycle from docs/tasks/competition-tracking/orbit-strong-tier/prompts/07-loop-ladder-iterate-to-strong-tier.md until its per-cycle acceptance criteria pass or stop conditions trigger.
```
