"""M11-T005: drive the local solver loop against both bundled challenges.

Operates against the frozen `kca-fixtures-2026` event (T004 bundles):

  - web-1-cookie-monster (docker-compose, Flask, unsigned-cookie tamper)
  - crypto-1-tiny-rsa    (in-process, 143-bit RSA factor + decrypt)

Sequence per challenge:

  1. Read `challenge.yaml` + `description.md` + attachments. Log the
     category strategy.
  2. For web: generate a fresh flag, sha256 it, write it into the
     bundle's `expected.sha256` (the README documents this contract —
     the harness owns the flag value, the bundle only holds the hash).
     Export `KCA_FIXTURE_FLAG`, `docker compose up -d`, wait for the
     service to come up, run the cookie-tamper exploit via
     `solver_template.py::solve`, verify the recovered flag against
     `expected.sha256`. Then `docker compose down -v`.
     For crypto: in-process `solve()` (already deterministic from the
     committed params; no flag generation, no docker).
  3. Compute `flag_length` and a sha256 of the flag (used ONLY to grep
     audit logs for accidental disclosure — never persisted).
  4. `kca run init` + `kca run record-metric --key flag_length` for the
     experiment_runs row.
  5. `record_attempt(accepted=True, flag_length=<len>, response_excerpt
     '<scrubbed>')` into `ctf_attempts`.
  6. `kca ctf solver run --dry-run` for the gate-path side-effect
     record (T006 owns the gate-ON path).
  7. Drop the flag from memory.

Hygiene invariants:

  - The flag string never enters a log, a DB column, or a JSON payload
    that we control.
  - `expected.sha256` is rewritten for the web challenge; this is the
    documented "deterministic per harness invocation" contract.
  - The crypto challenge's `expected.sha256` is NOT touched (the flag
    is mathematically determined by the committed `params.json`).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
import string
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kca"))

from src.db import ctf as ctf_db  # noqa: E402

EVENT_SLUG = "kca-fixtures-2026"
EVENT_DIR = REPO_ROOT / "data" / "ctf" / EVENT_SLUG
WEB_SLUG = "web-1-cookie-monster"
CRYPTO_SLUG = "crypto-1-tiny-rsa"

# Loopback host port from docker-compose.yml — see description.md.
WEB_BASE_URL = "http://127.0.0.1:18080"


def _log(msg: str) -> None:
    print(f"[m11-t005] {msg}", flush=True)


def _load_solver_module(challenge_dir: Path):
    spec = importlib.util.spec_from_file_location(
        f"_m11_t005_{challenge_dir.name}",
        challenge_dir / "solver_template.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _gen_flag() -> str:
    # 16 chars of base32-ish material inside kca{...}. Long enough to
    # not collide with any committed string, short enough to fit in the
    # cookie / response without overflow.
    alphabet = string.ascii_lowercase + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(16))
    return f"kca{{{body}}}"


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _write_expected_sha256(path: Path, flag: str) -> None:
    """Write the sha256-style line. NEVER includes the flag value."""
    digest = _sha256(flag)
    path.write_text(f"{digest}  flag\n", encoding="utf-8")


def _wait_for_http(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.5)
    raise RuntimeError(f"service at {url} did not come up: {last_err!r}")


def _docker_compose(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    compose_file = EVENT_DIR / WEB_SLUG / "docker-compose.yml"
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    # `compose down` still interpolates the FLAG env even though the value
    # is irrelevant for teardown — supply a placeholder so interpolation
    # doesn't crash. The placeholder is non-flag-shaped.
    env.setdefault("KCA_FIXTURE_FLAG", "x")
    return subprocess.run(
        ["docker", "compose", "-f", str(compose_file), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _kca(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "kca" / "kca.py"), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _ensure_competition() -> str:
    # ctf-<event-slug> mirrors the kca-run convention noted in the task spec.
    comp_slug = f"ctf-{EVENT_SLUG}"
    res = _kca(
        "run",
        "init",
        "--competition",
        comp_slug,
        "--run-id",
        f"_warmup_{int(time.time())}",
    )
    # The init creates a competition row if missing. We don't need the warmup run.
    if res.returncode != 0:
        raise RuntimeError(f"run init warmup failed: {res.stderr or res.stdout}")
    return comp_slug


def _record_run_and_attempt(
    challenge_slug: str,
    challenge_id: str,
    flag_length: int,
    excerpt: str,
    comp_slug: str,
) -> tuple[str, str]:
    # 1. kca run init
    run_id = f"{challenge_slug}-{int(time.time())}"
    res = _kca(
        "run",
        "init",
        "--competition",
        comp_slug,
        "--run-id",
        run_id,
        "--hypothesis",
        f"M11-T005 local solve of {challenge_slug}",
    )
    if res.returncode != 0:
        raise RuntimeError(f"kca run init failed: {res.stderr or res.stdout}")
    init_payload = json.loads(res.stdout.strip().splitlines()[-1])
    experiment_run_id = init_payload["experiment_run_id"]

    # 2. kca run record-metric
    res = _kca(
        "run",
        "record-metric",
        "--experiment-run-id",
        experiment_run_id,
        "--key",
        "flag_length",
        "--value",
        str(flag_length),
    )
    if res.returncode != 0:
        raise RuntimeError(f"kca run record-metric failed: {res.stderr or res.stdout}")

    # 3. record_attempt via src/db/ctf.py
    attempt_id = ctf_db.record_attempt(
        challenge_id=challenge_id,
        accepted=True,
        http_status=None,
        flag_length=flag_length,
        response_excerpt=excerpt,
        run_id=experiment_run_id,
    )

    # 4. kca ctf solver run --dry-run (gate-path side-effect record)
    res = _kca(
        "ctf",
        "solver",
        "run",
        "--event",
        EVENT_SLUG,
        "--challenge",
        challenge_slug,
        "--dry-run",
    )
    if res.returncode != 0:
        raise RuntimeError(f"kca ctf solver run --dry-run failed: {res.stderr or res.stdout}")

    return experiment_run_id, attempt_id


def solve_crypto() -> dict:
    challenge_dir = EVENT_DIR / CRYPTO_SLUG
    _log(f"=== {CRYPTO_SLUG} ===")
    _log("strategy: crypto / 143-bit RSA -- sympy.factorint(n), d=e^-1 mod phi, m=c^d, decode")

    mod = _load_solver_module(challenge_dir)
    flag = mod.solve()
    verified = mod._verify(flag)
    if not verified:
        raise RuntimeError(f"{CRYPTO_SLUG}: sha256 verify FAILED (flag_length={len(flag)})")
    _log(f"{CRYPTO_SLUG}: sha256 verify PASS, flag_length={len(flag)}")
    return {"flag": flag, "flag_length": len(flag), "flag_sha256": _sha256(flag)}


def solve_web() -> dict:
    challenge_dir = EVENT_DIR / WEB_SLUG
    _log(f"=== {WEB_SLUG} ===")
    _log(
        "strategy: web / Flask /admin gated on role=admin in a base64-JSON unsigned session cookie. "
        "POST /login as guest, decode cookie, flip role to admin, re-encode, GET /admin, parse FLAG."
    )

    # Generate fresh flag, pin expected.sha256, supply via env to compose.
    flag = _gen_flag()
    expected_path = challenge_dir / "expected.sha256"
    _write_expected_sha256(expected_path, flag)

    env_extra = {"KCA_FIXTURE_FLAG": flag}
    # docker compose up -d
    up = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(challenge_dir / "docker-compose.yml"),
            "up",
            "-d",
            "--build",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, **env_extra},
    )
    if up.returncode != 0:
        raise RuntimeError(
            f"docker compose up failed: returncode={up.returncode} "
            f"stderr=(omitted to avoid env-line FLAG echo) stdout_tail={up.stdout[-200:]!r}"
        )
    try:
        _wait_for_http(WEB_BASE_URL + "/")
        mod = _load_solver_module(challenge_dir)
        recovered = mod.solve()
        verified = mod._verify(recovered)
        if not verified:
            raise RuntimeError(f"{WEB_SLUG}: sha256 verify FAILED (flag_length={len(recovered)})")
        _log(f"{WEB_SLUG}: sha256 verify PASS, flag_length={len(recovered)}")
        return {
            "flag": recovered,
            "flag_length": len(recovered),
            "flag_sha256": _sha256(recovered),
        }
    finally:
        down = _docker_compose("down", "-v")
        if down.returncode != 0:
            _log(f"WARN docker compose down rc={down.returncode}: {down.stderr[-200:]}")
        else:
            _log(f"{WEB_SLUG}: docker compose down -v ok")


def main() -> int:
    if not os.environ.get("SUPABASE_DB_URL"):
        print("SUPABASE_DB_URL not set; refusing to record attempts", file=sys.stderr)
        return 2

    # 1. SOLVE both — keep flag strings in local scope only.
    crypto_res = solve_crypto()
    web_res = solve_web()

    # 2. LOOKUP DB ids
    crypto_row = ctf_db.get_challenge(EVENT_SLUG, CRYPTO_SLUG)
    web_row = ctf_db.get_challenge(EVENT_SLUG, WEB_SLUG)
    if not crypto_row or not web_row:
        raise RuntimeError("ctf_challenges rows missing for fixtures")

    comp_slug = _ensure_competition()

    # 3. RECORD. Scrubbed excerpts — NO flag string, NO format-regex match.
    crypto_excerpt = "solver: sympy.factorint(n)->{p,q}; d=pow(e,-1,phi(n)); m=pow(c,d,n); bytes->utf8; sha256 ok"
    web_excerpt = (
        "solver: POST /login guest -> base64-JSON cookie -> flip role:user->admin "
        "-> GET /admin 200 -> regex FLAG marker -> sha256 ok"
    )

    crypto_run, crypto_att = _record_run_and_attempt(
        CRYPTO_SLUG,
        crypto_row["id"],
        crypto_res["flag_length"],
        crypto_excerpt,
        comp_slug,
    )
    web_run, web_att = _record_run_and_attempt(WEB_SLUG, web_row["id"], web_res["flag_length"], web_excerpt, comp_slug)

    # 4. Emit summary with NO flag, only sha256 (for audit-grep against logs).
    summary = {
        "ok": True,
        "event": EVENT_SLUG,
        "challenges": {
            CRYPTO_SLUG: {
                "flag_length": crypto_res["flag_length"],
                "flag_sha256": crypto_res["flag_sha256"],
                "experiment_run_id": crypto_run,
                "ctf_attempt_id": crypto_att,
            },
            WEB_SLUG: {
                "flag_length": web_res["flag_length"],
                "flag_sha256": web_res["flag_sha256"],
                "experiment_run_id": web_run,
                "ctf_attempt_id": web_att,
            },
        },
    }
    print(json.dumps(summary, indent=2))

    # 5. Explicitly drop flag strings.
    del crypto_res, web_res
    return 0


if __name__ == "__main__":
    sys.exit(main())
