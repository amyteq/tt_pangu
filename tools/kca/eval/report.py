"""M13-T007 metrics aggregator + report writers.

This module is the engine behind ``kca eval report``. The CLI verb in
``tools.kca.eval.cli`` is a thin wrapper that:

1. Resolves the target ``run_id`` (explicit, or the latest by
   ``started_at desc``).
2. Calls :func:`summarize_run` to build a :class:`ReportPayload`.
3. Renders it as JSON or Markdown, or both at once.

The aggregator is intentionally **pure over DB rows**: callers may
inject `run_row`, `result_rows`, and `suite_order` so the report can
be tested without a live DB. The DB-aware convenience wrapper
:func:`summarize_run` resolves those from ``tools.kca.db`` when
``SUPABASE_DB_URL`` is configured.

Ordering rules (the contract that makes ``report.md`` diff-clean):

- Suites are listed in registration order (``eval_suites.created_at``).
- Routes are listed in the canonical ADR-0016 order (mocked,
  local_vllm, claude_haiku_4_5, claude_sonnet_4_6, gpt_4o).
- Cases are listed in ``eval_results.created_at`` ascending — that
  matches the ``cases.yaml`` declaration order because the harness
  inserts cases in declared order.

Formatting rules:

- Floats (metric means / accuracies / RMSLE): ``f"{x:.4f}"``.
- Cost USD: ``f"{x:.2f}"``.
- Wall times: integer milliseconds.
- No locale-dependent thousand separators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from . import routes as _routes

# ---------------------------------------------------------------------------
# Public types.
# ---------------------------------------------------------------------------


@dataclass
class MetricAggregate:
    """min / max / mean / p50 over a numeric metric key."""

    mean: float
    min: float
    max: float
    p50: float

    def as_dict(self) -> dict[str, float]:
        return {"mean": self.mean, "min": self.min, "max": self.max, "p50": self.p50}


@dataclass
class CaseRow:
    name: str
    status: str
    metrics: dict[str, Any]
    latency_ms: int
    cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "metrics": self.metrics,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
        }


@dataclass
class GroupRow:
    suite: str
    route: str
    case_count: int
    pass_count: int
    metrics_aggregate: dict[str, MetricAggregate]
    cases: list[CaseRow]

    def as_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "route": self.route,
            "case_count": self.case_count,
            "pass_count": self.pass_count,
            "metrics_aggregate": {k: v.as_dict() for k, v in self.metrics_aggregate.items()},
            "cases": [c.as_dict() for c in self.cases],
        }


@dataclass
class ReportPayload:
    run_id: str
    started_at: str
    finished_at: str | None
    totals: dict[str, int]
    cost_usd: float
    aborted_on_budget: bool
    groups: list[GroupRow] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "totals": dict(self.totals),
            "cost_usd": self.cost_usd,
            "aborted_on_budget": self.aborted_on_budget,
            "groups": [g.as_dict() for g in self.groups],
        }


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _to_iso(ts: Any) -> str | None:
    """Coerce a timestamp-like value to an ISO-8601 string (UTC)."""
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        # Normalize to UTC for diff-stable output.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        # isoformat() with "+00:00" → replace with "Z" not required but
        # we keep the standard "+00:00" form to round-trip Postgres
        # textual output.
        return ts.isoformat()
    return str(ts)


def _to_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _percentile_50(sorted_values: list[float]) -> float:
    """Median of a pre-sorted list (linear interpolation, classic p50)."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return sorted_values[n // 2]
    return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2.0


def _numeric_keys(rows: Iterable[dict[str, Any]]) -> list[str]:
    """Stable list of numeric metric keys across a set of result rows.

    A key is included when at least one row has a numeric value for it.
    Booleans are excluded (Python treats bool as int subclass).
    """
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        metrics = r.get("metrics") or {}
        if not isinstance(metrics, dict):
            continue
        for k, v in metrics.items():
            if k in seen:
                continue
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                seen.add(k)
                keys.append(k)
    return sorted(keys)


def _aggregate_metric(rows: list[dict[str, Any]], key: str) -> MetricAggregate | None:
    values: list[float] = []
    for r in rows:
        metrics = r.get("metrics") or {}
        if not isinstance(metrics, dict):
            continue
        v = metrics.get(key)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            values.append(float(v))
    if not values:
        return None
    values_sorted = sorted(values)
    return MetricAggregate(
        mean=sum(values_sorted) / len(values_sorted),
        min=values_sorted[0],
        max=values_sorted[-1],
        p50=_percentile_50(values_sorted),
    )


def _route_rank(route: str) -> tuple[int, str]:
    """Stable sort key for routes: canonical order, then alphabetical."""
    try:
        return (_routes.ROUTE_KEYS.index(route), route)
    except ValueError:
        return (len(_routes.ROUTE_KEYS), route)


# ---------------------------------------------------------------------------
# Pure aggregator.
# ---------------------------------------------------------------------------


