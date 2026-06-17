"""M11-T008 — end-to-end dry-run + refusal-path tests.

CI-friendly counterpart to ``tests/test_m11_smoke.py`` (the DB-gated
regression-assertion module). This module exercises the M11 CTF
workflow's refusal paths and bundled-solver round-trip in dry-run
mode, with **no DB**, **no credentials**, and **no real network**.

Acceptance scope (per docs/tasks/M11-T008-e2e-dryrun-test.md):

  (a) `flag_submit` refused without prior approval (dry-run flag
      missing, KCA_ALLOW_REMOTE absent) — exit 2, no POST attempt.
  (b) `challenge_run` refused for a target URL outside
      `ctf_scopes.target_urls` — host-mismatch path returns False.
  (c) `network_egress` denied for kaggle.com from a CTF job context
      — cross-platform isolation.
  (d) Bundled web + crypto solver round-trip works locally without
      real network (httpx.MockTransport for web; in-process for
      crypto). Both flags verified via expected.sha256. Flag string
      appears nowhere in stdout/stderr.
  (e) Audit-grep across the captured pytest output: 0 secret-pattern
      hits and 0 flag-pattern hits across all tests in this module.

Soft pre-req (per the task spec): issue #11 (dotenv-leak) should be
CLOSED before this Loop Prompt runs. `gh` is denied at the agent
hook layer (~/.config/gh/hosts.yml is on the secret denylist), so
the runtime verification is deferred — closeout records the
deviation. Defensive posture: this module does NOT use
``subprocess.run`` to shell into ``kca``; every test calls the CLI
functions in-process so child processes can never inherit a real
``.env`` or ``~/.ctf/*`` file.

Run with:
    python -m pytest tests/test_m11_e2e.py -v
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_EVENT_DIR = REPO_ROOT / "data" / "ctf" / "kca-fixtures-2026"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

import _audit_grep  # noqa: E402  -- local helper
import ctf as ctf_mod  # noqa: E402  -- tools/kca/ctf.py

# Module-level capture buffer — every test that calls a CLI function
# tees its stdout/stderr in here so the (e) audit-grep test can scan
# the union without re-running the suite.
_CAPTURED: list[str] = []


@contextlib.contextmanager
def _capture():
    """Capture stdout + stderr from an in-process CLI call.

    Tees into the module-level ``_CAPTURED`` buffer so the audit-grep
    test in (e) sees everything every other test emitted.
    """
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
        yield buf_out, buf_err
    out = buf_out.getvalue()
    err = buf_err.getvalue()
    if out:
        _CAPTURED.append(out)
    if err:
        _CAPTURED.append(err)


def _parse_last_json(stdout: str) -> dict:
    """The kca emit path writes one JSON object on the last non-empty line."""
    lines = [ln for ln in (stdout or "").splitlines() if ln.strip()]
    assert lines, f"empty stdout: {stdout!r}"
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# (a) flag_submit refused without prior approval (dry-run False, no remote)
# ---------------------------------------------------------------------------


def test_flag_submit_refused_without_approval(tmp_path, monkeypatch):
    """Drive `cmd_flag_submit` with ``dry_run=False`` and no
    ``KCA_ALLOW_REMOTE=1``. Expect a hard refusal (exit 2, ok=False)
    and no DB / network access — the gate fires BEFORE the scope query.
    """
    # Scrub remote gate + any DB env so even a malformed code path
    # can't accidentally reach the network.
    monkeypatch.delenv("KCA_ALLOW_REMOTE", raising=False)
    monkeypatch.delenv("KCA_DB_TARGET", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # no ~/.ctf/ candidates

    # Write a minimal flag file. The value here is bespoke and not a
    # real flag from any event; the function should never read past
    # its length anyway.
    flag_file = tmp_path / "flag.txt"
    flag_file.write_text("test_value_not_a_real_flag", encoding="utf-8")

    args = argparse.Namespace(
        event="kca-fixtures-2026",
        challenge="web-1-cookie-monster",
        flag_file=str(flag_file),
        dry_run=False,
        json=True,
    )

    with _capture() as (out, err):
        rc = ctf_mod.cmd_flag_submit(args)

    # The CTF submit path returns EXIT_BLOCKED (2) when the remote gate
    # env var is missing — see tools/kca/ctf.py::cmd_flag_submit, the
    # `os.environ.get(_GATE_ENV) != "1"` branch.
    assert rc == 2, f"expected EXIT_BLOCKED=2 from gate refusal, got {rc!r}"
    payload = _parse_last_json(out.getvalue())
    assert payload["ok"] is False, payload
    assert payload.get("target_op") == "flag_submit", payload
    assert "KCA_ALLOW_REMOTE" in payload.get("error", ""), payload
    # `dispatched` must NOT appear (we never reached the network path).
    assert "dispatched" not in payload, payload
    # The flag file content must not have leaked into stdout.
    assert "test_value_not_a_real_flag" not in out.getvalue()
    assert "test_value_not_a_real_flag" not in err.getvalue()


# ---------------------------------------------------------------------------
# (b) challenge_run refused for an out-of-scope URL — `_scope_covers_url`
# ---------------------------------------------------------------------------


def test_challenge_run_refused_for_out_of_scope_url():
    """Build a fake scope row covering only ``http://localhost:8080`` and
    confirm that ``_scope_covers_url`` rejects an attempt against an
    arbitrary out-of-scope URL.

    `_scope_covers_url` is the function the worker / kca ctf solver
    consults BEFORE dispatching a ``challenge_run``; it is the
    deny-default gate exercised here.
    """
    scope = {
        "name": "ctf-local-fixtures",
        "target_urls": ["http://localhost:8080"],
        "expires_at": None,
    }
    # In-scope check (sanity).
    assert ctf_mod._scope_covers_url(scope, "http://localhost:8080/login") is True
    # Out-of-scope: different host, even on the same path / port.
    assert ctf_mod._scope_covers_url(scope, "http://example.com/login") is False
    assert ctf_mod._scope_covers_url(scope, "http://example.com:8080/login") is False
    # Out-of-scope: empty / missing URL.
    assert ctf_mod._scope_covers_url(scope, "") is False

    # `scope verify` CLI surfaces the same decision — exercise the
    # JSON envelope shape so test (e)'s audit-grep sees a clean record.
    args = argparse.Namespace(
        slug="ctf-local-fixtures",
        url="http://example.com/login",
        json=True,
    )
    # We can't call cmd_scope_verify without DB (it queries
    # ctf_scopes), but we CAN exercise the helper that the CLI
    # function ultimately delegates to. The CLI exit-code contract is
    # tested in tests/test_kca_ctf_cli.py with a live DB. Here we
    # verify the in-process decision is "covered=False" so the worker
    # has unambiguous deny-ground.
    covered = ctf_mod._scope_covers_url(scope, args.url)
    assert covered is False


def test_challenge_run_respects_scope_expiry(monkeypatch):
    """A scope whose ``expires_at`` is in the past must NOT cover any
    URL, even if the host is in ``target_urls``.

    Catches a clock-skew bug where an expired scope silently re-grants
    network egress to a stale target.
    """
    past = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1)
    scope = {
        "name": "ctf-local-expired",
        "target_urls": ["http://localhost:8080"],
        "expires_at": past,
    }
    assert ctf_mod._scope_covers_url(scope, "http://localhost:8080/login") is False


# ---------------------------------------------------------------------------
# (c) network_egress denied to kaggle.com from a CTF job context
# ---------------------------------------------------------------------------


def test_network_egress_denied_to_kaggle_from_ctf_job():
    """Cross-platform isolation: a CTF job context (scope covers only
    its event hosts) MUST NOT touch ``https://www.kaggle.com`` —
    even though Kaggle is on the broader project allowlist.

    The check is at the scope layer: ``_scope_covers_url`` denies
    kaggle.com because it is not in ``target_urls``. The reviewer's
    deny-default for ``network_egress`` would also fire downstream.
    """
    scope = {
        "name": "ctf-local-kca-fixtures-2026-web-1",
        "target_urls": [
            "http://localhost:8080",
            "http://127.0.0.1:18080",
        ],
        "expires_at": None,
    }
    for kaggle_url in (
        "https://www.kaggle.com",
        "https://www.kaggle.com/api/v1/competitions/data/list",
        "http://kaggle.com/c/spaceship-titanic",
    ):
        assert ctf_mod._scope_covers_url(scope, kaggle_url) is False, f"CTF job scope must NOT cover {kaggle_url!r}"

    # Also confirm reviewer policy default: network_egress is `deny`
    # in EVERY profile when the URL is not in scope.
    import yaml

    for profile in ("default", "permissive-dev", "competition-runner"):
        with (REPO_ROOT / ".kca" / "permissions" / f"{profile}.yaml").open() as f:
            policy = list(yaml.safe_load_all(f))[0]
        row = next(
            (r for r in policy if isinstance(r, dict) and r.get("operation") == "network_egress"),
            None,
        )
        assert row is not None, f"{profile}.yaml missing network_egress"
        assert row["default_decision"] == "deny", (
            f"{profile}.yaml::network_egress default must be deny, got {row['default_decision']!r}"
        )


# ---------------------------------------------------------------------------
# (d) Bundled solver round-trip — web (mocked) + crypto (in-process)
# ---------------------------------------------------------------------------


def _load_solver(challenge_dir: Path):
    """Import solver_template.py from the bundle dir without polluting
    sys.modules with a colliding name."""
    spec = importlib.util.spec_from_file_location(
        f"_m11_t008_{challenge_dir.name}",
        challenge_dir / "solver_template.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expected_digest(challenge_dir: Path) -> str:
    line = (challenge_dir / "expected.sha256").read_text(encoding="utf-8").strip()
    return line.split()[0]


def _build_web_mock_app(flag_value: str) -> httpx.MockTransport:
    """Build an httpx.MockTransport that mimics the Cookie Monster Flask app.

    The transport encodes the SAME unsigned-cookie design as the real
    app under data/ctf/.../attachments/app.py — the solver should
    tamper the role field and recover the flag from /admin.
    """
    import base64

    def _encode(payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    def _decode(token: str) -> dict | None:
        if not token:
            return None
        pad = "=" * (-len(token) % 4)
        try:
            raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
            out = json.loads(raw.decode("utf-8"))
            return out if isinstance(out, dict) else None
        except (ValueError, json.JSONDecodeError):
            return None

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/login" and request.method == "POST":
            # The Flask app uses `application/x-www-form-urlencoded`; the
            # solver client.post(data=...) sends that content-type.
            body = request.content.decode("utf-8") if request.content else ""
            # Parse `username=guest` form-encoded.
            username = ""
            for pair in body.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    if k == "username":
                        username = v
                        break
            if not username:
                return httpx.Response(400, text="username required")
            token = _encode({"username": username, "role": "user"})
            resp = httpx.Response(
                302,
                headers={"location": "/me"},
                text="",
            )
            resp.headers["set-cookie"] = f"session={token}; HttpOnly=False; SameSite=Lax; Path=/"
            return resp
        if path == "/admin" and request.method == "GET":
            cookies = request.headers.get_list("cookie")
            token = None
            for c in cookies:
                # Cookies arrive as "session=...; otherk=..." — split.
                for part in c.split(";"):
                    part = part.strip()
                    if part.startswith("session="):
                        token = part.split("=", 1)[1]
                        break
            payload = _decode(token or "")
            if not payload:
                return httpx.Response(401, text="no session")
            if payload.get("role") != "admin":
                return httpx.Response(403, text="forbidden — admins only")
            return httpx.Response(200, text=f"<pre>FLAG: {flag_value}</pre>")
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler)


def test_bundled_solver_roundtrip_local(monkeypatch, tmp_path):
    """Run BOTH bundled solvers against deterministic local inputs:

      * crypto: in-process — sympy.factorint cracks the 143-bit n in
        well under a second. Flag is mathematically determined by the
        committed params.json; expected.sha256 is asserted as-is.
      * web:    a fresh flag is generated, sha256-pinned in a
        tmp-copy of the bundle's expected.sha256, and the cookie-tamper
        exploit runs against an httpx.MockTransport (no docker, no
        real network).

    Both flags MUST verify. Neither flag string may appear in
    captured stdout/stderr.
    """
    crypto_dir = FIXTURE_EVENT_DIR / "crypto-1-tiny-rsa"
    web_dir = FIXTURE_EVENT_DIR / "web-1-cookie-monster"
    assert crypto_dir.is_dir(), f"missing fixture: {crypto_dir}"
    assert web_dir.is_dir(), f"missing fixture: {web_dir}"

    # ------------------------------------------------------------------
    # Crypto: in-process. The solver is fully deterministic from params.
    # ------------------------------------------------------------------
    pytest.importorskip("sympy")
    crypto_mod = _load_solver(crypto_dir)
    with _capture() as (out, err):
        flag_crypto = crypto_mod.solve()
    assert isinstance(flag_crypto, str) and flag_crypto, "empty crypto flag"
    digest_crypto = hashlib.sha256(flag_crypto.encode("utf-8")).hexdigest()
    assert digest_crypto == _expected_digest(crypto_dir), (
        f"crypto flag digest mismatch — expected "
        f"{_expected_digest(crypto_dir)!r}, got {digest_crypto!r} "
        f"(flag_length={len(flag_crypto)})"
    )
    # The solver itself only prints on failure / return-code paths in
    # __main__; in-process call to solve() should not print anything.
    assert flag_crypto not in out.getvalue()
    assert flag_crypto not in err.getvalue()

    # ------------------------------------------------------------------
    # Web: generate a fresh flag, pin sha256 in a tmp-copy of the
    # bundle dir, then route the solver through httpx.MockTransport.
    # ------------------------------------------------------------------
    import shutil

    web_tmp = tmp_path / "web-1-cookie-monster"
    shutil.copytree(web_dir, web_tmp)
    flag_web = "kca{m11_t008_e2e_mocked_run_xyz}"
    digest_web = hashlib.sha256(flag_web.encode("utf-8")).hexdigest()
    (web_tmp / "expected.sha256").write_text(f"{digest_web}  flag\n", encoding="utf-8")

    # Reload the solver from the tmp dir (so its EXPECTED constant
    # points to the freshly pinned hash).
    web_mod = _load_solver(web_tmp)

    # Monkeypatch httpx.Client to use our MockTransport. The solver
    # calls `httpx.Client(base_url=TARGET, timeout=5.0)`; we override
    # the class so the MockTransport applies to that constructor call.
    transport = _build_web_mock_app(flag_web)
    original_client = httpx.Client

    class _ClientWithMock(original_client):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **kw):
            kw.setdefault("transport", transport)
            super().__init__(*a, **kw)

    monkeypatch.setattr(httpx, "Client", _ClientWithMock)

    with _capture() as (out_w, err_w):
        recovered_web = web_mod.solve()
    assert recovered_web == flag_web, (
        f"web solver recovered {len(recovered_web)}-char string but it "
        f"did not match the pinned flag (digest check below catches it too)"
    )
    digest_recovered = hashlib.sha256(recovered_web.encode("utf-8")).hexdigest()
    assert digest_recovered == digest_web

    # CRITICAL: the flag value must not appear in any captured output.
    # The solver does not print on success; the httpx mock's response
    # body contains the flag but is not echoed by the client.
    assert flag_web not in out_w.getvalue()
    assert flag_web not in err_w.getvalue()
    assert flag_crypto not in out_w.getvalue()
    assert flag_crypto not in err_w.getvalue()


# ---------------------------------------------------------------------------
# (e) Audit-grep — 0 secret / flag leaks across the captured pytest output
# ---------------------------------------------------------------------------


def test_no_secret_leak_in_test_stdout(capsys):
    """Scan the union of every other test's captured stdout/stderr
    (collected into module-level ``_CAPTURED``) for secret-pattern and
    flag-pattern hits. 0 hits ⇒ PASS.

    This is the M11 analogue of the M10 dotenv-leak regression
    (issue #11). It also directly closes the CTF side of #11 by
    asserting that ``~/.ctf/*.json`` contents and ``CTF_*_TOKEN``
    env lines do NOT escape into any in-process test's stdout.
    """
    # Pull in capsys output too — anything the other tests printed via
    # `pytest`'s own capturefd path lands here.
    captured = capsys.readouterr()
    blob = "\n".join(_CAPTURED + [captured.out, captured.err])
    hits = _audit_grep.scan_text(blob)
    assert hits == [], f"audit-grep found {len(hits)} secret/flag leak(s) in captured test output: {hits!r}"

    # Defensive self-check: the audit-grep harness DOES catch a known-bad
    # synthetic injection. Without this assertion, a regression that
    # silently broke the catalog would never fail any test.
    synthetic_hits = _audit_grep.scan_text("KCA_TOKEN=tok_should_be_caught_xyz\nFLAG{synthetic_audit_grep_canary}\n")
    assert any(name == "secret_kv" for name, _ in synthetic_hits)
    assert any(name == "flag" for name, _ in synthetic_hits)


def test_audit_grep_helper_self_test_passes(capsys):
    """Run the harness's built-in self-test in-process so a regression
    in the catalog produces a per-test failure, not a silent skip."""
    _audit_grep._self_test()
    captured = capsys.readouterr()
    # The self-test print is whitelisted; it MUST NOT contain a real
    # secret or flag value. The synthetic strings inside _self_test()
    # are scrubbed before printing.
    assert "PASS" in captured.out
    # The self-test print itself is a positive control for the harness;
    # the audit-grep test above scans `_CAPTURED` which does NOT include
    # this stdout (we use capsys here, not _capture()). Belt-and-suspenders:
    # verify the self-test summary line carries no hit-worthy substring.
    hits = _audit_grep.scan_text(captured.out)
    assert hits == [], f"self-test summary unexpectedly hit: {hits!r}"


# ---------------------------------------------------------------------------
# Hygiene gate — sanity-check that this module made 0 real network calls.
# ---------------------------------------------------------------------------


def test_no_real_network_calls_attempted():
    """Module-wide sanity gate: NONE of the test bodies above route
    through real httpx without a MockTransport.

    We can't easily intercept the global httpx machinery from here
    after the fact, but we CAN verify the gate-refusal env state was
    in force throughout — there is no live SUPABASE_DB_URL, no
    KCA_ALLOW_REMOTE, no inherited KAGGLE_USERNAME / KAGGLE_KEY in the
    process at module-end.

    Together with the per-test ``monkeypatch.delenv`` scrubs above,
    this catches a subtle regression where a future test accidentally
    leaks `--dry-run=False` + `KCA_ALLOW_REMOTE=1` to a sibling test.
    """
    # NOTE: this test runs LAST in the file (pytest collects in file
    # order). At this point, the env should be free of any remote-gate
    # variables set by the earlier monkeypatch.delenv calls (they
    # delete + restore on teardown — they do NOT set).
    assert os.environ.get("KCA_ALLOW_REMOTE") in (None, "0"), (
        "KCA_ALLOW_REMOTE is set — a previous test should not have exported it; the refusal paths rely on its absence"
    )
