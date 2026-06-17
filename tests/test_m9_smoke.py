"""M9 smoke tests — regression assertions for Spaceship Titanic.

This module is **assertion-only**. It does not retrain models, does not
re-submit to Kaggle, and does not write to the DB. It reads the metrics
recorded by:

  - M9-T002 (baseline LR, ``experiment_runs.external_run_id='baseline-lr'``)
  - M9-T005 (HGB + feature engineering, ``external_run_id='hgb-fe-v1'``)
  - M9-T004 (the single approved real Kaggle submission, recorded in
    ``submissions.public_score``; the submissions row's
    ``experiment_run_id`` FK points back to the baseline-lr run)

and asserts:

  - ``cv_lr >= 0.78``         (M9 sanity guard, see docs/milestones/README.md §M9)
  - ``cv_hgb >= 0.80``        (M9 sanity guard)
  - ``cv_hgb > cv_lr``        (HGB beat LR on the same CV split)
  - ``public_score IS NOT NULL`` for the M9-T004 submission row

Tests are DB-aware and SKIP cleanly when ``SUPABASE_DB_URL`` is unset OR
when the M9 seed rows (LR run, HGB run, M9-T004 submission) are absent —
so the no-DB CI job stays green, and the live-DB CI job (fresh postgres,
migrations only, no seed data) also stays green. They FAIL on a real
regression only when run against a DB that *does* hold M9 data.

Run with:
    python -m pytest tests/test_m9_smoke.py -v
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

# M9 thresholds — these are sanity guards copied from docs/milestones/README.md §M9.
# They are deliberately well below the recorded values so a real regression
# (data leakage, broken CV split, mis-recorded metric) trips them, but
# routine variance from seed/version drift does not.
LR_CV_FLOOR = 0.78
HGB_CV_FLOOR = 0.80

# External run names (experiment_runs.external_run_id).
LR_RUN_NAME = "baseline-lr"
HGB_RUN_NAME = "hgb-fe-v1"

# The one real Kaggle submission from M9-T004, identified by its
# Kaggle-side submission id. Looking up by external_submission_id keeps
# the test stable across DB recreations.
M9_T004_EXTERNAL_SUBMISSION_ID = "52955657"


def _fetch_cv_accuracy(cur, external_run_id: str) -> float | None:
    """Return the recorded cv_accuracy for an experiment_runs row, or None.

    Reads ``metrics->'cv_accuracy'->>'value'`` which is the shape
    written by the M2 metrics path (see ``tools/kca/db.py::record_metric``).

    Returns None when no row exists for ``external_run_id`` so the caller
    can distinguish "no seed data" (fresh CI DB) from "regression".
    """
    cur.execute(
        """
        SELECT (metrics->'cv_accuracy'->>'value')::float AS cv_accuracy
        FROM experiment_runs
        WHERE external_run_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (external_run_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    cv = row[0]
    assert cv is not None, f"experiment_runs[{external_run_id!r}].metrics->'cv_accuracy'->>'value' is NULL"
    return float(cv)


@pytest.fixture(scope="module")
def m9_metrics():
    """Read all four M9 regression metrics from the DB in one connection.

    Skips cleanly when any seed row (LR run, HGB run, M9-T004 submission)
    is missing — e.g. against the live-db CI job's fresh postgres, which
    has migrations applied but no recorded M9 data. The regression
    assertions only mean something when the seed data is present, so we
    don't want an empty DB to masquerade as a regression.
    """
    import psycopg

    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn:
        with conn.cursor() as cur:
            cv_lr = _fetch_cv_accuracy(cur, LR_RUN_NAME)
            cv_hgb = _fetch_cv_accuracy(cur, HGB_RUN_NAME)

            cur.execute(
                """
                SELECT id, public_score, experiment_run_id
                FROM submissions
                WHERE external_submission_id = %s
                """,
                (M9_T004_EXTERNAL_SUBMISSION_ID,),
            )
            sub = cur.fetchone()

    missing = []
    if cv_lr is None:
        missing.append(f"experiment_runs[{LR_RUN_NAME!r}]")
    if cv_hgb is None:
        missing.append(f"experiment_runs[{HGB_RUN_NAME!r}]")
    if sub is None:
        missing.append(f"submissions[{M9_T004_EXTERNAL_SUBMISSION_ID!r}]")
    if missing:
        pytest.skip(
            "M9 seed data not present in DB ("
            + ", ".join(missing)
            + "); regression assertions require a DB seeded by M9-T002/T004/T005"
        )

    return {
        "cv_lr": cv_lr,
        "cv_hgb": cv_hgb,
        "submission_id": sub[0],
        "public_score": sub[1],
        "submission_experiment_run_id": sub[2],
    }


@requires_db
def test_lr_cv_meets_floor(m9_metrics):
    cv = m9_metrics["cv_lr"]
    assert cv >= LR_CV_FLOOR, (
        f"LR baseline cv_accuracy={cv:.6f} fell below M9 floor {LR_CV_FLOOR}; "
        "do NOT lower the threshold — investigate the run first"
    )


@requires_db
def test_hgb_cv_meets_floor(m9_metrics):
    cv = m9_metrics["cv_hgb"]
    assert cv >= HGB_CV_FLOOR, (
        f"HGB+FE cv_accuracy={cv:.6f} fell below M9 floor {HGB_CV_FLOOR}; "
        "do NOT lower the threshold — investigate the run first"
    )


@requires_db
def test_hgb_beats_lr_on_cv(m9_metrics):
    cv_lr = m9_metrics["cv_lr"]
    cv_hgb = m9_metrics["cv_hgb"]
    assert cv_hgb > cv_lr, (
        f"HGB CV {cv_hgb:.6f} did NOT beat LR CV {cv_lr:.6f}; "
        "the second experiment is expected to improve over the baseline"
    )


@requires_db
def test_m9_t004_public_score_recorded(m9_metrics):
    score = m9_metrics["public_score"]
    assert score is not None, (
        f"submissions row for external_submission_id={M9_T004_EXTERNAL_SUBMISSION_ID!r} has NULL public_score"
    )
    # Sanity: a Kaggle accuracy LB score sits in (0, 1].
    assert 0.0 < float(score) <= 1.0, f"public_score={score!r} outside plausible range (0, 1]"
