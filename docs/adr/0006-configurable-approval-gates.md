# ADR-0006: Configurable approval gates — default allow

Status: accepted  
Date: 2026-05-19  
Decided in: `docs/meeting-notes/2026-05-19-r1.md`  
Supersedes: prior implicit policy of "always require approval for remote writes"

---

## Context

Earlier platform design required human approval for all Kaggle submissions, kernel pushes, and git pushes. This was chosen conservatively during M0–M2 setup.

The user's actual Kaggle workflow (see `docs/meeting-notes/2026-05-17-r1.md`) is iterative and fast. Requiring manual approval on every submission adds friction without meaningfully increasing safety for an experienced user who:
- Has already reviewed the code in the job's experiment run
- Understands the submission mechanics
- Wants the agent to handle routine mechanics autonomously

The main human decision points are **strategic** (switch model, switch approach, ensemble), not operational (submit file X, push kernel Y).

## Decision

All approval gates are **configurable per project** and **default to allow (no approval required)**.

### Default policy

```json
{
  "approval_gates": {
    "kaggle_submit":    false,
    "kernel_push":      false,
    "dataset_upload":   true,
    "git_push":         false,
    "git_force_push":   true,
    "supabase_migrate": true,
    "delete_artifact":  true
  }
}
```

`true` = requires human approval before executing.  
`false` = agent executes autonomously (logged, auditable, but no pause).

`dataset_upload`, `git_force_push`, `supabase_migrate`, and `delete_artifact` default to `true` because they are infrequent, higher-blast-radius operations.

### Per-competition override

A competition record can override the project defaults:
```json
{
  "competition_policy": {
    "kaggle_submit":  true,
    "max_daily_submissions": 5
  }
}
```

Useful if a competition has strict submission limits or the user wants to be more careful during the final days before deadline.

### Per-job override

A job can further restrict (but not loosen) the project/competition policy:
```json
{
  "job_approval_override": {
    "kaggle_submit": true
  }
}
```

Jobs cannot lower gates below what the competition policy sets.

## Implementation

### In `tools/kca/kg.py` (previously `kaggle.py`)

Replace the hard-wired `KCA_ALLOW_REMOTE=1` env-var gate with a policy lookup:

```python
def _check_approval_gate(operation: str, policy: dict) -> None:
    """Raise ApprovalRequired if the operation needs human approval per policy."""
    approval_gates = policy.get('approval_gates', {})
    requires = approval_gates.get(operation, OPERATION_DEFAULTS[operation])
    if requires:
        raise ApprovalRequired(operation, policy)
```

`OPERATION_DEFAULTS` mirrors the table above. The `KCA_ALLOW_REMOTE` env var is kept as an emergency override for CI/scripted contexts but is no longer the primary gate.

### In `src/worker/tools.py` (`ToolExecutor`)

`ToolExecutor` receives the job's resolved approval policy and calls `_check_approval_gate` before executing any REMOTE_WRITE or SUBMISSION tool.

### In `scripts/run_job.py`

Policy resolution order (highest priority first):
1. Per-job `job_approval_override`
2. Competition `competition_policy`
3. Project `approval_gates`
4. Platform defaults (table above)

### In `kca decisions`

When an approval gate fires, the worker:
1. Inserts a `human_decisions` row with `status='pending'`.
2. Logs the decision_id to stderr.
3. Returns `WorkerResult(status='paused')`.

The human resolves with `kca decisions approve --id <id>` or via the future UI. The job can then be restarted (M4+ resume logic).

## Consequences

- **Positive:** Faster iteration. Agent can run a full research → implement → submit cycle without human touch on routine operations.
- **Positive:** Experienced users are not blocked by unnecessary gates.
- **Positive:** All operations are still logged in `agent_job_events` — autonomy does not mean invisibility.
- **Negative:** Higher risk of an unintended submission on a fresh competition if the user forgets to set `kaggle_submit: true` for that competition.
- **Mitigation:** New competition records should remind the user to review the approval policy before the first `submit` job runs. Platform UI (M7) will surface this clearly.
- **Mitigation:** `kca decisions list` still works as an audit trail for all completed actions, even auto-approved ones.

## Human intervention points (unchanged)

The following always require human judgment regardless of approval gate settings:
- **Major direction changes:** switch model, switch approach, ensemble strategy.
- **Budget exhaustion:** when `max_cost_usd` is hit, human decides whether to increase.
- **Data policy decisions:** using external data, expanding training set beyond competition data.
- **Final submission selection:** choosing which 1–2 runs to use as final submissions.

These are not gate-able by the platform — they are judgment calls that belong to the human and are surfaced via the analysis and eval job outputs.
