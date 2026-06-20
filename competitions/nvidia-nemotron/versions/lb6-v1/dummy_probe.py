"""Per-domain DUMMY-masking attribution probe (lb6-v1) — the signature LB6 lever.

Reproduces LB6's per-domain LB probing (method_summary.md §4): to read a *single*
domain's signal, train/eval the model to emit the target domain's real CoT but a
fixed **DUMMY** answer for every other domain:

    I will ignore this problem
    \\boxed{DUMMY}

On the live competition LB6 read this off the public LB; the competition is over, so
this harness runs the probe **offline** against a local labelled set — directly
addressing our recurring **B8** ("single-category gain ≠ total gain") by isolating
per-domain attribution. LB6 inferred test = 500 (250 public / 250 private), so
**0.01 ≈ 3 problems** (their `-0/-1/-2` notation).

`mask_for_domain` builds the DUMMY-masked dataset for one target; `attribute`
computes the per-domain solved fraction (DUMMY rows are intentionally not credited —
they carry no signal). Pure CPU.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

DUMMY_ANSWER = "I will ignore this problem\n\\boxed{DUMMY}"
PROBLEMS_PER_001 = 3  # 0.01 LB ~ 3 problems (test=500, LB6 -0/-1/-2 notation)


def mask_for_domain(records, target_domain):
    """Return a copy where every NON-target row's trace is the DUMMY output."""
    out = []
    for r in records:
        if r["category"] == target_domain:
            out.append(dict(r))
        else:
            out.append({**r, "trace": DUMMY_ANSWER, "masked": True})
    return out


def _solved(record):
    """Offline 'LB' check: does the trace's boxed answer match the gold answer?"""
    import os
    import sys

    _HERE = os.path.dirname(os.path.abspath(__file__))
    if os.path.join(_HERE, "..", "..", "eval") not in sys.path:
        sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
    from official_metric import extract_final_answer, verify

    return verify(record["answer"], extract_final_answer(record["trace"]))


def attribute(records):
    """Per-domain solved fraction via DUMMY masking (one probe per domain).

    For each domain, mask all others to DUMMY, then score ONLY the target rows ->
    a clean per-domain signal uncontaminated by the other domains.
    """
    domains = sorted({r["category"] for r in records})
    result = {}
    for d in domains:
        masked = mask_for_domain(records, d)
        target_rows = [r for r in masked if r["category"] == d]
        solved = sum(_solved(r) for r in target_rows)
        result[d] = (solved, len(target_rows))
    return result


def lb_delta_problems(frac_a, frac_b, n_test=500):
    """Convert a CV-fraction delta to LB6-style problem counts (-0/-1/-2)."""
    return round((frac_a - frac_b) * n_test)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    args = ap.parse_args()
    import corpus

    recs = corpus.build_demo_corpus(args.n, seed=0)
    by_dom = defaultdict(int)
    for r in recs:
        by_dom[r["category"]] += 1
    print(f"DUMMY-masking per-domain attribution probe (offline; domains={dict(by_dom)}):")
    attr = attribute(recs)
    for d, (s, t) in sorted(attr.items()):
        print(f"  domain={d:11s} isolated solved {s}/{t} = {100 * s / t:5.1f}%")
    # show the masking produces a clean signal: masked rows emit DUMMY (not scored)
    masked = mask_for_domain(recs, sorted(by_dom)[0])
    dummies = sum(1 for r in masked if r.get("masked"))
    print(f"  masking check: {dummies}/{len(masked)} non-target rows emit DUMMY ('{DUMMY_ANSWER.splitlines()[0]}...')")
    print(f"  LB units: 0.01 ~ {PROBLEMS_PER_001} problems (test=500); use for -0/-1/-2 per-domain attribution")


if __name__ == "__main__":
    main()
