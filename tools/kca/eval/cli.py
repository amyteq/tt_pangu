"""``kca eval`` subcommand implementation (M13-T001 scaffold).

Four verbs:

- ``kca eval list`` — list suites registered via ``register_all()``.
- ``kca eval run`` — run one or more suites. Until T002+ land their
  per-suite drivers, every invocation refuses with
  ``{"ok": false, "error": "NO_SUITES_REGISTERED"}``.
- ``kca eval show <run_id>`` — print roll-up rows for one ``eval_runs``
  id. Returns ``{"ok": false, "error": "NOT_FOUND"}`` on miss.
- ``kca eval report <run_id>`` — defers to T007's aggregator;
  refuses with ``REPORT_AGGREGATOR_NOT_YET_IMPLEMENTED`` until then.

The scaffold writes nothing to the DB unless ``run`` actually dispatches
suites (which it cannot do until T002+). It is therefore safe to invoke
in any environment, including CI without a DB.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import pkgutil
import sys
from typing import Any

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect

from . import routes as _routes


# ---------------------------------------------------------------------------
# Suite registry (in-process; populated by register_all()).
# ---------------------------------------------------------------------------

# Each entry is the dict the suite module's register(db) function returned.
# Minimum keys (per ADR-0016): "name", "category", "version".
_REGISTRY: list[dict[str, Any]] = []


def _emit(payload: dict, side_effect: SideEffect = SideEffect.READ_ONLY) -> None:
    out = {"side_effect": side_effect.value, **payload}
    print(json.dumps(out, ensure_ascii=False))


def _maybe_db_module() -> object | None:
    """Resolve the kca db module if a DSN is configured; else None.

    The eval CLI is DB-optional: ``list`` / ``run --dry-run`` against the
    in-process registry work without a DB; ``show`` / ``run`` that
    persists rows need ``SUPABASE_DB_URL``.
    """
    if not os.environ.get("SUPABASE_DB_URL"):
        return None
    try:
        import db as db_mod  # local import; lives at tools/kca/db.py
    except Exception:  # pragma: no cover - defensive
        return None
    return db_mod


def register_all(db_module: object | None = None) -> list[dict[str, Any]]:
    """Discover and register every suite under ``tools/kca/eval/suites/``.

    Each suite module is expected to expose a ``register(db)`` callable
    returning a dict with at least ``name`` / ``category`` / ``version``.
    Suites that raise on import are skipped with a stderr warning so a
    single broken suite does not break the whole CLI.

    T001 ships this hook with zero suites; T002+ populate the suites
    directory.
    """
    _REGISTRY.clear()
    # Re-import via __package__ so this works under both `python -m
    # tools.kca.kca` (where the parent is `tools.kca.eval`) and a flat
    # sys.path layout where the parent is just `eval`.
    parent = __package__ or "tools.kca.eval"
    suites_pkg = importlib.import_module(f"{parent}.suites")

    for mod_info in pkgutil.iter_modules(suites_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        full_name = f"{suites_pkg.__name__}.{mod_info.name}"
        try:
            mod = importlib.import_module(full_name)
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"[kca eval] suite '{mod_info.name}' import failed: {exc}",
                file=sys.stderr,
            )
            continue
        register_fn = getattr(mod, "register", None)
        if register_fn is None:
            print(
                f"[kca eval] suite '{mod_info.name}' missing register(db); skipped",
                file=sys.stderr,
            )
            continue
        try:
            spec = register_fn(db_module)
        except Exception as exc:  # pragma: no cover - defensive
            print(
                f"[kca eval] suite '{mod_info.name}' register() raised: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(spec, dict):
            print(
                f"[kca eval] suite '{mod_info.name}' register() returned {type(spec).__name__}; expected dict",
                file=sys.stderr,
            )
            continue
        _REGISTRY.append(spec)
    return list(_REGISTRY)


def _ensure_registered(db_module: object | None = None) -> list[dict[str, Any]]:
    """Lazy re-registration — populates _REGISTRY on first verb call."""
    if not _REGISTRY:
        # Prefer the caller-supplied module; fall back to env-discovered.
        register_all(db_module if db_module is not None else _maybe_db_module())
    return _REGISTRY


# ---------------------------------------------------------------------------
# Verb implementations.
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    suites = _ensure_registered()
    payload = {
        "ok": True,
        "suites": [
            {
                "name": s.get("name"),
                "category": s.get("category"),
                "version": s.get("version"),
                "description": s.get("description"),
            }
            for s in suites
        ],
        "count": len(suites),
    }
    if getattr(args, "json", False):
        _emit(payload)
    else:
        if not suites:
            print("(no suites registered)")
        else:
            for s in suites:
                print(f"{s.get('name'):<32} {s.get('category'):<20} {s.get('version')}")
        # Always emit a JSON line at the end so callers can pipe.
        _emit(payload)
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    # --route-compare branches off here BEFORE any per-suite dispatch.
    if getattr(args, "route_compare", False):
        return _cmd_route_compare(args)

    db_mod = _maybe_db_module()
    suites = _ensure_registered(db_mod)
    if not suites:
        _emit({"ok": False, "error": "NO_SUITES_REGISTERED"})
        return EXIT_RUNTIME

    # Resolve target suites.
    if getattr(args, "all", False):
        targets = list(suites)
    else:
        wanted = [s.strip() for s in getattr(args, "suite", []) if s and s.strip()]
        if not wanted:
            _emit({"ok": False, "error": "SUITE_REQUIRED"})
            return EXIT_RUNTIME
        by_name = {s.get("name"): s for s in suites}
        targets = []
        unknown: list[str] = []
        for w in wanted:
            if w in by_name:
                targets.append(by_name[w])
            else:
                unknown.append(w)
        if unknown:
            _emit(
                {
                    "ok": False,
                    "error": "UNKNOWN_SUITE",
                    "unknown": unknown,
                    "available": sorted(by_name.keys()),
                }
            )
            return EXIT_RUNTIME

    route = getattr(args, "route", None) or "mocked"
    dry_run = bool(getattr(args, "dry_run", False))
    budget = getattr(args, "budget", None)

    # Route resolution — fires BEFORE any case starts AND BEFORE any
    # API key is read (resolve() does not touch the API key env unless
    # KCA_ALLOW_REMOTE=1).
    try:
        spec = _routes.resolve(route)
    except _routes.UnknownRouteError as exc:
        _emit(
            {
                "ok": False,
                "error": "UNKNOWN_ROUTE",
                "route": route,
                "message": str(exc),
                "available": list(_routes.ROUTE_KEYS),
            }
        )
        return EXIT_RUNTIME

    if not spec.ok:
        _emit({"ok": False, "error": spec.error, "route": route})
        return EXIT_RUNTIME

    # local_vllm requires a live LAN endpoint AND budget is irrelevant
    # (local = $0).
    if route == "local_vllm":
        probe = _routes.probe_local_vllm()
        if not probe.get("ok"):
            _emit(
                {
                    "ok": False,
                    "error": "NO_LIVE_LOCAL_ENDPOINT",
                    "route": route,
                    "reason": probe.get("reason"),
                }
            )
            return EXIT_RUNTIME

    # Persist the eval_runs row when a DB is configured. ``--dry-run``
    # mirrors into ``eval_runs.dry_run`` per the schema; the row STILL
    # lands so the run is auditable. The dry-run flag is the data
    # consumer's signal to discount the metrics, not a "skip the insert"
    # toggle.
    run_id: str | None = None
    if db_mod is not None:
        try:
            run_id = db_mod.start_eval_run(
                route=route,
                dry_run=dry_run,
                budget_usd=budget,
                metadata={
                    "suite_names": [s.get("name") for s in targets],
                    "trigger": "kca-eval-run",
                },
            )
        except Exception as exc:
            _emit(
                {
                    "ok": False,
                    "error": "DB_ERROR",
                    "phase": "start_eval_run",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return EXIT_RUNTIME

    suite_summaries: list[dict[str, Any]] = []
    totals = {"total_cases": 0, "total_pass": 0, "total_fail": 0, "total_skip": 0}
    total_error = 0
    audit_violations_total = 0

    for spec in targets:
        runner = spec.get("runner")
        suite_name = spec.get("name") or "<unknown>"
        suite_id = spec.get("suite_id")
        if not callable(runner):
            # Spec registered (DB row exists) but no in-process runner —
            # legitimate during scaffold tests where a future suite is
            # registered without an implementation yet.
            suite_summaries.append(
                {
                    "name": suite_name,
                    "status": "skipped",
                    "reason": "NO_RUNNER",
                }
            )
            continue

        try:
            outcome = runner(route=route)
        except Exception as exc:
            suite_summaries.append(
                {
                    "name": suite_name,
                    "status": "errored",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            total_error += 1
            continue

        # Persist per-case results.
        cases_persisted = 0
        for r in outcome.results:
            if db_mod is not None and run_id is not None and suite_id is not None:
                try:
                    db_mod.record_eval_result(
                        run_id=run_id,
                        suite_id=suite_id,
                        case_name=r.case_name,
                        route=route,
                        status=r.status,
                        metrics=r.metrics,
                        latency_ms=r.latency_ms,
                        cost_usd=0.0,
                        error_text=r.error_text,
                    )
                    cases_persisted += 1
                except Exception as exc:
                    # Surface the DB error in the summary; do not abort
                    # remaining cases so the suite still reports.
                    suite_summaries.append(
                        {
                            "name": suite_name,
                            "case": r.case_name,
                            "status": "db_error",
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        }
                    )

        totals["total_cases"] += outcome.total_cases
        totals["total_pass"] += outcome.total_pass
        totals["total_fail"] += outcome.total_fail
        totals["total_skip"] += outcome.total_skip
        total_error += outcome.total_error
        audit_violations_total += outcome.audit_grep_violations

        suite_summaries.append(
            {
                "name": suite_name,
                "case_count": outcome.total_cases,
                "pass": outcome.total_pass,
                "fail": outcome.total_fail,
                "skip": outcome.total_skip,
                "error": outcome.total_error,
                "audit_grep_violations": outcome.audit_grep_violations,
                "audit_grep_sample": outcome.audit_grep_lines,
                "results": [
                    {
                        "case_name": r.case_name,
                        "status": r.status,
                        "latency_ms": r.latency_ms,
                        "metrics": r.metrics,
                        "error_text": r.error_text,
                    }
                    for r in outcome.results
                ],
                "rows_persisted": cases_persisted,
            }
        )

    if db_mod is not None and run_id is not None:
        try:
            db_mod.finish_eval_run(
                run_id=run_id,
                totals=totals,
                cost_usd=0.0,
                aborted_on_budget=False,
            )
        except Exception as exc:
            _emit(
                {
                    "ok": False,
                    "error": "DB_ERROR",
                    "phase": "finish_eval_run",
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return EXIT_RUNTIME

    payload = {
        "ok": True,
        "run_id": run_id,
        "route": route,
        "dry_run": dry_run,
        "totals": {**totals, "total_error": total_error},
        "audit_grep_violations": audit_violations_total,
        "suites": suite_summaries,
    }
    _emit(payload, SideEffect.LOCAL_WRITE)
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    run_id = (getattr(args, "run_id", None) or "").strip()
    if not run_id:
        _emit({"ok": False, "error": "RUN_ID_REQUIRED"})
        return EXIT_RUNTIME
    # DB optional: if SUPABASE_DB_URL is unset we cannot resolve the run,
    # so surface NOT_FOUND consistently with a missing row.
    if not os.environ.get("SUPABASE_DB_URL"):
        _emit({"ok": False, "error": "NOT_FOUND", "reason": "DB_NOT_CONFIGURED"})
        return EXIT_RUNTIME
    import db as db_mod  # local import; module is at tools/kca/db.py

    try:
        rows = db_mod.fetch_eval_results(run_id)
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": "DB_ERROR",
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return EXIT_RUNTIME
    if not rows:
        _emit({"ok": False, "error": "NOT_FOUND", "run_id": run_id})
        return EXIT_RUNTIME
    payload = {
        "ok": True,
        "run_id": run_id,
        "count": len(rows),
        "results": [_json_safe(r) for r in rows],
    }
    _emit(payload, SideEffect.READ_ONLY)
    return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    """T007 — roll up eval_results into JSON + Markdown.

    Behaviour summary:
    - With ``--json``: emit ReportPayload JSON to stdout (or ``--out``).
    - With ``--md``: emit Markdown to stdout (or ``--out``).
    - With neither flag: write BOTH files under
      ``runs/m13-eval/<timestamp>/report.{json,md}`` and print the
      directory path.
    """
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    from . import report as _report

    db_mod = _maybe_db_module()
    if db_mod is None:
        _emit(
            {
                "ok": False,
                "error": "DB_NOT_CONFIGURED",
                "message": "kca eval report needs SUPABASE_DB_URL to read eval_results.",
            }
        )
        return EXIT_RUNTIME

    run_id = (getattr(args, "run_id", None) or "").strip() or None
    if run_id is None:
        # Default to the latest eval_runs row.
        try:
            rows = db_mod.list_eval_runs(limit=1)
        except Exception as exc:
            _emit(
                {
                    "ok": False,
                    "error": "DB_ERROR",
                    "phase": "list_eval_runs",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return EXIT_RUNTIME
        if not rows:
            _emit({"ok": False, "error": "NO_EVAL_RUNS"})
            return EXIT_RUNTIME
        run_id = str(rows[0].get("id"))

    try:
        payload = _report.summarize_run(run_id, db_module=db_mod)
    except LookupError as exc:
        _emit({"ok": False, "error": "NOT_FOUND", "run_id": run_id, "message": str(exc)})
        return EXIT_RUNTIME
    except Exception as exc:
        _emit(
            {
                "ok": False,
                "error": "AGGREGATOR_ERROR",
                "run_id": run_id,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
        return EXIT_RUNTIME

    want_json = bool(getattr(args, "json", False))
    want_md = bool(getattr(args, "md", False))
    out_path = getattr(args, "out", None)

    if want_json:
        text = _report.render_json(payload)
        _write_or_stdout(text, out_path)
        return EXIT_OK
    if want_md:
        text = _report.render_markdown(payload)
        _write_or_stdout(text, out_path)
        return EXIT_OK

    # Default — write both under runs/m13-eval/<timestamp>/.
    timestamp = _dt.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = _Path("runs/m13-eval") / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"
    json_path.write_text(_report.render_json(payload), encoding="utf-8")
    md_path.write_text(_report.render_markdown(payload), encoding="utf-8")
    _emit(
        {
            "ok": True,
            "run_id": run_id,
            "dir": str(out_dir),
            "json": str(json_path),
            "md": str(md_path),
        },
        SideEffect.LOCAL_WRITE,
    )
    print(str(out_dir))
    return EXIT_OK


def _write_or_stdout(text: str, out_path: str | None) -> None:
    if out_path:
        from pathlib import Path as _Path

        p = _Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    else:
        # Print without an extra newline — renderers already terminate
        # with one for byte-determinism.
        sys.stdout.write(text)
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Route comparison harness (T006).
# ---------------------------------------------------------------------------


# The shared sub-suite for the route-compare run: 3 tool-smoke +
# 2 reasoning cases. Fixed at T006 — future milestones may rotate
# the slice, but the count (5 cases × 5 routes = 25 rows) is the
# acceptance contract.
ROUTE_COMPARE_SLICE: tuple[tuple[str, str], ...] = (
    ("tool-smoke", "read_file_sample_ok"),
    ("tool-smoke", "grep_workspace_match_one"),
    ("tool-smoke", "write_file_creates_new"),
    ("reasoning", "research_brief_from_cached_pages"),
    ("reasoning", "debug_worker_trace"),
)

# Per-run defaults; env-tunable per the task spec.
ROUTE_COMPARE_DEFAULT_BUDGET = 0.50
ROUTE_COMPARE_DEFAULT_TIME_S = 600.0


def _cmd_route_compare(args: argparse.Namespace) -> int:
    """Run the 5-case shared slice across all 5 routes.

    Refusal logic fires BEFORE any case starts:
    - Per-route ``routes.resolve()`` decides REMOTE_NOT_APPROVED /
      MISSING_API_KEY / ok=True.
    - For local_vllm, ``routes.probe_local_vllm()`` checks for a
      live endpoint; on miss, NO_LIVE_LOCAL_ENDPOINT.

    Mocked-only path (no KCA_ALLOW_REMOTE, no API keys):
    - mocked route runs all 5 cases normally → 5 rows (pass/fail per
      case).
    - local_vllm typically NO_LIVE_LOCAL_ENDPOINT in CI → 5 skip rows.
    - claude_haiku_4_5 / claude_sonnet_4_6 / gpt_4o → REMOTE_NOT_APPROVED
      → 5 skip rows each.

    Total: 25 rows under any path.
    """
    import time as _time

    db_mod = _maybe_db_module()
    suites = _ensure_registered(db_mod)
    if not suites:
        _emit({"ok": False, "error": "NO_SUITES_REGISTERED"})
        return EXIT_RUNTIME

    dry_run = bool(getattr(args, "dry_run", False))
    budget = getattr(args, "budget", None)
    if budget is None:
        budget = ROUTE_COMPARE_DEFAULT_BUDGET
    try:
        budget = float(budget)
    except (TypeError, ValueError):
        _emit({"ok": False, "error": "INVALID_BUDGET", "value": budget})
        return EXIT_RUNTIME
    time_cap_s = float(os.environ.get("KCA_EVAL_TIME_CAP_S", ROUTE_COMPARE_DEFAULT_TIME_S))

    # If a single explicit --route was supplied alongside --route-compare,
    # restrict to that route (used by the explicit-refusal test).
    # The argparse default is "mocked" — distinguish "user passed
    # --route mocked" from "user passed nothing" via the sentinel
    # ``args.route_explicit`` set by a custom action.
    explicit_route = getattr(args, "route_explicit", None)
    if explicit_route is not None:
        route_list = [explicit_route]
    else:
        route_list = list(_routes.ROUTE_KEYS)

    # Validate route names early.
    for r in route_list:
        if r not in _routes.ROUTE_TABLE:
            _emit(
                {
                    "ok": False,
                    "error": "UNKNOWN_ROUTE",
                    "route": r,
                    "available": list(_routes.ROUTE_KEYS),
                }
            )
            return EXIT_RUNTIME

    # Resolve each route up front. This is the "fires BEFORE any case
    # starts AND BEFORE any API key is read" guarantee.
    resolved: dict[str, _routes.RouteSpec] = {}
    for r in route_list:
        spec = _routes.resolve(r)
        resolved[r] = spec

    # If a single explicit non-mocked route was requested AND it's
    # refused, emit the refusal payload + return EXIT_RUNTIME WITHOUT
    # starting an eval_runs row. This matches the task spec contract:
    # "refuses cleanly with REMOTE_NOT_APPROVED payload BEFORE any case
    # starts".
    if len(route_list) == 1 and not resolved[route_list[0]].ok:
        spec = resolved[route_list[0]]
        _emit({"ok": False, "error": spec.error, "route": route_list[0]})
        return EXIT_RUNTIME

    # Persist the eval_runs row when a DB is configured.
    by_name = {s.get("name"): s for s in suites}
    suite_names_in_slice = sorted({sname for sname, _ in ROUTE_COMPARE_SLICE})
    run_id: str | None = None
    if db_mod is not None:
        try:
            run_id = db_mod.start_eval_run(
                route="route-compare",
                dry_run=dry_run,
                budget_usd=budget,
                metadata={
                    "trigger": "kca-eval-route-compare",
                    "routes": route_list,
                    "slice": [{"suite": s, "case": c} for s, c in ROUTE_COMPARE_SLICE],
                    "suite_names": suite_names_in_slice,
                },
            )
        except Exception as exc:
            _emit(
                {
                    "ok": False,
                    "error": "DB_ERROR",
                    "phase": "start_eval_run",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return EXIT_RUNTIME

    # Pre-compute per-suite results once for the mocked + local_vllm
    # routes to avoid re-running the suite per slice case. Suites are
    # pure under a fixed seed (mocked) so this is safe.
    suite_results_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _get_case_result(suite_name: str, case_name: str, route: str):
        """Return (status, metrics, latency_ms, error_text) for one case."""
        key = (suite_name, route)
        if key not in suite_results_cache:
            spec = by_name.get(suite_name)
            if spec is None or not callable(spec.get("runner")):
                suite_results_cache[key] = {}
                return None
            try:
                outcome = spec["runner"](route=route)
            except Exception as exc:
                suite_results_cache[key] = {"__error__": exc}
                return None
            suite_results_cache[key] = {r.case_name: r for r in outcome.results}
            # Track audit-grep violations across all (suite, route) runs.
            if outcome.audit_grep_violations:
                suite_results_cache.setdefault("__audit__", []).extend(outcome.audit_grep_lines)
        cache = suite_results_cache[key]
        if "__error__" in cache:
            return cache["__error__"]
        return cache.get(case_name)

    rows: list[dict[str, Any]] = []
    totals = {"total_cases": 0, "total_pass": 0, "total_fail": 0, "total_skip": 0}
    total_error = 0
    cost_ledger: dict[str, float] = {r: 0.0 for r in route_list}
    aborted_routes: set[str] = set()
    aborted_on_budget = False
    started_at = _time.monotonic()

    for route in route_list:
        spec = resolved[route]
        # Per-route refusal pre-check.
        route_refused: str | None = None
        if not spec.ok:
            route_refused = spec.error
        elif route == "local_vllm":
            probe = _routes.probe_local_vllm()
            if not probe.get("ok"):
                route_refused = "NO_LIVE_LOCAL_ENDPOINT"

        for suite_name, case_name in ROUTE_COMPARE_SLICE:
            totals["total_cases"] += 1
            # Time cap check.
            if (_time.monotonic() - started_at) > time_cap_s:
                aborted_on_budget = True
                rows.append(
                    {
                        "case_name": case_name,
                        "suite": suite_name,
                        "route": route,
                        "status": "skip",
                        "latency_ms": 0,
                        "cost_usd": 0.0,
                        "metrics": {
                            "route": route,
                            "route_no_op": True,
                            "reason": "TIME_EXCEEDED",
                        },
                        "error_text": "TIME_EXCEEDED",
                    }
                )
                totals["total_skip"] += 1
                continue

            if route_refused or route in aborted_routes:
                err = route_refused or ("BUDGET_EXCEEDED" if route in aborted_routes else "REFUSED")
                rows.append(
                    {
                        "case_name": case_name,
                        "suite": suite_name,
                        "route": route,
                        "status": "skip",
                        "latency_ms": 0,
                        "cost_usd": 0.0,
                        "metrics": {
                            "route": route,
                            "route_no_op": True,
                            "reason": err,
                            "refusal_layer": "resolver" if route_refused else "budget_ledger",
                        },
                        "error_text": err,
                    }
                )
                totals["total_skip"] += 1
                continue

            case_obj = _get_case_result(suite_name, case_name, route)
            if isinstance(case_obj, Exception):
                rows.append(
                    {
                        "case_name": case_name,
                        "suite": suite_name,
                        "route": route,
                        "status": "error",
                        "latency_ms": 0,
                        "cost_usd": 0.0,
                        "metrics": {
                            "route": route,
                            "route_no_op": True,
                            "error_type": type(case_obj).__name__,
                        },
                        "error_text": f"{type(case_obj).__name__}: {case_obj}",
                    }
                )
                total_error += 1
                continue
            if case_obj is None:
                rows.append(
                    {
                        "case_name": case_name,
                        "suite": suite_name,
                        "route": route,
                        "status": "skip",
                        "latency_ms": 0,
                        "cost_usd": 0.0,
                        "metrics": {
                            "route": route,
                            "route_no_op": True,
                            "reason": "CASE_NOT_FOUND",
                        },
                        "error_text": "CASE_NOT_FOUND",
                    }
                )
                totals["total_skip"] += 1
                continue

            # case_obj is a CaseResult dataclass instance.
            case_metrics = dict(case_obj.metrics or {})
            case_metrics.setdefault("route", route)
            # Suites with no LLM-relevant cases (tool-smoke,
            # kaggle-replay-*, kernel-dryrun) carry route_no_op=True
            # whenever route != "mocked". The reasoning suite is the
            # primary LLM consumer (route_no_op=False on non-mocked).
            if "route_no_op" not in case_metrics:
                if suite_name == "reasoning" and route != "mocked":
                    case_metrics["route_no_op"] = False
                else:
                    case_metrics["route_no_op"] = route != "mocked"
            case_cost = float(case_metrics.get("cost_usd", 0.0) or 0.0)
            cost_ledger[route] += case_cost
            if cost_ledger[route] > budget:
                aborted_on_budget = True
                aborted_routes.add(route)
                rows.append(
                    {
                        "case_name": case_name,
                        "suite": suite_name,
                        "route": route,
                        "status": "skip",
                        "latency_ms": case_obj.latency_ms,
                        "cost_usd": 0.0,
                        "metrics": {
                            "route": route,
                            "route_no_op": True,
                            "reason": "BUDGET_EXCEEDED",
                            "cost_ledger_usd": cost_ledger[route],
                        },
                        "error_text": "BUDGET_EXCEEDED",
                    }
                )
                totals["total_skip"] += 1
                continue

            rows.append(
                {
                    "case_name": case_name,
                    "suite": suite_name,
                    "route": route,
                    "status": case_obj.status,
                    "latency_ms": case_obj.latency_ms,
                    "cost_usd": case_cost,
                    "metrics": case_metrics,
                    "error_text": case_obj.error_text,
                }
            )
            if case_obj.status == "pass":
                totals["total_pass"] += 1
            elif case_obj.status == "fail":
                totals["total_fail"] += 1
            elif case_obj.status == "skip":
                totals["total_skip"] += 1
            else:
                total_error += 1

    # Persist eval_results rows.
    persisted = 0
    if db_mod is not None and run_id is not None:
        for row in rows:
            spec = by_name.get(row["suite"])
            suite_id = spec.get("suite_id") if spec else None
            if suite_id is None:
                continue
            try:
                db_mod.record_eval_result(
                    run_id=run_id,
                    suite_id=suite_id,
                    case_name=row["case_name"],
                    route=row["route"],
                    status=row["status"],
                    metrics=row["metrics"],
                    latency_ms=row["latency_ms"],
                    cost_usd=row["cost_usd"],
                    error_text=row["error_text"],
                )
                persisted += 1
            except Exception as exc:
                row["db_error"] = f"{type(exc).__name__}: {exc}"

        # Close out the eval_runs row.
        try:
            db_mod.finish_eval_run(
                run_id=run_id,
                totals=totals,
                cost_usd=sum(cost_ledger.values()),
                aborted_on_budget=aborted_on_budget,
            )
        except Exception as exc:
            _emit(
                {
                    "ok": False,
                    "error": "DB_ERROR",
                    "phase": "finish_eval_run",
                    "run_id": run_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return EXIT_RUNTIME

    audit_lines = suite_results_cache.get("__audit__", []) or []

    payload = {
        "ok": True,
        "mode": "route-compare",
        "run_id": run_id,
        "routes": route_list,
        "slice": [{"suite": s, "case": c} for s, c in ROUTE_COMPARE_SLICE],
        "dry_run": dry_run,
        "budget_usd": budget,
        "cost_ledger_usd": cost_ledger,
        "aborted_on_budget": aborted_on_budget,
        "totals": {**totals, "total_error": total_error},
        "rows": rows,
        "rows_persisted": persisted,
        "audit_grep_violations": len(audit_lines),
        "audit_grep_sample": audit_lines[:20],
        "refusal_summary": {r: (resolved[r].error if not resolved[r].ok else "ok") for r in route_list},
    }
    _emit(payload, SideEffect.LOCAL_WRITE)
    return EXIT_OK


# ---------------------------------------------------------------------------
# Argparse wiring.
# ---------------------------------------------------------------------------


def add_parsers(sub: argparse._SubParsersAction) -> None:
    ev = sub.add_parser(
        "eval",
        help="Evaluation regression-suite harness (M13).",
        description=(
            "M13 regression-suite framework. Four verbs: list, run, show, "
            "report. T001 scaffolds the surface; T002+ land per-suite "
            "drivers."
        ),
    )
    ev_sub = ev.add_subparsers(dest="eval_cmd", required=True)

    # list ------------------------------------------------------------------
    p_list = ev_sub.add_parser("list", help="List registered eval suites.")
    p_list.add_argument(
        "--category",
        help="Filter by suite category (tool_smoke / kaggle_replay / ...).",
    )
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    # run -------------------------------------------------------------------
    p_run = ev_sub.add_parser(
        "run",
        help="Run one or more suites. Refuses if no suites are registered.",
    )
    p_run.add_argument(
        "--suite",
        action="append",
        default=[],
        help="Suite name to run; repeat for multiple.",
    )
    p_run.add_argument(
        "--all",
        action="store_true",
        help="Run every registered suite.",
    )

    class _RouteAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, values)
            # Mark that the user explicitly passed --route, so
            # --route-compare can distinguish "user pinned to one route"
            # from "user did not pass --route at all".
            setattr(namespace, "route_explicit", values)

    p_run.add_argument(
        "--route",
        default="mocked",
        action=_RouteAction,
        help="Route key (mocked / local_vllm / claude_* / gpt_*). Default: mocked.",
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk through the suite without persisting eval_results rows.",
    )
    p_run.add_argument(
        "--budget",
        type=float,
        default=None,
        help=(
            "Hard cost cap in USD per route. Default 0.50 for "
            "--route-compare. Required for any non-mocked / non-local "
            "single-route run."
        ),
    )
    p_run.add_argument(
        "--route-compare",
        dest="route_compare",
        action="store_true",
        help=(
            "Run the 5-case shared slice (3 tool-smoke + 2 reasoning) "
            "across all 5 routes. Emits one eval_results row per "
            "(case, route) = 25 rows. Honours --dry-run and --budget."
        ),
    )
    p_run.add_argument("--json", action="store_true")
    p_run.set_defaults(func=cmd_run)

    # show ------------------------------------------------------------------
    p_show = ev_sub.add_parser(
        "show",
        help="Print eval_results rows for a given run id.",
    )
    p_show.add_argument("run_id", help="UUID of the eval_runs row.")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    # report ----------------------------------------------------------------
    p_report = ev_sub.add_parser(
        "report",
        help="Roll up eval_results into JSON + Markdown (T007).",
    )
    p_report.add_argument(
        "run_id",
        nargs="?",
        default=None,
        help=("UUID of the eval_runs row. If omitted, defaults to the latest run by started_at."),
    )
    grp = p_report.add_mutually_exclusive_group()
    grp.add_argument("--json", action="store_true")
    grp.add_argument("--md", action="store_true")
    p_report.add_argument(
        "--out",
        help=(
            "Output path. With --json/--md, writes to this file (default: "
            "stdout). Without either flag, the report is written to "
            "runs/m13-eval/<timestamp>/report.{json,md}."
        ),
    )
    p_report.set_defaults(func=cmd_report)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _json_safe(d: dict) -> dict:
    """Coerce psycopg row values to JSON-serialisable types."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if hasattr(v, "isoformat"):  # datetime / date / time
            out[k] = v.isoformat()
        elif hasattr(v, "hex") and not isinstance(v, (bytes, bytearray, str)):
            # UUID
            out[k] = str(v)
        else:
            try:
                json.dumps(v)
                out[k] = v
            except TypeError:
                out[k] = str(v)
    return out
