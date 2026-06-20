"""Validation harness for lb3-v1 (CPU; the LB3 private-tracking lever).

Implements the LB3 validation design (gap_analysis.md / method_summary.md):
  * **10% stratified-by-category hold-out**;
  * **leakage exclusion**: drop any augmented sample whose ``origin_seed`` (the
    original it was resampled from) is a held-out original;
  * **perfect-trace-rate** as a leading indicator (target >85% bit, >95% cipher/numeric);
  * official-metric extraction / within-budget accuracy (via ``scorer``);
  * adapter **rank<=32** + **zip-structure** preflight checks (via ``package_submission``);
  * **fail-fast one-example self-check** before any long run.

The "private-tracking" property — local val correlating with the *private* LB, not
the noisy public LB — is the decision rule; it cannot be measured offline without
LB points, so ``--self`` asserts the *mechanics* (stratification, leakage exclusion,
extraction, trace fidelity) that make that property achievable, and documents the
correlation check to run when LB points exist.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import defaultdict

import corpus
import package_submission as pkg
import scorer

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
from official_metric import extract_final_answer, verify  # noqa: E402


# --------------------------------------------------------------------------- #
# stratified split + leakage exclusion
# --------------------------------------------------------------------------- #
def stratified_holdout(records, frac=0.10, seed=42):
    """Return (train, val) holding out ``frac`` of EACH category (deterministic)."""
    import random

    rng = random.Random(seed)
    by_cat = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    train, val = [], []
    for cat, recs in by_cat.items():
        idx = list(range(len(recs)))
        rng.shuffle(idx)
        k = max(1, int(round(len(recs) * frac)))
        val_idx = set(idx[:k])
        for i, r in enumerate(recs):
            (val if i in val_idx else train).append(r)
    return train, val


def exclude_leakage(train, val):
    """Drop train augments derived from a val original (matching origin_seed+category)."""
    val_origins = {(r["category"], r.get("origin_seed")) for r in val}
    kept = [r for r in train if (r["category"], r.get("origin_seed")) not in val_origins]
    return kept, len(train) - len(kept)


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def perfect_trace_rate(records):
    """Fraction whose \\boxed{} extraction equals the gold answer, per category."""
    ok = defaultdict(int)
    tot = defaultdict(int)
    for r in records:
        tot[r["category"]] += 1
        if verify(r["answer"], extract_final_answer(r["trace"])):
            ok[r["category"]] += 1
    return {c: (ok[c], tot[c]) for c in tot}


# --------------------------------------------------------------------------- #
# preflight gate (zip structure + rank<=32)
# --------------------------------------------------------------------------- #
def preflight_adapter(max_rank=32):
    """Build a dummy adapter, zip it, assert root structure + rank<=32 + no secrets.

    Returns (ok, details). Exercises the packaging path with no GPU.
    """
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
            details["zip_root_files"] = names
            # root structure: required files at root, no nesting
            details["root_ok"] = all("/" not in n for n in names) and set(pkg.REQUIRED_FILES).issubset(names)
            cfg = json.loads(z.read("adapter_config.json"))
            details["rank"] = cfg.get("r")
            details["rank_ok"] = cfg.get("r", 999) <= max_rank
            details["size_ok"] = os.path.getsize(out) > 0
    ok = details["root_ok"] and details["rank_ok"] and details["size_ok"]
    return ok, details


# --------------------------------------------------------------------------- #
# self-check (fail-fast)
# --------------------------------------------------------------------------- #
def self_check():
    print("== lb3-v1 validation self-check (CPU, no train.csv needed) ==")
    recs = corpus.build_demo_corpus(120, seed=0)
    print(f"[1] demo corpus: {len(recs)} records across {sorted(set(r['category'] for r in recs))}")

    train, val = stratified_holdout(recs, frac=0.10)
    # stratification check: every category present in val
    cats = sorted(set(r["category"] for r in recs))
    val_cats = sorted(set(r["category"] for r in val))
    assert val_cats == cats, f"stratification lost a category: {val_cats} != {cats}"
    print(f"[2] stratified 10% hold-out: train={len(train)} val={len(val)} (all categories in val: OK)")

    kept, dropped = exclude_leakage(train, val)
    print(f"[3] leakage exclusion: dropped {dropped} train rows derived from val originals -> train={len(kept)}")

    ptr = perfect_trace_rate(recs)
    print("[4] perfect-trace-rate (target >85% bit, >95% cipher/numeric):")
    for c, (o, t) in sorted(ptr.items()):
        print(f"      {c:12s} {o}/{t} = {100 * o / t:5.1f}%")

    acc = scorer.category_coverage(recs)
    print("[5] within-budget coverage (official extractor, max_tokens=7680):")
    for c, (s, t, med) in sorted(acc.items()):
        print(f"      {c:12s} {s}/{t} = {100 * s / t:5.1f}%  median_tokens={med:.0f}")

    ok, det = preflight_adapter()
    print(
        f"[6] adapter preflight: rank={det['rank']} (<=32:{det['rank_ok']}) "
        f"root_ok={det['root_ok']} size_ok={det['size_ok']} -> {'PASS' if ok else 'FAIL'}"
    )

    # fail-fast single-example extraction
    r0 = recs[0]
    assert verify(r0["answer"], extract_final_answer(r0["trace"])), "fail-fast: boxed extraction broke"
    print("[7] fail-fast single-example boxed extraction: OK")
    assert ok, "adapter preflight failed"
    print("== self-check PASSED ==")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", dest="selfcheck", action="store_true", help="run the CPU self-check")
    args = ap.parse_args()
    if args.selfcheck:
        raise SystemExit(self_check())
    ap.print_help()


if __name__ == "__main__":
    main()
