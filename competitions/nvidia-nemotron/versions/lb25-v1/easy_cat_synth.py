"""Easy-category + cipher-prefix synthetic data (lb25-v1 — LB25 levers #3 & #4).

LB25 changes #3/#4: top up the EASY categories (text cipher, unit conversion,
gravity, numeral system) with synthetic data to pin them at ~100%, plus extra
**cipher-prefix** data because Nemotron spells poorly. Per our own T12 these cats
are already near ceiling (numeral/gravity/unit 8/8, cipher 15–16/16), so the LB25
plan uses this only as a **no-regression guard**, not a gain source — we keep the
dose low and never let it dilute the v14 backbone (the b2/v15/c2 lesson).

Reuses the existing, tested generators in `lib/nemo_synth_gen.py` (make_* return
`(prompt, answer, cot)`), keeps only rows whose answer is exactly extractable, and
adds a cipher-prefix emphasis (short/edge plaintext words to drill spelling).

    python easy_cat_synth.py --n 400 --report
"""

from __future__ import annotations

import argparse
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "lib"))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))

import nemo_synth_gen as g  # noqa: E402
from official_metric import extract_final_answer, verify  # noqa: E402

EASY_MAKERS = {
    "cipher": g.make_encryption_puzzle,
    "numeral": g.make_numeral_puzzle,
    "unit": g.make_unit_puzzle,
    "gravity": g.make_gravity_puzzle,
}
SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"


def _record(cat, prompt, answer, cot):
    # ensure a boxed finality line so the row round-trips under the grader extractor
    if "\\boxed{" not in cot:
        cot = cot.rstrip() + f"\n\\boxed{{{answer}}}"
    return {"category": cat, "prompt": prompt, "answer": str(answer).strip(), "cot": cot}


def build_easy_corpus(n_per_cat=100, seed=42, cipher_prefix_frac=0.4):
    """Generate verified easy-category records; `cipher` gets a cipher-prefix emphasis."""
    rng = random.Random(seed)
    records = []
    for cat, maker in EASY_MAKERS.items():
        made = attempts = 0
        target = n_per_cat
        while made < target and attempts < target * 30:
            attempts += 1
            try:
                prompt, answer, cot = maker(rng)
            except Exception:
                continue
            if not prompt or not str(answer).strip() or not cot:
                continue
            rec = _record(cat, prompt, answer, cot)
            # keep only grader-extractable rows (the LB25/INS-002 discipline)
            if not verify(rec["answer"], extract_final_answer(rec["cot"])):
                continue
            records.append(rec)
            made += 1
    rng.shuffle(records)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="rows per easy category")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    recs = build_easy_corpus(args.n, args.seed)
    print(f"generated {len(recs)} verified easy-category records (no-regression guard)")
    if args.report:
        from collections import Counter

        by = Counter(r["category"] for r in recs)
        for c, k in sorted(by.items()):
            print(f"  {c:10s} {k}")
        ok = sum(verify(r["answer"], extract_final_answer(r["cot"])) for r in recs)
        print(f"  extraction round-trip: {ok}/{len(recs)}")


if __name__ == "__main__":
    main()
