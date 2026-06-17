"""M10-T007 — end-to-end dry-run smoke test for the Petals-to-the-Metal loop.

This is the M10 counterpart to ``tests/test_m9_e2e.py``. It exercises the M10
pipeline shape — research-stub → baseline notebook → kg-nb round-trip →
reviewer-gate / decision_api approve → ``kca kaggle push`` REMOTE_WRITE-gate
refusal — *in dry-run mode*, on a tiny fixture stub
(``tests/fixtures/tpu-getting-started/``), with **no network**, **no real
Kaggle credentials**, and **no real Kaggle CLI invocation**.

Why this module exists in this exact shape (read this before editing):

  The equivalent M9 test inadvertently posted ERROR submissions to a live
  Kaggle leaderboard because ``tools/kca/db.py`` auto-loaded the repo-root
  ``.env`` into every kca subprocess regardless of ``cwd`` — re-injecting
  ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` even into a "scrubbed" subprocess env
  (issue #11). Petals-to-the-Metal is image-based and kernel pushes count
  against a *daily* limit, so a repeat would be costlier. The fix (issue #11,
  CLOSED) added ``KCA_SKIP_DOTENV`` to ``tools/kca/db.py``. **Every kca
  subprocess in this module sets ``KCA_SKIP_DOTENV=1`` and points ``HOME`` at a
  clean tmp dir** so the repo-root ``.env`` cannot silently re-inject Kaggle
  credentials. Test 5 (the audit-grep sentinel) is the explicit regression
  guard against repeating the leak.

A note on the credentials gate (divergence from the task-spec snippet):
  ``tools/kca/kg.py::cmd_submit`` has an early ``KAGGLE_USERNAME`` /
  ``KAGGLE_KEY`` check, but ``cmd_push`` does **not** — ``kernel_push`` refuses
  via the *approval gate* (``ApprovalRequired: kernel_push``,
  ``side_effect == "REMOTE_WRITE"``). M10-T007 must NOT extend ``cmd_push``
  (that is M10-T002 / #11 scope), so the push-refusal test asserts the actual
  approval-gate refusal and — critically — that the refusal happens *before*
  the kaggle CLI is reached (verified by the audit-grep sentinel + the fact
  that no real ``kaggle kernels push`` ran).

The whole module SKIPs cleanly if lightweight deps (``nbformat``, ``fastapi``)
are missing, and does **not** require ``SUPABASE_DB_URL`` (the DB-backed
reviewer-gate assertions SKIP without it; the in-memory variant always runs).

Run with:
    python -m pytest tests/test_m10_e2e.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "tpu-getting-started"
KCA = REPO_ROOT / "tools" / "kca" / "kca.py"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

# Skip the whole module if heavy-ish optional deps are missing — keeps the
# `no-db` CI job green on a minimal install.
nbformat = pytest.importorskip("nbformat")
pytest.importorskip("fastapi")

requires_db = pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL not set",
)

# The real push command the kaggle CLI would run. The audit-grep sentinel
# asserts ZERO occurrences of these reaching the CLI from this test process.
_REAL_PUSH_PREFIXES = ("kaggle kernels push", "kca kaggle push")


def _scrubbed_env(home: Path) -> dict:
    """A minimal, credentials-free env for a kca subprocess.

    Deliberately does NOT inherit KAGGLE_USERNAME / KAGGLE_KEY /
    SUPABASE_DB_URL / KCA_ALLOW_REMOTE from the parent. ``KCA_SKIP_DOTENV=1``
    stops ``tools/kca/db.py`` from re-injecting the repo-root ``.env`` (issue
    #11); ``HOME`` points away from any ``~/.kaggle/kaggle.json``.
    """
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "PYTHONPATH": str(REPO_ROOT),
        "KCA_SKIP_DOTENV": "1",
    }


def _run_kca(args: list[str], home: Path, *, extra_env: dict | None = None):
    env = _scrubbed_env(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(KCA), *args],
        env=env,
        cwd=str(home),  # outside repo root → no .env auto-discovery either
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# 1. Baseline notebook smoke — fixture stub executes top-to-bottom < 60s.
# ---------------------------------------------------------------------------
def test_baseline_stub_executes_and_writes_submission_shape(tmp_path):
    """Execute the fixture stub's submission writer and assert the resulting
    ``submission.csv`` matches Petals-to-the-Metal's ``id,label`` schema.

    Stands in for the real (TF/TPU) baseline notebook, which cannot run in CI.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("petals_stub", FIXTURE_DIR / "baseline_stub.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # exercises the stub top-to-bottom

    sub_path = tmp_path / "submission.csv"
    n = mod.write_submission(str(sub_path), mod.STUB_TEST_IDS)
    assert n == len(mod.STUB_TEST_IDS)

    import csv

    with sub_path.open(newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["id", "label"], f"bad header: {rows[0]!r}"
    assert len(rows) - 1 == n
    for tid, label in rows[1:]:
        assert tid.startswith("flower_")
        assert 0 <= int(label) < mod.NUM_CLASSES


# ---------------------------------------------------------------------------
# 2. kg-nb round-trip — to-ipynb → to-py preserves the cell sequence.
# ---------------------------------------------------------------------------
def test_kg_nb_round_trip_preserves_cells(tmp_path):
    """``kca nb to-ipynb`` then ``kca nb to-py`` must preserve the cell counts
    and code-cell sources (modulo execution metadata).
    """
    ipynb_path = tmp_path / "baseline.ipynb"
    py_back_path = tmp_path / "baseline_back.py"

    r1 = _run_kca(
        [
            "nb",
            "to-ipynb",
            str(FIXTURE_DIR / "baseline_stub.py"),
            "-o",
            str(ipynb_path),
            "--keep-markdown",
        ],
        tmp_path,
    )
    assert r1.returncode == 0, f"to-ipynb failed: {r1.stdout!r} {r1.stderr!r}"
    p1 = json.loads(r1.stdout.strip())
    assert p1["ok"] is True
    assert ipynb_path.is_file()

    # The generated notebook must carry a kernelspec (py2nb emits it).
    nb = nbformat.read(str(ipynb_path), as_version=4)
    assert nb.metadata.get("kernelspec", {}).get("name") == "python3"
    n_code_fwd = sum(1 for c in nb.cells if c.cell_type == "code")
    n_md_fwd = sum(1 for c in nb.cells if c.cell_type == "markdown")

    r2 = _run_kca(
        ["nb", "to-py", str(ipynb_path), "-o", str(py_back_path)],
        tmp_path,
    )
    assert r2.returncode == 0, f"to-py failed: {r2.stdout!r} {r2.stderr!r}"
    p2 = json.loads(r2.stdout.strip())
    assert p2["ok"] is True
    assert py_back_path.is_file()

    # Round-trip is cell-count-stable in both directions.
    assert p1["code_cells"] == p2["code_cells"] == n_code_fwd
    assert p1["markdown_cells"] == p2["markdown_cells"] == n_md_fwd

    # The load-bearing code survives the round-trip.
    back_text = py_back_path.read_text()
    assert "def write_submission(" in back_text
    assert "NUM_CLASSES = 104" in back_text


# ---------------------------------------------------------------------------
# 3a. Reviewer-gate / decision_api approve flow — in-memory fake DB (always).
# ---------------------------------------------------------------------------
def test_decision_api_approve_flow_dry_run_in_memory():
    """Stand up decision_api against a fake DB and approve a pending
    ``kernel_push`` decision via FastAPI's ``TestClient`` — no Supabase, no
    network. Mirrors ``tests/test_m9_e2e.py``.
    """
    from fastapi.testclient import TestClient

    from services.decision_api.app import make_app

    class _FakeDB:
        def __init__(self):
            self.decisions = {
                "m10-e2e-decision": {
                    "id": "m10-e2e-decision",
                    "status": "pending",
                    "job_id": "33333333-3333-3333-3333-333333333333",
                    "decision_type": "kernel_push",
                }
            }
            self.events: list[dict] = []

        def get_decision(self, did):
            return self.decisions.get(did)

        def resolve_decision(self, did, resolution, notes=None):
            self.decisions[did]["status"] = resolution
            self.decisions[did]["notes"] = notes

        def append_job_event(self, job_id, event_type, event_data=None, **_):
            self.events.append({"job_id": job_id, "event_type": event_type, "event_data": event_data})
            return len(self.events)

    fake = _FakeDB()
    app = make_app(decisions_module=fake, audit_logger=lambda **_: None)
    client = TestClient(app)

    r = client.post(
        "/decision/m10-e2e-decision/approve",
        json={"reason": "m10 e2e dry-run approval"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "approved"
    assert fake.decisions["m10-e2e-decision"]["status"] == "approved"

    # Idempotency: a second approve must 409, not silently re-approve.
    r2 = client.post(
        "/decision/m10-e2e-decision/approve",
        json={"reason": "second attempt"},
    )
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# 3b. Reviewer-gate / decision round-trip against the live sandbox DB.
# ---------------------------------------------------------------------------
@requires_db
def test_kernel_push_decision_round_trip_live_db():
    """With ``SUPABASE_DB_URL`` set, insert a pending ``kernel_push`` decision,
    approve it, and assert the status flip lands in ``human_decisions``.

    SKIPs cleanly without the DB (no-db CI job); PASSes against the live local
    supabase-db (live-db CI job).
    """
    import db as _db

    decision_id = _db.insert_approval_request(
        decision_type="kaggle.kernel_push",
        prompt="m10-e2e dry-run kernel_push approval",
        options={"competition": "tpu-getting-started"},
    )
    assert decision_id

    before = _db.get_decision(decision_id)
    assert before["status"] == "pending"

    _db.resolve_decision(decision_id, "approved", notes="m10-e2e dry-run")

    after = _db.get_decision(decision_id)
    assert after["status"] == "approved", after
    assert after["decided_at"] is not None


# ---------------------------------------------------------------------------
# 4. kca kaggle push REMOTE_WRITE-gate refusal — MUST refuse before the CLI.
# ---------------------------------------------------------------------------
def test_kca_kaggle_push_refuses_before_cli(tmp_path):
    """The whole point of dry-run CI: ``kca kaggle push`` must refuse cleanly
    via the approval gate — BEFORE any real ``kaggle kernels push`` could run —
    when no approval is granted.

    We enable the ``kernel_push`` approval gate via ``KCA_POLICY`` (its
    ADR-0006 default is allow). With the gate on and ``KCA_ALLOW_REMOTE``
    absent, ``cmd_push`` raises ``ApprovalRequired: kernel_push`` and emits a
    blocked envelope with ``side_effect == "REMOTE_WRITE"`` — no subprocess to
    the kaggle CLI happens.

    M14-T004 added a ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` pre-check (issue #62)
    that fires BEFORE the approval gate, mirroring ``cmd_submit``. To keep this
    test exercising the *approval-gate* refusal specifically, we pass stub
    creds so the pre-check is satisfied and control reaches the gate. (The
    creds-missing refusal is covered by ``tests/test_m14_concurrency.py``.)
    """
    proc = _run_kca(
        [
            "kaggle",
            "push",
            "--kernel-dir",
            "/dev/null",
            "--json",
        ],
        tmp_path,
        extra_env={
            "KCA_POLICY": json.dumps({"approval_gates": {"kernel_push": True}}),
            "KAGGLE_USERNAME": "stub-user",
            "KAGGLE_KEY": "stub-key",
        },
    )
    assert proc.returncode != 0, (
        f"expected non-zero exit on gated kernel_push; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    stdout = (proc.stdout or "").strip()
    assert stdout, f"empty stdout; stderr={proc.stderr!r}"
    payload = json.loads(stdout)
    assert payload["ok"] is False, payload
    assert payload["side_effect"] == "REMOTE_WRITE", payload
    assert "kernel_push" in payload["error"], payload
    # No real kaggle CLI auth/network error leaked into the envelope — the
    # refusal happened at the gate, not at the kaggle library.
    assert "authenticate" not in json.dumps(payload).lower(), (
        f"refusal appears to have reached the kaggle CLI: {payload!r}"
    )


# ---------------------------------------------------------------------------
# 5. Audit-grep regression sentinel — 0 real push commands left this process.
# ---------------------------------------------------------------------------
def test_audit_grep_no_real_push_leaked(tmp_path):
    """Drive ``kca kaggle push`` (gated) and assert that the audit JSONL for
    THIS test process contains 0 lines whose command starts with a real push.

    This is the explicit guard against repeating the M9 leak. We point
    ``KCA_AUDIT_PATH`` at a per-test file so the assertion is scoped to this
    process only, and grep both the audit log and the kca stdout/stderr.
    """
    audit_path = tmp_path / "tool-events.jsonl"
    proc = _run_kca(
        ["kaggle", "push", "--kernel-dir", "/dev/null", "--json"],
        tmp_path,
        extra_env={
            "KCA_POLICY": json.dumps({"approval_gates": {"kernel_push": True}}),
            "KCA_AUDIT_PATH": str(audit_path),
            # Stub creds so the M14-T004 pre-check passes and the audit-grep
            # assertion still exercises the approval-gate refusal path.
            "KAGGLE_USERNAME": "stub-user",
            "KAGGLE_KEY": "stub-key",
        },
    )

    # The combined output stream must contain no real-push command, and no
    # sign of the kaggle CLI having been invoked.
    combined = (proc.stdout or "") + (proc.stderr or "")
    for line in combined.splitlines():
        stripped = line.strip().strip('"').lstrip("$ ").strip()
        assert not stripped.startswith(_REAL_PUSH_PREFIXES), f"a real push command leaked to the CLI: {line!r}"
    assert "authenticate before you can call the Kaggle API" not in combined, (
        "kaggle CLI was reached — the gate did not refuse first"
    )

    # If an audit JSONL was written, scan its recorded commands too.
    if audit_path.is_file():
        leaked = []
        for line in audit_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cmd = str(row.get("command") or row.get("operation") or "")
            if cmd.startswith(_REAL_PUSH_PREFIXES):
                leaked.append(cmd)
        assert leaked == [], f"audit log shows leaked push commands: {leaked!r}"


# ---------------------------------------------------------------------------
# 6. Submission-shape sanity — kernel-metadata.json parses & has required keys.
# ---------------------------------------------------------------------------
def test_kernel_metadata_schema_is_valid():
    """The fixture ``kernel-metadata.json`` must parse and carry the fields
    ``kaggle kernels init`` produces — validated structurally, with NO real
    Kaggle CLI call.
    """
    meta = json.loads((FIXTURE_DIR / "kernel-metadata.json").read_text())

    # Keys emitted by `kaggle kernels init` for a notebook kernel.
    required = {
        "id": str,
        "title": str,
        "code_file": str,
        "language": str,
        "kernel_type": str,
        "is_private": bool,
        "enable_gpu": bool,
        "enable_internet": bool,
        "competition_sources": list,
    }
    for key, typ in required.items():
        assert key in meta, f"missing kernel-metadata key: {key}"
        assert isinstance(meta[key], typ), f"{key} should be {typ.__name__}, got {type(meta[key]).__name__}"

    assert meta["language"] == "python"
    assert meta["kernel_type"] in {"notebook", "script"}
    assert meta["code_file"].endswith((".ipynb", ".py"))
    # The Petals competition must be wired as a competition source.
    assert "tpu-getting-started" in meta["competition_sources"]
    # Dry-run safety: the fixture kernel must not enable internet.
    assert meta["enable_internet"] is False
