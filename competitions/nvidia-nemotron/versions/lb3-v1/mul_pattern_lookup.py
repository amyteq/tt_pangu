"""Multiplication-pattern lookup table for the LB3 CSP cryptarithm solver (lb3-v1).

LB3 / 3rd place builds a **multiplication-pattern lookup** that, for a given
multiplication *shape signature* (operand/product digit lengths), enumerates the
integer rows producing that shape, capped at a small number of rows per signature
(`row_cap`, default 48 — the writeup's order of magnitude). The CSP solver
(`cryptarithm_csp.py`) uses the table to:

  * emit per-symbol candidate digit **domains** from a multiplication example
    (`<RECALL_DOMAINS>` in the trace), and
  * list the candidate integer rows for the signature (`<RECALL_ROWS>`),

which it then **intersects/joins** across multiple multiplication examples to pin
the symbol -> digit bijection before any backtracking.

This module is pure CPU. Build the table with :func:`build_lookup`; query
candidate digit domains for a positional pattern with
:meth:`MulLookup.domains_for`.

Design note: the *signature* deliberately keys on digit lengths only. The
per-example symbol-equality structure (same symbol => same digit) is applied by
the CSP layer, not baked into the table, so one table serves every symbol
alphabet (the table is generator-faithful, the bijection is per problem).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


def mul_signature(a: int, b: int) -> tuple[int, int, int]:
    """Shape signature of a multiplication: (len a, len b, len a*b)."""
    return (len(str(a)), len(str(b)), len(str(a * b)))


@dataclass
class MulLookup:
    """signature -> capped list of (a, b, product) integer rows."""

    row_cap: int = 48
    max_operand: int = 99  # 2-digit operands (LB3 cryptarithm examples are small)
    table: dict[tuple[int, int, int], list[tuple[int, int, int]]] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    def rows_for(self, sig: tuple[int, int, int]) -> list[tuple[int, int, int]]:
        return self.table.get(sig, [])

    def domains_for(self, sig: tuple[int, int, int]):
        """Per-position candidate digit sets for (a-digits, b-digits, p-digits).

        Returns (a_digits, b_digits, p_digits) where each is a list (one entry per
        digit position, most-significant first) of the **set of digits** observed
        at that position across all rows of the signature. This is the
        `<RECALL_DOMAINS>` payload the trace cites before intersection.
        """
        rows = self.rows_for(sig)
        la, lb, lp = sig
        a_dom = [set() for _ in range(la)]
        b_dom = [set() for _ in range(lb)]
        p_dom = [set() for _ in range(lp)]
        for a, b, p in rows:
            for i, ch in enumerate(str(a)):
                a_dom[i].add(int(ch))
            for i, ch in enumerate(str(b)):
                b_dom[i].add(int(ch))
            for i, ch in enumerate(str(p)):
                p_dom[i].add(int(ch))
        return a_dom, b_dom, p_dom

    def signatures(self):
        return sorted(self.table)


def build_lookup(row_cap: int = 48, max_operand: int = 99, kinds=("simple", "plus1", "minus1")) -> MulLookup:
    """Enumerate a*b (and the LB3 ``a*b ± 1`` variants) into a capped lookup table.

    ``kinds``: which product families to index.
      * ``simple``  -> product = a*b
      * ``plus1``   -> product = a*b + 1   (LB3 "a*b+1" mul family)
      * ``minus1``  -> product = a*b - 1

    Rows are inserted deterministically (ascending a, then b) and the per-signature
    list is capped at ``row_cap`` so the recalled table stays small/memorizable.
    """
    lut = MulLookup(row_cap=row_cap, max_operand=max_operand)
    by_sig: dict[tuple[int, int, int], list[tuple[int, int, int]]] = defaultdict(list)
    for a in range(1, max_operand + 1):
        for b in range(1, max_operand + 1):
            base = a * b
            for kind in kinds:
                p = base + (1 if kind == "plus1" else -1 if kind == "minus1" else 0)
                if p <= 0:
                    continue
                sig = (len(str(a)), len(str(b)), len(str(p)))
                bucket = by_sig[sig]
                if len(bucket) < row_cap and (a, b, p) not in bucket:
                    bucket.append((a, b, p))
    lut.table = dict(by_sig)
    return lut


if __name__ == "__main__":
    lut = build_lookup()
    sigs = lut.signatures()
    total = sum(len(v) for v in lut.table.values())
    print(f"mul-pattern lookup: {len(sigs)} signatures, {total} rows (row_cap={lut.row_cap})")
    for sig in sigs[:8]:
        rows = lut.rows_for(sig)
        print(f"  sig={sig}: {len(rows)} rows  e.g. {rows[:3]}")
    a_dom, b_dom, p_dom = lut.domains_for((2, 1, 2))
    print(f"  domains for (2,1,2): a={[sorted(s) for s in a_dom]} b={[sorted(s) for s in b_dom]}")
    assert all(len(v) <= lut.row_cap for v in lut.table.values()), "row cap violated"
    print("OK: row cap respected")
