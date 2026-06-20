"""Validation harness for lb6-v1 (CPU; LB6's full-train-as-validation + DUMMY probing).

Implements the LB6 validation design (method_summary.md §4):
  * **full-train-as-validation** discipline (train on distribution-matched synthetic,
    validate on the real labelled set) — here the offline labelled set is the demo corpus;
  * **per-domain DUMMY-masking attribution** (`dummy_probe.attribute`) — the B8 fix;
  * **per-domain solved counts** (LB6 `-0/-1/-2`, 0.01 LB ~ 3 problems);
  * **perfect-trace-rate** via the official extractor;
  * adapter **rank<=32** + zip-structure preflight; **fail-fast** one-example check.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import defaultdict

import corpus
import dummy_probe
import package_submission as pkg
import scorer

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
from official_metric import extract_final_answer, verify  # noqa: E402


def perfect_trace_rate(records):
    ok = defaultdict(int)
    tot = defaultdict(int)
    for r in records:
        tot[r["category"]] += 1
        if verify(r["answer"], extract_final_answer(r["trace"])):
            ok[r["category"]] += 1
    return {c: (ok[c], tot[c]) for c in tot}


def preflight_adapter(max_rank=32):
    details = {}
    with tempfile.TemporaryDirectory() as d:
        adir = os.path.join(d, "adapter")
        pkg.make_dummy_adapter(adir, rank=max_rank)
        out = os.path.join(d, "submission.zip")
        pkg.build_submission_zip(adir, out)
        import json
        import zipfile

        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            details["root_ok"] = all("/" not in n for n in names) and set(pkg.REQUIRED_FILES).issubset(names)
            cfg = json.loads(z.read("adapter_config.json"))
            details["rank"] = cfg.get("r")
            details["rank_ok"] = cfg.get("r", 999) <= max_rank
            details["size_ok"] = os.path.getsize(out) > 0
    ok = details["root_ok"] and details["rank_ok"] and details["size_ok"]
    return ok, details


def self_check():
    print("== lb6-v1 validation self-check (CPU) ==")
    recs = corpus.build_demo_corpus(150, seed=0)
    cats = sorted({r["category"] for r in recs})
    print(f"[1] full-train-as-validation set: {len(recs)} records across {cats}")

    # per-domain DUMMY-masking attribution (the signature LB6 lever / B8 fix)
    attr = dummy_probe.attribute(recs)
    print("[2] DUMMY-masking per-domain attribution (isolated signal):")
    for d, (s, t) in sorted(attr.items()):
        print(f"      {d:11s} {s}/{t} = {100 * s / t:5.1f}%")
    # masking actually emits DUMMY for non-target rows
    masked = dummy_probe.mask_for_domain(recs, cats[0])
    n_dummy = sum(1 for r in masked if r.get("masked"))
    assert n_dummy == len(recs) - sum(1 for r in recs if r["category"] == cats[0])
    print(f"      masking OK: {n_dummy} non-target rows -> DUMMY (clean per-domain signal)")

    ptr = perfect_trace_rate(recs)
    cov = scorer.category_coverage(recs)
    print("[3] perfect-trace-rate / within-budget:")
    for c in sorted(ptr):
        o, t = ptr[c]
        s, tt, med = cov[c]
        print(
            f"      {c:11s} ptr {o}/{t}={100 * o / t:5.1f}%  within-budget {s}/{tt}={100 * s / tt:5.1f}% med_tok={med:.0f}"
        )

    ok, det = preflight_adapter()
    print(
        f"[4] adapter preflight: rank={det['rank']} (<=32:{det['rank_ok']}) root_ok={det['root_ok']} -> {'PASS' if ok else 'FAIL'}"
    )
    assert ok

    r0 = recs[0]
    assert verify(r0["answer"], extract_final_answer(r0["trace"])), "fail-fast extraction broke"
    print("[5] fail-fast single-example boxed extraction: OK")
    print("== self-check PASSED ==")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", dest="selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        raise SystemExit(self_check())
    ap.print_help()


if __name__ == "__main__":
    main()
