"""Cryptarithm signature catalog (lb1-v1).

Re-derives the 1st-place "signature catalog": enumerate the two 2-digit operands
(00..99 x 00..99), apply each of the 22 non-join rules, normalise the digit
sequence ``left + right + output`` by first occurrence into A,B,C,... (the
*signature*), and record per signature the candidate rows
``(rule, slot_digit_string)`` plus a candidate count.

Writeup target: **4205 unique signatures** (a sanity check; the writeup is prose,
not released code, so the actual count is reported and any delta documented —
never forced). The published ``ABCCCDD`` row is reproduced as a unit check:
add=1, flip_add=8, flip_add+1=6, total candidates 15.

Build (CPU, seconds):
    python signature_catalog.py            # prints count + ABCCCDD check
    python signature_catalog.py --dump out.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from rules24 import NON_JOIN_RULES, apply_rule, digit_slots, signature_of


def two_digit_strings():
    return [f"{i:02d}" for i in range(100)]


def build_catalog():
    """Return {signature: {"count": int, "rows": [(rule, slot_digit_string), ...]}}.

    ``count`` is the total number of (rule, operand-pair) candidates producing the
    signature (matches the writeup's "candidate count").
    """
    cat = defaultdict(lambda: {"count": 0, "rows": []})
    operands = two_digit_strings()
    for sA in operands:
        for sB in operands:
            for rule in NON_JOIN_RULES:
                out = apply_rule(rule, sA, sB)
                if out is None:
                    continue
                sig = signature_of(sA, sB, out)
                slots = digit_slots(sA, sB, out)
                entry = cat[sig]
                entry["count"] += 1
                entry["rows"].append((rule, slots))
    return dict(cat)


def candidate_count(catalog, signature):
    return catalog.get(signature, {}).get("count", 0)


def rows_by_rule(catalog, signature):
    by = defaultdict(list)
    for rule, slots in catalog.get(signature, {}).get("rows", []):
        by[rule].append(slots)
    return by


def _summary(catalog):
    total_sigs = len(catalog)
    total_rows = sum(e["count"] for e in catalog.values())
    return total_sigs, total_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", help="write the full catalog to JSON")
    ap.add_argument("--target", type=int, default=4205, help="writeup sanity-check count")
    args = ap.parse_args()

    cat = build_catalog()
    total_sigs, total_rows = _summary(cat)
    print(f"unique signatures : {total_sigs}  (writeup target {args.target})")
    print(f"total candidate rows: {total_rows}")
    delta = total_sigs - args.target
    print(f"delta vs target    : {delta:+d}")

    # Published unit check: ABCCCDD
    sig = "ABCCCDD"
    by = rows_by_rule(cat, sig)
    cc = candidate_count(cat, sig)
    print(f"\n[unit check] signature {sig}: candidate count = {cc} (writeup: 15)")
    for rule in ("add", "flip_add", "flip_add+1"):
        slots = sorted(set(by.get(rule, [])))
        print(f"   {rule:12s} count={len(slots):3d}  e.g. {slots[:3]}")

    if args.dump:
        with open(args.dump, "w") as f:
            json.dump({k: v for k, v in cat.items()}, f)
        print(f"\nwrote catalog -> {args.dump}")


if __name__ == "__main__":
    main()
