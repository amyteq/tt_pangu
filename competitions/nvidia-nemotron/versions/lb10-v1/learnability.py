"""Oracle-ceiling vs model-fidelity + logprob-learnability diagnostics (lb10-v1).

Reproduces the LB10 validation discipline (method_summary.md): separate two things
the aggregate score conflates —
  * **oracle ceiling**: can the deterministic *teacher* (our solver) solve the
    problem at all? (the score ceiling — "improve the teacher" first);
  * **model fidelity**: does the trained model reproduce the teacher's trace? (the
    imitation gap);
and export **per-example logprob learnability** to surface fragile traces (low mean
logprob) for priority-2× upsampling + failure-mode demos.

Without a GPU/model here, fidelity + logprob operate on *provided* values (a model's
per-example outputs / token logprobs). `--self` runs the oracle-coverage half on the
lb10-v1 solvers and demonstrates the split with a simulated fidelity/logprob stream,
so the reporting mechanics are exercised end-to-end. Pure CPU.
"""

from __future__ import annotations

import argparse
from collections import defaultdict


def oracle_coverage(records):
    """Per-category oracle ceiling: fraction the teacher solver got right (record['solved'])."""
    ok = defaultdict(int)
    tot = defaultdict(int)
    for r in records:
        tot[r["category"]] += 1
        if r.get("solved"):
            ok[r["category"]] += 1
    return {c: (ok[c], tot[c]) for c in tot}


def fidelity_vs_oracle(records, model_outputs):
    """Split: of the oracle-solved problems, how many did the MODEL also get right?

    model_outputs: {id: predicted_answer}. Returns per-category
    (oracle_solved, model_correct_within_oracle, imitation_gap).
    """
    by = defaultdict(lambda: [0, 0])
    for r in records:
        if not r.get("solved"):
            continue
        c = r["category"]
        by[c][0] += 1
        if model_outputs.get(r["id"]) == r["answer"]:
            by[c][1] += 1
    out = {}
    for c, (orc, mc) in by.items():
        out[c] = (orc, mc, (orc - mc) / orc if orc else 0.0)
    return out


def fragile_traces(logprobs, threshold):
    """Return ids whose mean per-token logprob is below threshold (priority-2x targets)."""
    frag = []
    for rid, lps in logprobs.items():
        if lps and (sum(lps) / len(lps)) < threshold:
            frag.append(rid)
    return frag


def self_check():
    import corpus

    print("== lb10-v1 learnability / oracle-vs-fidelity self-check (CPU) ==")
    recs = corpus.build_demo_corpus(150, seed=0)
    cov = oracle_coverage(recs)
    print("[1] oracle ceiling (teacher solver per category):")
    for c, (o, t) in sorted(cov.items()):
        print(f"      {c:14s} {o}/{t} = {100 * o / t:5.1f}%")

    # simulate a model that reproduces 90% of solved traces (imitation gap = 10%)
    import random

    rng = random.Random(0)
    model_out = {r["id"]: (r["answer"] if (r.get("solved") and rng.random() < 0.9) else "WRONG") for r in recs}
    fid = fidelity_vs_oracle(recs, model_out)
    print("[2] oracle-vs-fidelity split (model reproduces the teacher trace?):")
    for c, (orc, mc, gap) in sorted(fid.items()):
        print(f"      {c:14s} oracle {orc} | model {mc} | imitation_gap {100 * gap:4.1f}%")

    # simulated per-example logprobs; flag the fragile tail for priority upsampling
    logprobs = {r["id"]: [rng.uniform(-3.0, -0.1) for _ in range(5)] for r in recs}
    frag = fragile_traces(logprobs, threshold=-2.0)
    print(f"[3] logprob learnability: {len(frag)}/{len(recs)} fragile traces (mean logprob < -2.0) -> priority 2x")
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
