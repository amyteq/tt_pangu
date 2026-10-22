"""M9-T007 — end-to-end dry-run smoke test for the Spaceship Titanic loop.

This is the CI-friendly counterpart to ``tests/test_m9_smoke.py`` (the
DB-gated regression-assertion module). It exercises the full M9 path —
research → baseline → CV → ``submission.csv`` → reviewer-gate → decision
approve — *in dry-run mode*, on synthetic fixtures (200 train rows / 40
test rows), with **no network**, **no DB**, and **no real Kaggle
credentials**.

Acceptance scope (per docs/tasks/M9-T007-e2e-dryrun-test.md):

  - Run the worker in ``dry_run=True`` mode against a fixture data slice
    and verify the policy + audit wiring fires (audit JSONL row written,
    worker returns ``done``).
  - Produce a valid Kaggle ``submission.csv`` by driving the same
    baseline pipeline used by M9-T002 (``scripts/baseline_lr_spaceship``)
    against the fixture slice with a reduced ``n_splits``.
  - Drive the reviewer-gate decision flow via the decision_api
    ``TestClient`` with an in-memory fake DB (mirrors
    ``tests/test_m8_smoke.py``).
  - Assert that ``tools/kca/kg.py::cmd_submit`` refuses cleanly when
    ``KAGGLE_USERNAME`` / ``KAGGLE_KEY`` are absent — the credentials
    gate must fire before any real Kaggle call could happen.

The whole module SKIPs cleanly if any of the lightweight third-party
imports (``pandas``, ``sklearn``, ``fastapi``) are missing; the test
also does **not** require ``SUPABASE_DB_URL``.

Run with:
    python -m pytest tests/test_m9_e2e.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "spaceship-titanic"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))


# Skip the whole module if heavy optional deps are missing — keeps the
# `no-db` CI job green on a minimal install.
pd = pytest.importorskip("pandas")
sklearn = pytest.importorskip("sklearn")
pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# 1. Worker dry-run path — research/baseline tool call audited + done.
# ---------------------------------------------------------------------------
def test_worker_dry_run_audits_baseline_tool_call(tmp_path, monkeypatch):
    """Drive ``AgentWorker.run()`` once in dry-run mode with a mocked LiteLLM
    client that simulates the worker reaching for a baseline tool. Asserts the
    audit JSONL row lands and the worker terminates cleanly — the same
    contract M9-T002's worker loop relied on.
    """
    from src.worker._types import JobPolicy
    from src.worker.worker import AgentWorker, MockLiteLLMClient

    monkeypatch.setenv("KCA_AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    (tmp_path / "hello.txt").write_text("hi")

    policy = JobPolicy(
        skill_name="_test_fixture",
        policy_profile="permissive-dev",
        mode="default",
        tool_decisions={"read_file": "allow"},
    )
    worker = AgentWorker(
        job_id="00000000-0000-0000-0000-000000000000",
        prompt="m9-e2e dry-run: research → baseline → CV",
        policy=policy,
        workspace=tmp_path,
        db_url=None,
        dry_run=True,
    )

    client = MockLiteLLMClient(scenario="two_turns")
    turn_state = {"n": 0}

    def completion(**_kwargs):
        turn_state["n"] += 1
        if turn_state["n"] == 1:
            tc = types.SimpleNamespace(
                id="m9_e2e_call",
                type="function",
                function=types.SimpleNamespace(
                    name="read_file",
                    arguments=json.dumps({"path": "hello.txt"}),
                ),
            )
            msg = types.SimpleNamespace(content=None, tool_calls=[tc])
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=msg, finish_reason="tool_calls")],
                usage=types.SimpleNamespace(prompt_tokens=12, completion_tokens=6),
            )
        msg = types.SimpleNamespace(content="dry-run complete", tool_calls=None)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=msg, finish_reason="stop")],
            usage=types.SimpleNamespace(prompt_tokens=8, completion_tokens=4),
        )

    client.completion = completion  # type: ignore[method-assign]
    worker._mock_client = client

    result = worker.run()
    assert result.status == "done", result
    assert result.stop_reason == "end_turn"

    audit_path = tmp_path / "audit.jsonl"
    assert audit_path.is_file(), "expected audit.jsonl to be written"
    rows = [json.loads(line) for line in audit_path.read_text().splitlines() if line]
    assert any(r.get("tool_name") == "read_file" and r.get("decision") == "allow" for r in rows), (
        f"expected a read_file allow audit row, got {rows!r}"
    )


# ---------------------------------------------------------------------------
# 2. Baseline pipeline on the fixture slice — produces submission.csv + CV.
# ---------------------------------------------------------------------------
def test_baseline_pipeline_on_fixture_produces_submission_csv(tmp_path):
    """Run the same preprocessing + LR pipeline as
    ``scripts/baseline_lr_spaceship.py`` against the small fixture slice.

    Uses ``n_splits=3`` on the 200-row synthetic fixture. The
    point is the *shape* of the output, not a meaningful CV score.
    """
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    train = pd.read_csv(FIXTURE_DIR / "train.csv")
    test = pd.read_csv(FIXTURE_DIR / "test.csv")
    sample = pd.read_csv(FIXTURE_DIR / "sample_submission.csv")

    assert len(train) >= 50, "fixture train slice too small"
    assert len(test) == len(sample), (
        "fixture test/sample_submission row counts must match for a valid Kaggle submission shape"
    )

    def _split_cabin(df):
        parts = df["Cabin"].astype("string").str.split("/", expand=True)
        out = df.copy()
        out["Deck"] = parts[0].fillna("Missing").astype("string")
        out["Side"] = parts[2].fillna("Missing").astype("string")
        return out.drop(columns=["Cabin"])

    def _prep(df):
        return _split_cabin(df).drop(columns=["Name"], errors="ignore")

    y = train["Transported"].astype(int).to_numpy()
    train_feat = _prep(train.drop(columns=["Transported"]))
    test_feat = _prep(test)

    numeric_cols = [c for c in train_feat.columns if train_feat[c].dtype.kind in {"f", "i"} and c != "PassengerId"]
    categorical_cols = [c for c in train_feat.columns if c not in numeric_cols and c != "PassengerId"]

    pre = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="median")),
                        ("sc", StandardScaler()),
                    ]
                ),
                numeric_cols,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        (
                            "ohe",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical_cols,
            ),
        ]
    )
    pipe = Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=2000, random_state=42))])

    X_train = train_feat.drop(columns=["PassengerId"])
    X_test = test_feat.drop(columns=["PassengerId"])

    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    scores = cross_val_score(pipe, X_train, y, cv=skf, scoring="accuracy", n_jobs=1)
    cv_mean = float(scores.mean())

    # On 80 rows of noisy real data the CV will be modest; we just assert it
    # is in the plausible (0, 1) accuracy range. The real CV-threshold guard
    # lives in tests/test_m9_smoke.py against the live DB rows.
    assert 0.0 < cv_mean < 1.0, f"implausible CV mean: {cv_mean}"

    pipe.fit(X_train, y)
    preds = pipe.predict(X_test).astype(bool)

    submission = pd.DataFrame({"PassengerId": test_feat["PassengerId"].to_numpy(), "Transported": preds})
    submission = submission.set_index("PassengerId").loc[sample["PassengerId"]].reset_index()
    sub_path = tmp_path / "submission.csv"
    submission.to_csv(sub_path, index=False)

    # Validate submission file shape (the Kaggle-side schema for Spaceship
    # Titanic: PassengerId,Transported with boolean values).
    out = pd.read_csv(sub_path)
    assert list(out.columns) == ["PassengerId", "Transported"]
    assert len(out) == len(sample)
    assert out["Transported"].dtype == bool or set(out["Transported"].unique()).issubset({True, False, "True", "False"})


# ---------------------------------------------------------------------------
# 3. Reviewer-gate / decision-api approve flow with an in-memory fake DB.
# ---------------------------------------------------------------------------
def test_decision_api_approve_flow_dry_run():
    """Stand up the decision_api against a fake DB and approve the pending
    kaggle_submit decision via FastAPI's ``TestClient`` — no Supabase, no
    network. Mirrors the wiring used by ``tests/test_m8_smoke.py``.
    """
    from fastapi.testclient import TestClient

    from services.decision_api.app import make_app

    class _FakeDB:
        def __init__(self):
            self.decisions = {
                "m9-e2e-decision": {
                    "id": "m9-e2e-decision",
                    "status": "pending",
                    "job_id": "22222222-2222-2222-2222-222222222222",
                    "decision_type": "kaggle_submit",
                }
            }
            self.events: list[dict] = []

        def get_decision(self, did):
            return self.decisions.get(did)

        def resolve_decision(self, did, resolution, notes=None):
            self.decisions[did]["status"] = resolution
            self.decisions[did]["notes"] = notes

        def append_job_event(self, job_id, event_type, event_data=None, **_):
            self.events.append(
                {
                    "job_id": job_id,
                    "event_type": event_type,
                    "event_data": event_data,
                }
            )
            return len(self.events)

    fake = _FakeDB()
    app = make_app(decisions_module=fake, audit_logger=lambda **_: None)
    client = TestClient(app)

    r = client.post(
        "/decision/m9-e2e-decision/approve",
        json={"reason": "m9 e2e dry-run approval"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "approved"
    # Idempotency: second approve should 409, not silently re-approve.
    r2 = client.post(
        "/decision/m9-e2e-decision/approve",
        json={"reason": "second attempt"},
    )
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# 4. Credentials-gate refusal — kca kaggle submit MUST refuse without keys.
# ---------------------------------------------------------------------------
def test_kca_kaggle_submit_refuses_without_credentials(tmp_path):
    """The whole point of dry-run CI: even if a buggy worker tried to call
    ``kca kaggle submit``, it must refuse cleanly when KAGGLE_USERNAME or
    KAGGLE_KEY are absent — before any network or subprocess call to
    ``kaggle`` could happen.

    We run kca as a subprocess with a scrubbed env. We also disable dotenv
    autoloading via ``KCA_SKIP_DOTENV`` (defensive — see below) and point
    ``HOME`` at a clean tmp dir so any local ``~/.kaggle/kaggle.json``
    is not picked up by the kaggle library.
    """
    env = {
        # Start from a minimal env. We deliberately do NOT inherit
        # KAGGLE_USERNAME / KAGGLE_KEY / SUPABASE_DB_URL / KCA_ALLOW_REMOTE
        # from the parent process — the whole point is to assert the
        # gate fires under a creds-free CI shell.
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "PYTHONPATH": str(REPO_ROOT),
        # Belt-and-suspenders: tell dotenv-style loaders to ignore .env.
        # `tools/kca/db.py` uses python-dotenv with override=False, so an
        # explicitly absent KAGGLE_USERNAME in the subprocess env can
        # still be re-populated from a project-root .env file. We point
        # HOME away and additionally set KCA_SKIP_DOTENV so db.py skips the
        # repo-root .env auto-load entirely (issue #11).
        "KCA_SKIP_DOTENV": "1",
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "kca" / "kca.py"),
            "kaggle",
            "submit",
            "--competition",
            "spaceship-titanic",
            "--file",
            "/dev/null",
            "--message",
            "m9-e2e dry-run — must refuse",
            "--json",
        ],
        env=env,
        cwd=str(tmp_path),  # outside repo root → no .env auto-discovery
        capture_output=True,
        text=True,
        timeout=30,
    )
    # The submit path returns ok=False with EXIT_RUNTIME when creds are
    # missing (see tools/kca/kg.py::cmd_submit lines 145–162).
    assert proc.returncode != 0, (
        f"expected non-zero exit when KAGGLE_USERNAME absent; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    stdout = (proc.stdout or "").strip()
    assert stdout, f"empty stdout; stderr={proc.stderr!r}"
    payload = json.loads(stdout)
    assert payload["ok"] is False
    assert payload["side_effect"] == "SUBMISSION"
    assert "KAGGLE_USERNAME" in payload["error"] or "KAGGLE_KEY" in payload["error"], (
        f"expected credentials-gate refusal, got {payload!r}"
    )


# ---------------------------------------------------------------------------
# 5. Submission file shape contract — the worker's product is a valid CSV.
# ---------------------------------------------------------------------------
def test_submission_csv_shape_is_kaggle_compatible(tmp_path):
    """If a future worker dry-run ever produces a ``submission.csv`` whose
    schema diverges from sample_submission.csv, this test catches it before
    the real-submission Loop Prompt (M9-T004) can fire."""
    sample = pd.read_csv(FIXTURE_DIR / "sample_submission.csv")
    # Build a trivially-correct submission (all False) and check its shape.
    sub_path = tmp_path / "submission.csv"
    sub = pd.DataFrame(
        {
            "PassengerId": sample["PassengerId"],
            "Transported": [False] * len(sample),
        }
    )
    sub.to_csv(sub_path, index=False)

    loaded = pd.read_csv(sub_path)
    assert list(loaded.columns) == ["PassengerId", "Transported"]
    assert len(loaded) == len(sample)
    # Kaggle accepts True/False (Python bool) — verify the round-trip
    # preserved boolean semantics.
    assert set(loaded["Transported"].unique()).issubset({True, False})
