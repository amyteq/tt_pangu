# M6-T004: Reviewer worker + sync gate integration

## Milestone
M6.

## Goal
Add an independent reviewer worker that — when the primary worker is about
to call a high-stakes operation — reads the job's event trail and final
plan, calls the reviewer model via LiteLLM, writes the verdict to
`agent_reviews`, and gates the operation accordingly. Sync mode only.

## Read first
1. `src/worker/worker.py` (`_handle_approval_required`, `AgentWorker.resume`).
2. `tools/kca/decisions.py` (existing approval flow).
3. `docs/adr/0006-configurable-approval-gates.md`.
4. `docs/tasks/m6/M6-T001-db-layer-reviews-telemetry.md`.
5. ADR-0012 — draft alongside this task as
   `docs/adr/0012-multi-agent-review.md`.

## Files

### New: `src/worker/reviewer.py`
```python
@dataclass
class ReviewRequest:
    job_id: str
    target_op: str          # kaggle_submit, supabase_migrate, ...
    tool_name: str          # the tool call that triggered the gate
    tool_input: dict
    final_message: str | None
    event_trail: list[dict] # subset of agent_job_events for context

@dataclass
class ReviewVerdict:
    verdict: str            # approve | reject | abstain
    rationale: str
    evidence: dict
    cost_usd: float
    reviewer_model: str

class Reviewer:
    def __init__(self, model: str | None = None, max_tokens: int = 2048,
                 timeout_s: int = 120, dry_run: bool = False): ...
    def review(self, req: ReviewRequest) -> ReviewVerdict: ...
```

The Reviewer prompt template (literal, do not let the agent compose it
from a tool call): a short instruction + the request fields rendered as a
structured block. It must end with a strict JSON output schema:
```json
{"verdict": "approve|reject|abstain", "rationale": "string", "evidence": {...}}
```

Dry-run mode (`dry_run=True`) returns a deterministic `approve` verdict
without calling LiteLLM (used by tests).

### Update: `src/worker/worker.py`
- New helper `_should_consult_reviewer(operation)` reads
  `KCA_REVIEWER_TRIGGER_OPS`; default list matches env.example.
- In `_handle_approval_required(...)`:
  1. If `_should_consult_reviewer(exc.tool_name)` is True and a reviewer
     hasn't already been run for this `(job_id, target_op)` pair:
     a. Build `ReviewRequest` from current job events + tool_input.
     b. Call `Reviewer().review(req)`.
     c. `db.create_review(...)`; emit `reviewer_verdict` span via the OTEL
        helper from T005.
     d. If `verdict == "approve"` → record an `approval_resume` event with
        `event_data={"source": "reviewer", "verdict": "approve"}` and
        let the worker continue (one-shot allowlist for this tool_input,
        same mechanism as human approve).
     e. If `verdict == "reject"`:
        - If `KCA_REVIEWER_ESCALATE_REJECT=1`: fall through to the existing
          human-decisions flow with the reviewer's rationale attached.
        - Else: mark the job `failed` with `stop_reason="reviewer_reject"`.
     f. If `verdict == "abstain"`: same as no reviewer — fall through to
        human-decisions.
- The pause/resume mechanism from M5 keeps working; reviewer is an
  additional pre-pause checkpoint.

### Update: `tools/kca/decisions.py`
Add `decisions list --include-reviews` to surface reviewer rows alongside
human decisions.

## Acceptance criteria
- `python -c "from src.worker.reviewer import Reviewer; r=Reviewer(dry_run=True); print(r.review_dry_run().verdict)"`
  prints `approve`.
- Live test: a dry-run job triggers `kaggle_submit`; with `KCA_REVIEWER_MODEL`
  unset and `dry_run=True` reviewer mode, the worker auto-approves, an
  `agent_reviews` row is inserted, and the job runs to `succeeded`.
- Reject path: forcing the dry-run reviewer to return `reject` produces a
  `human_decisions` row (when `ESCALATE_REJECT=1`) or a `failed` job (when
  `=0`).
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 30 turns. If the reviewer prompt grows beyond ~3k chars, trim
event_trail to the last 20 events rather than truncating the rationale
section.
