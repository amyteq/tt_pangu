"""Shared helpers for the M13-T003 Kaggle replay suites.

Each replay (Titanic / Spaceship Titanic / House Prices) reads original
synthetic, schema-compatible CSV fixtures from ``tests/fixtures/<comp>/``
and runs a deterministic baseline (LR for classification, Ridge for
regression). Metrics land in ``eval_results.metrics`` per the
``architecture/eval-regression-suite.md`` contract.

Design notes
------------
- **Determinism.** ``random.seed(0)`` + ``numpy.random.seed(0)`` +
  sklearn ``random_state=0`` on every stochastic component. Two
  consecutive runs against the same fixture must produce byte-identical
  ``metrics`` JSON.
- **No real Kaggle.** Replays read CSVs from
  ``tests/fixtures/<comp>/`` only. The M10-T007 audit-grep guard is
  inherited via the parent runner.
- **No LLM in --route mocked.** Pure pandas / sklearn. Any non-mocked
  route raises ``NotImplementedError("deferred to T006")``.
- **fit_time_ms isolation.** Because timings vary across hardware, the
  ``fit_time_ms`` value is *recorded* in the metrics bag (so reports can
  show it) but is **excluded** from the byte-identical determinism
  check. The determinism contract covers the score-shaped fields:
  ``cv_*``, ``holdout_*``, ``n_train``, ``n_holdout``, ``n_folds``.
"""

from __future__ import annotations

import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURES_ROOT = _REPO_ROOT / "tests" / "fixtures"

# Forbidden Kaggle CLI patterns inherited from M10-T007.
AUDIT_GREP_FORBIDDEN = (
    "kaggle competitions submit",
    "kaggle kernels push",
    "kaggle datasets create",
    "kaggle datasets version",
)


@dataclass
class CaseResult:
    case_name: str
    status: str
    metrics: dict
    latency_ms: int
    error_text: str | None = None


@dataclass
class RunOutcome:
    results: list[CaseResult] = field(default_factory=list)
    audit_grep_violations: int = 0
    audit_grep_lines: list[str] = field(default_factory=list)
    total_cases: int = 0
    total_pass: int = 0
    total_fail: int = 0
    total_skip: int = 0
    total_error: int = 0


def _ensure_repo_on_path() -> None:
    """Lazy push the repo root onto sys.path for ``src.*`` imports."""
    repo = str(_REPO_ROOT)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def _seed_everything(seed: int = 0) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _audit_grep(audit_path: Path) -> tuple[int, list[str]]:
    if not audit_path.exists():
        return 0, []
    violations: list[str] = []
    needles = AUDIT_GREP_FORBIDDEN
    with audit_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for needle in needles:
                if needle in line:
                    violations.append(line.rstrip("\n"))
                    break
    return len(violations), violations[:20]


def fixture_path(comp: str) -> Path:
    return _FIXTURES_ROOT / comp / "train.csv"


def assert_mocked_route(route: str) -> None:
    """Replays default to ``mocked``. T006 allows any valid route; the
    kaggle-replay cases are pure pandas / sklearn and have no
    LLM-relevant work, so non-mocked routes are accepted but flagged
    as no-ops via ``metrics["route_no_op"] = True``.
    """
    if route in {
        "mocked",
        "local_vllm",
        "claude_haiku_4_5",
        "claude_sonnet_4_6",
        "gpt_4o",
    }:
        return
    raise ValueError(
        f"unknown route {route!r}; expected one of mocked, local_vllm, claude_haiku_4_5, claude_sonnet_4_6, gpt_4o"
    )


def run_suite(
    *,
    case_name: str,
    case_runner: Callable[[], dict[str, Any]],
    route: str = "mocked",
    audit_path: Path | None = None,
) -> RunOutcome:
    """Generic envelope: seed, time, audit-grep, package outcome.

    ``case_runner`` returns the suite-specific metrics dict (per-suite
    schema lives in each driver module).
    """
    assert_mocked_route(route)
    _route_no_op = route != "mocked"
    _seed_everything(0)

    t0 = time.perf_counter()
    status = "pass"
    error_text: str | None = None
    metrics: dict[str, Any] = {}
    try:
        metrics = case_runner()
    except Exception as exc:  # pragma: no cover - defensive
        status = "error"
        error_text = f"{type(exc).__name__}: {exc}"
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Stamp route + route_no_op so the route-compare report can join
    # rows by route without an extra column.
    if isinstance(metrics, dict):
        metrics.setdefault("route", route)
        metrics["route_no_op"] = _route_no_op

    outcome = RunOutcome()
    outcome.results.append(
        CaseResult(
            case_name=case_name,
            status=status,
            metrics=metrics,
            latency_ms=latency_ms,
            error_text=error_text,
        )
    )
    outcome.total_cases = 1
    if status == "pass":
        outcome.total_pass = 1
    elif status == "fail":
        outcome.total_fail = 1
    elif status == "skip":
        outcome.total_skip = 1
    else:
        outcome.total_error = 1

    if audit_path is None:
        # KCA audit log (ADR-0021): .agent/kca/audit.jsonl.
        audit_path = _REPO_ROOT / ".agent" / "kca" / "audit.jsonl"
    v_count, v_lines = _audit_grep(audit_path)
    outcome.audit_grep_violations = v_count
    outcome.audit_grep_lines = v_lines
    return outcome


def stable_metric_subset(metrics: dict[str, Any]) -> str:
    """Canonical JSON serialisation of the score-shaped subset of metrics.

    Used by the determinism check. Excludes ``fit_time_ms`` and
    ``latency_ms`` which vary across hardware runs.
    """
    excluded = {"fit_time_ms", "latency_ms"}
    pruned = {k: v for k, v in metrics.items() if k not in excluded}
    return json.dumps(pruned, sort_keys=True, ensure_ascii=False)


def register_db(
    db_module: object | None,
    *,
    name: str,
    category: str,
    version: str,
    description: str,
    metadata: dict[str, Any],
) -> str | None:
    if db_module is None:
        return None
    try:
        return db_module.register_eval_suite(
            name=name,
            description=description,
            version=version,
            category=category,
            metadata=metadata,
        )
    except Exception as exc:  # pragma: no cover - DB-optional
        print(
            f"[{name}] db registration skipped: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


__all__ = [
    "AUDIT_GREP_FORBIDDEN",
    "CaseResult",
    "RunOutcome",
    "assert_mocked_route",
    "fixture_path",
    "register_db",
    "run_suite",
    "stable_metric_subset",
]
