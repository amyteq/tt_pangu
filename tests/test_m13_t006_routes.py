"""M13-T006 unit + smoke tests for the route comparison harness.

These tests run WITHOUT a DB and WITHOUT any real LLM API key.
They exercise:

1. ``tools.kca.eval.routes.resolve`` refusal logic for the 5 routes.
2. The per-route cost ledger + budget gate (via the in-process runner
   path with a synthesised cost).
3. The ``--route-compare`` slice shape (5 cases × 5 routes = 25 rows).

The DB-bound shape (eval_runs / eval_results persistence) is covered
by an out-of-test invocation in the loop prompt closeout and is NOT
re-asserted here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_KCA = REPO_ROOT / "tools" / "kca"
if str(TOOLS_KCA) not in sys.path:
    sys.path.insert(0, str(TOOLS_KCA))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.kca.eval import routes as _routes  # noqa: E402


# ---------------------------------------------------------------------------
# resolve() refusal table.
# ---------------------------------------------------------------------------


def test_routes_keys_are_canonical():
    assert _routes.ROUTE_KEYS == (
        "mocked",
        "local_vllm",
        "claude_haiku_4_5",
        "claude_sonnet_4_6",
        "gpt_4o",
    )


def test_resolve_unknown_route_raises():
    with pytest.raises(_routes.UnknownRouteError):
        _routes.resolve("bogus_route")


def test_resolve_mocked_always_ok():
    spec = _routes.resolve("mocked", allow_remote=False, env={})
    assert spec.ok is True
    assert spec.error is None
    assert spec.requires_remote is False


def test_resolve_local_vllm_ok_without_remote():
    # local_vllm does NOT require KCA_ALLOW_REMOTE; the probe is a
    # separate step.
    spec = _routes.resolve("local_vllm", allow_remote=False, env={})
    assert spec.ok is True
    assert spec.requires_remote is False
    assert spec.requires_local_lan is True


def test_resolve_claude_haiku_refuses_without_allow_remote():
    spec = _routes.resolve("claude_haiku_4_5", allow_remote=False, env={})
    assert spec.ok is False
    assert spec.error == "REMOTE_NOT_APPROVED"
    # And the API key was not consulted (env={} has no key).
    assert spec.api_key_env == "ANTHROPIC_API_KEY"


def test_resolve_claude_haiku_refuses_when_key_missing():
    spec = _routes.resolve("claude_haiku_4_5", allow_remote=True, env={"KCA_ALLOW_REMOTE": "1"})
    assert spec.ok is False
    assert spec.error == "MISSING_API_KEY:ANTHROPIC_API_KEY"


def test_resolve_claude_sonnet_refuses_when_key_missing():
    spec = _routes.resolve("claude_sonnet_4_6", allow_remote=True, env={"KCA_ALLOW_REMOTE": "1"})
    assert spec.ok is False
    assert spec.error == "MISSING_API_KEY:ANTHROPIC_API_KEY"


def test_resolve_gpt_4o_refuses_when_key_missing():
    spec = _routes.resolve("gpt_4o", allow_remote=True, env={"KCA_ALLOW_REMOTE": "1"})
    assert spec.ok is False
    assert spec.error == "MISSING_API_KEY:OPENAI_API_KEY"


def test_resolve_claude_haiku_ok_when_remote_and_key_set():
    spec = _routes.resolve(
        "claude_haiku_4_5",
        allow_remote=True,
        env={"KCA_ALLOW_REMOTE": "1", "ANTHROPIC_API_KEY": "sk-test"},
    )
    assert spec.ok is True
    assert spec.error is None
    # The key value is NOT echoed by RouteSpec — only the env name.
    assert spec.api_key_env == "ANTHROPIC_API_KEY"
    spec_dict = spec.to_dict()
    assert "sk-test" not in repr(spec_dict)


def test_resolve_gpt_4o_ok_when_remote_and_key_set():
    spec = _routes.resolve(
        "gpt_4o",
        allow_remote=True,
        env={"KCA_ALLOW_REMOTE": "1", "OPENAI_API_KEY": "sk-test-openai"},
    )
    assert spec.ok is True
    assert spec.error is None


def test_resolve_defaults_to_os_environ_for_allow_remote(monkeypatch):
    monkeypatch.delenv("KCA_ALLOW_REMOTE", raising=False)
    spec = _routes.resolve("claude_haiku_4_5")
    assert spec.ok is False
    assert spec.error == "REMOTE_NOT_APPROVED"


def test_probe_local_vllm_returns_no_endpoint_in_clean_env(monkeypatch):
    # Strip every KCA_LOCAL_ENDPOINT_* var so load_endpoints() returns [].
    for key in list(__import__("os").environ.keys()):
        if key.startswith("KCA_LOCAL_ENDPOINT_") or key.startswith("KCA_LOCAL_"):
            monkeypatch.delenv(key, raising=False)
    probe = _routes.probe_local_vllm()
    assert probe["ok"] is False
    assert probe["error"] == "NO_LIVE_LOCAL_ENDPOINT"


# ---------------------------------------------------------------------------
# CLI smoke — route-compare slice shape.
# ---------------------------------------------------------------------------


def test_route_compare_slice_has_five_cases_three_tool_smoke_two_reasoning():
    from tools.kca.eval.cli import ROUTE_COMPARE_SLICE

    assert len(ROUTE_COMPARE_SLICE) == 5
    suites = [s for s, _ in ROUTE_COMPARE_SLICE]
    assert suites.count("tool-smoke") == 3
    assert suites.count("reasoning") == 2


def test_route_compare_dry_run_no_db_mocked_only(tmp_path, monkeypatch, capsys):
    """End-to-end: route-compare in a fresh env produces 25 rows.

    No KCA_ALLOW_REMOTE, no API keys, no DB. Mocked path PASSes the
    5 mocked cases; non-mocked routes report SKIP with their refusal
    code. The total rows == 25.
    """
    # Strip any contaminating env from the parent shell.
    for k in (
        "KCA_ALLOW_REMOTE",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "SUPABASE_DB_URL",
    ):
        monkeypatch.delenv(k, raising=False)
    # Strip every local endpoint so probe_local_vllm returns
    # NO_LIVE_LOCAL_ENDPOINT.
    for key in list(__import__("os").environ.keys()):
        if key.startswith("KCA_LOCAL_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")

    from tools.kca.eval import cli as _cli

    # Force re-discovery so suites pick up the no-DB env.
    _cli._REGISTRY.clear()

    class Args:
        route_compare = True
        dry_run = True
        budget = None
        route = "mocked"
        route_explicit = None  # not explicitly set
        json = True
        suite: list[str] = []
        all = False

    rc = _cli._cmd_route_compare(Args())
    assert rc == 0
    out = capsys.readouterr().out
    # The last JSON line is the run payload.
    import json as _json

    last = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    payload = _json.loads(last)
    assert payload["ok"] is True
    assert payload["mode"] == "route-compare"
    assert len(payload["rows"]) == 25
    by_route_status: dict[tuple[str, str], int] = {}
    for r in payload["rows"]:
        key = (r["route"], r["status"])
        by_route_status[key] = by_route_status.get(key, 0) + 1

    # 5 mocked rows, all pass.
    assert by_route_status.get(("mocked", "pass"), 0) == 5
    # 5 local_vllm rows skipped with NO_LIVE_LOCAL_ENDPOINT.
    assert by_route_status.get(("local_vllm", "skip"), 0) == 5
    # 15 paid-route rows skipped with REMOTE_NOT_APPROVED.
    for r in ("claude_haiku_4_5", "claude_sonnet_4_6", "gpt_4o"):
        assert by_route_status.get((r, "skip"), 0) == 5

    # The refusal summary surfaces the right error code per route.
    assert payload["refusal_summary"]["mocked"] == "ok"
    assert payload["refusal_summary"]["claude_haiku_4_5"] == "REMOTE_NOT_APPROVED"
    assert payload["refusal_summary"]["claude_sonnet_4_6"] == "REMOTE_NOT_APPROVED"
    assert payload["refusal_summary"]["gpt_4o"] == "REMOTE_NOT_APPROVED"


def test_route_compare_single_paid_route_refuses_before_any_case(monkeypatch, capsys):
    """``--route claude_haiku_4_5`` without KCA_ALLOW_REMOTE refuses cleanly.

    The acceptance criterion is that the refusal payload is emitted
    BEFORE any case starts AND BEFORE any API key is read. We assert
    on the JSON shape; the "no case ran" part is implicit (the payload
    has no ``rows`` key — it's the bare refusal envelope).
    """
    for k in (
        "KCA_ALLOW_REMOTE",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "SUPABASE_DB_URL",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")

    from tools.kca.eval import cli as _cli

    _cli._REGISTRY.clear()

    class Args:
        route_compare = True
        dry_run = True
        budget = None
        route = "claude_haiku_4_5"
        route_explicit = "claude_haiku_4_5"
        json = True
        suite: list[str] = []
        all = False

    rc = _cli._cmd_route_compare(Args())
    assert rc != 0
    out = capsys.readouterr().out
    import json as _json

    last = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    payload = _json.loads(last)
    assert payload["ok"] is False
    assert payload["error"] == "REMOTE_NOT_APPROVED"
    assert payload["route"] == "claude_haiku_4_5"
    # No "rows" key — refusal happened before any case started.
    assert "rows" not in payload


def test_route_compare_budget_cap_aborts_remaining(monkeypatch, capsys):
    """Force a non-zero per-case cost and a tiny budget to verify the
    in-memory cost ledger triggers BUDGET_EXCEEDED + aborted_on_budget=True.

    Mocked routes have cost 0 by default, so we monkey-patch the
    reasoning suite's _run_case to inject a synthetic cost_usd on each
    case. The runner then exceeds the $0.0001 budget on the first
    reasoning case and skips the rest.
    """
    for k in (
        "KCA_ALLOW_REMOTE",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "SUPABASE_DB_URL",
    ):
        monkeypatch.delenv(k, raising=False)
    for key in list(__import__("os").environ.keys()):
        if key.startswith("KCA_LOCAL_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KCA_SKIP_DOTENV", "1")

    from tools.kca.eval import cli as _cli
    from tools.kca.eval.suites import reasoning as _reasoning

    _cli._REGISTRY.clear()

    # Inject a non-zero cost so the mocked-route ledger crosses budget.
    original_run = _reasoning.run

    def patched_run(*args, **kwargs):
        outcome = original_run(*args, **kwargs)
        for r in outcome.results:
            r.metrics["cost_usd"] = 0.10  # > $0.0001 budget
        return outcome

    monkeypatch.setattr(_reasoning, "run", patched_run)

    # ALSO patch the registry spec runner (it captures the original
    # callable at register time).
    _cli._REGISTRY.clear()
    _cli._ensure_registered(None)
    for spec in _cli._REGISTRY:
        if spec.get("name") == "reasoning":
            spec["runner"] = patched_run

    class Args:
        route_compare = True
        dry_run = True
        budget = 0.0001  # tiny — first reasoning case crosses it
        route = "mocked"
        route_explicit = "mocked"  # restrict to the mocked route
        json = True
        suite: list[str] = []
        all = False

    rc = _cli._cmd_route_compare(Args())
    assert rc == 0
    out = capsys.readouterr().out
    import json as _json

    last = [ln for ln in out.splitlines() if ln.startswith("{")][-1]
    payload = _json.loads(last)
    assert payload["ok"] is True
    assert payload["aborted_on_budget"] is True
    # Find the rows that hit BUDGET_EXCEEDED.
    budget_skips = [r for r in payload["rows"] if r.get("error_text") == "BUDGET_EXCEEDED"]
    assert len(budget_skips) >= 1
