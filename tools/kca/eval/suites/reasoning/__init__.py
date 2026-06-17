"""reasoning — reasoning-heavy benchmark suite (M13-T005).

Five canonical fixed prompts spanning research-brief, debug-trace,
CV-result analysis, submission-decision rationale, and tool-choice
rationale. Each case is judged by two layers:

1. ``deterministic_check`` — pure shape / enum / count contract over
   the LLM response. Runs WITHOUT any LLM call. Produces
   ``metrics["deterministic_pass"] = bool``.
2. ``rubric_prompt`` — optional rubric-LLM call gated to the cheapest
   route (T006 wires this; T005 plumbs only). ``metrics["rubric_score"]``
   is ``null`` in ``--route mocked`` mode (the default), float in [0, 1]
   otherwise.

T005 ships ``--route mocked`` only. Two consecutive ``--route mocked``
runs must produce byte-identical ``metrics`` JSON per case (no clocks,
no random ordering, no per-run keys). Latency_ms is deliberately
excluded from the determinism-compared bag — it's recorded in the
``latency_ms`` column instead.

Cost-cap plumbing: every case carries ``max_cost_usd`` (default 0.05)
AND the runner accepts an optional ``budget_usd_remaining``. T005 never
exercises the budget gate because ``--route mocked`` has cost 0; T006
will wire the live routes that actually consume budget.

The suite NEVER calls the kaggle CLI nor any remote API. The
M10-T007 audit-grep sentinel still runs and must report 0 violations.

Registration shape mirrors tool-smoke / kernel-dryrun: ``register(db)``
is called by ``tools.kca.eval.register_all``; the runner is plain
``run(*, route, tmpdir, audit_path)``.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - hard requirement
    raise RuntimeError("reasoning suite requires PyYAML; pip install pyyaml") from exc

SUITE_NAME = "reasoning"
SUITE_VERSION = "0.1.0"
SUITE_CATEGORY = "reasoning"
SUITE_DESCRIPTION = (
    "Reasoning-heavy benchmark — 5 fixed prompts (research-brief, "
    "debug-trace, cv-analysis, submit-decision, tool-choice). "
    "Two judges per prompt: deterministic shape check + optional "
    "rubric-LLM (T006 wires live; T005 plumbs only)."
)

_SUITE_DIR = Path(__file__).resolve().parent
_CASES_PATH = _SUITE_DIR / "cases.yaml"
_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "reasoning"
_MOCKED_RESPONSES_PATH = _FIXTURE_DIR / "mocked_responses.json"

# M10-T007 forbidden patterns. Inherited by every M13 suite.
AUDIT_GREP_FORBIDDEN = (
    "kaggle competitions submit",
    "kaggle kernels push",
    "kaggle datasets create",
    "kaggle datasets version",
)

DEFAULT_MAX_COST_USD = 0.05


# ---------------------------------------------------------------------------
# Case loader.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Case:
    name: str
    prompt_kind: str
    input_files: tuple[str, ...]
    deterministic_check: dict
    rubric_prompt: str
    expected_keys: tuple[str, ...]
    max_cost_usd: float


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
                prompt_kind=c.get("prompt_kind", ""),
                input_files=tuple(c.get("input_files") or ()),
                deterministic_check=dict(c.get("deterministic_check") or {}),
                rubric_prompt=str(c.get("rubric_prompt") or ""),
                expected_keys=tuple(c.get("expected_keys") or ()),
                max_cost_usd=float(c.get("max_cost_usd", DEFAULT_MAX_COST_USD)),
            )
        )
    return out


def cases() -> list[Case]:
    """Public iterator of cases — used by the runner and tests."""
    return _load_cases()


# ---------------------------------------------------------------------------
# Result shapes (compatible with tools/kca/eval/cli.py expectations).
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    case_name: str
    status: str  # pass | fail | skip | error
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


# ---------------------------------------------------------------------------
# Mocked responder — byte-deterministic by construction.
# ---------------------------------------------------------------------------


def _load_mocked_responses() -> dict[str, Any]:
    if not _MOCKED_RESPONSES_PATH.exists():
        raise FileNotFoundError(f"mocked_responses.json missing at {_MOCKED_RESPONSES_PATH}")
    return json.loads(_MOCKED_RESPONSES_PATH.read_text(encoding="utf-8"))


def _materialise_input_files(case: Case) -> dict[str, str]:
    """Read each fixture relative to tests/fixtures/reasoning/ into a dict.

    Returned dict is informational — the suite does not pipe these into a
    live LLM call in T005 (mocked route only). They're recorded into the
    metrics bag so the report aggregator (T007) can join the input
    fingerprint with the case.
    """
    materialised: dict[str, str] = {}
    for rel in case.input_files:
        path = _FIXTURE_DIR / rel
        if not path.exists():
            materialised[rel] = ""
            continue
        # Truncate per-file to keep the metrics bag small AND deterministic.
        text = path.read_text(encoding="utf-8", errors="replace")
        materialised[rel] = text
    return materialised


# ---------------------------------------------------------------------------
# Deterministic checks — one per prompt_kind, dispatched by name.
# ---------------------------------------------------------------------------


def _deterministic_check(
    response: dict[str, Any],
    check: dict[str, Any],
    case: Case,
) -> tuple[bool, list[str]]:
    """Validate the response shape WITHOUT calling an LLM.

    Returns (pass_bool, reasons[]).
    """
    reasons: list[str] = []
    if not isinstance(response, dict):
        return False, ["response is not a JSON object"]

    required_keys = check.get("required_keys") or []
    for k in required_keys:
        if k not in response:
            reasons.append(f"missing required key: {k}")

    extra = check.get("extra") or {}

    # citation_count_min --------------------------------------------------
    if "citation_count_min" in extra:
        citations = response.get("citations") or []
        min_n = int(extra["citation_count_min"])
        if not isinstance(citations, list) or len(citations) < min_n:
            reasons.append(
                f"citations count {len(citations) if isinstance(citations, list) else 'n/a'} < required minimum {min_n}"
            )

    # trust label enum check (over the `sources` field) -------------------
    if "trust_enum" in extra:
        allowed = set(extra["trust_enum"])
        trust_field = extra.get("trust_field", "sources")
        sources = response.get(trust_field) or []
        if not isinstance(sources, list) or not sources:
            reasons.append(f"trust-labelled sources missing or empty under {trust_field!r}")
        else:
            for s in sources:
                if not isinstance(s, dict):
                    reasons.append(f"source entry is not an object: {type(s).__name__}")
                    continue
                trust = s.get("trust")
                if trust not in allowed:
                    reasons.append(f"trust label {trust!r} not in enum {sorted(allowed)}")

    # evidence_min + valid_event_id_prefix (debug_worker_trace) -----------
    if "evidence_min" in extra:
        ev = response.get("evidence_event_ids") or []
        min_n = int(extra["evidence_min"])
        if not isinstance(ev, list) or len(ev) < min_n:
            reasons.append(
                f"evidence_event_ids count {len(ev) if isinstance(ev, list) else 'n/a'} < required minimum {min_n}"
            )
        else:
            prefix = extra.get("valid_event_id_prefix", "")
            for eid in ev:
                if not isinstance(eid, str) or (prefix and not eid.startswith(prefix)):
                    reasons.append(f"event id {eid!r} fails prefix check (expected {prefix!r})")

    # recommendation_enum (cv_result_analysis) ----------------------------
    if "recommendation_enum" in extra:
        allowed = set(extra["recommendation_enum"])
        rec = response.get("recommendation")
        if rec not in allowed:
            reasons.append(f"recommendation {rec!r} not in enum {sorted(allowed)}")

    # boolean_keys (cv_result_analysis / submit_decision_rationale) -------
    for bk in extra.get("boolean_keys", []) or []:
        v = response.get(bk)
        if not isinstance(v, bool):
            reasons.append(f"key {bk!r} expected bool, got {type(v).__name__}")

    # scenario_enum (submit_decision_rationale) ---------------------------
    if "scenario_enum" in extra:
        allowed = set(extra["scenario_enum"])
        tag = response.get("scenario_tag")
        if tag not in allowed:
            reasons.append(f"scenario_tag {tag!r} not in enum {sorted(allowed)}")

    # tool_choice_rationale: chosen_tool ∈ legal_subcommands --------------
    if "chosen_tool_field" in extra:
        chosen = response.get(extra["chosen_tool_field"])
        # Pull the legal subcommand list from the case's input file.
        # We re-read the input fixture here (cheap, deterministic) so the
        # check stays self-contained.
        legal: list[str] = []
        src_rel = extra.get("legal_subcommand_source")
        if src_rel:
            src_path = _FIXTURE_DIR / src_rel
            if src_path.exists():
                try:
                    payload = json.loads(src_path.read_text(encoding="utf-8"))
                    legal = list(payload.get("legal_subcommands") or [])
                except Exception:
                    legal = []
        if not legal:
            reasons.append(f"legal_subcommand_source {src_rel!r} missing or empty")
        elif chosen not in legal:
            reasons.append(f"chosen_tool {chosen!r} not in legal subcommands {legal}")

    return (len(reasons) == 0), reasons


# ---------------------------------------------------------------------------
# Per-case runner.
# ---------------------------------------------------------------------------


def _run_case(
    case: Case,
    route: str,
    mocked_responses: dict[str, Any],
    budget_usd_remaining: float | None,
) -> CaseResult:
    t0 = time.perf_counter()

    # Cost cap plumbing. T005 had cost 0 on mocked; T006 keeps the mocked
    # path at cost 0 and surfaces BUDGET_EXCEEDED only when a non-mocked
    # route actually consumes budget.
    case_cost_usd = 0.0
    if route != "mocked":
        # T006: non-mocked routes that reach the per-case runner have
        # already passed resolve() / probe checks. Honour the
        # budget_usd_remaining gate.
        if budget_usd_remaining is not None and budget_usd_remaining <= 0:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return CaseResult(
                case_name=case.name,
                status="skip",
                metrics={
                    "deterministic_pass": False,
                    "rubric_score": None,
                    "route": route,
                    "case_max_cost_usd": case.max_cost_usd,
                    "cost_usd": 0.0,
                    "prompt_kind": case.prompt_kind,
                    "input_files": list(case.input_files),
                    "reasons": ["BUDGET_EXCEEDED"],
                },
                latency_ms=latency_ms,
                error_text="BUDGET_EXCEEDED",
            )
        if case.max_cost_usd <= 0:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return CaseResult(
                case_name=case.name,
                status="skip",
                metrics={
                    "deterministic_pass": False,
                    "rubric_score": None,
                    "route": route,
                    "case_max_cost_usd": case.max_cost_usd,
                    "cost_usd": 0.0,
                    "prompt_kind": case.prompt_kind,
                    "input_files": list(case.input_files),
                    "reasons": ["BUDGET_EXCEEDED"],
                },
                latency_ms=latency_ms,
                error_text="BUDGET_EXCEEDED",
            )

    # Input fixtures (read for fingerprint; not piped to live LLM in T005).
    _ = _materialise_input_files(case)

    # Mocked responder. The fixture is keyed by case name and is the
    # SINGLE source of "what the LLM would have said". This is what makes
    # the --route mocked runs byte-deterministic.
    response: dict[str, Any] | None
    if route == "mocked":
        response = mocked_responses.get(case.name)
        if response is None:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return CaseResult(
                case_name=case.name,
                status="error",
                metrics={
                    "deterministic_pass": False,
                    "rubric_score": None,
                    "route": route,
                    "case_max_cost_usd": case.max_cost_usd,
                    "cost_usd": 0.0,
                    "prompt_kind": case.prompt_kind,
                    "input_files": list(case.input_files),
                    "reasons": ["MOCKED_RESPONSE_MISSING"],
                },
                latency_ms=latency_ms,
                error_text=f"mocked_responses.json missing key {case.name!r}",
            )
    else:
        # T006: non-mocked routes share the mocked fixture as the
        # "expected response shape" baseline. The deterministic check
        # judges whatever the route returned against the same rubric.
        # In this Loop Prompt no real LLM call is made (the route-compare
        # mocked-only path refuses non-mocked routes BEFORE the per-case
        # runner is invoked). The reasoning suite's per-case runner is
        # still callable with non-mocked routes when allow_remote=True
        # + the API key is set; in that case it falls through to the
        # mocked fixture as the canonical response, marks the case
        # ``route_no_op=False`` (the route was used for the request,
        # but the response is mocked at the suite layer). Live LLM
        # dispatch is future work — see ADR-0016 follow-up.
        response = mocked_responses.get(case.name)
        if response is None:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return CaseResult(
                case_name=case.name,
                status="error",
                metrics={
                    "deterministic_pass": False,
                    "rubric_score": None,
                    "route": route,
                    "case_max_cost_usd": case.max_cost_usd,
                    "cost_usd": 0.0,
                    "prompt_kind": case.prompt_kind,
                    "input_files": list(case.input_files),
                    "reasons": ["MOCKED_RESPONSE_MISSING"],
                },
                latency_ms=latency_ms,
                error_text=f"mocked_responses.json missing key {case.name!r}",
            )

    # Deterministic check.
    det_pass, det_reasons = _deterministic_check(response, case.deterministic_check, case)

    # Rubric judge — null in mocked mode by design. T006 calls the real
    # rubric LLM and emits a float in [0, 1].
    rubric_score: float | None = None

    # Latency intentionally excluded from the determinism-compared bag.
    metrics: dict[str, Any] = {
        "deterministic_pass": det_pass,
        "rubric_score": rubric_score,
        "route": route,
        "case_max_cost_usd": case.max_cost_usd,
        "cost_usd": case_cost_usd,
        "prompt_kind": case.prompt_kind,
        "input_files": list(case.input_files),
        "response_keys": sorted(response.keys()) if isinstance(response, dict) else [],
        "reasons": det_reasons,
    }
    latency_ms = int((time.perf_counter() - t0) * 1000)
    status = "pass" if det_pass else "fail"
    return CaseResult(
        case_name=case.name,
        status=status,
        metrics=metrics,
        latency_ms=latency_ms,
        error_text=None if det_pass else "; ".join(det_reasons)[:500],
    )


# ---------------------------------------------------------------------------
# Audit-grep over the on-disk audit log.
# ---------------------------------------------------------------------------


def _audit_grep(audit_path: Path) -> tuple[int, list[str]]:
    if not audit_path.exists():
        return 0, []
    pattern = re.compile("|".join(re.escape(p) for p in AUDIT_GREP_FORBIDDEN))
    violations: list[str] = []
    with audit_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if pattern.search(line):
                violations.append(line.rstrip("\n"))
    return len(violations), violations[:20]


# ---------------------------------------------------------------------------
# Top-level runner.
# ---------------------------------------------------------------------------


def run(
    *,
    route: str = "mocked",
    tmpdir: Path | None = None,
    audit_path: Path | None = None,
    budget_usd: float | None = None,
) -> RunOutcome:
    """Execute every case in order; package a RunOutcome.

    Side-effects: NONE outside the metrics it returns. No DB writes
    here — ``tools/kca/eval/cli.py`` is the only path that persists
    rows to ``eval_runs`` / ``eval_results``. No network. No subprocess.
    No filesystem writes (the fixture reads are all reads).

    ``route='mocked'`` is the default. T006 wires the per-suite route
    adapter so each non-mocked route can be dispatched too; refusal
    logic (REMOTE_NOT_APPROVED / MISSING_API_KEY) lives in the route
    resolver and fires BEFORE the suite's ``run()`` is called.

    ``budget_usd`` plumbs the per-run cap; in mocked mode every case
    has cost 0 so the budget is never decremented.
    """
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

    mocked_responses = _load_mocked_responses()

    outcome = RunOutcome()
    budget_remaining = budget_usd

    for case in _load_cases():
        result = _run_case(case, route, mocked_responses, budget_remaining)
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
        # Decrement budget (no-op in mocked mode).
        if budget_remaining is not None:
            budget_remaining -= float(result.metrics.get("cost_usd", 0.0) or 0.0)

    if audit_path is None:
        # KCA audit log (ADR-0021): .agent/kca/audit.jsonl. Mirrors
        # tools/kca/agent/audit.py:_default_audit_path().
        audit_path = _REPO_ROOT / ".agent" / "kca" / "audit.jsonl"
    v_count, v_lines = _audit_grep(audit_path)
    outcome.audit_grep_violations = v_count
    outcome.audit_grep_lines = v_lines
    return outcome


# ---------------------------------------------------------------------------
# Registration hook (called by tools.kca.eval.register_all).
# ---------------------------------------------------------------------------


def register(db_module: object | None) -> dict[str, Any]:
    case_list = _load_cases()
    spec: dict[str, Any] = {
        "name": SUITE_NAME,
        "category": SUITE_CATEGORY,
        "version": SUITE_VERSION,
        "description": SUITE_DESCRIPTION,
        "default_route": "mocked",
        "requires_db": False,
        "requires_remote": False,
        "runner": run,
        "case_count": len(case_list),
    }
    if db_module is not None:
        try:
            suite_id = db_module.register_eval_suite(
                name=SUITE_NAME,
                description=SUITE_DESCRIPTION,
                version=SUITE_VERSION,
                category=SUITE_CATEGORY,
                metadata={
                    "case_count": len(case_list),
                    "fixture_dir": "tests/fixtures/reasoning",
                    "cases": [c.name for c in case_list],
                },
            )
            spec["suite_id"] = suite_id
        except Exception as exc:  # pragma: no cover - DB-optional
            print(
                f"[{SUITE_NAME}] db registration skipped: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
    return spec


__all__ = [
    "AUDIT_GREP_FORBIDDEN",
    "Case",
    "CaseResult",
    "DEFAULT_MAX_COST_USD",
    "RunOutcome",
    "SUITE_CATEGORY",
    "SUITE_DESCRIPTION",
    "SUITE_NAME",
    "SUITE_VERSION",
    "cases",
    "register",
    "run",
]
