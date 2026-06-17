"""M4 smoke tests — all run without ANTHROPIC_API_KEY / SUPABASE_DB_URL / KAGGLE_KEY.

Run with:
    python -m pytest tests/test_m4_smoke.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
KCA = [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py")]
RUN_JOB = [sys.executable, str(REPO_ROOT / "scripts" / "run_job.py")]


def _env_clean(**overrides) -> dict:
    """Copy os.environ minus DB/Kaggle/API keys; apply overrides last."""
    env = os.environ.copy()
    for k in (
        "SUPABASE_DB_URL",
        "KCA_DB_TARGET",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
        "ANTHROPIC_API_KEY",
        "KCA_ALLOW_REMOTE",
    ):
        env.pop(k, None)
    # Prevent db.py from re-injecting popped repo-root .env creds (issue #11).
    env["KCA_SKIP_DOTENV"] = "1"
    for k, v in overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def _run(argv, cwd=None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=False,
        env=env if env is not None else _env_clean(),
        cwd=str(cwd) if cwd is not None else str(REPO_ROOT),
    )


def test_competition_list_no_db():
    proc = _run([*KCA, "competition", "list", "--json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert "competitions" in payload
    assert payload["ok"] is True


def test_workspace_init_with_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
    )
    proc = _run(
        [
            *KCA,
            "workspace",
            "init",
            "--job-id",
            "test-m4-ws-1",
            "--repo",
            str(repo),
            "--json",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    ws = Path(payload["workspace_path"])
    assert ws.is_dir()
    # Cleanup
    _run(
        [
            *KCA,
            "workspace",
            "clean",
            "--job-id",
            "test-m4-ws-1",
            "--repo",
            str(repo),
            "--json",
        ]
    )


def test_run_init_creates_meta(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proc = _run(
        [
            *KCA,
            "run",
            "init",
            "--competition",
            "titanic",
            "--hypothesis",
            "smoke test",
            "--json",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    run_dir = tmp_path / payload["run_dir"]
    meta_path = run_dir / "meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["competition"] == "titanic"
    assert meta["hypothesis"] == "smoke test"


def test_run_record_metric(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init = _run(
        [
            *KCA,
            "run",
            "init",
            "--competition",
            "titanic",
            "--hypothesis",
            "smoke",
            "--json",
        ],
        cwd=tmp_path,
    )
    payload = json.loads(init.stdout.strip())
    run_dir = payload["run_dir"]
    rec = _run(
        [
            *KCA,
            "run",
            "record-metric",
            "--run-dir",
            run_dir,
            "--key",
            "cv_accuracy",
            "--value",
            "0.83",
            "--json",
        ],
        cwd=tmp_path,
    )
    assert rec.returncode == 0, rec.stderr
    metrics = json.loads((tmp_path / run_dir / "metrics.json").read_text())
    assert metrics == {"cv_accuracy": 0.83}


def test_run_list_no_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    proc = _run([*KCA, "run", "list", "--competition", "titanic", "--json"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert "runs" in payload


def test_kaggle_push_dry_run(tmp_path):
    (tmp_path / "kernel-metadata.json").write_text(
        json.dumps(
            {
                "id": "testuser/k",
                "title": "k",
                "code_file": "k.py",
                "language": "python",
                "kernel_type": "script",
                "is_private": True,
            }
        )
    )
    (tmp_path / "k.py").write_text("print('hi')\n")
    proc = _run([*KCA, "kaggle", "push", "--kernel-dir", str(tmp_path), "--dry-run", "--json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert payload.get("dry_run") is True


def test_kaggle_submit_no_credentials():
    proc = _run(
        [
            *KCA,
            "kaggle",
            "submit",
            "--competition",
            "titanic",
            "--file",
            "/dev/null",
            "--message",
            "m",
            "--json",
        ]
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False
    assert "error" in payload


def test_approval_gate_blocks_by_policy():
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    from kg import _check_approval_gate, ApprovalRequired

    os.environ.pop("KCA_ALLOW_REMOTE", None)
    with pytest.raises(ApprovalRequired):
        _check_approval_gate("kaggle_submit", {"approval_gates": {"kaggle_submit": True}})


def test_approval_gate_allows_by_default():
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    from kg import _check_approval_gate

    os.environ.pop("KCA_ALLOW_REMOTE", None)
    # Default: kaggle_submit=False → should NOT raise.
    _check_approval_gate("kaggle_submit", {"approval_gates": {"kaggle_submit": False}})


def test_run_job_competition_slug_dry_run():
    proc = _run(
        [
            *RUN_JOB,
            "--prompt",
            "test",
            "--competition-slug",
            "titanic",
            "--max-turns",
            "2",
            "--dry-run",
            "--json",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().split("\n")[-1])
    assert payload["status"] == "done"
