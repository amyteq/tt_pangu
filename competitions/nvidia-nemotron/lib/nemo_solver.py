"""Real-prompt solver-distillation for the Nemotron reasoning comp (Option C).

For each train.csv row we (a) classify the category, (b) run a deterministic
solver that recovers the hidden rule from the in-prompt examples, (c) apply it to
the query, and (d) KEEP the row only if the solver's answer matches the
ground-truth `answer` column (exact string, or numeric within 1e-2 — the official
metric). Kept rows yield a verified long-CoT trace for SFT. Because every kept
trace ends in the ground-truth answer, the data cannot poison training.

This is the Idea A/D/E lever from work/00.nemo.md that was never built:
verified reasoning on the *real* prompts (vs v15's synthetic puzzles).

solve_dataset(rows) -> (records, coverage_by_category)
"""

import math
import re

# --- official-metric verify (string exact, case-insensitive; or numeric 1e-2) ---


def verify(pred, gt):
    pred = str(pred).strip()
    gt = str(gt).strip()
    try:
        return math.isclose(float(pred), float(gt), rel_tol=1e-2, abs_tol=1e-5)
    except (ValueError, TypeError):
        return pred.lower() == gt.lower()


def classify(p):
    pl = p.lower()
    if "8-bit binary" in pl or "bit manipulation" in pl:
        return "bit"
    if "gravitational constant" in pl:
        return "gravity"
    if "unit conversion" in pl or "convert the following measurement" in pl:
        return "unit"
    if "secret encryption" in pl or "decrypt" in pl:
        return "cipher"
    if "numeral system" in pl:
        return "numeral"
    if "transformation rules is applied to equations" in pl:
        return "equation"
    return "other"


# --------------------------------------------------------------------------- #
# numeral (Roman)
# --------------------------------------------------------------------------- #
_ROMAN = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def _roman(n):
    out = []
    for v, s in _ROMAN:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


def solve_numeral(p):
    m = re.search(r"write the number\s+(\d+)", p, re.I)
    if not m:
        return None
    n = int(m.group(1))
    # sanity: the examples must be standard Roman too
    for a, b in re.findall(r"(\d+)\s*->\s*([A-Z]+)", p):
        if _roman(int(a)) != b:
            return None
    ans = _roman(n)
    steps = []
    rem = n
    for v, s in _ROMAN:
        while rem >= v:
            steps.append(f"  {rem} >= {v}: append '{s}', remainder {rem - v}")
            rem -= v
    cot = (
        "The examples are standard Roman-numeral conversion. "
        f"Decompose {n} by greedily subtracting the largest value:\n"
        + "\n".join(steps)
        + f"\nConcatenating the symbols gives {ans}.\n"
        f"Final answer: \\boxed{{{ans}}}"
    )
    return ans, cot


# --------------------------------------------------------------------------- #
# gravity:  d = 0.5 * g * t^2  ->  g = 2d/t^2 from examples, apply to query t
# --------------------------------------------------------------------------- #
def solve_gravity(p):
    pairs = [(float(t), float(d)) for t, d in re.findall(r"t\s*=\s*([0-9.]+)s,\s*distance\s*=\s*([0-9.]+)", p)]
    m = re.search(r"falling distance for t\s*=\s*([0-9.]+)s", p)
    if not pairs or not m:
        return None
    tq = float(m.group(1))
    gs = [2.0 * d / (t * t) for t, d in pairs if t]
    g = sum(gs) / len(gs)
    ans = round(0.5 * g * tq * tq, 2)
    t0, d0 = pairs[0]
    t1, d1 = pairs[1]
    cot = (
        "Use d = 0.5*g*t^2, so g = 2d/t^2. Estimate g from the examples:\n"
        f"  from t={t0}, d={d0}: g = 2*{d0}/{t0}^2 = {2 * d0 / (t0 * t0):.4f}\n"
        f"  from t={t1}, d={d1}: g = 2*{d1}/{t1}^2 = {2 * d1 / (t1 * t1):.4f}\n"
        f"  average g = {g:.4f}\n"
        f"For t={tq}: d = 0.5*{g:.4f}*{tq}^2 = {ans}\n"
        f"Final answer: \\boxed{{{ans}}}"
    )
    return f"{ans}", cot


