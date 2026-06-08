"""M12-T007: fire the devpost_submit reviewer-gate in prepare-and-halt mode.

This script does NOT run cmd_submit. It records the three canonical
rows (agent_reviews + human_decisions + agent_job_events) that the
worker would write when stopping at the devpost_submit gate, so the
human-approval / decision_api round-trip can be exercised without any
network call to devpost.com.

Wired to the T006 run id `r-20260608_154243` for slug `h01`. The
agent_jobs row id and experiment_runs row id are taken from the T006
closeout and passed via env so the script never embeds them.

Outputs (stdout, JSON):
  {"agent_reviews_id": "...", "human_decisions_id": "...",
   "agent_job_events_id": <int>, "job_id": "...",
   "run_id": "...", "slug": "...", "competition_id": "..."}

Side-effects: three DB inserts. No HTTP. Idempotent across re-runs only
in the sense that a re-run inserts a SECOND set of rows; the prepare-
and-halt acceptance is "at least one" of each. Do not run twice.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import db as _db  # type: ignore  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--job-id",
        required=True,
        help="agent_jobs row id from M12-T006 closeout (UUID).",
    )
    p.add_argument(
        "--run-id",
        required=True,
        help="experiment_runs row id from M12-T006 closeout (UUID).",
    )
    p.add_argument("--slug", required=True, help="hackathon slug, e.g. 'h01'.")
    p.add_argument(
        "--competition-id",
        required=True,
        help="competitions row id for the hackathon (UUID).",
    )
    p.add_argument(
        "--target-op",
        default="devpost_submit",
        help="reviewer-gate target_op literal (default: devpost_submit).",
    )
    args = p.parse_args()

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("SUPABASE_DB_URL not set", file=sys.stderr)
        return 2

    target_op = args.target_op
    pack_dir = f"runs/{args.slug}/r-20260608_154243/submission_pack"

    # 1) agent_reviews row — sync reviewer ABSTAINS so the gate falls
    #    through to the human-decisions branch. This mirrors the M9-T003
    #    prepare-and-halt pattern (the reviewer never auto-approves a
    #    SUBMISSION-level write op when the artefacts list is incomplete).
    review_evidence = {
        "mode": "m12_t007_prepare_and_halt",
        "submission_pack": pack_dir,
        "checklist_summary": {
            "done": 6,
            "blocked": 3,
            "total": 9,
            "completion_pct": 66.67,
        },
        "blocked_items": [
            "less_than_3minute_demo_video_youtube_preferred",
            "published_vercel_project_link__vercel_team_id",
            "include_the_following_screenshots_of_your_v0vercel_project",
        ],
    }
    review_id = _db.create_review(
        job_id=args.job_id,
        run_id=args.run_id,
        reviewer_model="m12-t007-prepare-and-halt",
        verdict="abstain",
        reviewer_kind="sync",
        target_op=target_op,
        rationale=(
            "M12-T007 prepare-and-halt: submission pack is 6/9 complete "
            "with 3 human-gated artefacts (video, Vercel link, screenshots) "
            "still blocked. Defer to human-decisions branch; do NOT auto-"
            "approve a SUBMISSION-level write."
        ),
        evidence=review_evidence,
        cost_usd=0.0,
    )

    # 2) human_decisions row — pending. Linked to job + carries the
    #    devpost-specific prompt the UI / `kca decisions approve` will
    #    surface.
    options = {
        "approve": "allow the real `kca devpost submit` call to run",
        "deny": "block the submit; close T007 with status='blocked'",
    }
    prompt = (
        f"Worker job {args.job_id} wants to call devpost_submit "
        f"for slug={args.slug} run_id={args.run_id}. "
        "Submission pack is 6/9 complete; 3 human-gated artefacts "
        "(demo video, Vercel link, screenshots) still missing. Approve "
        "only after providing the three artefacts in a follow-up "
        "comment on the closing issue."
    )
    decision_id = _db.insert_approval_request(
        decision_type="tool_approval",
        prompt=prompt,
        options=options,
        job_id=args.job_id,
    )

    # 3) agent_job_events row — canonical `approval_pause` event type
    #    (matches src/worker/worker.py _handle_approval_required).
    event_data = {
        "tool": target_op,
        "operation": target_op,
        "target_op": target_op,
        "tool_input": {
            "slug": args.slug,
            "run_id": args.run_id,
            "competition_id": args.competition_id,
        },
        "side_effect": "SUBMISSION",
        "decision_id": decision_id,
        "review_id": review_id,
        "mode": "m12_t007_prepare_and_halt",
    }
    event_id = _db.append_job_event(
        job_id=args.job_id,
        event_type="approval_pause",
        turn_number=None,
        event_data=event_data,
    )

    print(
        json.dumps(
            {
                "agent_reviews_id": review_id,
                "human_decisions_id": decision_id,
                "agent_job_events_id": event_id,
                "job_id": args.job_id,
                "run_id": args.run_id,
                "slug": args.slug,
                "competition_id": args.competition_id,
                "target_op": target_op,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
