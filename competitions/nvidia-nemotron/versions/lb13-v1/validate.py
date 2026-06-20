"""Validation harness for lb13-v1 (CPU).

Implements the LB13 validation design (method_summary.md §4): the optimization target
is **per-category teacher-oracle coverage** + a held-out official-metric check, plus
the LB13 data-discipline checks:
  * **keep-failures + 1:1 rebalance** (via `rebalance.py`) does not collapse the corpus;
  * **robust aggregation** (op valid if it matches >=1 example) survives transcription
    noise that strict all-match would reject;
  * **perfect-trace-rate** via the official extractor;
  * adapter **rank<=32** + zip-structure preflight; **fail-fast** one-example check.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections import Counter, defaultdict

import argparse

import corpus
import equation_solver as eqs
import package_submission as pkg
import rebalance
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
    print("== lb13-v1 validation self-check (CPU) ==")
    recs = corpus.build_demo_corpus(160, seed=0)
    print(f"[1] corpus: {len(recs)} records {dict(Counter(r['category'] for r in recs))}")

    # teacher-oracle coverage (clean) per category, from the solvers directly
    eq_clean = eqs._measure(200, deduce=True, noise=False, robust=True)
    print(f"[2] equation teacher oracle (deduce, clean): {eq_clean}/200 = {100 * eq_clean / 200:.1f}%  (writeup 95.3%)")

    # robust aggregation beats strict under transcription noise (the LB13 lever)
    rob = eqs._measure(200, deduce=True, noise=True, robust=True)
    strict = eqs._measure(200, deduce=True, noise=True, robust=False)
    print(f"[3] robust vs strict under noise: robust {100 * rob / 200:.1f}% vs strict {100 * strict / 200:.1f}%")
    assert rob > strict, "robust aggregation must beat strict under noise"

    # keep-failures 1:1 rebalance does not collapse the corpus
    bal = rebalance.rebalance_one_to_one(recs)
    bc = sum(r["correct"] for r in bal)
    print(f"[4] 1:1 rebalance: {len(bal)} kept, correct={bc} incorrect={len(bal) - bc} (keeps teacher-incorrect)")

    ptr = perfect_trace_rate(recs)
    print("[5] perfect-trace-rate / within-budget:")
    cov = scorer.category_coverage(recs)
    for c in sorted(ptr):
        o, t = ptr[c]
        s, tt, med = cov[c]
        print(
            f"      {c:9s} ptr {o}/{t}={100 * o / t:5.1f}%  within-budget {s}/{tt}={100 * s / tt:5.1f}% med_tok={med:.0f}"
        )

    ok, det = preflight_adapter()
    print(
        f"[6] adapter preflight: rank={det['rank']} (<=32:{det['rank_ok']}) root_ok={det['root_ok']} -> {'PASS' if ok else 'FAIL'}"
    )
    assert ok

    r0 = recs[0]
    assert verify(r0["answer"], extract_final_answer(r0["trace"])), "fail-fast extraction broke"
    print("[7] fail-fast single-example boxed extraction: OK")
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
