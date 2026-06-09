"""M13-T007 — pure-function tests for the metrics aggregator.

These tests intentionally avoid any DB connection: they call
:func:`tools.kca.eval.report.build_payload` with hand-built rows and
assert on the resulting :class:`ReportPayload`, the JSON serialisation
shape, and the byte-identical Markdown contract.

The DB-aware entry point (:func:`summarize_run`) is exercised via a
stub ``db_module`` object that satisfies the same protocol the real
``tools/kca/db.py`` exposes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure tools/kca is on the path the same way the CLI invokes it.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "kca"))

from eval import report as _report  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


def _make_run_row() -> dict:
    return {
        "id": "abc-123",
        "started_at": datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 6, 1, 10, 5, 0, tzinfo=timezone.utc),
        "total_pass": 2,
        "total_fail": 1,
        "total_skip": 1,
        "total_cases": 4,
        "cost_usd": 0.0123,
        "aborted_on_budget": False,
    }


def _make_result_rows() -> list[dict]:
    return [
        {
            "suite_name": "tool-smoke",
            "route": "mocked",
            "case_name": "a",
            "status": "pass",
            "metrics": {"accuracy": 0.95, "tokens": 100},
            "latency_ms": 50,
            "cost_usd": 0.0,
            "created_at": datetime(2026, 6, 1, 10, 0, 1, tzinfo=timezone.utc),
        },
        {
            "suite_name": "tool-smoke",
            "route": "mocked",
            "case_name": "b",
            "status": "fail",
            "metrics": {"accuracy": 0.80},
            "latency_ms": 60,
            "cost_usd": 0.0,
            "created_at": datetime(2026, 6, 1, 10, 0, 2, tzinfo=timezone.utc),
        },
        {
            "suite_name": "reasoning",
            "route": "claude_haiku_4_5",
            "case_name": "c",
            "status": "skip",
            "metrics": {"reason": "REMOTE_NOT_APPROVED"},
            "latency_ms": 0,
            "cost_usd": 0.0,
            "created_at": datetime(2026, 6, 1, 10, 0, 3, tzinfo=timezone.utc),
        },
        {
            "suite_name": "reasoning",
            "route": "mocked",
            "case_name": "d",
            "status": "pass",
            "metrics": {"rubric_score": 0.92, "tokens": 200},
            "latency_ms": 75,
            "cost_usd": 0.01,
            "created_at": datetime(2026, 6, 1, 10, 0, 4, tzinfo=timezone.utc),
        },
    ]


# ---------------------------------------------------------------------------
# Pure-function tests.
# ---------------------------------------------------------------------------


def test_build_payload_groups_by_suite_route():
    payload = _report.build_payload(
        run_id="abc-123",
        run_row=_make_run_row(),
        result_rows=_make_result_rows(),
        suite_order=["tool-smoke", "reasoning"],
    )

    assert payload.run_id == "abc-123"
    assert payload.totals == {"pass": 2, "fail": 1, "skip": 1, "error": 0}

    # Two suites, three (suite, route) groups: tool-smoke/mocked,
    # reasoning/mocked, reasoning/claude_haiku_4_5.
    assert len(payload.groups) == 3

    # Suite registration order is honoured: tool-smoke first.
    assert payload.groups[0].suite == "tool-smoke"

    # Routes within reasoning use canonical order: mocked before
    # claude_haiku_4_5.
    reasoning_groups = [g for g in payload.groups if g.suite == "reasoning"]
    assert [g.route for g in reasoning_groups] == ["mocked", "claude_haiku_4_5"]


def test_metric_aggregate_includes_min_max_mean_p50():
    rows = [
        {"metrics": {"acc": 0.50}, "status": "pass", "case_name": "a"},
        {"metrics": {"acc": 0.80}, "status": "pass", "case_name": "b"},
        {"metrics": {"acc": 0.90}, "status": "pass", "case_name": "c"},
    ]
    payload = _report.build_payload(
        run_id="r",
        run_row={"started_at": "t", "total_pass": 3},
        result_rows=[{**r, "suite_name": "s", "route": "mocked"} for r in rows],
    )
    agg = payload.groups[0].metrics_aggregate["acc"]
    assert agg.min == 0.50
    assert agg.max == 0.90
    assert abs(agg.mean - (0.50 + 0.80 + 0.90) / 3) < 1e-9
    assert agg.p50 == 0.80


def test_aggregate_skips_booleans_and_non_numerics():
    payload = _report.build_payload(
        run_id="r",
        run_row={"started_at": "t", "total_pass": 1},
        result_rows=[
            {
                "suite_name": "s",
                "route": "mocked",
                "case_name": "a",
                "status": "pass",
                "metrics": {
                    "ok": True,  # bool — must be excluded
                    "reason": "skipped",  # str — must be excluded
                    "score": 0.5,
                },
                "latency_ms": 0,
                "cost_usd": 0.0,
            }
        ],
    )
    assert list(payload.groups[0].metrics_aggregate.keys()) == ["score"]


def test_recomputes_totals_when_run_row_lacks_counts():
    rows = _make_result_rows()
    payload = _report.build_payload(
        run_id="r",
        run_row={"started_at": "t"},  # no totals — must recompute
        result_rows=rows,
    )
    assert payload.totals == {"pass": 2, "fail": 1, "skip": 1, "error": 0}


def test_render_markdown_is_byte_deterministic():
    payload = _report.build_payload(
        run_id="abc-123",
        run_row=_make_run_row(),
        result_rows=_make_result_rows(),
        suite_order=["tool-smoke", "reasoning"],
    )
    md1 = _report.render_markdown(payload)
    md2 = _report.render_markdown(payload)
    assert md1 == md2
    # Smoke-check expected structural elements.
    assert "# M13 eval report — abc-123" in md1
    assert "## Totals" in md1
    assert "## By suite × route" in md1
    assert "<details>" in md1
    assert "tool-smoke" in md1


def test_render_json_is_parseable_and_deterministic():
    payload = _report.build_payload(
        run_id="abc-123",
        run_row=_make_run_row(),
        result_rows=_make_result_rows(),
        suite_order=["tool-smoke", "reasoning"],
    )
    j1 = _report.render_json(payload)
    j2 = _report.render_json(payload)
    assert j1 == j2
    d = json.loads(j1)
    for k in (
        "run_id",
        "started_at",
        "finished_at",
        "totals",
        "cost_usd",
        "aborted_on_budget",
        "groups",
    ):
        assert k in d
    # Every group carries the required keys (per ReportPayload contract).
    for g in d["groups"]:
        for k in (
            "suite",
            "route",
            "case_count",
            "pass_count",
            "metrics_aggregate",
            "cases",
        ):
            assert k in g


def test_fixed_point_formatting_in_markdown():
    payload = _report.build_payload(
        run_id="r",
        run_row={
            "started_at": "t",
            "total_pass": 1,
            "cost_usd": 0.123456,
        },
        result_rows=[
            {
                "suite_name": "s",
                "route": "mocked",
                "case_name": "a",
                "status": "pass",
                "metrics": {"acc": 0.876543},
                "latency_ms": 17,
                "cost_usd": 0.045678,
            }
        ],
    )
    md = _report.render_markdown(payload)
    # Cost uses 2 d.p.
    assert "cost $0.12" in md
    # Metric means use 4 d.p.
    assert "0.8765" in md
    # Latency is integer ms.
    assert "| a | pass | 17 |" in md


# ---------------------------------------------------------------------------
# summarize_run with an injected db_module stub.
# ---------------------------------------------------------------------------


class _DBStub:
    def __init__(self, run_row, result_rows, suite_rows):
        self.run_row = run_row
        self.result_rows = result_rows
        self.suite_rows = suite_rows

    def get_eval_run(self, run_id):
        return self.run_row if run_id == self.run_row.get("id") else None

    def fetch_eval_results(self, run_id):
        if run_id != self.run_row.get("id"):
            return []
        return list(self.result_rows)

    def list_eval_suites(self):
        return list(self.suite_rows)


def test_summarize_run_resolves_via_injected_db_module():
    run_row = _make_run_row()
    result_rows = _make_result_rows()
    # Registration order: tool-smoke first.
    suite_rows = [
        {
            "name": "tool-smoke",
            "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        },
        {
            "name": "reasoning",
            "created_at": datetime(2026, 5, 2, tzinfo=timezone.utc),
        },
    ]
    db = _DBStub(run_row, result_rows, suite_rows)
    payload = _report.summarize_run("abc-123", db_module=db)
    assert payload.run_id == "abc-123"
    assert payload.groups[0].suite == "tool-smoke"


def test_summarize_run_raises_lookup_on_missing_run():
    db = _DBStub({"id": "other"}, [], [])
    try:
        _report.summarize_run("missing", db_module=db)
    except LookupError as exc:
        assert "missing" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected LookupError")
