"""M13-T008 smoke tests — DB-gated assertions for the eval framework.

These tests exercise the M13 eval framework against the configured
``SUPABASE_DB_URL`` Postgres instance. They SKIP cleanly when no DSN is
set, so the no-DB CI path stays green; against a real DB, they assert
that:

  - migration 0008 applied (``eval_suites`` / ``eval_runs`` /
    ``eval_results`` tables exist);
  - ``register_eval_suite`` / ``start_eval_run`` /
    ``record_eval_result`` / ``fetch_eval_results`` round-trip cleanly;
  - ``kca eval list`` (subprocess) reports ≥6 registered suites;
  - ``kca eval run --suite tool-smoke --route mocked --dry-run --json``
    inserts exactly one new ``eval_runs`` row;
  - ``kca eval report --json`` against the latest run emits a payload
    with the expected top-level keys + non-empty ``groups``;
  - a full ``kca eval run --all --route mocked --dry-run`` does not
    add any forbidden Kaggle CLI command lines to
    ``.agent/audit.jsonl``.

Each DB-touching test cleans up any rows it inserted, so repeated
runs are idempotent against the same DB.

Run with::

    KCA_SKIP_DOTENV=1 SUPABASE_DB_URL=... \\
        python -m pytest tests/test_m13_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_KCA = REPO_ROOT / "tools" / "kca"
KCA_BIN = TOOLS_KCA / "kca.py"
AUDIT_LOG = REPO_ROOT / ".agent" / "audit.jsonl"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOLS_KCA) not in sys.path:
    sys.path.insert(0, str(TOOLS_KCA))

requires_db = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set",
)

FORBIDDEN_KAGGLE_PATTERNS = (
    "kaggle competitions submit",
    "kaggle kernels push",
    "kaggle datasets create",
    "kaggle datasets version",
)


def _subprocess_env() -> dict:
    """Forward only the bits a kca subprocess needs.

    Forwards ``SUPABASE_DB_URL`` when present so DB-aware paths can
    reach the same Postgres as the in-process tests. Leaves
    ``KCA_ALLOW_REMOTE`` unset and clears any contaminating
    ``KAGGLE_*`` / paid-LLM env so subprocess invocations stay on the
    mocked / refusal path.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(REPO_ROOT)),
        "KCA_SKIP_DOTENV": "1",
        "PYTHONUNBUFFERED": "1",
    }
    if os.environ.get("SUPABASE_DB_URL"):
        env["SUPABASE_DB_URL"] = os.environ["SUPABASE_DB_URL"]
    return env


@requires_db
def test_migration_0008_applied():
    """``eval_suites`` / ``eval_runs`` / ``eval_results`` exist on the DB."""
    import db as db_mod  # tools/kca/db.py

    with db_mod.get_conn() as conn:
        with conn.cursor() as cur:
            missing = []
            for table in ("eval_suites", "eval_runs", "eval_results"):
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                row = cur.fetchone()
                regclass = row.get("to_regclass") if row else None
                if regclass is None:
                    missing.append(table)
    assert not missing, (
        f"migration 0010 not applied — missing tables: {missing}. Apply supabase/migrations/0010_m13_eval.sql."
    )


