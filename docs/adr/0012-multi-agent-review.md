# ADR-0012: Multi-agent sync review for high-stakes operations

## Status
Accepted (M6).

## Context
Approval gates from ADR-0006 already pause the worker before high-stakes operations (`kaggle_submit`, `supabase_migrate`, `git_force_push`, `dataset_upload`, `delete_artifact`) and hand off to a human via `human_decisions`. The human approval flow is correct but slow — even when the operation is obviously safe, the worker idles until someone clicks. We want a second AI agent to clear the obvious cases sync, leaving humans only the genuinely ambiguous ones.

## Decision
Add `src/worker/reviewer.py` implementing a sync reviewer that runs inside the worker process when an approval gate fires.

Trigger set is `KCA_REVIEWER_TRIGGER_OPS` (default matches the high-stakes list above). When the gating op matches, the worker:

1. Looks up `agent_reviews(job_id, target_op)` — if a verdict already exists for this pair, skips re-review (idempotent on resume).
2. Builds a `ReviewRequest` from the recent `agent_job_events` trail and the gated tool's input.
3. Calls `Reviewer.review(req)` which returns `ReviewVerdict(verdict, rationale, evidence, cost_usd, reviewer_model)`.
4. Writes one row to `agent_reviews` via `db.create_review(...)`.
5. Dispatches on the verdict:
   - **approve** → emit `approval_resume` event with `event_data={"source":"reviewer","verdict":"approve"}`. The worker then re-executes the gated tool through the same one-shot allowlist mechanism used for human approves.
   - **reject** + `KCA_REVIEWER_ESCALATE_REJECT=1` → fall through to the existing human-decisions flow, attaching the reviewer's rationale so the human sees why the AI said no.
   - **reject** + `KCA_REVIEWER_ESCALATE_REJECT=0` → mark the job `failed` with `stop_reason="reviewer_reject"` and persist the `agent_reviews` row.
   - **abstain** → fall through to the human path unchanged. Reviewer declined to take responsibility; humans must.

The reviewer uses a strict-JSON output schema and a deterministic `dry_run=True` mode that returns `approve` without any model call (for tests and CI). The reviewer model defaults to `KCA_REVIEWER_MODEL` (default `claude-opus-4-7`), but can be swapped to a local model in later milestones.

## Consequences
- High-volume safe operations stop pinging humans.
- Reviewer rejects + escalations still preserve human-in-the-loop authority.
- A pathological reviewer cannot silently push: a reject either pages a human or fails the job; it never auto-resumes.
- Every verdict is persisted in `agent_reviews` for audit, including the reviewer model id and cost — making it easy to compare reviewer quality across milestones.
- Costs roughly one extra LLM call per high-stakes attempt; offset by skipping when the verdict already exists for the (job, target_op) pair.
