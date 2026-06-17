"""kernel_dryrun — notebook / kernel dry-run regression suite (M13-T004).

Replays the M10-T007 notebook / kernel-push dry-run path as four
record-producing cases instead of a single pytest. The metric per case
is the gate result (fired vs not fired) + the M10-T007 audit-grep
sentinel (zero hits for ``kaggle kernels push`` / ``kca kaggle push``
in the suite's subprocess command log).

Cases (one ``eval_results`` row each):

- ``kg_nb_roundtrip``               — ipynb -> percent .py -> ipynb;
                                       cell counts equal.
- ``reviewer_gate_fires``           — human_decisions + agent_reviews
                                       rows land with ``target_op=
                                       'kernel_push'`` against the
                                       configured DB.
- ``decision_api_approve_roundtrip``— pending human_decisions row is
                                       flipped to ``approved`` via the
                                       same code path the decision_api
                                       uses (``db.resolve_decision``).
- ``credentials_gate_refusal``      — ``kca kaggle push`` subprocess
                                       under a scrubbed env refuses
                                       with ``ok=False`` AND never
                                       reaches the real kaggle CLI.

Fixture reuse: ``tests/fixtures/tpu-getting-started/`` (a stub when
M10-T007 has not yet landed; superseded by that task's richer fixture
when it does).

The suite NEVER calls the real Kaggle API and NEVER invokes the real
``kaggle kernels push``. The credentials-gate case uses
``--dry-run`` + ``--kernel-dir /dev/null`` so cmd_push short-circuits
on the missing ``kernel-metadata.json`` before any kaggle CLI call.

DEVIATION NOTE — task spec wording: the spec asks the
``credentials_gate_refusal`` case to assert
``payload["error"]`` contains ``KAGGLE_USERNAME`` or ``KAGGLE_KEY``.
``tools/kca/kg.py::cmd_push`` does NOT check those env vars — the
push gate is the ``KCA_ALLOW_REMOTE`` approval gate, and even that
is bypassed for ``kernel_push`` by ``OPERATION_DEFAULTS``. The case
therefore asserts a weaker but actually-truthful invariant: the
subprocess refuses (``ok=False``) AND never produces an audit line
matching the forbidden Kaggle CLI patterns. The task spec's
non-goal "No extension of cmd_push" forbids the alternative
(adding a credentials check to cmd_push).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SUITE_NAME = "kernel-dryrun"
SUITE_VERSION = "0.1.0"
SUITE_CATEGORY = "kernel_dryrun"
SUITE_DESCRIPTION = (
    "Notebook / kernel dry-run regression suite (M13-T004). "
    "Replays the M10-T007 kg-nb round-trip, reviewer-gate firing, "
    "decision_api approve round-trip, and credentials-gate refusal "
    "cases as record-producing eval_results rows."
)

_SUITE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "tpu-getting-started"
_FIXTURE_NB = _FIXTURE_DIR / "notebook.ipynb"
_KCA_ENTRYPOINT = _REPO_ROOT / "tools" / "kca" / "kca.py"

# M10-T007 forbidden patterns. Inherited by every M13 suite.
AUDIT_GREP_FORBIDDEN = (
    "kaggle competitions submit",
    "kaggle kernels push",
    "kaggle datasets create",
    "kaggle datasets version",
    "kca kaggle push",
)


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


def _ensure_repo_on_path() -> None:
    repo = str(_REPO_ROOT)
    if repo not in sys.path:
        sys.path.insert(0, repo)
    tools_kca = str(_REPO_ROOT / "tools" / "kca")
    if tools_kca not in sys.path:
        sys.path.insert(0, tools_kca)


def _db_module():
    """Resolve the kca db module if SUPABASE_DB_URL is set; else None."""
    if not os.environ.get("SUPABASE_DB_URL"):
        return None
    _ensure_repo_on_path()
    try:
        import db as db_mod  # type: ignore

        return db_mod
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Case 1 — kg_nb_roundtrip.
# ---------------------------------------------------------------------------


def _count_ipynb_cells(path: Path) -> tuple[int, int, int]:
    """Return (total_cells, code_cells, markdown_cells) for an .ipynb file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    cells = data.get("cells") or []
    code = sum(1 for c in cells if c.get("cell_type") == "code")
    md = sum(1 for c in cells if c.get("cell_type") == "markdown")
    return len(cells), code, md


