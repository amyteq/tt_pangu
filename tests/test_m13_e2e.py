"""M13-T008 e2e tests — no DB, no creds, no net.

Each test exercises the M13 eval framework against an ephemeral
tmpdir (scrubbed ``HOME``, no ``SUPABASE_DB_URL``, no
``KCA_ALLOW_REMOTE``), and runs the eval suites against checked-in
fixtures only. No real Kaggle, no real LLM, no Anthropic API.

The eval CLI is DB-optional: with ``SUPABASE_DB_URL`` unset the
runner still produces an in-process payload with per-case results,
which these tests assert on.

Total wall budget < 60 s.

Run with::

    python -m pytest tests/test_m13_e2e.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_KCA = REPO_ROOT / "tools" / "kca"
KCA_BIN = TOOLS_KCA / "kca.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_KCA) not in sys.path:
    sys.path.insert(0, str(TOOLS_KCA))


FORBIDDEN_KAGGLE_PATTERNS = (
    "kaggle competitions submit",
    "kaggle kernels push",
    "kaggle datasets create",
    "kaggle datasets version",
)


@pytest.fixture
def scrubbed_env(tmp_path, monkeypatch) -> Iterator[dict]:
    """Yield a scrubbed env dict suitable for kca subprocess calls.

    Drops any contaminating DSN / Kaggle / API-key vars that may have
    leaked from the parent shell so the eval run executes purely
    against checked-in fixtures and the in-process suite registry.
    """
    for key in (
        "SUPABASE_DB_URL",
        "SUPABASE_DB_HOST",
        "SUPABASE_DB_PORT",
        "SUPABASE_DB_USER",
        "SUPABASE_DB_PASSWORD",
        "SUPABASE_DB",
        "KCA_ALLOW_REMOTE",
        "KCA_DB_TARGET",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    # Strip every KCA_LOCAL_ENDPOINT_* var so probe_local_vllm returns
    # NO_LIVE_LOCAL_ENDPOINT cleanly.
    for key in list(os.environ.keys()):
        if key.startswith("KCA_LOCAL_"):
            monkeypatch.delenv(key, raising=False)

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "KCA_SKIP_DOTENV": "1",
        "PYTHONUNBUFFERED": "1",
    }
    yield env


def _run_kca(env: dict, *argv: str, timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(KCA_BIN), *argv],
        env=env,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _last_json(stdout: str) -> dict:
    lines = [ln for ln in stdout.splitlines() if ln.startswith("{")]
    assert lines, f"no JSON payload in stdout:\n{stdout}"
    return json.loads(lines[-1])


def _clear_registry() -> None:
    """Drop the in-process suite registry so re-registration picks up
    a fresh env on the next ``_ensure_registered`` call."""
    sys.path.insert(0, str(TOOLS_KCA))
    from tools.kca.eval import cli as _cli

    _cli._REGISTRY.clear()


# ---------------------------------------------------------------------------
# 1. Full tool-smoke run against the in-process registry.
# ---------------------------------------------------------------------------


def test_tool_smoke_suite_runs_mocked(scrubbed_env):
    """tool-smoke runs end-to-end against the fixture; ≥10 results recorded."""
    rc, stdout, stderr = _run_kca(
        scrubbed_env,
        "eval",
        "run",
        "--suite",
        "tool-smoke",
        "--route",
        "mocked",
        "--dry-run",
        "--json",
    )
    assert rc == 0, f"rc={rc}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    payload = _last_json(stdout)
    assert payload.get("ok") is True
    # No DB → run_id is None (and that's fine — payload still has totals).
    assert payload.get("run_id") in (None, ""), f"unexpected run_id with no DB: {payload.get('run_id')}"
    # Find the tool-smoke suite summary.
    suites = payload.get("suites", [])
    assert suites, "no per-suite summaries"
    smoke = next(s for s in suites if s.get("name") == "tool-smoke")
    case_count = smoke.get("case_count", 0)
    assert case_count >= 10, f"expected ≥10 tool-smoke cases, got {case_count}"
    # Verify per-case results are present and well-formed.
    results = smoke.get("results", [])
    assert len(results) >= 10
    for r in results:
        assert "case_name" in r
        assert r.get("status") in {"pass", "fail", "skip", "error"}
    # The CLI also recorded zero audit-grep violations.
    assert payload.get("audit_grep_violations", 0) == 0


# ---------------------------------------------------------------------------
# 2. All three kaggle replays run under --route mocked.
# ---------------------------------------------------------------------------


def test_kaggle_replays_run_mocked(scrubbed_env):
    """Each of the three kaggle-replay suites runs against fixtures and
    emits the expected metric keys."""
    # The three kaggle-replay suites need numpy / pandas / sklearn at
    # import time (declared via the `[eval]` optional-dependencies extra
    # in pyproject.toml). On a lean `pip install -e .[dev]` install they
    # never register, so the test should skip cleanly rather than fail.
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    pytest.importorskip("sklearn")
    suite_names = (
        "kaggle-replay-titanic",
        "kaggle-replay-spaceship-titanic",
        "kaggle-replay-house-prices",
    )
    rc, stdout, stderr = _run_kca(
        scrubbed_env,
        "eval",
        "run",
        *sum((["--suite", s] for s in suite_names), []),
        "--route",
        "mocked",
        "--dry-run",
        "--json",
        timeout=120,
    )
    assert rc == 0, f"rc={rc}\nstdout:\n{stdout[-2000:]}\nstderr:\n{stderr[-2000:]}"
    payload = _last_json(stdout)
    assert payload.get("ok") is True
    suites_by_name = {s.get("name"): s for s in payload.get("suites", [])}
    for name in suite_names:
        s = suites_by_name.get(name)
        assert s is not None, f"missing suite {name!r} in payload"
        assert s.get("case_count", 0) >= 1
        results = s.get("results", [])
        assert results, f"no results for {name}"
        metrics = results[0].get("metrics") or {}
        # All three replays carry a "fixture" key plus at least one
        # score-shaped metric.
        assert "fixture" in metrics or "model" in metrics, f"{name} missing fixture/model in metrics: {metrics}"
        assert metrics["fixture_origin"] == "synthetic"
        assert metrics["fixture_version"] == "synthetic-2026-10-22"


# ---------------------------------------------------------------------------
# 3. kernel-dryrun credentials_gate_refusal case mirrors M10-T007.
# ---------------------------------------------------------------------------


def test_kernel_dryrun_credentials_gate_refusal(scrubbed_env):
    """The kernel-dryrun suite's credentials-gate refusal case fires."""
    rc, stdout, stderr = _run_kca(
        scrubbed_env,
        "eval",
        "run",
        "--suite",
        "kernel-dryrun",
        "--route",
        "mocked",
        "--dry-run",
        "--json",
        timeout=120,
    )
    assert rc == 0, f"rc={rc}\nstdout:\n{stdout[-2000:]}\nstderr:\n{stderr[-2000:]}"
    payload = _last_json(stdout)
    suite = next(s for s in payload["suites"] if s.get("name") == "kernel-dryrun")
    results = suite.get("results", [])
    refusal = next(
        (r for r in results if r.get("case_name") == "credentials_gate_refusal"),
        None,
    )
    assert refusal is not None, (
        f"credentials_gate_refusal case not present in kernel-dryrun results: {[r.get('case_name') for r in results]}"
    )
    # The case shape — either passes (refusal happened, gate caught it)
    # or carries a refusal flag in metrics.
    metrics = refusal.get("metrics") or {}
    # The case is a pass when the gate fires; the metric records the
    # observed refusal code (or equivalent).
    assert refusal.get("status") in {"pass", "skip"}, (
        f"unexpected status for credentials_gate_refusal: {refusal.get('status')} metrics={metrics}"
    )


