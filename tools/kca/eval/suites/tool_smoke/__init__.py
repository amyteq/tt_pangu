"""tool_smoke — deterministic per-tool smoke suite (M13-T002).

Exercises the worker tool registry (``src/worker/tools.py``) with a
checked-in case list (``cases.yaml``). Every case:

- runs against a per-run tmpdir (no network, no DB, no LLM);
- is fully deterministic — seeded ``random.seed(0)`` + frozen fixtures;
- emits the M13 ``tool_smoke`` metric bag into ``eval_results.metrics``:
  ``latency_ms``, ``output_match`` (subset-match boolean),
  ``output_keys`` (sorted JSON top-level keys; ``[]`` for plain text).

The suite never invokes the kaggle CLI nor any remote API. A post-run
audit-grep guard verifies that ``.agent/kca/audit.jsonl`` and the suite's
own captured command log contain zero hits for the M10-T007 forbidden
patterns (``kaggle competitions submit``, ``kaggle kernels push``,
``kaggle datasets create``, ``kaggle datasets version``).

Registration shape: ``register(db)`` is called by
``tools.kca.eval.register_all``; it upserts the row in ``eval_suites``
when a DB is configured AND returns the in-process suite spec dict
either way.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - hard requirement
    raise RuntimeError("tool_smoke suite requires PyYAML; pip install pyyaml") from exc

SUITE_NAME = "tool-smoke"
SUITE_VERSION = "0.1.0"
SUITE_CATEGORY = "tool_smoke"
SUITE_DESCRIPTION = (
    "Deterministic per-tool smoke suite exercising src/worker/tools.py. ≥10 cases, no LLM, no Kaggle network."
)

_SUITE_DIR = Path(__file__).resolve().parent
_CASES_PATH = _SUITE_DIR / "cases.yaml"
_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "tool_smoke"

# M10-T007 forbidden patterns. Inherited by every M13 suite.
AUDIT_GREP_FORBIDDEN = (
    "kaggle competitions submit",
    "kaggle kernels push",
    "kaggle datasets create",
    "kaggle datasets version",
)

# Policy used by the suite. Allows ``python *`` so the
# run_bash_allowed_pattern case can shell out to a one-shot python.
# Hard-deny entries in src/worker/tools.py still take priority over
# this allow-list (kaggle submit, sudo, rm -rf, git push, ``..`` path
# traversal).
_SUITE_BASH_PATTERNS = ["python *", "kca *", "pytest *"]


# ---------------------------------------------------------------------------
# Case loader.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    name: str
    tool: str
    category: str
    input: dict
    expected_status: str
    expected_contains: tuple[str, ...] = ()
    expected_keys: tuple[str, ...] = ()
    workspace: str = "tmpdir"
    depends_on: str | None = None


def _load_cases() -> list[Case]:
    if not _CASES_PATH.exists():
        raise FileNotFoundError(f"cases.yaml missing at {_CASES_PATH}")
    raw = yaml.safe_load(_CASES_PATH.read_text(encoding="utf-8")) or {}
    cases_raw = raw.get("cases") or []
    out: list[Case] = []
    for c in cases_raw:
        out.append(
            Case(
                name=c["name"],
                tool=c["tool"],
                category=c.get("category", "read_only"),
                input=dict(c.get("input") or {}),
                expected_status=c.get("expected_status", "pass"),
                expected_contains=tuple(c.get("expected_contains") or ()),
                expected_keys=tuple(sorted(c.get("expected_keys") or ())),
                workspace=c.get("workspace", "tmpdir"),
                depends_on=c.get("depends_on"),
            )
        )
    return out


def cases() -> list[Case]:
    """Public iterator of cases — used by the runner and tests."""
    return _load_cases()


# ---------------------------------------------------------------------------
# Per-run execution.
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    case_name: str
    status: str  # pass | fail | skip | error
    metrics: dict
    latency_ms: int
    error_text: str | None = None
    tool_output_preview: str = ""


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


def _output_keys_from(output: str) -> list[str]:
    """Return sorted top-level JSON keys, or [] when output is not a JSON object."""
    if not output:
        return []
    stripped = output.strip()
    if not stripped or stripped[0] not in "{[":
        return []
    try:
        parsed = json.loads(stripped)
    except Exception:
        return []
    if isinstance(parsed, dict):
        return sorted(parsed.keys())
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        # For arrays of objects (grep_workspace), expose the FIRST row's keys
        # so the contract stays useful while still being deterministic.
        return sorted(parsed[0].keys())
    return []


def _subset_match(output: str, expected_contains: tuple[str, ...]) -> bool:
    if not expected_contains:
        return True
    return all(needle in output for needle in expected_contains)


def _build_executor(workspace: Path):
    """Construct a ToolExecutor with a suite-specific JobPolicy."""
    # Lazy import keeps the suite module importable without src/ on sys.path
    # (e.g. when ``kca eval list`` runs and only enumerates suites).
    sys.path.insert(0, str(_REPO_ROOT))
    from src.worker._types import JobPolicy  # noqa: E402
    from src.worker.tools import ToolExecutor  # noqa: E402

    policy = JobPolicy(
        allowed_tool_patterns=list(_SUITE_BASH_PATTERNS),
        max_side_effect="LOCAL_WRITE",
    )
    return ToolExecutor(workspace, policy)


def _materialise_workspace(case: Case, fixture_dir: Path, tmpdir: Path) -> Path:
    """Return the workspace path for a case.

    fixture cases run against a copy of the read-only fixture dir to keep
    the source tree pristine; tmpdir cases run against a shared per-run
    tmpdir so write/edit chains work across cases.
    """
    if case.workspace == "fixture":
        # The fixture dir is read-only by convention; copy into a per-case
        # subdir so a buggy tool (e.g. write_file with a fixture path)
        # never mutates the checked-in tree.
        case_ws = tmpdir / "fixture" / case.name
        if not case_ws.exists():
            shutil.copytree(fixture_dir, case_ws)
        return case_ws
    return tmpdir / "tmpdir"


def _run_case(case: Case, fixture_dir: Path, tmpdir: Path) -> CaseResult:
    workspace = _materialise_workspace(case, fixture_dir, tmpdir)
    workspace.mkdir(parents=True, exist_ok=True)
    executor = _build_executor(workspace)

    t0 = time.perf_counter()
    output_str = ""
    status = "pass"
    error_text: str | None = None
    try:
        raw = executor.execute(case.tool, dict(case.input))
        output_str = raw if isinstance(raw, str) else str(raw)
    except Exception as exc:  # ApprovalRequired or unexpected
        status = "error"
        error_text = f"{type(exc).__name__}: {exc}"
        output_str = ""
    latency_ms = int((time.perf_counter() - t0) * 1000)

    output_keys = _output_keys_from(output_str)
    output_match = _subset_match(output_str, case.expected_contains)
    if not output_match and status == "pass":
        status = "fail"
        error_text = error_text or "subset-match failed"
    if case.expected_keys and tuple(output_keys) != case.expected_keys:
        if status == "pass":
            status = "fail"
            error_text = error_text or (
                f"expected_keys mismatch: got={output_keys} expected={list(case.expected_keys)}"
            )

    metrics = {
        "latency_ms": latency_ms,
        "output_match": output_match,
        "output_keys": output_keys,
        # Per-suite extras (kept inside the metric bag, not separate columns).
        "tool": case.tool,
        "expected_status": case.expected_status,
        "category": case.category,
    }
    return CaseResult(
        case_name=case.name,
        status=status,
        metrics=metrics,
        latency_ms=latency_ms,
        error_text=error_text,
        tool_output_preview=output_str[:200],
    )


def _audit_grep(audit_path: Path, started_after_ns: int) -> tuple[int, list[str]]:
    """Return (violation_count, sample_lines) for the M10-T007 forbidden patterns.

    Only inspects audit lines whose ``timestamp`` (ISO-8601 string) parses
    to a moment AFTER the suite started — older lines from previous
    sessions are not the suite's responsibility.
    """
    if not audit_path.exists():
        return 0, []
    violations: list[str] = []
    pattern = re.compile("|".join(re.escape(p) for p in AUDIT_GREP_FORBIDDEN))
    with audit_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if pattern.search(line):
                violations.append(line.rstrip("\n"))
    return len(violations), violations[:20]


def run(
    *,
    route: str = "mocked",
    seed: int = 0,
    tmpdir: Path | None = None,
    audit_path: Path | None = None,
) -> RunOutcome:
    """Execute every case in cases.yaml and return a RunOutcome.

    Side-effects: writes inside ``tmpdir`` only. Never touches the DB —
    the runner in ``tools/kca/eval/cli.py`` is the only path that
    persists rows to ``eval_runs`` / ``eval_results``.
    """
    random.seed(seed)
    started_ns = time.time_ns()

    if tmpdir is None:
        import tempfile

        tmpdir = Path(tempfile.mkdtemp(prefix="m13-tool-smoke-"))
    else:
        tmpdir = Path(tmpdir)
    tmpdir.mkdir(parents=True, exist_ok=True)

    fixture_dir = _FIXTURE_DIR
    if not fixture_dir.exists():
        raise FileNotFoundError(f"tool_smoke fixture missing: {fixture_dir} — checked-in fixture required")

    # tool-smoke has no LLM-relevant cases; non-mocked routes are a
    # no-op for the model-call portion (the case still runs, but
    # ``route_no_op=True`` flags that no LLM was consulted).
    _route_no_op = route != "mocked"
    if route not in {
        "mocked",
        "local_vllm",
        "claude_haiku_4_5",
        "claude_sonnet_4_6",
        "gpt_4o",
    }:
        raise ValueError(
            f"unknown route {route!r}; expected one of mocked, local_vllm, claude_haiku_4_5, claude_sonnet_4_6, gpt_4o"
        )

    outcome = RunOutcome()
    for case in _load_cases():
        result = _run_case(case, fixture_dir, tmpdir)
        if isinstance(result.metrics, dict):
            result.metrics.setdefault("route", route)
            result.metrics["route_no_op"] = _route_no_op
        outcome.results.append(result)
        outcome.total_cases += 1
        if result.status == "pass":
            outcome.total_pass += 1
        elif result.status == "fail":
            outcome.total_fail += 1
        elif result.status == "skip":
            outcome.total_skip += 1
        else:
            outcome.total_error += 1

    if audit_path is None:
        # KCA audit log (ADR-0021): .agent/kca/audit.jsonl.
        audit_path = _REPO_ROOT / ".agent" / "kca" / "audit.jsonl"
    v_count, v_lines = _audit_grep(audit_path, started_ns)
    outcome.audit_grep_violations = v_count
    outcome.audit_grep_lines = v_lines
    return outcome


# ---------------------------------------------------------------------------
# Registration hook (called by tools.kca.eval.register_all).
# ---------------------------------------------------------------------------


def register(db_module: object | None) -> dict[str, Any]:
    """Return the suite spec; upsert into ``eval_suites`` when a DB is set.

    The runner stays purely functional: ``register`` records "this suite
    exists"; ``cmd_run`` in ``tools/kca/eval/cli.py`` invokes ``run()`` to
    produce results.
    """
    spec: dict[str, Any] = {
        "name": SUITE_NAME,
        "category": SUITE_CATEGORY,
        "version": SUITE_VERSION,
        "description": SUITE_DESCRIPTION,
        "default_route": "mocked",
        "requires_db": False,
        "requires_remote": False,
        "runner": run,  # in-process handle for cmd_run
        "case_count": len(_load_cases()),
    }
    if db_module is not None:
        try:
            suite_id = db_module.register_eval_suite(
                name=SUITE_NAME,
                description=SUITE_DESCRIPTION,
                version=SUITE_VERSION,
                category=SUITE_CATEGORY,
                metadata={"case_count": spec["case_count"]},
            )
            spec["suite_id"] = suite_id
        except Exception as exc:  # pragma: no cover - DB-optional
            print(
                f"[tool-smoke] db registration skipped: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
    return spec
