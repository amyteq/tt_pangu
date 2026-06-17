"""M1 smoke tests for the kca CLI.

Each test invokes kca via subprocess so the CLI surface is what's exercised,
not the internals. No network. Uses tmp_path for filesystem isolation.
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

# As of M2-T004, `kca run` is DB-first. Tests that exercise it skip when no DB
# is configured. Set KCA_DB_TARGET=local + SUPABASE_DB_URL to enable them.
requires_db = pytest.mark.skipif(
    not (os.environ.get("KCA_DB_TARGET") and os.environ.get("SUPABASE_DB_URL")),
    reason="kca run tests need KCA_DB_TARGET=local + SUPABASE_DB_URL (M2-T004 DB-first).",
)


def _run(*argv: str, env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env is not None:
        for k, v in env.items():
            if v is None:
                full_env.pop(k, None)
            else:
                full_env[k] = v
    return subprocess.run(
        [*KCA, *argv],
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
        cwd=str(cwd or REPO_ROOT),
    )


def _parse_json(proc: subprocess.CompletedProcess) -> dict:
    stdout = (proc.stdout or "").strip()
    assert stdout, f"empty stdout; stderr={proc.stderr!r}"
    return json.loads(stdout)


def test_nb_to_ipynb_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "src.py"
    src.write_text(
        "# %% [markdown]\n# Hello\n\n# %%\nx = 1\nprint('hi', x)\n",
        encoding="utf-8",
    )
    dst = tmp_path / "out.ipynb"
    proc = _run("nb", "to-ipynb", str(src), "--output", str(dst), "--keep-markdown", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = _parse_json(proc)
    assert payload["ok"] is True
    assert payload["side_effect"] == "LOCAL_WRITE"
    assert dst.exists()


def test_nb_to_py_roundtrip(tmp_path: Path) -> None:
    # Make an ipynb via to-ipynb first.
    src = tmp_path / "src.py"
    src.write_text("# %% [markdown]\n# Hi\n\n# %%\nx = 2\n", encoding="utf-8")
    ipynb = tmp_path / "round.ipynb"
    p1 = _run("nb", "to-ipynb", str(src), "--output", str(ipynb), "--keep-markdown", "--json")
    assert p1.returncode == 0

    out_py = tmp_path / "round.py"
    p2 = _run("nb", "to-py", str(ipynb), "--output", str(out_py), "--json")
    assert p2.returncode == 0, p2.stderr
    payload = _parse_json(p2)
    assert payload["ok"] is True
    assert out_py.exists()
    assert "x = 2" in out_py.read_text(encoding="utf-8")


@requires_db
def test_run_init_creates_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use a temp HOME-like sandbox: invoke from a temp cwd-equivalent by patching RUNS_ROOT via cwd.
    # The kca run module resolves runs/ relative to REPO_ROOT, so we use a competition slug
    # specific to this test and clean it up after.
    competition = "test_smoke_init"
    runs_path = REPO_ROOT / "runs" / competition
    try:
        proc = _run("run", "init", "--competition", competition, "--json")
        assert proc.returncode == 0, proc.stderr
        payload = _parse_json(proc)
        assert payload["ok"] is True
        assert payload["competition"] == competition

        run_dir = REPO_ROOT / payload["run_dir"]
        assert run_dir.is_dir()
        assert (run_dir / "meta.json").is_file()
        assert (run_dir / "metrics.json").is_file()
        assert (run_dir / "config.json").is_file()
        assert (run_dir / "logs").is_dir()
        assert (run_dir / "artifacts").is_dir()
    finally:
        if runs_path.exists():
            import shutil

            shutil.rmtree(runs_path)


@requires_db
def test_run_record_metric(tmp_path: Path) -> None:
    competition = "test_smoke_metric"
    runs_path = REPO_ROOT / "runs" / competition
    try:
        init = _parse_json(_run("run", "init", "--competition", competition, "--json"))
        run_dir = init["run_dir"]
        proc = _run(
            "run",
            "record-metric",
            "--run-dir",
            run_dir,
            "--key",
            "cv_score",
            "--value",
            "0.82",
            "--json",
        )
        assert proc.returncode == 0, proc.stderr
        payload = _parse_json(proc)
        assert payload["ok"] is True
        # M4 made metrics.json flat (key→value).
        metrics = json.loads((REPO_ROOT / run_dir / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["cv_score"] == 0.82
    finally:
        if runs_path.exists():
            import shutil

            shutil.rmtree(runs_path)


def test_kaggle_submit_blocked_without_env(tmp_path: Path) -> None:
    # M4: missing Kaggle credentials short-circuit before any approval check.
    proc = _run(
        "kaggle",
        "submit",
        "--competition",
        "x",
        "--file",
        "/dev/null",
        "--message",
        "test",
        "--json",
        env={
            "KCA_ALLOW_REMOTE": None,
            "KCA_DB_TARGET": None,
            "SUPABASE_DB_URL": None,
            "KAGGLE_USERNAME": None,
            "KAGGLE_KEY": None,
            # Prevent db.py from re-injecting repo-root .env creds (issue #11).
            "KCA_SKIP_DOTENV": "1",
        },
    )
    assert proc.returncode != 0
    payload = _parse_json(proc)
    assert payload["ok"] is False
    assert payload["side_effect"] == "SUBMISSION"
    assert "KAGGLE_USERNAME" in payload["error"] or "KAGGLE_KEY" in payload["error"]


def test_kaggle_submit_stub_with_env(tmp_path: Path) -> None:
    # M4: kca kaggle push --dry-run replaces the M2 'stub' contract for
    # exercising the gated remote-write path without credentials.
    proc = _run(
        "kaggle",
        "push",
        "--kernel-dir",
        str(REPO_ROOT / "tests" / "fixtures" / "sample_kernel"),
        "--dry-run",
        "--json",
        env={
            "KCA_ALLOW_REMOTE": None,
            "KCA_DB_TARGET": None,
            "SUPABASE_DB_URL": None,
        },
    )
    assert proc.returncode == 0, proc.stderr
    payload = _parse_json(proc)
    assert payload["ok"] is True
    assert payload.get("dry_run") is True
    assert payload["side_effect"] == "READ_ONLY"