@requires_db
def test_db_helpers_roundtrip():
    """register_eval_suite → start_eval_run → record_eval_result → fetch."""
    import db as db_mod

    suite_name = "smoke-roundtrip-m13t008"
    inserted_run_id: str | None = None
    inserted_suite_id: str | None = None

    try:
        inserted_suite_id = db_mod.register_eval_suite(
            name=suite_name,
            description="M13-T008 round-trip probe (deleted on test exit).",
            version="0.0.0",
            category="tool_smoke",
            metadata={"test_only": True},
        )
        assert inserted_suite_id, "register_eval_suite returned empty id"

        inserted_run_id = db_mod.start_eval_run(
            route="mocked",
            dry_run=True,
            budget_usd=None,
            metadata={"test_only": True, "task": "M13-T008"},
        )
        assert inserted_run_id, "start_eval_run returned empty id"

        result_id = db_mod.record_eval_result(
            run_id=inserted_run_id,
            suite_id=inserted_suite_id,
            case_name="probe_case",
            route="mocked",
            status="pass",
            metrics={"probe": 1.0, "route": "mocked"},
            latency_ms=1,
            cost_usd=0.0,
            error_text=None,
        )
        assert result_id, "record_eval_result returned empty id"

        rows = db_mod.fetch_eval_results(inserted_run_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["case_name"] == "probe_case"
        assert row["status"] == "pass"
        assert row["route"] == "mocked"
        # Metrics column round-trips via jsonb.
        assert row["metrics"].get("probe") == 1.0

        db_mod.finish_eval_run(
            run_id=inserted_run_id,
            totals={
                "total_cases": 1,
                "total_pass": 1,
                "total_fail": 0,
                "total_skip": 0,
            },
            cost_usd=0.0,
            aborted_on_budget=False,
        )

        run_row = db_mod.get_eval_run(inserted_run_id)
        assert run_row is not None
        assert run_row["finished_at"] is not None
        assert run_row["total_pass"] == 1
    finally:
        # Cleanup — defer to a fresh connection to avoid commit semantics
        # locking the row up.
        with db_mod.get_conn() as conn:
            with conn.cursor() as cur:
                if inserted_run_id:
                    cur.execute(
                        "DELETE FROM eval_results WHERE run_id = %s::uuid",
                        (inserted_run_id,),
                    )
                    cur.execute(
                        "DELETE FROM eval_runs WHERE id = %s::uuid",
                        (inserted_run_id,),
                    )
                if inserted_suite_id:
                    cur.execute(
                        "DELETE FROM eval_suites WHERE id = %s::uuid",
                        (inserted_suite_id,),
                    )
            conn.commit()


@requires_db
def test_kca_eval_list_shows_registered_suites():
    """``kca eval list --json`` reports the core 3 suites; with the
    ``[eval]`` optional-dependencies extra installed (numpy / pandas /
    scikit-learn) the 3 kaggle-replay suites also register, bringing
    the total to 6."""
    proc = subprocess.run(
        [sys.executable, str(KCA_BIN), "eval", "list", "--json"],
        env=_subprocess_env(),
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"kca eval list rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    # The last JSON line is the payload (suites may also print stderr warnings).
    json_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    assert json_lines, f"no JSON payload in stdout:\n{proc.stdout}"
    payload = json.loads(json_lines[-1])
    assert payload.get("ok") is True
    names = set(s["name"] for s in payload["suites"])
    # The 3 core suites must always register — they have no heavy deps.
    core = {"tool-smoke", "reasoning", "kernel-dryrun"}
    missing_core = core - names
    assert not missing_core, f"core suites missing from list: {sorted(missing_core)}"
    # Kaggle replay suites require the `[eval]` extra (numpy / pandas /
    # scikit-learn). If those deps are installed, all 3 should register.
    try:
        import numpy  # noqa: F401
        import pandas  # noqa: F401
        import sklearn  # noqa: F401

        have_eval_deps = True
    except ImportError:
        have_eval_deps = False
    if have_eval_deps:
        kaggle_suites = {
            "kaggle-replay-titanic",
            "kaggle-replay-spaceship-titanic",
            "kaggle-replay-house-prices",
        }
        missing_kaggle = kaggle_suites - names
        assert not missing_kaggle, f"kaggle-replay suites missing despite eval deps installed: {sorted(missing_kaggle)}"


@requires_db
def test_kca_eval_run_creates_one_runs_row():
    """``kca eval run --suite tool-smoke --route mocked --dry-run`` adds 1 row."""
    import db as db_mod

    before = db_mod.list_eval_runs(limit=200)
    before_ids = {str(r["id"]) for r in before}

    new_run_id: str | None = None
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(KCA_BIN),
                "eval",
                "run",
                "--suite",
                "tool-smoke",
                "--route",
                "mocked",
                "--dry-run",
                "--json",
            ],
            env=_subprocess_env(),
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, (
            f"kca eval run rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
        # Parse the payload from the last JSON line of stdout.
        json_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
        assert json_lines, f"no JSON payload in stdout:\n{proc.stdout}"
        payload = json.loads(json_lines[-1])
        assert payload.get("ok") is True
        new_run_id = payload.get("run_id")
        assert new_run_id, f"missing run_id in payload: {payload}"

        after = db_mod.list_eval_runs(limit=200)
        after_ids = {str(r["id"]) for r in after}
        added = after_ids - before_ids
        assert len(added) == 1, f"expected exactly one new eval_runs row, got {len(added)}: {added}"
        assert new_run_id in added
    finally:
        if new_run_id:
            with db_mod.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM eval_results WHERE run_id = %s::uuid",
                        (new_run_id,),
                    )
                    cur.execute(
                        "DELETE FROM eval_runs WHERE id = %s::uuid",
                        (new_run_id,),
                    )
                conn.commit()


@requires_db
def test_kca_eval_report_json_shape():
    """``kca eval report --json`` against a fresh run emits a ReportPayload.

    Uses a fresh eval_runs row created inside the test (then deletes it)
    so the assertion is deterministic regardless of what other rows
    happen to exist on the DB.
    """
    import db as db_mod

    suite_name = "tool-smoke"
    # Find the registered suite_id by name; tool-smoke is the cheapest case
    # to populate so we use it for the report shape probe.
    suites = db_mod.list_eval_suites()
    suite_id = next((s["id"] for s in suites if s["name"] == suite_name), None)
    assert suite_id is not None, f"suite {suite_name!r} not registered; run any kca eval run first."

    run_id = db_mod.start_eval_run(
        route="mocked",
        dry_run=True,
        budget_usd=None,
        metadata={"test_only": True, "task": "M13-T008", "probe": "report-shape"},
    )
    try:
        db_mod.record_eval_result(
            run_id=run_id,
            suite_id=str(suite_id),
            case_name="probe_case",
            route="mocked",
            status="pass",
            metrics={"accuracy": 0.9, "route": "mocked"},
            latency_ms=1,
            cost_usd=0.0,
        )
        db_mod.finish_eval_run(
            run_id=run_id,
            totals={
                "total_cases": 1,
                "total_pass": 1,
                "total_fail": 0,
                "total_skip": 0,
            },
            cost_usd=0.0,
            aborted_on_budget=False,
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(KCA_BIN),
                "eval",
                "report",
                run_id,
                "--json",
            ],
            env=_subprocess_env(),
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, (
            f"kca eval report rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
        payload = json.loads(proc.stdout)
        for key in (
            "run_id",
            "started_at",
            "totals",
            "groups",
        ):
            assert key in payload, f"missing key {key!r} in report payload"
        assert payload["run_id"] == run_id
        assert isinstance(payload["groups"], list)
        assert len(payload["groups"]) >= 1, "groups must be non-empty"
        g = payload["groups"][0]
        for key in ("suite", "route", "case_count", "pass_count", "cases"):
            assert key in g, f"missing key {key!r} in group payload"
    finally:
        with db_mod.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM eval_results WHERE run_id = %s::uuid",
                    (run_id,),
                )
                cur.execute(
                    "DELETE FROM eval_runs WHERE id = %s::uuid",
                    (run_id,),
                )
            conn.commit()


@requires_db
def test_audit_grep_sentinel_clean():
    """Full mocked eval run must not leak forbidden kaggle CLI commands.

    Runs ``kca eval run --all --route mocked --dry-run`` as a subprocess
    and asserts that ``.agent/audit.jsonl`` contains no new lines
    matching the M10-T007 forbidden-pattern list during the run window.
    """
    import db as db_mod

    # Record audit log size before so we only inspect lines the
    # subprocess could plausibly have appended.
    before_size = AUDIT_LOG.stat().st_size if AUDIT_LOG.exists() else 0

    proc = subprocess.run(
        [
            sys.executable,
            str(KCA_BIN),
            "eval",
            "run",
            "--all",
            "--route",
            "mocked",
            "--dry-run",
            "--json",
        ],
        env=_subprocess_env(),
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"kca eval run --all rc={proc.returncode}\nstdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}"
    )

    # Parse the run payload to extract run_id for cleanup.
    json_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")]
    assert json_lines
    payload = json.loads(json_lines[-1])
    new_run_id = payload.get("run_id")
    try:
        # Audit-grep over the appended chunk only.
        violations: list[str] = []
        if AUDIT_LOG.exists():
            with AUDIT_LOG.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(before_size)
                for line in fh:
                    for needle in FORBIDDEN_KAGGLE_PATTERNS:
                        if needle in line:
                            violations.append(line.rstrip("\n"))
                            break
        assert not violations, f"audit-grep sentinel tripped — {len(violations)} forbidden lines:\n" + "\n".join(
            violations[:5]
        )
        # The CLI itself also tallies audit_grep_violations across all
        # suites during the run; that must be 0 as well.
        assert payload.get("audit_grep_violations", 0) == 0, (
            f"in-process audit_grep_violations={payload.get('audit_grep_violations')}; expected 0"
        )
    finally:
        if new_run_id:
            with db_mod.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM eval_results WHERE run_id = %s::uuid",
                        (new_run_id,),
                    )
                    cur.execute(
                        "DELETE FROM eval_runs WHERE id = %s::uuid",
                        (new_run_id,),
                    )
                conn.commit()
