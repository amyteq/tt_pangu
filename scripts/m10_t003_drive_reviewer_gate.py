"""M10-T003: drive the worker to fire the reviewer-gate on kernel_push.

Mirrors M9-T003's reviewer-gate driver but for the
``target_op="kernel_push"`` path used by the Petals to the Metal
notebook-submission flow.

This script:
  1. Creates a real ``agent_jobs`` row for the M10 baseline notebook
     (``experiments/tpu-getting-started/baseline-tl/baseline.ipynb`` +
     ``kernel-metadata.json`` from M10-T002).
  2. Runs ``AgentWorker`` with a ``MockLiteLLMClient`` that emits one
     synthetic ``kernel_push`` tool call. ``tool_decisions["kernel_push"]="ask"``
     forces ``ApprovalRequired`` into ``_handle_approval_required``.
  3. Sets ``KCA_REVIEWER_TRIGGER_OPS=kernel_push`` so the reviewer gate
     actually fires for this op (default trigger set only covers
     ``kaggle_submit`` / migrations / git_force_push).
  4. Forces the sync reviewer to ABSTAIN (no live LLM call) so the
     handler writes an ``agent_reviews`` row (verdict='abstain') AND
     falls through to the human-decisions branch — inserting a pending
     ``human_decisions`` row tied to the job.
  5. Prints job_id / review_id / decision_id for the closeout report.

The script never invokes ``kaggle kernels push`` / ``kca kaggle push``.
The worker stops with ``stop_reason="approval_required"``.

Note on event-type literals (issue #16): the worker emits
``approval_pause`` (human gate) + ``reviewer_abstain`` (reviewer gate)
under current code. M10-T003 uses whatever literals the worker emits
today, per the task spec's "do NOT block on closing #16" rule.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import db as _db  # type: ignore  # noqa: E402

from src.worker._types import JobPolicy  # noqa: E402
from src.worker.worker import AgentWorker, MockLiteLLMClient  # noqa: E402
from src.worker import reviewer as reviewer_mod  # noqa: E402


def _single_kernel_push_client() -> MockLiteLLMClient:
    """LiteLLM mock: emit one `kernel_push` tool call, then stop."""

    client = MockLiteLLMClient(scenario="two_turns")
    turn = {"n": 0}

    def completion(**_kwargs):
        turn["n"] += 1
        if turn["n"] == 1:
            tc = types.SimpleNamespace(
                id="call_kernel_push_0",
                type="function",
                function=types.SimpleNamespace(
                    name="kernel_push",
                    arguments=json.dumps(
                        {
                            "competition": "tpu-getting-started",
                            "notebook": "experiments/tpu-getting-started/baseline-tl/baseline.ipynb",
                            "kernel_metadata": "experiments/tpu-getting-started/baseline-tl/kernel-metadata.json",
                            "message": "M10-T002 baseline TL (M10-T003 reviewer gate)",
                        }
                    ),
                ),
            )
            msg = types.SimpleNamespace(content=None, tool_calls=[tc])
            choice = types.SimpleNamespace(message=msg, finish_reason="tool_calls")
            return types.SimpleNamespace(
                choices=[choice],
                usage=types.SimpleNamespace(prompt_tokens=20, completion_tokens=10),
            )
        msg = types.SimpleNamespace(content="done", tool_calls=None)
        choice = types.SimpleNamespace(message=msg, finish_reason="stop")
        return types.SimpleNamespace(
            choices=[choice],
            usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )

    client.completion = completion  # type: ignore[method-assign]
    return client


class _AbstainReviewer:
    """Sync reviewer stub that always abstains. Never calls a real LLM."""

    def __init__(self, *_args, **_kwargs):
        self.model = "stub-abstain"
        self.dry_run = False

    def review(self, _req):
        return reviewer_mod.ReviewVerdict(
            verdict="abstain",
            rationale="M10-T003 driver: forced abstain to exercise human-decisions path",
            evidence={"mode": "m10_t003_stub"},
            cost_usd=0.0,
            reviewer_model=self.model,
        )


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("SUPABASE_DB_URL not set", file=sys.stderr)
        return 2

    # Tell the reviewer gate to fire for kernel_push (default set only
    # covers kaggle_submit / supabase_migrate / git_force_push / ...).
    os.environ["KCA_REVIEWER_TRIGGER_OPS"] = "kernel_push"

    # Patch reviewer to abstain so the handler records agent_reviews AND
    # falls through to insert_approval_request (human_decisions pending).
    reviewer_mod.Reviewer = _AbstainReviewer  # type: ignore[assignment]

    # Build a real agent_jobs row directly (local schema lacks competition_id).
    policy_payload = {
        "max_turns": 4,
        "model": "claude-sonnet-4-6",
        "tool_decisions": {"kernel_push": "ask"},
    }
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(db_url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_jobs
                  (project_id, status, prompt, model, policy, job_type)
                VALUES
                  (%s::uuid, 'queued', %s, %s, %s::jsonb, 'm10_t003_driver')
                RETURNING id::text
                """,
                (
                    _db.DEFAULT_PROJECT_ID,
                    "M10-T003 driver: kernel_push tpu-getting-started baseline",
                    "claude-sonnet-4-6",
                    json.dumps(policy_payload),
                ),
            )
            job_id = cur.fetchone()["id"]
        conn.commit()
    finally:
        conn.close()
    print(f"job_id={job_id}")

    policy = JobPolicy(
        max_turns=4,
        skill_name="m10-t003-driver",
        policy_profile="default",
        mode="default",
        tool_decisions={"kernel_push": "ask"},
    )
    workspace = REPO_ROOT
    worker = AgentWorker(
        job_id=job_id,
        prompt="M10-T003 driver: kernel_push tpu-getting-started baseline",
        policy=policy,
        workspace=workspace,
        db_url=db_url,
        dry_run=True,  # avoid real LiteLLM in the worker main loop
    )
    worker._mock_client = _single_kernel_push_client()
    result = worker.run()
    print(f"worker.status={result.status} stop_reason={result.stop_reason}")

    # Surface the agent_reviews + human_decisions rows for closeout.
    review = _db.find_review_for_op(job_id, "kernel_push")
    print(f"agent_reviews.id={review['id'] if review else None} verdict={review['verdict'] if review else None}")

    pending = _db.list_pending_decisions(job_id=job_id)
    print(f"human_decisions pending count={len(pending)}")
    if pending:
        print(f"human_decisions.id={pending[0]['id']} status={pending[0]['status']}")

    # List job events so the closeout can cite the approval_pause event.
    events = _db.list_job_events(job_id)
    types_only = [
        (
            e.get("event_type"),
            (e.get("event_data") or {}).get("operation") or (e.get("event_data") or {}).get("target_op") or "",
        )
        for e in events
    ]
    print(f"events={types_only}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
