"""Programmatic synthetic-data generator (lb5-v1).

Same discipline as lb1-v1/synth_gen.py — generate structured instances with the
lb5 oracle solvers, render **competition-format** prompts, attach a solver-derived
staged trace, and keep only **internally consistent** puzzles (the lb5 solver must
reproduce the gold answer on the structured instance) that also round-trip through
the official `extract_final_answer`.

Categories are the LB5 heavy levers (method_summary.md):

  * **equation_numeric** — the LB5 2-world / 4-family / 13-rule deduce lever
    (`equation_solver.py`). Each seen glyph contributes a block of `AopB = out`
    example lines; the query is `Now, determine the result for: AopB`.
  * **bit** — the LB5 ternary-extended raw-bit lever (`bit_ternary_solver.py`),
    15 primitives (8 binary + 7 ternary). LB5 lesson: **RAW 8-bit binary**, never
    hex / merged tokens (those broke the model; `tokenizer_probe.py`). Ternary
    prompts show the 2-or-3 operands per line.

Every kept record carries a `len(trace)` token proxy; `--report` prints the
per-category trace-length histogram (gate: bit median < 5000).

    python synth_gen.py --n 1500 --seed 42 --out corpus.jsonl --report
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "eval"))

import bit_ternary_solver as bit  # noqa: E402
import equation_solver as eqs  # noqa: E402
from official_metric import extract_final_answer  # noqa: E402

# Header strings copied verbatim from lb1-v1/synth_gen.py (competition format).
ALICE_HEADER = (
    "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:\n"
)
ALICE_BIT_HEADER = (
    "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers. "
    "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, NOT, "
    "and possibly majority or choice functions.\n\nHere are some examples of input -> output:\n"
)


# ── equation numeric (LB5 2-world/4-family/13-rule) ──────────────────────────
def gen_equation_numeric(rng, *, deduce=True):
    """Render an lb5 equation instance as a competition prompt + staged trace.

    Consistency filter: the lb5 solver must reproduce the gold answer on the
    structured (by_glyph, query) instance.
    """
    seed = rng.randint(0, 2**31 - 1)
    n_glyphs = rng.randint(2, 3)
    ex_per_glyph = rng.randint(3, 5)
    by_glyph, query, truth = eqs.generate_problem(seed, n_glyphs=n_glyphs, ex_per_glyph=ex_per_glyph, deduce=deduce)
    # consistency filter: solver reproduces the gold answer on this instance
    pred, mode, rule, world = eqs.solve(by_glyph, query)
    if pred is None or pred != truth:
        return None
    answer = truth

    # competition-format prompt: one "AopB = out" line per example, across glyphs
    ex_lines = []
    for g, rows in by_glyph.items():
        for a, b, out in rows:
            ex_lines.append(f"{a}{g}{b} = {out}")
    rng.shuffle(ex_lines)
    qg, qa, qb = query
    prompt = f"{ALICE_HEADER}" + "\n".join(ex_lines) + f"\nNow, determine the result for: {qa}{qg}{qb}"

    # staged trace: per-glyph resolved (rule, world), then the query application
    resolved = {}
    for g in by_glyph:
        cands = eqs.consistent(by_glyph[g])
        if cands:
            resolved[g] = cands[0]
    think = ["<think>", "Equation numeric (LB5 2-world / 4-family / 13-rule inventory)."]
    for g, (r, w) in resolved.items():
        think.append(f"glyph '{g}' -> rule {r} (family {eqs.RULE_FAMILY[r]}), world {w}")
    think.append(f"Query {qa}{qg}{qb}: mode={mode}, apply rule {rule}/{world} -> {answer}")
    think.append(f"</think>\n\\boxed{{{answer}}}")
    trace = "\n".join(think)
    return {"category": "equation_numeric", "prompt": prompt, "answer": answer, "trace": trace}


# ── bit manipulation (LB5 ternary-extended, raw bits) ────────────────────────
def gen_bit(rng):
    """Render an lb5 bit instance (binary OR ternary primitive) as a prompt + CoT.

    Consistency filter: the lb5 solver must reproduce the gold answer on the
    structured (examples, query) instance using the cut (<=7-example) view.
    """
    arity = rng.choice([2, 3])
    seed = rng.randint(0, 2**31 - 1)
    # LB5 cut to ~7 examples to fit the 7680-token budget (raw bits, no merge)
    n_examples = rng.randint(6, 7)
    name, examples, q, ans = bit.generate_bit_problem(seed, arity=arity, n_examples=n_examples)
    used = examples[:7]
    pred_name, pred = bit.solve_bit(used, q, arity)
    # consistency filter: solver reproduces the gold answer on this instance
    if pred is None or pred != ans:
        return None
    answer = bit.to_bits(ans)

    # competition-format prompt: raw 8-bit operand line(s) per example
    ex_lines = [" ".join(bit.to_bits(o) for o in ops) + " -> " + bit.to_bits(res) for ops, res in used]
    q_line = " ".join(bit.to_bits(o) for o in q)
    prompt = f"{ALICE_BIT_HEADER}" + "\n".join(ex_lines) + f"\nNow, determine the output for: {q_line}"

    # compact raw-bit CoT trace ending in \boxed{to_bits(answer)}
    trace = (
        bit.render_raw_cot(used, q, arity)
        + f"\nhidden primitive = {pred_name} (arity {arity})"
        + f"\napply to query -> {answer}"
        + f"\n</think>\n\\boxed{{{answer}}}"
    )
    return {"category": "bit", "prompt": prompt, "answer": answer, "trace": trace}


def build_corpus(n, seed=42, mix=None):
    rng = random.Random(seed)
    mix = mix or {"equation_numeric": 0.5, "bit": 0.5}
    records = []
    attempts = 0
    target = n
    while len(records) < target and attempts < target * 50:
        attempts += 1
        r = rng.random()
        if r < mix["equation_numeric"]:
            rec = gen_equation_numeric(rng, deduce=True)
        else:
            rec = gen_bit(rng)
        if rec:
            # round-trip guard: the official extractor must recover the exact answer
            if extract_final_answer(rec["trace"]) != rec["answer"]:
                continue
            rec["id"] = f"synth-{len(records):06d}"
            rec["tokens"] = len(rec["trace"])
            records.append(rec)
    return records, attempts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", help="write JSONL")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    records, attempts = build_corpus(args.n, args.seed)
    print(
        f"generated {len(records)} consistency-verified records in {attempts} attempts "
        f"(accept rate {100 * len(records) / max(1, attempts):.1f}%)"
    )
    if args.report:
        from collections import defaultdict
        import statistics

        by = defaultdict(list)
        for r in records:
            by[r["category"]].append(r["tokens"])
        print("\nper-category trace-token histogram:")
        for cat, toks in sorted(by.items()):
            med = statistics.median(toks)
            gate = " (bit gate < 5000)" if cat == "bit" else ""
            print(f"  {cat:18s} n={len(toks):5d} median={med:7.0f} max={max(toks):6d}{gate}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {len(records)} records -> {args.out}")


if __name__ == "__main__":
    main()
