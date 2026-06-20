"""Programmatic synthetic-data generator (lb1-v1).

Generates synthetic problems for the hard categories the way the 1st-place team
did: **programmatically (no LLM authoring)**, sampling prompt skeletons, assigning
hidden rules under the 24-rule inventory while enforcing Observation 1 (one mode
per prompt) and Observation 2 (non-join operators do not reuse a group), rendering
competition-format prompts, attaching a solver-generated staged trace, and keeping
only **internally consistent** puzzles (the solver must reproduce the answer).

Categories implemented here are the lb1-v1 levers: equation-numeric (deduce/guess),
cryptarithm, and bit manipulation. The clean-backbone categories
(cipher/numeral/unit/gravity) are intentionally left to the existing
`lib/nemo_synth_gen.py` so we do NOT dilute the protected replay recipe
(gap_analysis.md / the b1/b2/v15 regression lesson).

Every record carries a token-count estimate; `--report` prints the per-category
trace-length histogram (gate: bit median < 5000 tokens after HEX).

    python synth_gen.py --n 2000 --out corpus.jsonl --report
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "eval"))

from rules24 import RULES, NON_JOIN_RULES, apply_rule, render_output_human  # noqa: E402
from hex_compress import char_tokens  # noqa: E402
import rule_sequence_catalog as rseq  # noqa: E402
import signature_catalog as sigcat_mod  # noqa: E402
import solvers  # noqa: E402
from eq_reprobe import solve_prompt as eq_solve  # noqa: E402
from official_metric import extract_final_answer  # noqa: E402

ALICE_HEADER = (
    "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:\n"
)
ALICE_BIT_HEADER = (
    "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers. "
    "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, NOT, "
    "and possibly majority or choice functions.\n\nHere are some examples of input -> output:\n"
)

# punctuation operator glyphs seen in the real equation prompts
OP_GLYPHS = list("`\\>/|!@#$%^&*~?")
# digit-hiding symbols for cryptarithm. '{' and '}' are excluded: they collide with
# the \boxed{} delimiters, so an answer containing them mis-extracts under the
# official metric (which truncates at the first '}'). Every kept record is also
# extraction-round-tripped below as a belt-and-braces guard.
SYMBOLS = list("|!)<[:\\'\"(@&^~?-+=]")


def _assign_rules(rng, n_ops, *, allow_join=True):
    """Assign rules to n_ops operators enforcing Obs.1 (mode) + Obs.2 (group)."""
    mode = rng.choice(["normal", "flip"])
    groups = ["add", "sub", "mul"]
    rng.shuffle(groups)
    assigned = {}
    gi = 0
    for i in range(n_ops):
        if allow_join and rng.random() < 0.2 and i > 0:
            assigned[i] = rng.choice(["join", "join_swap"])
            continue
        if gi >= len(groups):
            # ran out of distinct groups -> reuse join to respect Obs.2
            assigned[i] = rng.choice(["join", "join_swap"])
            continue
        grp = groups[gi]
        gi += 1
        rules = [r for r in NON_JOIN_RULES if RULES[r]["group"] == grp and RULES[r]["mode"] == mode]
        assigned[i] = rng.choice(rules)
    return assigned, mode


def _operand(rng):
    return f"{rng.randint(0, 99):02d}"


# ── equation numeric ────────────────────────────────────────────────────────
def gen_equation_numeric(rng, *, guess=False):
    n_ops = rng.randint(2, 3)
    glyphs = rng.sample(OP_GLYPHS, n_ops)
    rule_by_idx, mode = _assign_rules(rng, n_ops)
    op_rule = {glyphs[i]: rule_by_idx[i] for i in range(n_ops)}

    examples = []
    for _ in range(rng.randint(3, 5)):
        op = rng.choice(glyphs)
        sA, sB = _operand(rng), _operand(rng)
        tok = apply_rule(op_rule[op], sA, sB)
        if tok is None:
            continue
        out = render_output_human(tok, op)
        examples.append((sA, op, sB, out))
    if len(examples) < 2:
        return None
    seen_ops = {op for _, op, _, _ in examples}
    if guess:
        q_op = rng.choice([g for g in glyphs if g not in seen_ops] or glyphs)
    else:
        q_op = rng.choice(sorted(seen_ops))
    qA, qB = _operand(rng), _operand(rng)
    qtok = apply_rule(op_rule[q_op], qA, qB)
    if qtok is None:
        return None
    answer = render_output_human(qtok, q_op)

    ex_lines = "\n".join(f"{sA}{op}{sB} = {out}" for sA, op, sB, out in examples)
    prompt = f"{ALICE_HEADER}{ex_lines}\nNow, determine the result for: {qA}{q_op}{qB}"
    # consistency filter: the re-probe solver must recover this answer
    res = eq_solve(prompt)
    if res is None or res.get("predicted") != answer:
        return None
    trace = "\n".join(
        [
            "<think>",
            f"Equation numeric. Inferred prompt mode: {mode}. Per-operator rule via the 24-rule inventory.",
            *[
                f"operator '{op}' -> rule {op_rule[op]} ({RULES[op_rule[op]]['group']}/{RULES[op_rule[op]]['mode']})"
                for op in glyphs
            ],
            f"Query {qA}{q_op}{qB}: apply rule {op_rule[q_op]} -> {answer}",
            f"</think>\n\\boxed{{{answer}}}",
        ]
    )
    return {"category": "equation_numeric", "prompt": prompt, "answer": answer, "trace": trace}


# ── cryptarithm ─────────────────────────────────────────────────────────────
def gen_cryptarithm(rng, catalog):
    n_ops = rng.randint(2, 3)
    glyph_ops = rng.sample([s for s in SYMBOLS], n_ops)
    rule_by_idx, mode = _assign_rules(rng, n_ops, allow_join=True)
    op_rule = {glyph_ops[i]: rule_by_idx[i] for i in range(n_ops)}
    # bijective digit -> symbol map
    digits = list("0123456789")
    sympool = [s for s in SYMBOLS if s not in glyph_ops]
    if len(sympool) < 10:
        return None
    sym_for = dict(zip(digits, rng.sample(sympool, 10)))

    def enc(num_str):
        return "".join(sym_for[d] for d in num_str)

    examples = []
    for _ in range(rng.randint(3, 4)):
        op = rng.choice(glyph_ops)
        sA, sB = _operand(rng), _operand(rng)
        tok = apply_rule(op_rule[op], sA, sB)
        if tok is None:
            continue
        out_digits = render_output_human(tok, op)
        # only digit outputs are encodable to symbols (no sign-marker rules for synth simplicity)
        if any(not c.isdigit() for c in out_digits):
            continue
        lhs = enc(sA) + op + enc(sB)
        rhs = enc(out_digits)
        examples.append((lhs, rhs))
    if len(examples) < 2:
        return None
    q_op = rng.choice(glyph_ops)
    qA, qB = _operand(rng), _operand(rng)
    qtok = apply_rule(op_rule[q_op], qA, qB)
    if qtok is None:
        return None
    q_digits = render_output_human(qtok, q_op)
    if any(not c.isdigit() for c in q_digits):
        return None
    answer = enc(q_digits)
    ex_lines = "\n".join(f"{lhs} = {rhs}" for lhs, rhs in examples)
    prompt = f"{ALICE_HEADER}{ex_lines}\nNow, determine the result for: {enc(qA)}{q_op}{enc(qB)}"
    # consistency filter: catalog-DFS solver must recover the answer
    out = solvers.solve_cryptarithm(prompt, catalog)
    if out is None or out[0] != answer:
        return None
    return {"category": "cryptarithm", "prompt": prompt, "answer": answer, "trace": out[1]}


# ── bit manipulation ────────────────────────────────────────────────────────
def gen_bit(rng, core_catalog):
    op, args = rng.choice(list(core_catalog.values()))
    fn = rseq.transform_function(op, args)
    ins = rng.sample(range(256), rng.randint(8, 10))
    examples = [(x, fn(x)) for x in ins]
    q = rng.randint(0, 255)
    answer = f"{fn(q):08b}"
    ex_lines = "\n".join(f"{i:08b} -> {o:08b}" for i, o in examples)
    prompt = f"{ALICE_BIT_HEADER}{ex_lines}\nNow, determine the output for: {q:08b}"
    out = solvers.solve_bit(prompt, repair_catalog=core_catalog, use_hex=True)
    if out is None or out[0] != answer:
        return None
    return {"category": "bit", "prompt": prompt, "answer": answer, "trace": out[1]}


# Fast bit catalog for generation: the full CORE_PRIMS (~330k seqs) makes the
# repair NN ~10x slower per puzzle. Generation samples transforms from the catalog,
# so a smaller (~50k) catalog only trims bit diversity, not correctness.
GEN_BIT_PRIMS = (
    ["x", "not_x"]
    + [f"shl{k}" for k in range(1, 5)]
    + [f"shr{k}" for k in range(1, 5)]
    + [f"rol{k}" for k in range(1, 8)]
)


def build_corpus(n, seed=42, mix=None):
    rng = random.Random(seed)
    catalog = sigcat_mod.build_catalog()
    core = rseq.build_core_catalog(GEN_BIT_PRIMS)
    mix = mix or {"equation_numeric": 0.2, "cryptarithm": 0.5, "bit": 0.3}
    records = []
    attempts = 0
    target = n
    while len(records) < target and attempts < target * 50:
        attempts += 1
        r = rng.random()
        if r < mix["equation_numeric"]:
            rec = gen_equation_numeric(rng, guess=(rng.random() < 0.2))
        elif r < mix["equation_numeric"] + mix["cryptarithm"]:
            rec = gen_cryptarithm(rng, catalog)
        else:
            rec = gen_bit(rng, core)
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
    ap.add_argument("--n", type=int, default=500)
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
        with open(args.out, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {len(records)} records -> {args.out}")


if __name__ == "__main__":
    main()