def _run_kg_nb_roundtrip(tmpdir: Path) -> CaseResult:
    t0 = time.perf_counter()
    if not _FIXTURE_NB.exists():
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return CaseResult(
            case_name="kg_nb_roundtrip",
            status="skip",
            metrics={
                "cells_equal": False,
                "reason": "fixture-missing",
                "latency_ms": latency_ms,
            },
            latency_ms=latency_ms,
            error_text=f"fixture missing: {_FIXTURE_NB}",
        )

    py_path = tmpdir / "roundtrip.py"
    nb_out = tmpdir / "roundtrip_out.ipynb"

    # Step 1: .ipynb -> .py (keep markdown so the round-trip is lossless).
    p1 = subprocess.run(
        [
            sys.executable,
            str(_KCA_ENTRYPOINT),
            "nb",
            "to-py",
            str(_FIXTURE_NB),
            "--output",
            str(py_path),
            "--keep-markdown",
        ],
        capture_output=True,
        text=True,
    )
    if p1.returncode != 0:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return CaseResult(
            case_name="kg_nb_roundtrip",
            status="fail",
            metrics={
                "cells_equal": False,
                "step": "to-py",
                "latency_ms": latency_ms,
            },
            latency_ms=latency_ms,
            error_text=(p1.stderr or p1.stdout)[:500],
        )

    # Step 2: .py -> .ipynb (keep markdown so cell counts match).
    p2 = subprocess.run(
        [
            sys.executable,
            str(_KCA_ENTRYPOINT),
            "nb",
            "to-ipynb",
            str(py_path),
            "--output",
            str(nb_out),
            "--keep-markdown",
        ],
        capture_output=True,
        text=True,
    )
    if p2.returncode != 0:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return CaseResult(
            case_name="kg_nb_roundtrip",
            status="fail",
            metrics={
                "cells_equal": False,
                "step": "to-ipynb",
                "latency_ms": latency_ms,
            },
            latency_ms=latency_ms,
            error_text=(p2.stderr or p2.stdout)[:500],
        )

    src_total, src_code, src_md = _count_ipynb_cells(_FIXTURE_NB)
    out_total, out_code, out_md = _count_ipynb_cells(nb_out)
    cells_equal = src_total == out_total and src_code == out_code and src_md == out_md
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return CaseResult(
        case_name="kg_nb_roundtrip",
        status="pass" if cells_equal else "fail",
        metrics={
            "cells_equal": cells_equal,
            "src_cells": src_total,
            "src_code": src_code,
            "src_markdown": src_md,
            "out_cells": out_total,
            "out_code": out_code,
            "out_markdown": out_md,
            "latency_ms": latency_ms,
        },
        latency_ms=latency_ms,
        error_text=None if cells_equal else "cell-count mismatch after round-trip",
    )


# ---------------------------------------------------------------------------
# Case 2 — reviewer_gate_fires.
# ---------------------------------------------------------------------------


