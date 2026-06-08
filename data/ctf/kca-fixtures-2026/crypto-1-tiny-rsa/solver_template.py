"""solver_template.py — kca-fixtures-2026/crypto-1-tiny-rsa.

Skeleton for the M11-T005 solver loop. The math is wired (params load +
sha256 verify); the actual `factorint → d → decrypt → bytes` body is
left to T005 to fill in.

License: MIT.

Usage (T005):
    python solver_template.py
    Exit 0 iff sha256(recovered_flag) matches ./expected.sha256.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
PARAMS = HERE / "attachments" / "params.json"
EXPECTED = HERE / "expected.sha256"


def _expected_digest() -> str:
    line = EXPECTED.read_text(encoding="utf-8").strip().splitlines()[0]
    return line.split()[0]


def _verify(recovered: str) -> bool:
    return hashlib.sha256(recovered.encode("utf-8")).hexdigest() == _expected_digest()


def _load_params() -> tuple[int, int, int]:
    data = json.loads(PARAMS.read_text(encoding="utf-8"))
    return int(data["n"]), int(data["e"]), int(data["c"])


def solve() -> str:
    """Return the recovered flag string. T005 implementation.

    Intended path (see ../description.md):
      1. Load (n, e, c) from attachments/params.json.
      2. p, q = factor(n)   # sympy.factorint
      3. phi = (p-1)*(q-1); d = pow(e, -1, phi)
      4. m = pow(c, d, n)
      5. flag_bytes = m.to_bytes((m.bit_length()+7)//8, 'big')
      6. flag = flag_bytes.decode('utf-8')
    """
    from sympy import factorint

    n, e, c = _load_params()
    factors = factorint(n)
    primes = []
    for prime, mult in factors.items():
        primes.extend([int(prime)] * mult)
    if len(primes) != 2:
        raise RuntimeError(f"expected exactly 2 prime factors of n, got {len(primes)}")
    p, q = primes
    phi = (p - 1) * (q - 1)
    d = pow(e, -1, phi)
    m = pow(c, d, n)
    flag_bytes = m.to_bytes((m.bit_length() + 7) // 8, "big")
    return flag_bytes.decode("utf-8")


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
        print(f"flag verify FAIL (flag_length={len(flag)})", file=sys.stderr)
        return 1
    print("flag verify PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
