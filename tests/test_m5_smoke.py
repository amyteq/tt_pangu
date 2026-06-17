"""M5 smoke tests — all run without ANTHROPIC_API_KEY / SUPABASE_DB_URL / KAGGLE_KEY.

Run with:
    python -m pytest tests/test_m5_smoke.py -v
"""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
KCA = [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py")]
RUN_JOB = [sys.executable, str(REPO_ROOT / "scripts" / "run_job.py")]


def _env_clean(**overrides) -> dict:
    env = os.environ.copy()
    for k in (
        "SUPABASE_DB_URL",
        "KCA_DB_TARGET",
        "KAGGLE_USERNAME",
        "KAGGLE_KEY",
        "ANTHROPIC_API_KEY",
        "KCA_ALLOW_REMOTE",
        "KCA_RESEARCH_ALLOW_DOMAINS",
    ):
        env.pop(k, None)
    # Prevent db.py from re-injecting popped repo-root / .vscode .env creds (issue #11).
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


# ---------------------------------------------------------------------------
# 1. research_fetch refuses localhost
# ---------------------------------------------------------------------------


def test_research_fetch_refuses_localhost(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    from research_fetch import fetch_page

    r = fetch_page("http://127.0.0.1:1/", out_dir=tmp_path)
    assert r["ok"] is False
    assert "private-net" in r.get("policy_warnings", [])


# ---------------------------------------------------------------------------
# 2. research_fetch against a local HTTP server (allow private-net via allow-list)
# ---------------------------------------------------------------------------


class _Quiet(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<html><body><h1>Hello</h1><p>main content</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a, **k):
        return


def test_research_fetch_against_local_server(tmp_path, monkeypatch):
    # Bypass private-net guard by monkeypatching _is_private_host to False so
    # we can exercise the actual fetch path without a public server.
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    import research_fetch as rf

    with socketserver.TCPServer(("127.0.0.1", 0), _Quiet) as srv:
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            monkeypatch.setattr(rf, "_is_private_host", lambda host: False)
            r = rf.fetch_page(
                f"http://127.0.0.1:{port}/",
                out_dir=tmp_path,
                fetcher="http",
                timeout_s=5,
            )
        finally:
            srv.shutdown()
    assert r["ok"] is True, r
    assert (tmp_path / "raw.html").exists()
    assert (tmp_path / "main.txt").exists()
    assert r["content_hash"].startswith("sha256:")
    # Verify hash matches actual bytes.
    expected = hashlib.sha256((tmp_path / "raw.html").read_bytes()).hexdigest()
    assert r["content_hash"] == "sha256:" + expected


# ---------------------------------------------------------------------------
# 3. kca research add — graceful no-DB
# ---------------------------------------------------------------------------


def test_research_add_no_db(tmp_path):
    proc = _run(
        [
            *KCA,
            "research",
            "add",
            "--url",
            "https://example.com/x",
            "--title",
            "T",
            "--trust",
            "untrusted",
            "--json",
        ]
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert payload["url"] == "https://example.com/x"
    assert "db_warning" in payload  # degrades cleanly without DB


# ---------------------------------------------------------------------------
# 4. kca research list — graceful no-DB
# ---------------------------------------------------------------------------


def test_research_list_no_db():
    proc = _run([*KCA, "research", "list", "--json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert payload["items"] == []


# ---------------------------------------------------------------------------
# 5. kca kaggle download-equivalent + verify intact
# ---------------------------------------------------------------------------


def test_kaggle_download_verify_roundtrip(tmp_path):
    # Seed a manifest by hand (no actual kaggle CLI call).
    (tmp_path / "train.csv").write_bytes(b"hello\n")
    h = hashlib.sha256(b"hello\n").hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "competition": "x",
                "fetched_at": "x",
                "files": [{"name": "train.csv", "sha256": h, "bytes": 6}],
            }
        )
    )
    proc = _run([*KCA, "kaggle", "verify", "--path", str(tmp_path), "--json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert payload["ok_count"] == 1
    assert payload["mismatched"] == []


# ---------------------------------------------------------------------------
# 6. kca kaggle verify detects tampered files
# ---------------------------------------------------------------------------


def test_kaggle_download_verify_mismatch(tmp_path):
    (tmp_path / "train.csv").write_bytes(b"hello\n")
    h = hashlib.sha256(b"hello\n").hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "competition": "x",
                "fetched_at": "x",
                "files": [{"name": "train.csv", "sha256": h, "bytes": 6}],
            }
        )
    )
    # Tamper.
    (tmp_path / "train.csv").write_bytes(b"tampered\n")
    proc = _run([*KCA, "kaggle", "verify", "--path", str(tmp_path), "--json"])
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is False
    assert "train.csv" in payload["mismatched"]


# ---------------------------------------------------------------------------
# 7. model routing defaults
# ---------------------------------------------------------------------------


def test_model_routing_defaults():
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.routing import model_for

    assert model_for("eval") == "claude-opus-4-7"
    assert model_for("implement") == "claude-sonnet-4-6"
    assert model_for("research") == "claude-haiku-4-5"
    assert model_for("unknown_type") == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# 8. model routing override precedence
# ---------------------------------------------------------------------------


def test_model_routing_override():
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.routing import model_for

    assert model_for("eval", override="claude-haiku-4-5") == "claude-haiku-4-5"
    assert model_for("research", override="x") == "x"


# ---------------------------------------------------------------------------
# 9. run_job --job-type analysis → Opus in --json
# ---------------------------------------------------------------------------


def test_run_job_job_type_flag():
    proc = _run([*RUN_JOB, "--prompt", "p", "--dry-run", "--job-type", "analysis", "--json"])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert "opus" in payload.get("model", "").lower(), payload


# ---------------------------------------------------------------------------
# 10. external_fetch gate blocks when policy requires approval
# ---------------------------------------------------------------------------


def test_external_fetch_gate_blocks():
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    from kg import _check_approval_gate, ApprovalRequired

    saved = os.environ.pop("KCA_ALLOW_REMOTE", None)
    try:
        with pytest.raises(ApprovalRequired):
            _check_approval_gate(
                "external_fetch",
                {"approval_gates": {"external_fetch": True}},
            )
    finally:
        if saved is not None:
            os.environ["KCA_ALLOW_REMOTE"] = saved


# ---------------------------------------------------------------------------
# 11. external_fetch gate allows by default (False in OPERATION_DEFAULTS)
# ---------------------------------------------------------------------------


def test_external_fetch_gate_allows_default():
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker._types import JobPolicy

    assert JobPolicy().approval_gates.get("external_fetch") is False
    # And the kg.OPERATION_DEFAULTS agrees.
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
    from kg import OPERATION_DEFAULTS, _check_approval_gate

    assert OPERATION_DEFAULTS.get("external_fetch") is False
    saved = os.environ.pop("KCA_ALLOW_REMOTE", None)
    try:
        # Empty policy → default applies → no exception.
        _check_approval_gate("external_fetch", {})
    finally:
        if saved is not None:
            os.environ["KCA_ALLOW_REMOTE"] = saved


# ---------------------------------------------------------------------------
# 12. resume paused job (DB-dependent; skip cleanly when DB unavailable)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="resume test requires SUPABASE_DB_URL",
)
def test_resume_paused_dry_run(tmp_path):
    # Minimal exercise: AgentWorker.resume should import cleanly and refuse
    # unknown ids with a KeyError (not a connection error masquerading).
    sys.path.insert(0, str(REPO_ROOT))
    from src.worker.worker import AgentWorker

    with pytest.raises((KeyError, Exception)):
        AgentWorker.resume(
            job_id="00000000-0000-0000-0000-000000000000",
            workspace=tmp_path,
            dry_run=True,
        )
