---
name: agent-iteration-review
description: Use after tests, validation, benchmark, submission, or CTF solver results are available. Reviews evidence and decides whether to continue, revert, ask human, or stop.
---

# Agent Iteration Review

Use after any meaningful result: test output, failed command, validation score, benchmark, Kaggle public score, browser result, or CTF solver output.

## Review checklist

1. What changed?
2. What command/result produced the evidence?
3. Did the result improve, regress, or fail?
4. Is the failure due to code, data, environment, flaky test, or wrong assumption?
5. What is the smallest next action?
6. Should we continue automatically, ask human, revert, or stop?

## Output format

- **Result:** improved / regressed / failed / inconclusive
- **Evidence:** commands, metrics, logs, artifacts
- **Interpretation:** why it happened
- **Decision:** continue / revert / ask human / stop
- **Next action:** one concrete step
