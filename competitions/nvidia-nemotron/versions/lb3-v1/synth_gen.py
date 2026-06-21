"""Programmatic synthetic-data generator (lb3-v1).

Emits competition-format JSONL training records for the three lb3-v1 headline
levers, generated **programmatically** (no LLM authoring) the way the 3rd-place
team did: build a structured instance with its own ground-truth via the lb3 solver
modules, render it to a competition-format prompt, attach a solver-generated trace,
and keep only **internally consistent** instances (the lb3 solver must reproduce the
gold answer on the structured instance) that also **round-trip** through the official
extractor.

Categories (mix ~ cryptarithm 0.45 / bit 0.30 / equation_numeric 0.25):
  * ``cryptarithm``      -> ``cryptarithm_csp.py`` (op='*' deduce; CSP solve;
                            staged ``emit_trace`` ending ``\\boxed{enc(qc)}``).
  * ``bit``              -> ``bit_hex_trace.py`` (hidden bitwise rule; compact CoT
                            over the HEX+tail-2 rendering, ``\\boxed{to_bits(ans)}``).
  * ``equation_numeric`` -> ``numeric_solver.py`` (deduce; 13-op global rule;
                            equation prompt with the glyph rendered, ``\\boxed{z}``).

The cryptarithm symbol alphabet is A-Z (``cryptarithm_csp._ALPHABET``), so the
encoded answers never contain ``{`` / ``}`` and cannot collide with the ``\\boxed{}``
delimiters; every kept record is round-tripped anyway as a belt-and-braces guard.

Every record carries ``tokens = len(trace)`` (the Nemotron ~1 token/char proxy);
``--report`` prints the accept rate and the per-category token histogram
(gate: bit median < 5000 tokens after HEX).

    python synth_gen.py --n 1500 --seed 42 --out corpus.jsonl --report
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "eval"))

import bit_hex_trace as bh  # noqa: E402
import cryptarithm_csp as cc  # noqa: E402
import numeric_solver as ns  # noqa: E402
from official_metric import extract_final_answer  # noqa: E402

ALICE_HEADER = (
    "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:\n"
)
ALICE_BIT_HEADER = (
    "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers. "
    "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, NOT, "
    "and possibly majority or choice functions.\n\nHere are some examples of input -> output:\n"
)


def char_tokens(s: str) -> int:
    """Approximate Nemotron token count (~1 token / char) for a trace string."""
    return len(s)


# ── cryptarithm (cryptarithm_csp.py, op='*' deduce) ─────────────────────────
def gen_cryptarithm(rng, lut):
    """One multiplication-deduce cryptarithm instance + its staged CSP trace.

    The structured instance is built by ``generate_problem`` (known secret A-Z
    mapping); the prompt is a faithful symbol-substitution rendering; consistency
    is verified on the structured instance (the CSP ``solve`` must predict the gold
    ``enc(qc)``). ``emit_trace`` already ends ``</think>\\boxed{enc(qc)}``.
    """
    seed = rng.randint(0, 2**31 - 1)
    n_examples = rng.randint(4, 6)
    p = cc.generate_problem(seed=seed, op="*", n_examples=n_examples, deduce=True)
    answer = p.enc(p.qc)
    if any(c in "{}" for c in answer):  # A-Z alphabet -> never, but guard anyway
        return None
    # consistency filter: the lb3 CSP solver must recover the gold on this instance
    sol = cc.solve(p, lut)
    if not sol.solved or sol.predicted != answer:
        return None
    ex_lines = "\n".join(f"{p.enc(ex.a)}{ex.op}{p.enc(ex.b)} = {p.enc(ex.c)}" for ex in p.examples)
    query = f"{p.enc(p.qa)}{p.qop}{p.enc(p.qb)}"
    prompt = f"{ALICE_HEADER}{ex_lines}\nNow, determine the result for: {query}"
    trace = cc.emit_trace(p, lut)
    return {"category": "cryptarithm", "prompt": prompt, "answer": answer, "trace": trace}


# ── bit manipulation (bit_hex_trace.py, hidden bitwise rule) ────────────────
def gen_bit(rng):
    """One hidden-rule bit instance + a compact HEX-compressed CoT trace."""
    seed = rng.randint(0, 2**31 - 1)
    n_examples = rng.randint(6, 9)
    truth, examples, q, ans = bh.generate_bit_problem(seed=seed, n_examples=n_examples)
    # consistency filter: the lb3 bit solver must infer a rule that reproduces gold
    name, pred = bh.solve_bit(examples, q)
    if pred is None or pred != ans:
        return None
    answer = bh.to_bits(ans)
    ex_lines = "\n".join(f"{bh.to_bits(a):>8} -> {bh.to_bits(b):>8} -> {bh.to_bits(c)}" for a, b, c in examples)
    prompt = f"{ALICE_BIT_HEADER}{ex_lines}\nNow, determine the output for: {bh.to_bits(q[0])} {bh.to_bits(q[1])}"
    # compact CoT over the HEX+tail-2 rendering (the LB3 token-saving lever)
    trace = "\n".join(
        [
            "<think>",
            "Bit manipulation. Compress the column listing with HEX+tail-2 bits to free search budget.",
            bh.render_hex_trace(examples, q),
            f"Search rules OR-NOT-first (MAJ enabled): the rule matching ALL examples is {name}.",
            f"Apply {name} to the query {bh.to_bits(q[0])},{bh.to_bits(q[1])} -> {answer}.",
            "</think>",
            f"\\boxed{{{answer}}}",
        ]
    )
    return {"category": "bit", "prompt": prompt, "answer": answer, "trace": trace}


# ── equation numeric (numeric_solver.py, deduce) ────────────────────────────
def gen_equation_numeric(rng):
    """One deduce numeric instance + its 13-op trace, rendered as an equation prompt."""
    seed = rng.randint(0, 2**31 - 1)
    n_glyphs = rng.randint(1, 3)
    by_glyph, query, truth, glyph_op = ns.generate_numeric_problem(
        seed=seed, n_glyphs=n_glyphs, ex_per_glyph=rng.randint(3, 5), deduce=True
    )
    # consistency filter: the lb3 numeric solver must reproduce the gold answer
    pred, mode, op_name = ns.solve_numeric(by_glyph, query)
    if pred != truth or op_name is None:
        return None
    answer = str(truth)
    if any(c in "{}" for c in answer):
        return None
    qg, qa, qb = query
    ex_lines = "\n".join(f"{a}{g}{b} = {z}" for g, exs in by_glyph.items() for a, b, z in exs)
    prompt = f"{ALICE_HEADER}{ex_lines}\nNow, determine the result for: {qa}{qg}{qb}"
    resolved = "\n".join(
        f"glyph '{g}': consistent op across its examples -> {ns.consistent_ops(exs)[0]}"
        for g, exs in by_glyph.items()
        if ns.consistent_ops(exs)
    )
    trace = "\n".join(
        [
            "<think>",
            "Equation numeric. Resolve each glyph to one of the 13 global ops (simple/reverse).",
            resolved,
            f"Query {qa}{qg}{qb}: glyph '{qg}' -> op {op_name} ({mode}) -> {answer}.",
            "</think>",
            f"\\boxed{{{answer}}}",
        ]
    )
    return {"category": "equation_numeric", "prompt": prompt, "answer": answer, "trace": trace}


def build_corpus(n, seed=42, mix=None):
    rng = random.Random(seed)
    lut = cc.build_lookup()
    mix = mix or {"cryptarithm": 0.45, "bit": 0.30, "equation_numeric": 0.25}
    records = []
    attempts = 0
    target = n
    while len(records) < target and attempts < target * 50:
        attempts += 1
        r = rng.random()
        if r < mix["cryptarithm"]:
            rec = gen_cryptarithm(rng, lut)
        elif r < mix["cryptarithm"] + mix["bit"]:
            rec = gen_bit(rng)
        else:
            rec = gen_equation_numeric(rng)
        if rec:
            # round-trip guard: the official extractor must recover the exact answer
            if extract_final_answer(rec["trace"]) != rec["answer"]:
                continue
            rec["id"] = f"synth-{len(records):06d}"
            rec["tokens"] = char_tokens(rec["trace"])
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
        import statistics
        from collections import defaultdict

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
