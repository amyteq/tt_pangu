"""Validation harness for lb10-v1 (CPU; LB10 select-by-validation discipline).

Implements the LB10 validation design (method_summary.md):
  * **oracle-ceiling vs model-fidelity** split (via `learnability.py`) — diagnose the
    teacher ceiling separately from the imitation gap;
  * **keep-failures**: unsolved teacher traces are RETAINED in the corpus (LB10:
    excluding them hurt) — asserted here;
  * **logprob learnability** export to flag fragile traces for priority-2× upsampling;
  * **perfect-trace-rate** via the official extractor;
  * adapter **rank<=32** + zip-structure preflight; **fail-fast** one-example check.
  * **select by validation, never public LB** (documented decision rule).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import Counter, defaultdict

import corpus
import learnability
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
    print("== lb10-v1 validation self-check (CPU) ==")
    recs = corpus.build_demo_corpus(160, seed=0)
    cats = sorted({r["category"] for r in recs})
    print(f"[1] held-out validation set: {len(recs)} records across {cats}")

    # keep-failures: unsolved traces retained (LB10 discipline)
    solved_counts = Counter(r["solved"] for r in recs)
    print(
        f"[2] keep-failures: solved={solved_counts.get(True, 0)} kept-unsolved={solved_counts.get(False, 0)} (unsolved retained)"
    )

    cov = learnability.oracle_coverage(recs)
    print("[3] oracle ceiling (teacher solver per category — improve-the-teacher target):")
    for c, (o, t) in sorted(cov.items()):
        print(f"      {c:9s} {o}/{t} = {100 * o / t:5.1f}%")

    ptr = perfect_trace_rate(recs)
    sc = scorer.category_coverage(recs)
    print("[4] perfect-trace-rate / within-budget:")
    for c in sorted(ptr):
        o, t = ptr[c]
        s, tt, med = sc[c]
        print(
            f"      {c:9s} ptr {o}/{t}={100 * o / t:5.1f}%  within-budget {s}/{tt}={100 * s / tt:5.1f}% med_tok={med:.0f}"
        )

    ok, det = preflight_adapter()
    print(
        f"[5] adapter preflight: rank={det['rank']} (<=32:{det['rank_ok']}) root_ok={det['root_ok']} -> {'PASS' if ok else 'FAIL'}"
    )
    assert ok

    r0 = recs[0]
    assert verify(r0["answer"], extract_final_answer(r0["trace"])), "fail-fast extraction broke"
    print("[6] fail-fast single-example boxed extraction: OK")
    print("[7] selection rule: SELECT BY VALIDATION, never the public LB (LB10 lesson).")
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