def build_payload(
    run_id: str,
    run_row: dict[str, Any],
    result_rows: list[dict[str, Any]],
    suite_order: list[str] | None = None,
) -> ReportPayload:
    """Build a :class:`ReportPayload` from in-memory DB rows. Pure.

    ``suite_order`` is the registration order of suites — the list of
    suite names ordered by ``eval_suites.created_at``. When omitted,
    falls back to first-seen order in ``result_rows``.
    """
    # Totals: prefer the eval_runs roll-up columns; fall back to
    # counting result rows if the run row was never closed out.
    totals_pass = run_row.get("total_pass")
    totals_fail = run_row.get("total_fail")
    totals_skip = run_row.get("total_skip")
    totals_total = run_row.get("total_cases")
    if (
        totals_pass is None
        and totals_fail is None
        and totals_skip is None
        and (totals_total is None or _to_int(totals_total) == 0)
    ):
        # Recompute from result rows.
        totals_pass = sum(1 for r in result_rows if r.get("status") == "pass")
        totals_fail = sum(1 for r in result_rows if r.get("status") == "fail")
        totals_skip = sum(1 for r in result_rows if r.get("status") == "skip")
    totals_error = sum(1 for r in result_rows if r.get("status") == "error")

    totals = {
        "pass": _to_int(totals_pass),
        "fail": _to_int(totals_fail),
        "skip": _to_int(totals_skip),
        "error": _to_int(totals_error),
    }

    # Group by (suite, route). Maintain stable per-row ordering by
    # iterating result_rows in input order (caller fetches them in
    # ``created_at ASC, id ASC``).
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen_suite_order: list[str] = []
    for r in result_rows:
        suite_name = r.get("suite_name") or r.get("suite") or "<unknown>"
        route = r.get("route") or "<unknown>"
        key = (suite_name, route)
        if key not in groups:
            groups[key] = []
            if suite_name not in seen_suite_order:
                seen_suite_order.append(suite_name)
        groups[key].append(r)

    # Resolve suite ordering: explicit registration order wins; unknown
    # suites get appended in first-seen order.
    ordered_suites: list[str] = []
    if suite_order:
        for s in suite_order:
            if s not in ordered_suites:
                ordered_suites.append(s)
    for s in seen_suite_order:
        if s not in ordered_suites:
            ordered_suites.append(s)

    # Build GroupRow list.
    group_rows: list[GroupRow] = []
    for suite_name in ordered_suites:
        # Routes present for this suite — canonical order, then any
        # unknown route alphabetically.
        routes_for_suite = sorted(
            {k[1] for k in groups if k[0] == suite_name},
            key=_route_rank,
        )
        for route in routes_for_suite:
            key = (suite_name, route)
            rows = groups.get(key, [])
            if not rows:
                continue
            metric_keys = _numeric_keys(rows)
            metrics_agg: dict[str, MetricAggregate] = {}
            for mk in metric_keys:
                agg = _aggregate_metric(rows, mk)
                if agg is not None:
                    metrics_agg[mk] = agg

            cases: list[CaseRow] = []
            for r in rows:
                cases.append(
                    CaseRow(
                        name=str(r.get("case_name") or "<unknown>"),
                        status=str(r.get("status") or "<unknown>"),
                        metrics=dict(r.get("metrics") or {}),
                        latency_ms=_to_int(r.get("latency_ms")),
                        cost_usd=_to_float(r.get("cost_usd")),
                    )
                )

            group_rows.append(
                GroupRow(
                    suite=suite_name,
                    route=route,
                    case_count=len(rows),
                    pass_count=sum(1 for r in rows if r.get("status") == "pass"),
                    metrics_aggregate=metrics_agg,
                    cases=cases,
                )
            )

    return ReportPayload(
        run_id=run_id,
        started_at=_to_iso(run_row.get("started_at")) or "",
        finished_at=_to_iso(run_row.get("finished_at")),
        totals=totals,
        cost_usd=_to_float(run_row.get("cost_usd")),
        aborted_on_budget=bool(run_row.get("aborted_on_budget", False)),
        groups=group_rows,
    )


def summarize_run(
    run_id: str,
    *,
    db_module: Any = None,
) -> ReportPayload:
    """Resolve DB rows for ``run_id`` and build a :class:`ReportPayload`.

    Pure relative to the supplied ``db_module``: callers may inject a
    test double exposing ``get_eval_run`` / ``fetch_eval_results`` /
    ``list_eval_suites``. When ``db_module`` is None, the function
    imports ``tools.kca.db`` lazily so test environments without a DSN
    can import this module freely.
    """
    if db_module is None:
        try:
            import db as db_module  # type: ignore[no-redef]
        except ImportError:  # pragma: no cover - defensive
            from tools.kca import db as db_module  # type: ignore[no-redef]

    run_row = db_module.get_eval_run(run_id)
    if run_row is None:
        raise LookupError(f"eval_runs row not found for run_id={run_id!r}")
    result_rows = db_module.fetch_eval_results(run_id)

    # Suite order = eval_suites.created_at ascending = registration order.
    suite_rows = db_module.list_eval_suites()
    suite_rows_sorted = sorted(
        suite_rows,
        key=lambda s: (s.get("created_at") or datetime.min, s.get("name") or ""),
    )
    suite_order = [s.get("name") for s in suite_rows_sorted if s.get("name")]

    return build_payload(
        run_id=run_id,
        run_row=run_row,
        result_rows=result_rows,
        suite_order=suite_order,
    )