# --------------------------------------------------------------------------- #
# unit conversion:  out = ratio * in  ->  fit ratio, apply to query
# --------------------------------------------------------------------------- #
def solve_unit(p):
    pairs = [(float(a), float(b)) for a, b in re.findall(r"([0-9.]+)\s*m becomes\s*([0-9.]+)", p)]
    m = re.search(r"convert the following measurement:\s*([0-9.]+)\s*m", p)
    if not pairs or not m:
        return None
    q = float(m.group(1))
    rs = [b / a for a, b in pairs if a]
    r = sum(rs) / len(rs)
    ans = round(q * r, 2)
    a0, b0 = pairs[0]
    cot = (
        "The conversion is a constant multiplier r = out/in. Estimate from examples:\n"
        f"  {b0}/{a0} = {b0 / a0:.5f}\n"
        f"  average r = {r:.5f}\n"
        f"Apply to {q}: {q} * {r:.5f} = {ans}\n"
        f"Final answer: \\boxed{{{ans}}}"
    )
    return f"{ans}", cot


# --------------------------------------------------------------------------- #
# cipher: char-level substitution recovered from aligned example word pairs
# --------------------------------------------------------------------------- #
def solve_cipher(p):
    mapping = {}
    for enc, plain in re.findall(r"^([^\n>]+?)\s*->\s*([^\n]+)$", p, re.M):
        ew, pw = enc.strip().split(), plain.strip().split()
        if len(ew) != len(pw):
            continue
        for cw, pwo in zip(ew, pw):
            if len(cw) != len(pwo):
                return None  # not a clean char-aligned substitution
            for ce, cp in zip(cw, pwo):
                if mapping.get(ce, cp) != cp:
                    return None  # inconsistent map
                mapping[ce] = cp
    m = re.search(r"decrypt the following text:\s*([^\n]+)", p, re.I)
    if not mapping or not m:
        return None
    q = m.group(1).strip()
    if any(c != " " and c not in mapping for c in q):
        return None  # query needs a symbol we never learned
    decoded = "".join(" " if c == " " else mapping[c] for c in q)
    table = ", ".join(f"{k}->{v}" for k, v in sorted(mapping.items()))
    cot = (
        "Build a fixed character substitution from the aligned example pairs:\n"
        f"  {table}\n"
        f"Decode '{q}' character by character → '{decoded}'.\n"
        f"Final answer: \\boxed{{{decoded}}}"
    )
    return decoded, cot


# --------------------------------------------------------------------------- #
# bit: bounded candidate-function enumeration (single op + structural∘mask 2-op)
# --------------------------------------------------------------------------- #
def _rotl(x, k):
    return ((x << k) | (x >> (8 - k))) & 0xFF


def _rotr(x, k):
    return ((x >> k) | (x << (8 - k))) & 0xFF


def _revbits(x):
    return int(f"{x:08b}"[::-1], 2)


def _swapnib(x):
    return ((x & 0x0F) << 4) | ((x >> 4) & 0x0F)


def _structural_ops():
    ops = [
        ("identity", lambda x: x),
        ("NOT", lambda x: (~x) & 0xFF),
        ("reverse_bits", _revbits),
        ("swap_nibbles", _swapnib),
    ]
    for k in range(1, 8):
        ops.append((f"SHL {k}", lambda x, k=k: (x << k) & 0xFF))
        ops.append((f"SHR {k}", lambda x, k=k: x >> k))
        ops.append((f"ROTL {k}", lambda x, k=k: _rotl(x, k)))
        ops.append((f"ROTR {k}", lambda x, k=k: _rotr(x, k)))
    return ops


