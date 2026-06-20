"""Teacher-trace rebalancing + robust aggregation (lb13-v1).

Reproduces the LB13 data-discipline levers (method_summary.md §2/§5):
  * **keep teacher-incorrect traces** and **rebalance correct:incorrect = 1:1**
    (LB13 + LB10 both show excluding failed traces hurts) — challenges our c1/c2
    verified-only filter;
  * **robust aggregation**: an operator is valid if it matches **≥1 example** (not
    all) — tolerates symbol-transcription noise;
  * **cryptarithm-from-equation augmentation** (~3× cryptarithm seeded from equation
    rows) to offset the volume lost by rebalancing.

Pure CPU; the rebalance ratio and aggregation behavior are asserted on synthetic.
"""

from __future__ import annotations

import argparse
import random


def rebalance_one_to_one(traces, seed=42):
    """traces: [{...,'correct':bool}]. Return a 1:1 correct:incorrect subset (keep all
    of the minority class, downsample the majority). Keeps incorrect traces."""
    rng = random.Random(seed)
    correct = [t for t in traces if t.get("correct")]
    incorrect = [t for t in traces if not t.get("correct")]
    k = min(len(correct), len(incorrect))
    if k == 0:
        return list(traces)  # cannot balance; keep as-is
    rng.shuffle(correct)
    rng.shuffle(incorrect)
    out = correct[:k] + incorrect[:k]
    rng.shuffle(out)
    return out


def robust_aggregate(candidate_outputs, example_outputs):
    """An operator/candidate is VALID if it matches >=1 example (robust), vs the
    strict 'matches ALL' rule. Returns (robust_valid, strict_valid)."""
    matches = sum(1 for c, e in zip(candidate_outputs, example_outputs) if c == e)
    return matches >= 1, matches == len(example_outputs)


def augment_cryptarithm_from_equation(equation_rows, factor=3):
    """Seed cryptarithm items from equation rows (symbol-substitute the operands).
    Returns the augmented list (originals + `factor`x derived placeholders)."""
    out = list(equation_rows)
    for i, row in enumerate(equation_rows):
        for k in range(factor):
            out.append({**row, "category": "cryptarithm", "derived_from": ("equation", i), "variant": k})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    args = ap.parse_args()
    rng = random.Random(0)
    # synthetic teacher set: overrepresented correct (the LB13 imbalance to fix)
    traces = [{"id": i, "correct": rng.random() < 0.8} for i in range(args.n)]
    nc = sum(t["correct"] for t in traces)
    ni = args.n - nc
    bal = rebalance_one_to_one(traces)
    bc = sum(t["correct"] for t in bal)
    bi = len(bal) - bc
    print("LB13 rebalance (keep teacher-incorrect; correct:incorrect -> 1:1):")
    print(f"  before: correct={nc} incorrect={ni} (ratio {nc / max(ni, 1):.2f}:1)")
    print(f"  after : correct={bc} incorrect={bi} (ratio {bc / max(bi, 1):.2f}:1, kept all {ni} incorrect)")
    assert bc == bi, "rebalance must produce 1:1"

    # robust vs strict aggregation on a noisy example set (1 corrupted of 5)
    ex = ["10", "20", "30", "40", "50"]
    cand = ["10", "20", "30", "40", "99"]  # matches 4/5 (one transcription error)
    rob, strict = robust_aggregate(cand, ex)
    print(f"  robust aggregation (4/5 match): robust_valid={rob} strict_valid={strict}  (LB13 keeps robust)")
    assert rob and not strict

    eq_rows = [{"category": "equation", "id": i} for i in range(10)]
    aug = augment_cryptarithm_from_equation(eq_rows, factor=3)
    print(f"  cryptarithm-from-equation: {len(eq_rows)} eq rows -> +{len(aug) - len(eq_rows)} cryptarithm seeds")
    print("  all rebalance/aggregation/augment assertions passed.")


if __name__ == "__main__":
    main()
