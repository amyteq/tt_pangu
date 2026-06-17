---
id: OW-P2-HYBRID-001
title: Integrate model scorer with rules, RuleEngine, and FlightOracle
kind: claude-code-task
status: ready
scope: competition-agent-code-and-eval
competition_slug: orbit-wars
created: 2026-06-16
remote_side_effects: none
allowed_paths:
  - competitions/orbit-wars/**
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

# Task: Integrate model scorer with rules, RuleEngine, and FlightOracle

## Mission

Create a hybrid Orbit Wars agent version where a trained model scores/ranks legal candidates while deterministic rules and FlightOracle enforce safety and tactical constraints.

Do not perform Kaggle submit in this task. The ladder loop handles submit after gates.

## Preconditions

This task should only run after these are true or explicitly waived:

- FlightOracle exists and gates final actions.
- BattlefieldState / Ledger / Features exist.
- At least one model artifact or model-card recommendation exists.
- RuleEngine has initial guardrails.

If not true, stop and create/update tasks instead of forcing integration.

## Read first

- `competitions/orbit-wars/core/`
- `competitions/orbit-wars/agent/main.py`
- `competitions/orbit-wars/agent/versions/v4.py`
- `competitions/orbit-wars/models/reports/`
- `competitions/orbit-wars/models/artifacts/` if present
- `competitions/orbit-wars/VALIDATION.md`
- `docs/tasks/competition-tracking/orbit-strong-tier/configs/promotion_gate.yaml`

## Integration design

Preferred architecture:

```text
obs
  -> BattlefieldState
  -> CandidateGenerator rules/search
  -> FeatureBuilder
  -> ModelScorer(candidate)
  -> RuleEngine filters/downweights/upweights
  -> FlightOracle validate first-hit/path
  -> ActionEmitter
```

Rules:

- Model never directly emits raw continuous angle.
- Model may score candidates or adjust ship bucket/fraction.
- If model load/inference fails, fallback to rules-only.
- Every final action goes through FlightOracle.
- No torch runtime online unless a separate runtime-smoke says it is safe.
- Prefer pure Python / embedded small weights / npz-json export.

## Files to create/update

```text
competitions/orbit-wars/agent/main.py
competitions/orbit-wars/agent/versions/hybrid_v0.py
competitions/orbit-wars/agent/hybrid_model.py
competitions/orbit-wars/agent/hybrid_weights.py or equivalent tiny artifact
competitions/orbit-wars/postmortems/YYYY-MM-DD-hybrid-v0.md
competitions/orbit-wars/tasks.md
competitions/orbit-wars/tracking.md
competitions/orbit-wars/insights.md
```

## Evaluation gates

Run:

```bash
python -m py_compile competitions/orbit-wars/agent/main.py
python -m py_compile competitions/orbit-wars/agent/hybrid_model.py
python competitions/orbit-wars/arena/validate.py --games 10 --procs 4
python competitions/orbit-wars/arena/suite_gate.py main --games 12 --procs 4
python competitions/orbit-wars/arena/eval_4p.py --games 12 --procs 4
```

If promising:

```bash
python competitions/orbit-wars/arena/league.py --games 30 --seed0 <fresh_seed> --procs 4
python competitions/orbit-wars/ops/evaluate_candidate.py --agent competitions/orbit-wars/agent/main.py --games 30 --seed0 <fresh_seed>
```

## Submit-readiness output

If the hybrid candidate is promising, write:

```text
competitions/orbit-wars/live/last_eval.json
competitions/orbit-wars/live/hybrid_v0_eval.md
```

`last_eval.json` should include:

```json
{
  "candidate": "agent/main.py",
  "version": "hybrid_v0",
  "submit_ready": true,
  "gates": {},
  "summary": "..."
}
```

Do not submit in this task.

## Acceptance criteria

- Hybrid version exists and compiles.
- Model scorer is integrated only as scorer/value/posture helper.
- RuleEngine and FlightOracle remain final gate.
- Fallback to rules-only exists.
- Runtime is documented.
- Local gates run and results recorded.
- If promising, `live/last_eval.json` is produced for ladder loop.
- No Kaggle submit/push is performed.
- No secrets are read.

## Stop conditions

Stop if:

- model artifact is missing or too poor;
- FlightOracle is not ready;
- integration causes runtime or validation regressions;
- candidate cannot be made safe without large rewrite;
- forbidden paths would be touched.

## Final response requirements

Report:

- model artifact used;
- integration path;
- fallback behavior;
- validation results;
- submit-ready verdict;
- files changed;
- risks and next steps.
