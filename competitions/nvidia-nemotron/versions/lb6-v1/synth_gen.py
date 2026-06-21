"""Programmatic synthetic-data generator (lb6-v1).

Emits competition-format JSONL training records for the three LB6 levers, built the
same way the top teams did — **programmatically, no LLM authoring** — using the
lb6-v1 solver modules both to *generate* structured instances and as the
**consistency filter** (the same solver that scores the category must reproduce the
gold answer on the rendered instance, else the record is dropped).

Categories (mix cryptarithm 0.4 / bit 0.3 / equation_numeric 0.3):

  * cryptarithm     — `cryptarithm_dfs` (op='*'), ALICE_HEADER prompt, DFS+reversed
                      consistency filter, compact CoT trace ending \\boxed{answer}.
  * bit             — `bit_template_solver` (hidden template op(a,shift(b,s)) /
                      ternary), ALICE_BIT_HEADER prompt, hex CoT, trace ending
                      \\boxed{<8-bit binary>}.
  * equation_numeric— `equation_solver` (deduce; add/sub/mul + maxmodmin families),
                      ALICE_HEADER prompt with glyph-rendered examples, trace ending
                      \\boxed{answer}.

Every kept record round-trips under the official extractor
(`extract_final_answer(trace) == answer`). Each record carries a `tokens` proxy
(`len(trace)`); `--report` prints the per-category trace-length histogram
(gate: bit median < 5000).

    python synth_gen.py --n 1500 --seed 42 --out corpus.jsonl --report
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))

import bit_template_solver as bit_mod  # noqa: E402
import cryptarithm_dfs as crypt_mod  # noqa: E402
import equation_solver as eq_mod  # noqa: E402
from official_metric import extract_final_answer  # noqa: E402

# Header skeletons copied verbatim from lb1-v1/synth_gen.py.
ALICE_HEADER = (
    "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:\n"
)
ALICE_BIT_HEADER = (
    "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers. "
    "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, NOT, "
    "and possibly majority or choice functions.\n\nHere are some examples of input -> output:\n"
)

# Cryptarithm symbol pool. '{' and '}' are excluded by construction: cryptarithm_dfs
# encodes digits with A-Z, none of which is a brace, so answers never collide with
# the \boxed{} delimiters. We still assert no brace below and round-trip every record.
_BRACES = {"{", "}"}


def _to_bits(x: int) -> str:
    """8-bit binary rendering of a bit-category answer (leading zeros significant)."""
    return f"{x & bit_mod.MASK:08b}"


# ── cryptarithm ─────────────────────────────────────────────────────────────
def gen_cryptarithm(rng):
    seed = rng.randrange(1 << 30)
    mapping, examples, query, truth = crypt_mod._gen(seed, op="*", n_examples=rng.randint(4, 6))
    # exclude any symbol that is a brace (defensive; A-Z mapping never produces one)
    if any(ch in _BRACES for ex in examples for tok in ex if isinstance(tok, str) for ch in tok):
        return None
    if any(ch in _BRACES for ch in truth):
        return None

    # consistency filter: the lb6 DFS solver (forward + reversed) must reproduce gold
    pred, how = crypt_mod.solve(examples, query)
    if pred is None or pred != truth:
        return None

    ex_lines = "\n".join(f"{a}{op}{b} = {c}" for a, op, b, c in examples)
    qa, qop, qb = query
    prompt = f"{ALICE_HEADER}{ex_lines}\nNow, determine the result for: {qa}{qop}{qb}"

    trace = "\n".join(
        [
            "<think>",
            "Cryptarithm: recover the digit<->symbol bijection by DFS over the examples,",
            f"using leading-zero / units / equation-sorting pruning ({how} pass succeeded).",
            f"Apply the recovered mapping to the query {qa}{qop}{qb}.",
            f"</think>\n\\boxed{{{truth}}}",
        ]
    )
    return {"category": "cryptarithm", "prompt": prompt, "answer": truth, "trace": trace}


# ── bit manipulation ────────────────────────────────────────────────────────
def gen_bit(rng):
    seed = rng.randrange(1 << 30)
    arity = rng.choice([2, 2, 3])  # bias toward pairwise+shift (the bulk of LB6 bit)
    truth, examples, query, ans_int = bit_mod.generate(seed, arity=arity, n_examples=rng.randint(7, 9))

    # consistency filter: the lb6 template solver must reproduce the gold answer
    name, pred = bit_mod.solve(examples, query, arity)
    if pred is None or pred != ans_int:
        return None

    answer = _to_bits(ans_int)

    if arity == 2:
        ex_lines = "\n".join(f"{a:08b} {b:08b} -> {r:08b}" for (a, b), r in examples)
        qline = " ".join(f"{o:08b}" for o in query)
    else:
        ex_lines = "\n".join(f"{a:08b} {b:08b} {c:08b} -> {r:08b}" for (a, b, c), r in examples)
        qline = " ".join(f"{o:08b}" for o in query)
    prompt = f"{ALICE_BIT_HEADER}{ex_lines}\nNow, determine the output for: {qline}"

    # hidden-template hex CoT (compact; keeps bit traces well under the 5000 gate)
    cot = bit_mod.render_hex_cot(examples, query, arity)
    trace = "\n".join([cot, f"recovered template: {name}", f"</think>\n\\boxed{{{answer}}}"])
    return {"category": "bit", "prompt": prompt, "answer": answer, "trace": trace}


# ── equation numeric ────────────────────────────────────────────────────────
def gen_equation_numeric(rng):
    seed = rng.randrange(1 << 30)
    by_glyph, query, ans_int = eq_mod.generate(seed, n_glyphs=rng.randint(2, 3), ex=rng.randint(3, 5), deduce=True)
    qg, qa, qb = query

    # consistency filter: the lb6 family solver must reproduce gold on this instance
    val, mode, rule = eq_mod.solve(by_glyph, query)
    if val is None or val != ans_int:
        return None

    answer = str(ans_int)

    ex_lines = []
    for g in by_glyph:
        for a, b, z in by_glyph[g]:
            ex_lines.append(f"{a}{g}{b} = {z}")
    rng.shuffle(ex_lines)
    prompt = f"{ALICE_HEADER}" + "\n".join(ex_lines) + f"\nNow, determine the result for: {qa}{qg}{qb}"

    fam = eq_mod.RULE_FAMILY.get(rule, "?")
    trace = "\n".join(
        [
            "<think>",
            "Equation numeric (deduce): per-operator rule over add/sub/mul + maxmodmin families.",
            f"Operator '{qg}' is consistent with rule {rule} (family {fam}, mode {mode}).",
            f"Apply to query {qa}{qg}{qb} -> {answer}.",
            f"</think>\n\\boxed{{{answer}}}",
        ]
    )
    return {"category": "equation_numeric", "prompt": prompt, "answer": answer, "trace": trace}


def build_corpus(n, seed=42, mix=None):
    rng = random.Random(seed)
    mix = mix or {"cryptarithm": 0.4, "bit": 0.3, "equation_numeric": 0.3}
    c_thr = mix["cryptarithm"]
    b_thr = c_thr + mix["bit"]
    records = []
    attempts = 0
    while len(records) < n and attempts < n * 50:
        attempts += 1
        r = rng.random()
        if r < c_thr:
            rec = gen_cryptarithm(rng)
        elif r < b_thr:
            rec = gen_bit(rng)
        else:
            rec = gen_equation_numeric(rng)
        if not rec:
            continue
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
        for rec in records:
            by[rec["category"]].append(rec["tokens"])
        print("\nper-category trace-token histogram:")
        for cat, toks in sorted(by.items()):
            med = statistics.median(toks)
            gate = " (bit gate < 5000)" if cat == "bit" else ""
            print(f"  {cat:18s} n={len(toks):5d} median={med:7.0f} max={max(toks):6d}{gate}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        print(f"wrote {len(records)} records -> {args.out}")


if __name__ == "__main__":
    main()