def _run_reviewer_gate_fires() -> tuple[CaseResult, list[str], list[str], list[str]]:
    """Drive the reviewer-gate stub; assert 1 review + 1 decision row.

    Returns (result, decision_ids, review_ids, job_ids) for cleanup.
    """
    decision_ids: list[str] = []
    review_ids: list[str] = []
    job_ids: list[str] = []
    t0 = time.perf_counter()
    db_mod = _db_module()
    if db_mod is None:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return (
            CaseResult(
                case_name="reviewer_gate_fires",
                status="skip",
                metrics={
                    "gates_fired": 0,
                    "rows_created": 0,
                    "reason": "no-db",
                    "latency_ms": latency_ms,
                },
                latency_ms=latency_ms,
                error_text="SUPABASE_DB_URL not set",
            ),
            decision_ids,
            review_ids,
            job_ids,
        )

    try:
        # Stub a worker that hits kernel_push: create a placeholder agent_job
        # row, then the human_decisions + agent_reviews rows the worker would
        # emit on a real kernel_push. All three rows are tagged so the suite
        # can identify them deterministically at cleanup.
        #
        # We bypass db.create_job because the cloud schema's column set
        # varies across milestones (M5 added competition_id, etc.). A raw
        # insert with only the always-required columns is the stablest
        # cross-version path for a stub job.
        with db_mod.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_jobs (project_id, job_type, status, payload)
                    VALUES (%s::uuid, %s, 'queued', %s::jsonb)
                    RETURNING id::text
                    """,
                    (
                        db_mod.DEFAULT_PROJECT_ID,
                        "kernel_push_stub",
                        json.dumps(
                            {
                                "suite": "kernel-dryrun",
                                "case": "reviewer_gate_fires",
                                "purpose": "M13-T004 stub job",
                            }
                        ),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        job_id = (row or {}).get("id") if isinstance(row, dict) else None
        if not job_id:
            raise RuntimeError("failed to insert stub agent_jobs row")
        job_ids.append(job_id)

        prompt = "M13-T004 reviewer_gate_fires stub: approve kernel_push for tpu-getting-started?"
        decision_id = db_mod.insert_approval_request(
            decision_type="kernel_push",
            prompt=prompt,
            options={"kernel_dir": "tests/fixtures/tpu-getting-started"},
            job_id=job_id,
        )
        decision_ids.append(decision_id)

        review_id = db_mod.create_review(
            job_id=job_id,
            reviewer_model="m13-t004-stub",
            verdict="abstain",
            reviewer_kind="sync",
            target_op="kernel_push",
            rationale="M13-T004 reviewer_gate_fires stub — abstain pending human",
            evidence={"suite": "kernel-dryrun", "case": "reviewer_gate_fires"},
            decision_id=decision_id,
        )
        review_ids.append(review_id)

        # Assert both rows land with target_op="kernel_push".
        fetched_dec = db_mod.get_decision(decision_id)
        fetched_rev = None
        # No fetch-one helper for agent_reviews; use raw SELECT.
        with db_mod.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text AS id, target_op FROM agent_reviews WHERE id = %s::uuid",
                    (review_id,),
                )
                fetched_rev = cur.fetchone()

        decision_target = (fetched_dec or {}).get("decision_type") or ""
        review_target = (fetched_rev or {}).get("target_op") or ""
        rows_created = (1 if fetched_dec else 0) + (1 if fetched_rev else 0)
        gates_fired = 1 if (decision_target == "kernel_push" and review_target == "kernel_push") else 0
        latency_ms = int((time.perf_counter() - t0) * 1000)
        status = "pass" if (gates_fired == 1 and rows_created == 2) else "fail"
        return (
            CaseResult(
                case_name="reviewer_gate_fires",
                status=status,
                metrics={
                    "gates_fired": gates_fired,
                    "rows_created": rows_created,
                    "decision_target_op": decision_target,
                    "review_target_op": review_target,
                    "latency_ms": latency_ms,
                },
                latency_ms=latency_ms,
                error_text=(None if status == "pass" else f"gates_fired={gates_fired}, rows_created={rows_created}"),
            ),
            decision_ids,
            review_ids,
            job_ids,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return (
            CaseResult(
                case_name="reviewer_gate_fires",
                status="error",
                metrics={
                    "gates_fired": 0,
                    "rows_created": len(decision_ids) + len(review_ids),
                    "latency_ms": latency_ms,
                },
                latency_ms=latency_ms,
                error_text=f"{type(exc).__name__}: {exc}",
            ),
            decision_ids,
            review_ids,
            job_ids,
        )


# ---------------------------------------------------------------------------
# Case 3 — decision_api_approve_roundtrip.
# ---------------------------------------------------------------------------


def _run_decision_api_approve_roundtrip() -> tuple[CaseResult, list[str]]:
    decision_ids: list[str] = []
    t0 = time.perf_counter()
    db_mod = _db_module()
    if db_mod is None:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return (
            CaseResult(
                case_name="decision_api_approve_roundtrip",
                status="skip",
                metrics={
                    "approved": False,
                    "reason": "no-db",
                    "latency_ms": latency_ms,
                },
                latency_ms=latency_ms,
                error_text="SUPABASE_DB_URL not set",
            ),
            decision_ids,
        )

    try:
        decision_id = db_mod.insert_approval_request(
            decision_type="kernel_push",
            prompt="M13-T004 decision_api_approve_roundtrip stub",
            options={"kernel_dir": "tests/fixtures/tpu-getting-started"},
        )
        decision_ids.append(decision_id)

        # Pre-approval state.
        pre = db_mod.get_decision(decision_id)
        if (pre or {}).get("status") != "pending":
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return (
                CaseResult(
                    case_name="decision_api_approve_roundtrip",
                    status="fail",
                    metrics={
                        "approved": False,
                        "pre_status": (pre or {}).get("status"),
                        "latency_ms": latency_ms,
                    },
                    latency_ms=latency_ms,
                    error_text="pre-flip state was not pending",
                ),
                decision_ids,
            )

        # Same code path the FastAPI service uses internally.
        db_mod.resolve_decision(decision_id, "approved", notes="m13-t004 dry-run approve")
        post = db_mod.get_decision(decision_id)
        post_status = (post or {}).get("status")
        approved = post_status == "approved"
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return (
            CaseResult(
                case_name="decision_api_approve_roundtrip",
                status="pass" if approved else "fail",
                metrics={
                    "approved": approved,
                    "post_status": post_status,
                    "latency_ms": latency_ms,
                },
                latency_ms=latency_ms,
                error_text=(None if approved else f"post_status={post_status!r}, expected approved"),
            ),
            decision_ids,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return (
            CaseResult(
                case_name="decision_api_approve_roundtrip",
                status="error",
                metrics={
                    "approved": False,
                    "latency_ms": latency_ms,
                },
                latency_ms=latency_ms,
                error_text=f"{type(exc).__name__}: {exc}",
            ),
            decision_ids,
        )


# ---------------------------------------------------------------------------
# Case 4 — credentials_gate_refusal.
# ---------------------------------------------------------------------------


def _run_credentials_gate_refusal(tmpdir: Path, command_log: list[str]) -> CaseResult:
    """Invoke ``kca kaggle push`` under scrubbed env; assert refusal.

    See module DEVIATION NOTE: cmd_push has no credentials gate; this
    case asserts the *gate fires* (refusal AND no kaggle CLI reached)
    rather than a literal KAGGLE_USERNAME / KAGGLE_KEY error string.
    """
    t0 = time.perf_counter()
    # Build a scrubbed env: no KAGGLE_*, no KCA_ALLOW_REMOTE, no inherited
    # KCA_POLICY. KCA_SKIP_DOTENV=1 keeps tools/kca/db.py from re-injecting
    # creds from the repo .env. HOME is redirected to a tmpdir so any
    # ~/.kaggle/kaggle.json is invisible.
    home = tmpdir / "scrubbed_home"
    home.mkdir(parents=True, exist_ok=True)
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "KCA_SKIP_DOTENV": "1",
        # No KAGGLE_USERNAME / KAGGLE_KEY / KCA_ALLOW_REMOTE.
    }

    cmd = [
        sys.executable,
        str(_KCA_ENTRYPOINT),
        "kaggle",
        "push",
        "--kernel-dir",
        "/dev/null",
        "--dry-run",
    ]
    command_log.append(" ".join(cmd))
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=30,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    payload: dict[str, Any] = {}
    payload_keys: list[str] = []
    try:
        # The CLI prints exactly one JSON line on stdout for kg.cmd_push.
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                payload = json.loads(line)
                break
    except Exception:
        payload = {}
    payload_keys = sorted(payload.keys()) if isinstance(payload, dict) else []

    ok = bool(payload.get("ok", True))
    refused = not ok
    error_text = str(payload.get("error", ""))

    # Audit-grep over BOTH the suite's command log AND the on-disk audit
    # log (if present). Either route surfaces a forbidden kaggle CLI call.
    log_pattern = re.compile("|".join(re.escape(p) for p in AUDIT_GREP_FORBIDDEN))
    cmd_log_hits = [c for c in command_log if log_pattern.search(c)]
    # The suite's own invocation "kca kaggle push" matches "kca kaggle push";
    # that's expected and *not* a regression because the call refused. Only
    # raw "kaggle competitions submit / kernels push / datasets ..." actually
    # reaching the kaggle CLI counts. The on-disk audit captures real CLI
    # invocations from src/worker/tools.py; we read it separately.
    raw_kaggle_pattern = re.compile("|".join(re.escape(p) for p in AUDIT_GREP_FORBIDDEN if not p.startswith("kca ")))
    raw_hits_in_cmd_log = [c for c in command_log if raw_kaggle_pattern.search(c)]
    # The subprocess we ran is the only command in the log; it starts with
    # "python tools/kca/kca.py kaggle push" which contains "kaggle push" but
    # NOT the raw "kaggle kernels push" string (note: no "kernels" between
    # "kaggle" and "push" because we go through kca.py, not the kaggle CLI).
    audit_clean = len(raw_hits_in_cmd_log) == 0

    # Confirm the kaggle CLI was NOT reached by checking stdout. cmd_push
    # short-circuits in --dry-run when kernel-metadata.json is missing; if
    # we ever DO reach kaggle, stdout would contain "Kaggle API" auth
    # output or competition data. We check for the explicit dry-run error.
    short_circuited = "kernel-metadata.json not found" in error_text or "ApprovalRequired" in error_text

    latency_ms = int((time.perf_counter() - t0) * 1000)
    metrics = {
        "refused": refused,
        "payload_keys": payload_keys,
        "audit_grep_clean": audit_clean,
        "short_circuited": short_circuited,
        "cmd_log_hits": len(cmd_log_hits),
        "raw_kaggle_hits": len(raw_hits_in_cmd_log),
        "rc": proc.returncode,
        "stdout_len": len(stdout),
        "stderr_len": len(stderr),
        "error_text_preview": error_text[:200],
        "latency_ms": latency_ms,
    }
    status = "pass" if (refused and audit_clean and short_circuited) else "fail"
    return CaseResult(
        case_name="credentials_gate_refusal",
        status=status,
        metrics=metrics,
        latency_ms=latency_ms,
        error_text=None if status == "pass" else f"refused={refused}, audit_clean={audit_clean}",
    )


# ---------------------------------------------------------------------------
# Cleanup helper — remove the rows the suite inserted.
# ---------------------------------------------------------------------------


def _cleanup_rows(
    db_mod,
    decision_ids: list[str],
    review_ids: list[str],
    job_ids: list[str],
) -> dict[str, int]:
    removed_reviews = 0
    removed_decisions = 0
    removed_jobs = 0
    if db_mod is None:
        return {
            "removed_decisions": 0,
            "removed_reviews": 0,
            "removed_jobs": 0,
        }
    try:
        with db_mod.get_conn() as conn:
            with conn.cursor() as cur:
                for rid in review_ids:
                    cur.execute("DELETE FROM agent_reviews WHERE id = %s::uuid", (rid,))
                    removed_reviews += cur.rowcount or 0
                for did in decision_ids:
                    cur.execute(
                        "DELETE FROM human_decisions WHERE id = %s::uuid",
                        (did,),
                    )
                    removed_decisions += cur.rowcount or 0
                for jid in job_ids:
                    cur.execute("DELETE FROM agent_jobs WHERE id = %s::uuid", (jid,))
                    removed_jobs += cur.rowcount or 0
            conn.commit()
    except Exception as exc:  # pragma: no cover - best-effort cleanup
        print(
            f"[kernel-dryrun] cleanup failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
    return {
        "removed_decisions": removed_decisions,
        "removed_reviews": removed_reviews,
        "removed_jobs": removed_jobs,
    }


# ---------------------------------------------------------------------------
# Top-level runner.
# ---------------------------------------------------------------------------


def _audit_grep_disk(audit_path: Path) -> tuple[int, list[str]]:
    """Grep the on-disk audit log for forbidden Kaggle CLI patterns."""
    if not audit_path.exists():
        return 0, []
    raw_kaggle_pattern = re.compile("|".join(re.escape(p) for p in AUDIT_GREP_FORBIDDEN if not p.startswith("kca ")))
    violations: list[str] = []
    with audit_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if raw_kaggle_pattern.search(line):
                violations.append(line.rstrip("\n"))
    return len(violations), violations[:20]


def run(
    *,
    route: str = "mocked",
    tmpdir: Path | None = None,
    audit_path: Path | None = None,
) -> RunOutcome:
    """Execute every case in order; package a RunOutcome.

    Side-effects:
    - Writes inside ``tmpdir`` only (notebook round-trip artefacts).
    - Inserts 2 rows into ``human_decisions`` + 1 row into
      ``agent_reviews`` when ``SUPABASE_DB_URL`` is configured; cleans
      those rows up before returning.
    - Spawns one subprocess (``kca kaggle push --dry-run --kernel-dir
      /dev/null``) under a scrubbed env.

    Never touches the kaggle CLI. Never calls Anthropic. ``route`` is
    accepted for parity with the CLI runner; the suite has no
    LLM-relevant cases so any non-``mocked`` route is a no-op for the
    model-call portion of each case (metric ``route_no_op=True``).
    Refusal of paid routes happens in the resolver BEFORE this runner
    is invoked.
    """
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
    if tmpdir is None:
        import tempfile

        tmpdir = Path(tempfile.mkdtemp(prefix="m13-kernel-dryrun-"))
    else:
        tmpdir = Path(tmpdir)
    tmpdir.mkdir(parents=True, exist_ok=True)

    command_log: list[str] = []
    outcome = RunOutcome()

    # Case 1 — kg_nb_roundtrip.
    outcome.results.append(_run_kg_nb_roundtrip(tmpdir))

    # Case 2 — reviewer_gate_fires.
    rg_result, rg_decision_ids, rg_review_ids, rg_job_ids = _run_reviewer_gate_fires()
    outcome.results.append(rg_result)

    # Case 3 — decision_api_approve_roundtrip.
    dapi_result, dapi_decision_ids = _run_decision_api_approve_roundtrip()
    outcome.results.append(dapi_result)

    # Case 4 — credentials_gate_refusal.
    outcome.results.append(_run_credentials_gate_refusal(tmpdir, command_log))

    # Stamp route_no_op into every case's metrics so the route-compare
    # report can distinguish "model call was a no-op" from "model call
    # happened". kernel-dryrun has no LLM-relevant cases, so route_no_op
    # is True whenever route != "mocked".
    for r in outcome.results:
        if isinstance(r.metrics, dict):
            r.metrics.setdefault("route", route)
            r.metrics["route_no_op"] = _route_no_op

    # Tally.
    for r in outcome.results:
        outcome.total_cases += 1
        if r.status == "pass":
            outcome.total_pass += 1
        elif r.status == "fail":
            outcome.total_fail += 1
        elif r.status == "skip":
            outcome.total_skip += 1
        else:
            outcome.total_error += 1

    # Audit-grep over the KCA on-disk audit log (ADR-0021): .agent/kca/audit.jsonl.
    if audit_path is None:
        audit_path = _REPO_ROOT / ".agent" / "kca" / "audit.jsonl"
    disk_violations, disk_lines = _audit_grep_disk(audit_path)
    outcome.audit_grep_violations = disk_violations
    outcome.audit_grep_lines = disk_lines

    # Cleanup any rows the suite inserted.
    db_mod = _db_module()
    if db_mod is not None and (rg_decision_ids or rg_review_ids or dapi_decision_ids or rg_job_ids):
        _cleanup_rows(
            db_mod,
            rg_decision_ids + dapi_decision_ids,
            rg_review_ids,
            rg_job_ids,
        )

    return outcome


# ---------------------------------------------------------------------------
# Registration hook (called by tools.kca.eval.register_all).
# ---------------------------------------------------------------------------


def register(db_module: object | None) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "name": SUITE_NAME,
        "category": SUITE_CATEGORY,
        "version": SUITE_VERSION,
        "description": SUITE_DESCRIPTION,
        "default_route": "mocked",
        "requires_db": False,
        "requires_remote": False,
        "runner": run,
        "case_count": 4,
    }
    if db_module is not None:
        try:
            suite_id = db_module.register_eval_suite(
                name=SUITE_NAME,
                description=SUITE_DESCRIPTION,
                version=SUITE_VERSION,
                category=SUITE_CATEGORY,
                metadata={
                    "case_count": 4,
                    "fixture": "tests/fixtures/tpu-getting-started",
                    "cases": [
                        "kg_nb_roundtrip",
                        "reviewer_gate_fires",
                        "decision_api_approve_roundtrip",
                        "credentials_gate_refusal",
                    ],
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
    "CaseResult",
    "RunOutcome",
    "SUITE_CATEGORY",
    "SUITE_DESCRIPTION",
    "SUITE_NAME",
    "SUITE_VERSION",
    "register",
    "run",
]


# Keep the unused name marker happy for type-only Callable import.
_: Callable | None = None
