# ADR-0010: Per-job-type model routing

## Status
Accepted (M5).

## Context
M3/M4 used a single model (`claude-sonnet-4-6`) for every worker job regardless of job type. As we scale to multi-job workflows (research gathering, implementation, evaluation, analysis), one-size-fits-all spending becomes wasteful: Opus is overkill for a quick triage prompt and Haiku is too weak for code generation.

ADR-0002 sketched a hybrid worker model, and ADR-0004 chose LiteLLM as the provider layer; this ADR pins down *which* model is used by default for *which* job type, while keeping `--model` as a hard override.

## Decision
Introduce `src/worker/routing.py` with the following route table:

| Job type     | Default model        | Why                                        |
|--------------|----------------------|--------------------------------------------|
| `research`   | `claude-haiku-4-5`   | Read-heavy triage/log summarisation.       |
| `implement`  | `claude-sonnet-4-6`  | Default coding workhorse.                  |
| `experiment` | `claude-sonnet-4-6`  | Same as implement.                         |
| `eval`       | `claude-opus-4-7`    | Hard reasoning: pick best, judge outputs.  |
| `analysis`   | `claude-opus-4-7`    | Reserved for deeper failure analysis.      |
| `review`     | `claude-opus-4-7`    | Independent reviewer of agent output.      |

Override precedence: `--model <id>` > `MODEL_ROUTES[job_type]` > default Sonnet (`claude-sonnet-4-6`).

`scripts/run_job.py` gains `--job-type` (default: `implement`) and prints the resolved `"model"` field in its `--json` output.

## Consequences
- Cheaper average job cost: Haiku for routine work, Opus only when needed.
- One source of truth for routing; revisits land here, not in callers.
- Future work (M6+): tune table under real load; consider cost-aware routing (budget-driven downgrade Sonnet→Haiku for late turns) and local provider fallbacks for log triage.
