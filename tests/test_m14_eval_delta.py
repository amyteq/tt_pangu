"""M14-T009 / issue #63 — eval-delta-check PR gate regression tests.

The blocking gate lives inline in `.github/workflows/eval.yml`
(`eval-delta-check` job). These tests:

  1. Pin the per-suite threshold algorithm (absolute shape thresholds +
     relative cv_score deltas) against synthetic snapshots — a clean PR
     passes; a regressing PR fails.
  2. Assert the checked-in baseline matches the live mocked run shape so the
     gate compares against a faithful baseline.
  3. Assert the workflow wires the gate: PR trigger, the eval:waive-delta
     label bypass, the mandatory-rationale + agent_tool_audit recording.

The algorithm here MUST stay byte-compatible with the workflow heredoc; if
you change one, change the other.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / "eval" / "baselines" / "mocked-baseline.json"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "eval.yml"

REL_TOL = 0.02
LOWER_IS_BETTER = {"rmsle", "rmse", "logloss", "mae"}


def _regressions(baseline: dict, current: dict) -> list[str]:
    """Mirror of the eval-delta-check heredoc comparator in eval.yml."""
    base_by_name = {s["name"]: s for s in baseline.get("suites", [])}
    cur_by_name = {s["name"]: s for s in current.get("suites", [])}
    regressions: list[str] = []
    for name, b in base_by_name.items():
        c = cur_by_name.get(name)
        if c is None:
            regressions.append(f"{name}: suite missing from PR run")
            continue
        if c.get("fail", 0) > 0:
            regressions.append(f"{name}: fail")
        if c.get("error", 0) > 0:
            regressions.append(f"{name}: error")
        if c.get("audit_grep_violations", 0) > 0:
            regressions.append(f"{name}: audit_grep_violations")
        if c.get("pass", 0) < b.get("pass", 0):
            regressions.append(f"{name}: pass dropped below floor")
        b_cv = b.get("cv_score")
        c_cv = c.get("cv_score")
        if b_cv is not None and c_cv is not None:
            metric = (b.get("cv_metric") or "").lower()
            tol = b.get("rel_tol", REL_TOL)
            if metric in LOWER_IS_BETTER:
                if c_cv > b_cv * (1 + tol):
                    regressions.append(f"{name}: cv_score worse (lower-is-better)")
            else:
                if c_cv < b_cv * (1 - tol):
                    regressions.append(f"{name}: cv_score worse (higher-is-better)")
    return regressions


def _baseline() -> dict:
    return json.loads(BASELINE.read_text())


# ---------------------------------------------------------------------------
# Absolute shape thresholds
# ---------------------------------------------------------------------------


def test_clean_pr_against_self_has_no_regression():
    base = _baseline()
    assert _regressions(base, base) == []


def test_new_failing_case_regresses():
    base = _baseline()
    cur = json.loads(json.dumps(base))
    cur["suites"][0]["fail"] = 1
    regs = _regressions(base, cur)
    assert any("fail" in r for r in regs)


def test_new_error_regresses():
    base = _baseline()
    cur = json.loads(json.dumps(base))
    cur["suites"][0]["error"] = 1
    assert any("error" in r for r in _regressions(base, cur))


def test_audit_grep_violation_regresses():
    base = _baseline()
    cur = json.loads(json.dumps(base))
    cur["suites"][0]["audit_grep_violations"] = 1
    assert any("audit_grep" in r for r in _regressions(base, cur))


def test_pass_dropping_below_floor_regresses():
    base = _baseline()
    cur = json.loads(json.dumps(base))
    # flip one pass to skip in tool-smoke
    ts = next(s for s in cur["suites"] if s["name"] == "tool-smoke")
    ts["pass"] -= 1
    ts["skip"] += 1
    assert any("pass dropped" in r for r in _regressions(base, cur))


def test_missing_suite_regresses():
    base = _baseline()
    cur = json.loads(json.dumps(base))
    cur["suites"] = cur["suites"][1:]  # drop the first suite
    assert any("missing" in r for r in _regressions(base, cur))


def test_extra_pass_is_not_a_regression():
    """A PR that improves (more passing cases) must NOT be flagged."""
    base = _baseline()
    cur = json.loads(json.dumps(base))
    cur["suites"][0]["pass"] += 1
    cur["suites"][0]["case_count"] += 1
    assert _regressions(base, cur) == []


# ---------------------------------------------------------------------------
# Relative cv_score thresholds (arm only when baseline records a cv_score)
# ---------------------------------------------------------------------------


def test_cv_score_within_tolerance_passes_higher_is_better():
    base = {
        "suites": [
            {
                "name": "kaggle-replay-titanic",
                "pass": 1,
                "cv_score": 0.80,
                "cv_metric": "accuracy",
            }
        ]
    }
    cur = {
        "suites": [
            {
                "name": "kaggle-replay-titanic",
                "pass": 1,
                "cv_score": 0.792,
                "cv_metric": "accuracy",
            }
        ]
    }
    assert _regressions(base, cur) == []  # 1% drop within 2% tol


def test_cv_score_past_tolerance_regresses_higher_is_better():
    base = {
        "suites": [
            {
                "name": "kaggle-replay-titanic",
                "pass": 1,
                "cv_score": 0.80,
                "cv_metric": "accuracy",
            }
        ]
    }
    cur = {
        "suites": [
            {
                "name": "kaggle-replay-titanic",
                "pass": 1,
                "cv_score": 0.75,
                "cv_metric": "accuracy",
            }
        ]
    }
    assert any("cv_score" in r for r in _regressions(base, cur))  # ~6% drop


def test_cv_score_lower_is_better_regresses_on_increase():
    base = {
        "suites": [
            {
                "name": "kaggle-replay-house-prices",
                "pass": 1,
                "cv_score": 0.12,
                "cv_metric": "rmsle",
            }
        ]
    }
    cur = {
        "suites": [
            {
                "name": "kaggle-replay-house-prices",
                "pass": 1,
                "cv_score": 0.20,
                "cv_metric": "rmsle",
            }
        ]
    }
    assert any("cv_score" in r for r in _regressions(base, cur))


def test_cv_score_lower_is_better_passes_on_improvement():
    base = {
        "suites": [
            {
                "name": "kaggle-replay-house-prices",
                "pass": 1,
                "cv_score": 0.12,
                "cv_metric": "rmsle",
            }
        ]
    }
    cur = {
        "suites": [
            {
                "name": "kaggle-replay-house-prices",
                "pass": 1,
                "cv_score": 0.11,
                "cv_metric": "rmsle",
            }
        ]
    }
    assert _regressions(base, cur) == []


# ---------------------------------------------------------------------------
# Baseline fidelity + workflow wiring
# ---------------------------------------------------------------------------


def test_baseline_snapshot_is_well_formed():
    base = _baseline()
    assert base["route"] == "mocked"
    assert base["dry_run"] is True
    names = {s["name"] for s in base["suites"]}
    # the six M13 suites the gate covers
    assert names == {
        "tool-smoke",
        "reasoning",
        "kernel-dryrun",
        "kaggle-replay-titanic",
        "kaggle-replay-spaceship-titanic",
        "kaggle-replay-house-prices",
    }
    for s in base["suites"]:
        assert s["fail"] == 0
        assert s["error"] == 0
        assert s["audit_grep_violations"] == 0


def test_workflow_wires_the_pr_gate():
    text = WORKFLOW.read_text()
    assert "eval-delta-check" in text
    assert "pull_request" in text
    assert "eval/baselines/mocked-baseline.json" in text
    # human-only bypass label + mandatory rationale + audit recording
    assert "eval:waive-delta" in text
    assert "rationale" in text
    assert "insert_tool_audit" in text or "agent_tool_audit" in text
    # reuses the mocked, dry-run runner
    assert "--all --route mocked --dry-run --json" in text