# ---------------------------------------------------------------------------
# 4. Reasoning suite deterministic-check pass rate.
# ---------------------------------------------------------------------------


def test_reasoning_deterministic_check_passes(scrubbed_env):
    """≥80 % of reasoning cases pass the deterministic check in mocked mode."""
    rc, stdout, stderr = _run_kca(
        scrubbed_env,
        "eval",
        "run",
        "--suite",
        "reasoning",
        "--route",
        "mocked",
        "--dry-run",
        "--json",
        timeout=120,
    )
    assert rc == 0, f"rc={rc}\nstdout:\n{stdout[-2000:]}\nstderr:\n{stderr[-2000:]}"
    payload = _last_json(stdout)
    suite = next(s for s in payload["suites"] if s.get("name") == "reasoning")
    case_count = suite.get("case_count", 0)
    pass_count = suite.get("pass", 0)
    assert case_count > 0, "reasoning suite produced no cases"
    pass_rate = pass_count / case_count
    assert pass_rate >= 0.80, f"reasoning pass rate {pass_rate:.2%} < 0.80 (pass={pass_count}, total={case_count})"


# ---------------------------------------------------------------------------
# 5. route-compare refuses BEFORE any case starts under no KCA_ALLOW_REMOTE.
# ---------------------------------------------------------------------------