# ---------------------------------------------------------------------------
# Renderers.
# ---------------------------------------------------------------------------


def _fmt_float4(x: float) -> str:
    return f"{x:.4f}"


def _fmt_cost(x: float) -> str:
    return f"{x:.2f}"


def _json_safe(obj: Any) -> Any:
    """Recursively coerce DB / dataclass types into JSON-serialisable shapes."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, datetime):
        return _to_iso(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    # UUID (avoid matching int/float, both of which also expose ``hex``).
    import uuid as _uuid

    if isinstance(obj, _uuid.UUID):
        return str(obj)
    # Decimal: numeric() columns come back as Decimal under psycopg.
    try:
        from decimal import Decimal
    except ImportError:  # pragma: no cover - Decimal is stdlib
        Decimal = None  # type: ignore[assignment]
    if Decimal is not None and isinstance(obj, Decimal):
        return float(obj)
    return obj


def render_json(payload: ReportPayload) -> str:
    """Serialise the payload to deterministic JSON.

    ``sort_keys=True`` + ``indent=2`` makes the JSON file diff-friendly
    and round-trips for byte-determinism. The trailing newline is
    enforced so editors that auto-append one don't drift the diff.
    """
    return (
        json.dumps(
            _json_safe(payload.as_dict()),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )


def render_markdown(payload: ReportPayload) -> str:
    """Serialise the payload to diff-clean Markdown.

    Layout matches the M13-T007 task spec verbatim:
    title + meta line, Totals table, By-suite × route table, then
    one ``<details>`` per group with the per-case rows.
    """
    lines: list[str] = []
    finished = payload.finished_at if payload.finished_at else "running"
    lines.append(f"# M13 eval report — {payload.run_id}")
    lines.append(
        f"_started {payload.started_at}; finished {finished}; "
        f"cost ${_fmt_cost(payload.cost_usd)}; "
        f"aborted_on_budget={str(payload.aborted_on_budget).lower()}_"
    )
    lines.append("")

    # Totals -----------------------------------------------------------
    lines.append("## Totals")
    lines.append("")
    lines.append("| status | count |")
    lines.append("|---|---|")
    for k in ("pass", "fail", "skip", "error"):
        lines.append(f"| {k} | {payload.totals.get(k, 0)} |")
    lines.append("")

    # By suite × route -------------------------------------------------
    lines.append("## By suite × route")
    lines.append("")
    lines.append("| suite | route | cases | pass | metric_keys | latency_ms_p50 | cost_usd |")
    lines.append("|---|---|---|---|---|---|---|")
    for g in payload.groups:
        metric_keys = sorted(g.metrics_aggregate.keys())
        metric_keys_str = ",".join(metric_keys) if metric_keys else "—"
        latency_values = sorted(c.latency_ms for c in g.cases)
        latency_p50 = int(round(_percentile_50([float(v) for v in latency_values]))) if latency_values else 0
        cost_sum = sum(c.cost_usd for c in g.cases)
        lines.append(
            f"| {g.suite} | {g.route} | {g.case_count} | {g.pass_count} | "
            f"{metric_keys_str} | {latency_p50} | {_fmt_cost(cost_sum)} |"
        )
    if not payload.groups:
        lines.append("| _no rows_ | | | | | | |")
    lines.append("")

    # Per-case detail --------------------------------------------------
    lines.append("## Per-case detail")
    lines.append("")
    for g in payload.groups:
        lines.append("<details>")
        lines.append(f"<summary>{g.suite} × {g.route}</summary>")
        lines.append("")
        lines.append("| case | status | latency_ms | cost_usd | metrics |")
        lines.append("|---|---|---|---|---|")
        for c in g.cases:
            metrics_json = json.dumps(
                _json_safe(c.metrics),
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            # Escape pipe chars inside metrics JSON for table safety.
            metrics_cell = metrics_json.replace("|", "\\|")
            lines.append(f"| {c.name} | {c.status} | {c.latency_ms} | {_fmt_cost(c.cost_usd)} | `{metrics_cell}` |")
        # Aggregated metrics footer (means / min / max / p50).
        if g.metrics_aggregate:
            lines.append("")
            lines.append("Aggregated metrics:")
            lines.append("")
            lines.append("| key | mean | min | max | p50 |")
            lines.append("|---|---|---|---|---|")
            for key in sorted(g.metrics_aggregate.keys()):
                agg = g.metrics_aggregate[key]
                lines.append(
                    f"| {key} | {_fmt_float4(agg.mean)} | "
                    f"{_fmt_float4(agg.min)} | {_fmt_float4(agg.max)} | "
                    f"{_fmt_float4(agg.p50)} |"
                )
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


__all__ = [
    "MetricAggregate",
    "CaseRow",
    "GroupRow",
    "ReportPayload",
    "build_payload",
    "summarize_run",
    "render_json",
    "render_markdown",
]
