"""Programmatic synthetic-data generator (lb10-v1).

Generates synthetic problems for the two LB10 headline levers the same way the
top teams did: **programmatically (no LLM authoring)**, sampling a structured
hidden instance via the lb10 solver's own ``generate`` fn, rendering a
competition-format prompt, attaching a solver-generated staged trace, and keeping
only **internally consistent** puzzles (the lb10 solver must reproduce the gold
answer on the rendered instance).

Categories implemented here are the lb10-v1 levers:

  * **bit** — rotate/shift key-table bit reasoner
    (``bit_keytable_reasoner``): single-operand ``x -> output`` over 8-bit binary,
    ``out[i] = F(rotl(x,a), shl(x,b), shr(x,c))``. Examples are rendered as
    ``xxxxxxxx -> yyyyyyyy`` lines; we generate with enough examples (16) so the
    solver reaches its full-table (all-8-keys-seen) oracle. Trace = compact
    ``key>value`` CoT ending ``\\boxed{<binary>}``.
  * **equation_numeric** — frequency-deduce solver (``equation_solver``):
    glyph-rendered ``a<glyph>b = out`` example lines, query operator seen in the
    examples (deduce). Trace ends ``\\boxed{<answer>}``.

Mix defaults to ~0.5 bit / 0.5 equation_numeric. Every kept record is
round-trip-guarded (``extract_final_answer(trace) == answer``) under the official
metric. Token proxy is ``len(trace)``; ``--report`` prints the per-category
trace-length histogram (gate: bit median < 5000).

    python synth_gen.py --n 1500 --seed 42 --out corpus.jsonl --report
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "eval"))

import bit_keytable_reasoner as bk  # noqa: E402
import equation_solver as es  # noqa: E402
from official_metric import extract_final_answer  # noqa: E402

# Header skeletons — copied verbatim from lb1-v1/synth_gen.py so the rendered
# prompts match the competition prompt format the model trains/evals on.
ALICE_HEADER = (
    "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:\n"
)
ALICE_BIT_HEADER = (
    "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers. "
    "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, NOT, "
    "and possibly majority or choice functions.\n\nHere are some examples of input -> output:\n"
)

BIT_EXAMPLES = 16  # enough to drive the solver to its full-table oracle


# ── bit manipulation (rotate/shift key-table, single-operand x) ───────────────
def gen_bit(rng):
    """One bit record via bit_keytable_reasoner; kept only if the solver is right."""
    seed = rng.randrange(1 << 31)
    truth, examples, q, ans_int = bk.generate(seed, n_examples=BIT_EXAMPLES)
    answer = bk.to_bits(ans_int)

    pred, meta = bk.solve(examples, q)
    # consistency filter: solver must reproduce the gold answer
    if pred is None or meta.get("abc") is None or bk.to_bits(pred) != answer:
        return None

    a, b, c = meta["abc"]
    # rebuild the key-table the solver locked onto so the trace shows its CoT
    table = bk._build_table(examples, a, b, c)
    if table is None:  # should not happen for a conflict-free chosen (a,b,c)
        return None

    ex_lines = "\n".join(f"{x:08b} -> {o:08b}" for x, o in examples)
    prompt = f"{ALICE_BIT_HEADER}{ex_lines}\nNow, determine the output for: {q:08b}"

    body = bk.render_trace(examples, q, a, b, c, table)
    trace = f"{body}\nQuery {q:08b}: apply key-table -> {answer}\n</think>\n\\boxed{{{answer}}}"
    return {"category": "bit", "prompt": prompt, "answer": answer, "trace": trace}


# ── equation numeric (frequency-deduce) ───────────────────────────────────────
def _render_eq_prompt(by_glyph, query):
    qg, qa, qb = query
    ex_lines = "\n".join(f"{a}{g}{b} = {o}" for g, exs in by_glyph.items() for (a, b, o) in exs)
    return f"{ALICE_HEADER}{ex_lines}\nNow, determine the result for: {qa}{qg}{qb}"


def gen_equation_numeric(rng):
    """One equation_numeric (deduce) record; kept only if the solver is right."""
    seed = rng.randrange(1 << 31)
    by_glyph, query, answer = es.generate(seed, deduce=True)

    pred, mode, op, wrapper = es.solve(by_glyph, query)
    # consistency filter: solver must reproduce the gold answer
    if pred is None or pred != answer:
        return None
    qg, qa, qb = query

    prompt = _render_eq_prompt(by_glyph, query)
    trace = "\n".join(
        [
            "<think>",
            f"Equation numeric ({mode}). Inferred shared output wrapper: {wrapper}.",
            f"Query operator '{qg}' seen in examples -> frequency-deduce operation '{op}'.",
            f"Apply '{op}' under wrapper {wrapper} to {qa},{qb} -> {answer}",
            f"</think>\n\\boxed{{{answer}}}",
        ]
    )
    return {"category": "equation_numeric", "prompt": prompt, "answer": answer, "trace": trace}


def build_corpus(n, seed=42, mix=None):
    rng = random.Random(seed)
    mix = mix or {"bit": 0.5, "equation_numeric": 0.5}
    records = []
    attempts = 0
    target = n
    while len(records) < target and attempts < target * 50:
        attempts += 1
        r = rng.random()
        if r < mix["bit"]:
            rec = gen_bit(rng)
        else:
            rec = gen_equation_numeric(rng)
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