def _solve_mask(kind, ins, outs):
    """Solve a constant c s.t. (in OP c)==out for all pairs; return c or None."""
    c = 0
    for bit in range(8):
        col = [((i >> bit) & 1, (o >> bit) & 1) for i, o in zip(ins, outs)]
        if kind == "XOR":
            vals = {ib ^ ob for ib, ob in col}
            if len(vals) != 1:
                return None
            c |= next(iter(vals)) << bit
        elif kind == "AND":
            cb = None
            for ib, ob in col:
                if ib == 1:
                    if cb is not None and cb != ob:
                        return None
                    cb = ob
                elif ob != 0:
                    return None
            c |= (1 if cb in (None, 1) else 0) << bit
        elif kind == "OR":
            cb = None
            for ib, ob in col:
                if ib == 0:
                    if cb is not None and cb != ob:
                        return None
                    cb = ob
                elif ob != 1:
                    return None
            c |= (1 if cb == 1 else 0) << bit
    return c


def solve_bit(p):
    ex = re.findall(r"([01]{8})\s*->\s*([01]{8})", p)
    m = re.search(r"determine the output for:\s*([01]{8})", p)
    if len(ex) < 2 or not m:
        return None
    ins = [int(a, 2) for a, _ in ex]
    outs = [int(b, 2) for _, b in ex]
    q = int(m.group(1), 2)
    structural = _structural_ops()

    def chain_label_apply(label, fn):
        return label, fn

    candidates = []
    # 1-op
    for name, fn in structural:
        candidates.append((name, fn))
    for kind in ("XOR", "AND", "OR"):
        c = _solve_mask(kind, ins, outs)
        if c is not None:
            candidates.append(
                (
                    f"{kind} 0x{c:02X}",
                    lambda x, k=kind, cc=c: {"XOR": x ^ cc, "AND": x & cc, "OR": x | cc}[k] & 0xFF,
                )
            )
    # 2-op: structural then solved mask
    two = []
    for sname, sfn in structural:
        mid = [sfn(i) for i in ins]
        for kind in ("XOR", "AND", "OR"):
            c = _solve_mask(kind, mid, outs)
            if c is not None:
                two.append(
                    (
                        f"{sname} -> {kind} 0x{c:02X}",
                        lambda x, sf=sfn, k=kind, cc=c: (
                            {"XOR": sf(x) ^ cc, "AND": sf(x) & cc, "OR": sf(x) | cc}[k] & 0xFF
                        ),
                    )
                )
    # prefer the simplest consistent rule (1-op before 2-op)
    for label, fn in candidates + two:
        if all(fn(i) == o for i, o in zip(ins, outs)):
            ans = f"{fn(q) & 0xFF:08b}"
            cot = (
                "Compare the 8-bit pairs and search bitwise operations consistent with ALL examples.\n"
                f"The consistent rule is: {label}\n"
                f"Verify on {ins[0]:08b} -> {outs[0]:08b}: rule gives {fn(ins[0]) & 0xFF:08b} ✓\n"
                f"Apply to {q:08b}: result {ans}\n"
                f"Final answer: \\boxed{{{ans}}}"
            )
            return ans, cot
    return None


# --------------------------------------------------------------------------- #
# equation (symbol rewrite):  A op B = result ; infer per-operator rewrite rule
# --------------------------------------------------------------------------- #
_REWRITES = {
    "concat_ab": lambda a, b: a + b,
    "concat_ba": lambda a, b: b + a,
    "rev_a_b": lambda a, b: a[::-1] + b,
    "a_rev_b": lambda a, b: a + b[::-1],
    "interleave": lambda a, b: "".join(x + y for x, y in zip(a.ljust(len(b)), b.ljust(len(a)))),
    "swap_inner": lambda a, b: (a[0] + b[0] + b[1] + a[1]) if len(a) == 2 and len(b) == 2 else None,
    "left_dup": lambda a, b: a + a,
    "right_dup": lambda a, b: b + b,
    "rev_concat": lambda a, b: (a + b)[::-1],
}