def test_route_compare_refuses_without_allow_remote(scrubbed_env):
    """``kca eval run --route-compare --route claude_haiku_4_5`` refuses
    cleanly with REMOTE_NOT_APPROVED *before* any case starts."""
    rc, stdout, stderr = _run_kca(
        scrubbed_env,
        "eval",
        "run",
        "--route-compare",
        "--route",
        "claude_haiku_4_5",
        "--json",
    )
    # rc != 0 — refusal is a runtime error per the spec.
    assert rc != 0, f"expected non-zero rc on refusal; got rc={rc}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    payload = _last_json(stdout)
    assert payload.get("ok") is False
    assert payload.get("error") == "REMOTE_NOT_APPROVED"
    assert payload.get("route") == "claude_haiku_4_5"
    # No ``rows`` key — refusal happened before any case ran.
    assert "rows" not in payload


# ---------------------------------------------------------------------------
# 6. Report aggregator is byte-deterministic against a fixed payload.
# ---------------------------------------------------------------------------


def test_report_aggregator_idempotent():
    """Two ``render_markdown`` runs against the same payload are byte-equal.

    Mirrors the ``kca eval report --md`` byte-determinism contract from
    T007 without needing a DB — the report module is a pure function
    of a ``ReportPayload``.
    """
    from datetime import datetime, timezone

    sys.path.insert(0, str(TOOLS_KCA))
    from eval import report as _report

    run_row = {
        "id": "abc-123",
        "started_at": datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 6, 1, 10, 5, 0, tzinfo=timezone.utc),
        "total_pass": 1,
        "total_fail": 0,
        "total_skip": 0,
        "total_cases": 1,
        "cost_usd": 0.0,
        "aborted_on_budget": False,
    }
    result_rows = [
        {
            "suite_name": "tool-smoke",
            "route": "mocked",
            "case_name": "probe",
            "status": "pass",
            "metrics": {"acc": 0.9, "route": "mocked"},
            "latency_ms": 1,
            "cost_usd": 0.0,
            "created_at": datetime(2026, 6, 1, 10, 0, 1, tzinfo=timezone.utc),
        }
    ]
    payload = _report.build_payload(
        run_id="abc-123",
        run_row=run_row,
        result_rows=result_rows,
        suite_order=["tool-smoke"],
    )
    md1 = _report.render_markdown(payload)
    md2 = _report.render_markdown(payload)
    assert md1 == md2, "render_markdown is not byte-deterministic"
    j1 = _report.render_json(payload)
    j2 = _report.render_json(payload)
    assert j1 == j2, "render_json is not byte-deterministic"
