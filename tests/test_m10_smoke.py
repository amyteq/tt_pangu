"""M10 smoke tests — regression assertions for Petals to the Metal (TPU).

This module is **assertion-only**. It does not retrain models, does not
(re-)push a Kaggle kernel, and does not write to the DB. It reads the
metrics recorded by:

  - M10-T002 (baseline transfer learning, MobileNetV2; experiment_run_id
    ``830fc32f-2ea8-4309-9fa6-e9cd1e5877ec``, external run
    ``harrysun2006/petals-baseline-transfer-learning/version-1``)
  - M10-T005 (alt-backbone EfficientNetB0; experiment_run_id
    ``c3339154-944b-49aa-8322-f4a8607ad240``, external ``alt-backbone-v1``)
  - M10-T004 (the single approved real Kaggle kernel push; recorded in
    ``submissions`` row ``03b5d080-1c05-47d7-9be1-abdb2ea31aff``, whose
    ``experiment_run_id`` FK points back to the baseline run)
  - the worker's ``kernel_push`` audit trail in ``agent_job_events``

and asserts:

  - baseline ``holdout_accuracy >= BASELINE_FLOOR``
  - alt-backbone ``holdout_accuracy`` is within ``REGRESSION_GUARD_PP`` of
    the baseline (RELAXED — see below)
  - a ``submissions`` row exists for the M10-T004 push with
    ``external_submission_id`` populated (RELAXED — see below)
  - an ``agent_job_events`` row records a ``kernel_push``-related event

Tests are DB-aware and SKIP cleanly when ``SUPABASE_DB_URL`` is unset OR
when the M10 seed rows are absent — so the no-DB CI job stays green, and
the live-DB CI job (fresh postgres, migrations only, no seed data) also
stays green. They FAIL on a real regression only when run against a DB
that *does* hold M10 data.

---

Two acceptance criteria are **deliberately RELAXED** here, reflecting the
human's documented "accept and continue" decision after M10-T004/T005:

1. **LB-score assertion RELAXED.** M10-T004's single approved Kaggle push
   could not complete: push #1 stalled QUEUED and never ran; the approved
   re-push #2 errored on a now-fixed missing-kernelspec bug. NO public LB
   score exists. Push #1 nonetheless wrote a ``submissions`` row
   (``03b5d080-...``) with ``public_score`` NULL and a populated
   ``external_submission_id`` (the kernel-version ref). So instead of
   "public_score IS NOT NULL", this module asserts the row exists with a
   populated ``external_submission_id`` and links to the baseline run, and
   *documents* the NULL public_score as a known deviation (follow-ups
   #34/#35). It does NOT trigger any Kaggle push.

2. **"alt >= baseline" RELAXED.** M10-T005's EfficientNetB0 run REGRESSED
   ~3.4pp vs the MobileNetV2 baseline (alt holdout 0.3966 vs baseline
   0.4310), accepted as PASS-with-note (within the 10pp unexplained-
   regression guard; explained: classifier head still climbing at 3
   epochs). So this module asserts the WEAKER documented form: alt holdout
   is within ``REGRESSION_GUARD_PP`` of the baseline, not strictly >=.

Run with:
    python -m pytest tests/test_m10_smoke.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

requires_db = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set",
)

# --- M10 thresholds ---------------------------------------------------------
#
# Baseline floor. The full-dataset reference for this task is ~0.7707, but
# M10-T002 trains on a *local slice* with a short epoch budget, recording
# holdout_accuracy=0.4310. The floor is therefore a sanity guard against a
# leakage / broken-CV-split / mis-recorded-metric regression, NOT a target:
# 0.30 sits well above the ~0.0096 chance level for a 104-class task yet
# comfortably below the recorded 0.4310. Do NOT lower it to paper over a
# regression — investigate the run instead (task spec stop condition).
BASELINE_FLOOR = 0.30

# Unexplained-regression guard (percentage points), mirroring M10-T005's
# acceptance: a >10pp drop without explanation is a hard FAIL. The alt run's
# documented -3.4pp regression is within this guard.
REGRESSION_GUARD_PP = 0.10

# experiment_runs.id values (stable across DB recreations of the same seed).
BASELINE_RUN_ID = "830fc32f-2ea8-4309-9fa6-e9cd1e5877ec"
ALT_RUN_ID = "c3339154-944b-49aa-8322-f4a8607ad240"

# The single M10-T004 push's submissions row (push #1; see module docstring).
M10_T004_SUBMISSION_ID = "03b5d080-1c05-47d7-9be1-abdb2ea31aff"
COMPETITION_ID = "4c69e842-eade-41e4-9143-b5d3966a9578"


def _fetch_holdout_accuracy(cur, run_id: str) -> float | None:
    """Return recorded holdout_accuracy for an experiment_runs row, or None.

    Reads ``metrics->'holdout_accuracy'->>'value'`` — the shape written by
    the M2 metrics path (``tools/kca/db.py::record_metric``). Returns None
    when no row exists so the caller can distinguish "no seed data" (fresh
    CI DB) from "regression".
    """
    cur.execute(
        """
        SELECT (metrics->'holdout_accuracy'->>'value')::float AS holdout_accuracy
        FROM experiment_runs
        WHERE id = %s
        """,
        (run_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    acc = row[0]
    assert acc is not None, f"experiment_runs[{run_id!r}].metrics->'holdout_accuracy'->>'value' is NULL"
    return float(acc)


@pytest.fixture(scope="module")
def m10_metrics():
    """Read all M10 regression evidence from the DB in one connection.

    Skips cleanly when any seed row (baseline run, alt run, M10-T004
    submission) is missing — e.g. against the live-db CI job's fresh
    postgres, which has migrations applied but no recorded M10 data.
    """
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn:
        with conn.cursor() as cur:
            baseline_acc = _fetch_holdout_accuracy(cur, BASELINE_RUN_ID)
            alt_acc = _fetch_holdout_accuracy(cur, ALT_RUN_ID)

            cur.execute(
                """
                SELECT id, public_score, external_submission_id,
                       experiment_run_id, competition_id
                FROM submissions
                WHERE id = %s
                """,
                (M10_T004_SUBMISSION_ID,),
            )
            sub = cur.fetchone()

            # kernel_push-related audit trail. The worker did not emit a
            # dedicated ``kernel_push`` *event_type*; it tags the operation
            # inside event_data (tool / operation / target_op) across
            # tool_call / approval_pause / reviewer_abstain rows.
            cur.execute(
                """
                SELECT count(*) FROM agent_job_events
                WHERE event_data->>'operation' = 'kernel_push'
                   OR event_data->>'tool' = 'kernel_push'
                   OR event_data->>'target_op' = 'kernel_push'
                """
            )
            kernel_push_event_count = cur.fetchone()[0]

    missing = []
    if baseline_acc is None:
        missing.append(f"experiment_runs[{BASELINE_RUN_ID!r}]")
    if alt_acc is None:
        missing.append(f"experiment_runs[{ALT_RUN_ID!r}]")
    if sub is None:
        missing.append(f"submissions[{M10_T004_SUBMISSION_ID!r}]")
    if missing:
        pytest.skip(
            "M10 seed data not present in DB ("
            + ", ".join(missing)
            + "); regression assertions require a DB seeded by "
            "M10-T002/T004/T005"
        )

    return {
        "baseline_acc": baseline_acc,
        "alt_acc": alt_acc,
        "submission_id": sub[0],
        "public_score": sub[1],
        "external_submission_id": sub[2],
        "submission_experiment_run_id": sub[3],
        "submission_competition_id": sub[4],
        "kernel_push_event_count": kernel_push_event_count,
    }


@requires_db
def test_baseline_local_metric_clears_floor(m10_metrics):
    acc = m10_metrics["baseline_acc"]
    assert acc >= BASELINE_FLOOR, (
        f"baseline holdout_accuracy={acc:.6f} fell below M10 floor "
        f"{BASELINE_FLOOR}; do NOT lower the threshold — investigate the "
        "run first (task spec stop condition)"
    )


@requires_db
def test_alt_local_metric_within_regression_guard(m10_metrics):
    """RELAXED form of "alt >= baseline".

    M10-T005's EfficientNetB0 regressed ~3.4pp vs the MobileNetV2 baseline
    (0.3966 vs 0.4310), accepted as PASS-with-note (head still climbing at
    3 epochs). The hard guard is a >10pp unexplained drop, mirroring the
    M10-T005 acceptance criterion. A strict ``alt >= baseline`` assertion
    would contradict the human's accept-and-continue decision, so we assert
    the documented weaker form here.
    """
    baseline = m10_metrics["baseline_acc"]
    alt = m10_metrics["alt_acc"]
    drop = baseline - alt
    assert drop <= REGRESSION_GUARD_PP, (
        f"alt-backbone holdout_accuracy={alt:.6f} regressed "
        f"{drop * 100:.1f}pp below baseline {baseline:.6f}, exceeding the "
        f"{REGRESSION_GUARD_PP * 100:.0f}pp unexplained-regression guard; "
        "this is the M9 'CV scores diverge' rollback condition — re-run "
        "M10-T005, do NOT widen the guard"
    )


@requires_db
def test_real_push_submission_row_exists(m10_metrics):
    """RELAXED form of "public_score IS NOT NULL".

    M10-T004's approved push never produced a public LB score (push #1
    stalled QUEUED; approved re-push #2 hit a now-fixed missing-kernelspec
    bug). The documented deviation (follow-ups #34/#35) is: a submissions
    row exists for the push attempt with external_submission_id populated
    and public_score NULL. We assert that shape and explicitly document the
    NULL public_score rather than fail or trigger a new Kaggle push.
    """
    # The row exists and links to the baseline run + competition.
    assert str(m10_metrics["submission_experiment_run_id"]) == BASELINE_RUN_ID, (
        f"M10-T004 submission row does not link to the baseline run {BASELINE_RUN_ID}"
    )
    assert str(m10_metrics["submission_competition_id"]) == COMPETITION_ID, (
        "M10-T004 submission row competition_id mismatch"
    )
    # external_submission_id is populated (the kernel-version ref).
    ext = m10_metrics["external_submission_id"]
    assert ext, (
        "M10-T004 submission row has empty external_submission_id; the "
        "push attempt should have recorded the kernel-version ref"
    )
    # DOCUMENTED DEVIATION: public_score is NULL because no kernel run
    # completed. This is the human-accepted state, tracked by #34/#35.
    # Asserting it is NULL pins the known deviation so a future accidental
    # backfill (or a real LB score landing) flips this test and forces a
    # conscious update rather than silently masking the gap.
    assert m10_metrics["public_score"] is None, (
        "public_score is no longer NULL for the M10-T004 push — a real LB "
        "score may have landed; update this test and re-assert the "
        "0 < score <= 1 sanity bound (see follow-ups #34/#35)"
    )


@requires_db
def test_kernel_push_event_recorded(m10_metrics):
    count = m10_metrics["kernel_push_event_count"]
    assert count > 0, (
        "no agent_job_events row records a kernel_push-related event "
        "(event_data.operation / tool / target_op == 'kernel_push'); the "
        "M10-T004 worker push should have left an audit trail"
    )