def _parse_eq_line(line):
    # "<A><op><B> = <result>"; operands are 2 chars, op is the middle char
    m = re.match(r"^\s*(\S.*?)\s*=\s*(\S.*?)\s*$", line)
    if not m:
        return None
    lhs, res = m.group(1), m.group(2)
    if len(lhs) != 5:  # 2 + 1 op + 2
        return None
    return lhs[:2], lhs[2], lhs[3:5], res


def solve_equation(p):
    lines = p.splitlines()
    examples = []
    for ln in lines:
        if "=" in ln and "->" not in ln and "result for" not in ln.lower():
            pe = _parse_eq_line(ln)
            if pe:
                examples.append(pe)
    mq = re.search(r"result for:\s*(\S+)", p)
    if len(examples) < 2 or not mq:
        return None
    qexpr = mq.group(1)
    if len(qexpr) != 5:
        return None
    qa, qop, qb = qexpr[:2], qexpr[2], qexpr[3:5]
    # infer rule per operator
    op_rule = {}
    for a, op, b, res in examples:
        ok = [name for name, fn in _REWRITES.items() if fn(a, b) == res]
        if not ok:
            return None
        op_rule[op] = op_rule.get(op, set(ok)) & set(ok) if op in op_rule else set(ok)
    if qop not in op_rule or not op_rule[qop]:
        return None
    rule = sorted(op_rule[qop])[0]
    ans = _REWRITES[rule](qa, qb)
    if ans is None:
        return None
    cot = (
        "Each operator maps two 2-char operands to a result by a fixed string rule.\n"
        f"From the examples, operator '{qop}' is consistent with rule '{rule}'.\n"
        f"Apply to A='{qa}', B='{qb}' → '{ans}'.\n"
        f"Final answer: \\boxed{{{ans}}}"
    )
    return ans, cot


SOLVERS = {
    "numeral": solve_numeral,
    "gravity": solve_gravity,
    "unit": solve_unit,
    "cipher": solve_cipher,
    "bit": solve_bit,
    "equation": solve_equation,
}

SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"


def solve_dataset(rows, categories=None):
    from collections import Counter

    total = Counter()
    solved = Counter()
    records = []
    for r in rows:
        cat = classify(r["prompt"])
        if cat not in SOLVERS:
            continue
        if categories and cat not in categories:
            continue
        total[cat] += 1
        try:
            out = SOLVERS[cat](r["prompt"])
        except Exception:
            out = None
        if not out:
            continue
        ans, cot = out
        if not verify(ans, r["answer"]):
            continue  # solver disagrees with ground truth → drop (no poison)
        solved[cat] += 1
        records.append(
            {
                "id": r["id"],
                "prompt": r["prompt"],
                "answer": str(r["answer"]).strip(),
                "cot": cot,
                "category": cat,
            }
        )
    cov = {c: (solved[c], total[c]) for c in total}
    return records, cov


if __name__ == "__main__":
    import csv
    import os

    tc = os.path.expanduser("~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv")
    rows = list(csv.DictReader(open(tc, encoding="utf-8")))
    recs, cov = solve_dataset(rows)
    print(f"train rows: {len(rows)}; verified solver records: {len(recs)}")
    print("coverage (solved/total) by category:")
    for c, (s, t) in sorted(cov.items()):
        print(f"  {c:10s} {s:5d}/{t:5d}  ({100 * s / t:.1f}%)")
    for c in ("bit", "equation", "cipher"):
        ex = next((r for r in recs if r["category"] == c), None)
        if ex:
            print(f"\n=== sample {c} (answer={ex['answer']}) ===\n{ex['cot'][:400]}")
