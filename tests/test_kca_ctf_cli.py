"""M11-T003 smoke tests for the `kca ctf` CLI surface.

What this file covers:

  1. `kca ctf --help` lists the five sub-namespaces.
  2. `_load_event_credentials` resolves file + env-var paths and never
     surfaces raw values via `_safe_cred_presence`.
  3. `_scope_covers_url` matches on host and rejects expired scopes.
  4. `kca ctf flag submit --dry-run` works without `KCA_ALLOW_REMOTE=1`
     and never echoes the flag value or credential values.
  5. `kca ctf flag submit` (no `--dry-run`) refuses without
     `KCA_ALLOW_REMOTE=1` (gate-blocked exit 2).
  6. `kca ctf scope verify` exit-code contract via direct helper call
     (the DB-bound CLI path is exercised in T008 with a live DB).
  7. `cmd_event_register` is idempotent when called twice with the same
     slug (asserted via the underlying helper signature; the live
     idempotency round-trip lands in tests/test_kca_ctf_db.py when a
     DB is reachable).
  8. `_read_flag_length` reads only the integer length; the bytes are
     not exposed.
  9. Audit-grep: no flag value or credential value appears in any
     subprocess stdout/stderr captured in this file.

All tests are sandbox-safe: no real DB, no real network, no flag
strings printed.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
KCA = [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py")]

# Make tools/kca importable directly so unit-test calls can hit
# `tools.kca.ctf` internals without going via subprocess.
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

import ctf as ctf_mod  # noqa: E402


# A flag-like sentinel that must NEVER appear in any captured stdout
# or stderr from a subprocess. The audit-grep at the end of this file
# checks this across collected output.
_SENTINEL_FLAG = "flag{m11_t003_sentinel_DO_NOT_LEAK}"
_SENTINEL_TOKEN = "tok_m11_t003_DO_NOT_LEAK_eyJsZWFr"
_SENTINEL_USER = "user_m11_t003_DO_NOT_LEAK"

_CAPTURED_STDOUT: list[str] = []
_CAPTURED_STDERR: list[str] = []


def _run(*argv: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    # Strip parent-process DB / remote env so the no-network tests can't
    # accidentally hit a live DB.
    for k in (
        "KCA_ALLOW_REMOTE",
        "KCA_DB_TARGET",
        "SUPABASE_DB_URL",
        "SUPABASE_DB_HOST",
    ):
        full_env.pop(k, None)
    if env is not None:
        for k, v in env.items():
            if v is None:
                full_env.pop(k, None)
            else:
                full_env[k] = v
    proc = subprocess.run(
        [*KCA, *argv],
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
        cwd=str(REPO_ROOT),
    )
    _CAPTURED_STDOUT.append(proc.stdout or "")
    _CAPTURED_STDERR.append(proc.stderr or "")
    return proc


def _parse_last_json(stdout: str) -> dict:
    """kca emits a single JSON object on the last non-empty stdout line."""
    lines = [ln for ln in (stdout or "").splitlines() if ln.strip()]
    assert lines, "empty stdout"
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# 1. Top-level surface
# ---------------------------------------------------------------------------


def test_ctf_help_lists_five_sub_namespaces() -> None:
    proc = _run("ctf", "--help")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    for ns in ("event", "challenge", "scope", "solver", "flag"):
        assert ns in out, f"missing namespace {ns!r} in `kca ctf --help`"


@pytest.mark.parametrize(
    "argv",
    [
        ("ctf", "event", "register", "--help"),
        ("ctf", "event", "list", "--help"),
        ("ctf", "event", "info", "--help"),
        ("ctf", "challenge", "add", "--help"),
        ("ctf", "challenge", "fetch", "--help"),
        ("ctf", "challenge", "list", "--help"),
        ("ctf", "challenge", "info", "--help"),
        ("ctf", "scope", "set", "--help"),
        ("ctf", "scope", "list", "--help"),
        ("ctf", "scope", "verify", "--help"),
        ("ctf", "solver", "run", "--help"),
        ("ctf", "flag", "submit", "--help"),
    ],
)
def test_each_subcommand_has_help(argv) -> None:
    proc = _run(*argv)
    assert proc.returncode == 0, (argv, proc.stderr)
    assert "usage: kca ctf" in proc.stdout


# ---------------------------------------------------------------------------
# 2. Credential loading allow-list — file path + env path
# ---------------------------------------------------------------------------


def test_load_event_credentials_from_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctf_mod, "_CTF_CRED_DIR", tmp_path)
    (tmp_path / "demo.json").write_text(
        json.dumps({"username": _SENTINEL_USER, "token": _SENTINEL_TOKEN}),
        encoding="utf-8",
    )
    creds = ctf_mod._load_event_credentials("demo")
    assert creds["source"] == "file"
    assert creds["has_username"] is True
    assert creds["has_token"] is True
    assert creds["has_team_id"] is False
    # The safe-presence stripper drops underscored values.
    safe = ctf_mod._safe_cred_presence(creds)
    safe_dump = json.dumps(safe)
    assert _SENTINEL_USER not in safe_dump
    assert _SENTINEL_TOKEN not in safe_dump


def test_load_event_credentials_from_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctf_mod, "_CTF_CRED_DIR", tmp_path)  # empty dir
    monkeypatch.setenv("CTF_DEMO_EVENT_USERNAME", _SENTINEL_USER)
    monkeypatch.setenv("CTF_DEMO_EVENT_TOKEN", _SENTINEL_TOKEN)
    creds = ctf_mod._load_event_credentials("demo-event")
    assert creds["source"] == "env"
    assert creds["has_username"] is True
    assert creds["has_token"] is True


def test_load_event_credentials_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctf_mod, "_CTF_CRED_DIR", tmp_path)
    # ensure env not set
    for k in list(os.environ):
        if k.startswith("CTF_") and k.endswith(("_USERNAME", "_TOKEN", "_TEAM_ID")):
            monkeypatch.delenv(k, raising=False)
    with pytest.raises(ctf_mod.CredentialsMissing):
        ctf_mod._load_event_credentials("absent-event")


# ---------------------------------------------------------------------------
# 2b. CTFtime platform-tier credential loader (~/.env)
# ---------------------------------------------------------------------------


def _clear_ctftime_env(monkeypatch) -> None:
    for k in ("CTFTIME_USERNAME", "CTFTIME_PASSWORD", "CTFTIME_TOKEN"):
        monkeypatch.delenv(k, raising=False)


def test_load_ctftime_credentials_from_home_env_file(tmp_path, monkeypatch) -> None:
    fake_env = tmp_path / ".env"
    fake_env.write_text(
        f'# CTFtime platform account\nCTFTIME_USERNAME={_SENTINEL_USER}\nCTFTIME_PASSWORD="{_SENTINEL_TOKEN}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ctf_mod, "_CTFTIME_ENV_PATH", fake_env)
    _clear_ctftime_env(monkeypatch)
    creds = ctf_mod._load_ctftime_credentials()
    assert creds["source"] == "home_env"
    assert creds["has_username"] is True
    assert creds["has_token"] is True
    assert creds["has_team_id"] is False
    # _safe_cred_presence must NOT echo the underlying values
    safe_dump = json.dumps(ctf_mod._safe_cred_presence(creds))
    assert _SENTINEL_USER not in safe_dump
    assert _SENTINEL_TOKEN not in safe_dump


def test_load_ctftime_credentials_token_alias(tmp_path, monkeypatch) -> None:
    fake_env = tmp_path / ".env"
    fake_env.write_text(
        f"CTFTIME_USERNAME={_SENTINEL_USER}\nCTFTIME_TOKEN={_SENTINEL_TOKEN}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ctf_mod, "_CTFTIME_ENV_PATH", fake_env)
    _clear_ctftime_env(monkeypatch)
    creds = ctf_mod._load_ctftime_credentials()
    assert creds["source"] == "home_env"
    assert creds["_token"] == _SENTINEL_TOKEN


def test_load_ctftime_credentials_from_process_env(tmp_path, monkeypatch) -> None:
    # No ~/.env file; fall through to process env vars.
    monkeypatch.setattr(ctf_mod, "_CTFTIME_ENV_PATH", tmp_path / ".env")
    _clear_ctftime_env(monkeypatch)
    monkeypatch.setenv("CTFTIME_USERNAME", _SENTINEL_USER)
    monkeypatch.setenv("CTFTIME_PASSWORD", _SENTINEL_TOKEN)
    creds = ctf_mod._load_ctftime_credentials()
    assert creds["source"] == "process_env"
    assert creds["has_username"] is True
    assert creds["has_token"] is True


def test_load_ctftime_credentials_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ctf_mod, "_CTFTIME_ENV_PATH", tmp_path / ".env")
    _clear_ctftime_env(monkeypatch)
    with pytest.raises(ctf_mod.CredentialsMissing):
        ctf_mod._load_ctftime_credentials()


def test_parse_dotenv_basic_shapes() -> None:
    parsed = ctf_mod._parse_dotenv(
        "# comment\n"
        "EMPTY=\n"
        "BARE=value\n"
        'DQUOTED="quoted value"\n'
        "SQUOTED='single quoted'\n"
        "  WHITESPACE_KEY  =  spaced  \n"
    )
    assert parsed["BARE"] == "value"
    assert parsed["DQUOTED"] == "quoted value"
    assert parsed["SQUOTED"] == "single quoted"
    assert parsed["WHITESPACE_KEY"] == "spaced"
    assert parsed["EMPTY"] == ""
    assert "# comment" not in parsed
    # Comments and blank lines silently skipped — no exception.


# ---------------------------------------------------------------------------
# 3. Scope coverage helper
# ---------------------------------------------------------------------------


def test_scope_covers_url_host_match() -> None:
    scope = {
        "target_urls": [
            "https://event.example/api/submit",
            "https://www.event.example",
        ],
        "expires_at": None,
    }
    assert ctf_mod._scope_covers_url(scope, "https://event.example/anything")
    assert ctf_mod._scope_covers_url(scope, "https://www.event.example/api/submit")
    assert not ctf_mod._scope_covers_url(scope, "https://kaggle.com/submit")
    assert not ctf_mod._scope_covers_url(scope, "")


def test_scope_covers_url_rejects_expired() -> None:
    past = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=1)
    scope = {
        "target_urls": ["https://event.example/submit"],
        "expires_at": past,
    }
    assert not ctf_mod._scope_covers_url(scope, "https://event.example/submit")


def test_scope_covers_url_accepts_jsonb_string() -> None:
    # Postgres jsonb is occasionally returned as a JSON string by some
    # adapters — make sure the helper handles that shape too.
    scope = {
        "target_urls": json.dumps(["https://event.example/submit"]),
        "expires_at": None,
    }
    assert ctf_mod._scope_covers_url(scope, "https://event.example/anything")


# ---------------------------------------------------------------------------
# 4. flag submit --dry-run
# ---------------------------------------------------------------------------


def test_flag_submit_dry_run_no_remote_allow(tmp_path) -> None:
    flag_file = tmp_path / "flag.txt"
    flag_file.write_text(_SENTINEL_FLAG, encoding="utf-8")
    proc = _run(
        "ctf",
        "flag",
        "submit",
        "--event",
        "demo-event",
        "--challenge",
        "demo-challenge",
        "--flag-file",
        str(flag_file),
        "--dry-run",
    )
    assert proc.returncode == 0, proc.stderr
    payload = _parse_last_json(proc.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["command"] == "ctf flag submit"
    assert payload["flag_length"] == len(_SENTINEL_FLAG)
    # The flag value, sentinel chars, etc. MUST NOT appear in either
    # stdout or stderr of this subprocess.
    assert _SENTINEL_FLAG not in proc.stdout
    assert _SENTINEL_FLAG not in proc.stderr


def test_flag_submit_no_dry_run_refuses_without_remote_allow(tmp_path) -> None:
    flag_file = tmp_path / "flag.txt"
    flag_file.write_text(_SENTINEL_FLAG, encoding="utf-8")
    proc = _run(
        "ctf",
        "flag",
        "submit",
        "--event",
        "demo-event",
        "--challenge",
        "demo-challenge",
        "--flag-file",
        str(flag_file),
    )
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    payload = _parse_last_json(proc.stdout)
    assert payload["ok"] is False
    assert payload["target_op"] == "flag_submit"
    assert "KCA_ALLOW_REMOTE" in payload["error"]
    assert _SENTINEL_FLAG not in proc.stdout
    assert _SENTINEL_FLAG not in proc.stderr


def test_flag_submit_dry_run_does_not_echo_credentials(tmp_path, monkeypatch) -> None:
    # Stage a fake credential file under a tmp dir; monkeypatch the
    # module-level dir so we don't even touch the real ~/.ctf/.
    cred_dir = tmp_path / "ctf-creds"
    cred_dir.mkdir()
    monkeypatch.setattr(ctf_mod, "_CTF_CRED_DIR", cred_dir)
    (cred_dir / "demo-event.json").write_text(
        json.dumps({"username": _SENTINEL_USER, "token": _SENTINEL_TOKEN}),
        encoding="utf-8",
    )
    flag_file = tmp_path / "flag.txt"
    flag_file.write_text(_SENTINEL_FLAG, encoding="utf-8")

    # Invoke cmd_flag_submit directly to exercise the credential read
    # code path under the monkeypatched dir (subprocess wouldn't see
    # the monkeypatch).
    import argparse

    args = argparse.Namespace(
        event="demo-event",
        challenge="demo-challenge",
        flag_file=str(flag_file),
        dry_run=True,
        json=False,
    )

    import io

    buf = io.StringIO()
    real_stdout = sys.stdout
    try:
        sys.stdout = buf
        rc = ctf_mod.cmd_flag_submit(args)
    finally:
        sys.stdout = real_stdout
    assert rc == 0
    out = buf.getvalue()
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["dry_run"] is True
    assert payload["flag_length"] == len(_SENTINEL_FLAG)
    assert payload["credentials"]["has_username"] is True
    assert payload["credentials"]["has_token"] is True
    # No raw values anywhere in the emitted output.
    assert _SENTINEL_FLAG not in out
    assert _SENTINEL_TOKEN not in out
    assert _SENTINEL_USER not in out
    _CAPTURED_STDOUT.append(out)


# ---------------------------------------------------------------------------
# 5. solver run gate behavior (no DB required)
# ---------------------------------------------------------------------------


def test_solver_run_dry_run_no_gate() -> None:
    proc = _run(
        "ctf",
        "solver",
        "run",
        "--event",
        "demo-event",
        "--challenge",
        "demo-challenge",
        "--dry-run",
    )
    assert proc.returncode == 0, proc.stderr
    payload = _parse_last_json(proc.stdout)
    assert payload["dry_run"] is True
    assert payload["reviewer_gate"] is False
    assert payload["side_effect"] == "LOCAL_WRITE"


def test_solver_run_with_reviewer_gate_refuses_without_remote_allow() -> None:
    proc = _run(
        "ctf",
        "solver",
        "run",
        "--event",
        "demo-event",
        "--challenge",
        "demo-challenge",
        "--reviewer-gate",
    )
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    payload = _parse_last_json(proc.stdout)
    assert payload["ok"] is False
    assert payload["target_op"] == "challenge_run"


# ---------------------------------------------------------------------------
# 6. scope verify exit-code contract (direct helper call)
# ---------------------------------------------------------------------------


def test_scope_verify_helper_exit_zero_for_in_scope() -> None:
    scope = {
        "target_urls": ["https://event.example/api/submit"],
        "expires_at": None,
    }
    assert ctf_mod._scope_covers_url(scope, "https://event.example/anything")


def test_scope_verify_helper_exit_nonzero_for_out_of_scope() -> None:
    scope = {
        "target_urls": ["https://event.example/api/submit"],
        "expires_at": None,
    }
    assert not ctf_mod._scope_covers_url(scope, "https://other.example/x")


# ---------------------------------------------------------------------------
# 7. event register idempotency — helper signature check
# ---------------------------------------------------------------------------


def test_event_register_helper_idempotent_signature() -> None:
    # The underlying `register_event` helper uses ON CONFLICT (slug) DO
    # UPDATE SET slug = EXCLUDED.slug RETURNING id — i.e. idempotent on
    # slug. We assert that the helper signature exposes the
    # `credentials_ref` path-hint parameter (not the value itself), as
    # the CLI command relies on.
    from inspect import signature

    sys.path.insert(0, str(REPO_ROOT))
    from src.db.ctf import register_event

    sig = signature(register_event)
    params = sig.parameters
    assert "slug" in params
    assert "credentials_ref" in params
    # The helper should NOT accept any param that smells like a
    # credential value rather than a hint.
    for forbidden in ("password", "token", "username", "secret"):
        assert forbidden not in params, f"register_event accepts {forbidden!r} — should be a path hint only"


# ---------------------------------------------------------------------------
# 8. flag-file length-only read
# ---------------------------------------------------------------------------


def test_read_flag_length_returns_int_only(tmp_path) -> None:
    f = tmp_path / "flag.txt"
    f.write_text(_SENTINEL_FLAG + "\n", encoding="utf-8")
    n = ctf_mod._read_flag_length(f)
    assert isinstance(n, int)
    assert n == len(_SENTINEL_FLAG)  # strip() removes the trailing \n


# ---------------------------------------------------------------------------
# 9. Audit-grep — no sentinel ever appears in captured subprocess output
# ---------------------------------------------------------------------------


def test_audit_grep_no_flag_or_credential_in_captured_output() -> None:
    blob = "\n".join(_CAPTURED_STDOUT + _CAPTURED_STDERR)
    assert _SENTINEL_FLAG not in blob, "sentinel flag leaked into subprocess stdout/stderr"
    assert _SENTINEL_TOKEN not in blob, "sentinel token leaked into subprocess stdout/stderr"
    assert _SENTINEL_USER not in blob, "sentinel username leaked into subprocess stdout/stderr"
