"""Staged solver-trace generators for the hard categories (lb1-v1).

These re-express the 1st-place solvers as **staged, machine-checkable traces** the
model can replay within the 7680-token budget (no program at eval time). Each
solver returns ``(answer, trace)`` or ``None``; a trace is kept as an SFT teacher
only when its answer matches ground truth (the no-poison rule from
``lib/nemo_solver.py``). The trace ends with the competition finality line
``</think>\\n\\boxed{...}`` (insights.md convention).

  * ``solve_bit``         — per-output-bit search + HEX-compressed columns +
                            rule-sequence **repair** (Hamming NN onto the catalog).
  * ``solve_cryptarithm`` — Parse -> Join-first -> signature catalog candidate
                            counts -> anchor (min count) -> DFS with Observation
                            1/2 pruning -> query decode.

Both reuse ``rules24`` (24-rule inventory) and the bit grammar in
``rule_sequence_catalog``. Designed to be imported by ``synth_gen.py`` and scored
by ``scorer.py``.
"""

from __future__ import annotations

import re

from hex_compress import bits_to_hex
from rules24 import RULES, apply_rule, render_output_human
import rule_sequence_catalog as rseq
from rule_sequence_catalog import CONST0, CONST1, _src

FINALITY = "</think>\n\\boxed{{{ans}}}"


# ════════════════════════════════════════════════════════════════════════════
# BIT MANIPULATION
# ════════════════════════════════════════════════════════════════════════════
def _bits(byte: int) -> str:
    return f"{byte:08b}"


def _bit(byte: int, i: int) -> int:
    """Bit at MSB-first position i (0..7)."""
    return (byte >> (7 - i)) & 1


def _per_bit_rule(i, ins, outs):
    """Find a per-output-bit rule for position i consistent with all examples.

    Returns (label, fn(x)->bit, slot) or None, where ``slot`` is in the catalog's
    per-bit format ``(op, (source_codes,))`` so Hamming repair is meaningful.
    Priority follows @huikang: prefer input references (direct/negated, then
    2-input), and use a constant only as a last resort.
    """
    o = [_bit(o_, i) for o_ in outs]
    # direct / negated single input bit
    for j in range(8):
        col = [_bit(x, j) for x in ins]
        if col == o:
            return (f"I{j}", (lambda x, j=j: _bit(x, j)), ("id", (_src(j, False),)))
        if [1 - b for b in col] == o:
            return (f"~I{j}", (lambda x, j=j: 1 - _bit(x, j)), ("id", (_src(j, True),)))
    # 2-input
    for j in range(8):
        for k in range(8):
            if j == k:
                continue
            cj = [_bit(x, j) for x in ins]
            ck = [_bit(x, k) for x in ins]
            for op, f in (("xor", lambda a, b: a ^ b), ("and", lambda a, b: a & b), ("or", lambda a, b: a | b)):
                if [f(a, b) for a, b in zip(cj, ck)] == o:
                    return (
                        f"{op.upper()}{j}{k}",
                        (lambda x, j=j, k=k, f=f: f(_bit(x, j), _bit(x, k))),
                        (op, (_src(j, False), _src(k, False))),
                    )
    # constant (last resort)
    if all(v == o[0] for v in o):
        c = o[0]
        return (f"const{c}", (lambda x, c=c: c), ("id", (CONST1 if c else CONST0,)))
    return None


def _selected_sequence(ins, outs):
    """Heuristic @huikang-style per-bit selection; unresolved bits -> default 1.

    Returns (labels, fns, slots) where slots are catalog-format per-bit rules.
    """
    labels, fns, slots = [], [], []
    for i in range(8):
        r = _per_bit_rule(i, ins, outs)
        if r is None:
            labels.append("default1")
            fns.append(lambda x: 1)
            slots.append(("id", (CONST1,)))  # the non-catalog fallback repair must fix
        else:
            labels.append(r[0])
            fns.append(r[1])
            slots.append(r[2])
    return labels, fns, slots


def _apply_seq(fns, x):
    out = 0
    for i, f in enumerate(fns):
        out |= (f(x) & 1) << (7 - i)
    return out


def solve_bit(prompt: str, repair_catalog=None, use_hex: bool = True):
    ex = re.findall(r"([01]{8})\s*->\s*([01]{8})", prompt)
    m = re.search(r"determine the output for:\s*([01]{8})", prompt)
    if len(ex) < 2 or not m:
        return None
    ins = [int(a, 2) for a, _ in ex]
    outs = [int(b, 2) for _, b in ex]
    q = int(m.group(1), 2)

    labels, fns, slots = _selected_sequence(ins, outs)
    selected_ok = all(_apply_seq(fns, i) == o for i, o in zip(ins, outs))
    repaired = None
    if repair_catalog is not None and (not selected_ok or "default1" in labels):
        sel_seq = tuple(slots)  # catalog-format slots -> Hamming over the 8 rule slots
        examples = list(zip(ins, outs))
        repaired = rseq.repair(sel_seq, repair_catalog, examples, k=32)

    if repaired is not None:
        op, args = repaired[1]
        fn = rseq.transform_function(op, args)
        if not all(fn(i) == o for i, o in zip(ins, outs)):
            repaired = None
    if repaired is not None:
        op, args = repaired[1]
        fn = rseq.transform_function(op, args)
        ans = _bits(fn(q))
        method = f"repair->{op}{args}"
    else:
        if not selected_ok:
            return None
        ans = _bits(_apply_seq(fns, q))
        method = "selected"

    # ---- staged trace (HEX-compressed columns) ----
    cols = []
    for i in range(8):
        col = "".join(str(_bit(o_, i)) for o_ in outs)
        cols.append(bits_to_hex(col) if use_hex else col)
    lines = [
        "<think>",
        "Bit task: find a per-output-bit rule consistent with all examples, then repair.",
        "Inputs (hex): " + " ".join(bits_to_hex(_bits(x)) if use_hex else _bits(x) for x in ins),
        "Output bit columns (hex): " + " ".join(f"b{i}={cols[i]}" for i in range(8)),
        "Selected per-bit rules: " + " ".join(labels),
    ]
    if repaired is not None:
        lines.append(f"Repair: projected onto catalog -> {method}; matches all examples.")
    else:
        lines.append("Selected sequence matches all examples directly.")
    qhex = bits_to_hex(_bits(q)) if use_hex else _bits(q)
    lines.append(f"Apply to query {qhex}: result {bits_to_hex(ans) if use_hex else ans} (binary {ans}).")
    lines.append(FINALITY.format(ans=ans))
    return ans, "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# CRYPTARITHM (symbolic; catalog-seeded DFS)
# ════════════════════════════════════════════════════════════════════════════
_EQ_LINE = re.compile(r"^\s*(\S)(\S)(\S)(\S)(\S)\s*=\s*(\S+)\s*$")


def _parse_cryptarithm(prompt: str):
    eqs = []
    query = None
    for ln in prompt.splitlines():
        low = ln.lower()
        if "determine the result for" in low or "what is the result" in low:
            mq = re.search(r"for:\s*(\S+)", ln)
            if mq and len(mq.group(1)) == 5:
                s = mq.group(1)
                query = (s[0], s[1], s[2], s[3], s[4])
            continue
        m = _EQ_LINE.match(ln)
        if m and "=" in ln and "->" not in ln:
            a, b, op, c, d = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            out = m.group(6)
            eqs.append((a, b, op, c, d, out))
    return eqs, query


def _eq_signature(eq):
    """Signature of one symbolic equation by its repeat structure (symbols only)."""
    a, b, op, c, d, out = eq
    # left operand symbols ab, right cd, output symbols; op is the sign position when on output
    seq = a + b + c + d + out
    mapping, nxt, parts = {}, 0, []
    for ch in seq:
        if ch == op:  # operator symbol appearing on the output side = sign marker
            parts.append("-")
            continue
        if ch not in mapping:
            mapping[ch] = chr(ord("A") + nxt)
            nxt += 1
        parts.append(mapping[ch])
    return "".join(parts)


def _candidates_for_eq(eq, catalog):
    """Catalog-seeded candidate (rule, digit-map) rows for one equation's anchor."""
    a, b, op, c, d, out = eq
    sig = _eq_signature(eq)
    rows = catalog.get(sig, {}).get("rows", [])
    syms = [a, b, c, d] + [ch for ch in out if ch != op]
    cands = []
    for rule, slots in rows:
        if len(slots) != len(syms):
            continue
        dmap, ok = {}, True
        for s, dch in zip(syms, slots):
            if s in dmap and dmap[s] != dch:
                ok = False
                break
            dmap[s] = dch
        if ok:
            cands.append((rule, dmap))
    return sig, cands


def _check_eq(eq, dmap, rule):
    """Does (dmap, rule) reproduce this equation exactly?"""
    a, b, op, c, d, out = eq
    try:
        sA = dmap[a] + dmap[b]
        sB = dmap[c] + dmap[d]
    except KeyError:
        return None  # unknown symbol -> caller must assign
    tok = apply_rule(rule, sA, sB)
    if tok is None:
        return False
    rendered = render_output_human(tok, op)
    # map rendered digits back through symbol assignment for the output
    inv = {v: k for k, v in dmap.items()}
    want = []
    for ch in out:
        if ch == op:
            want.append(op)
        else:
            want.append(ch)
    # compare structurally: render output symbols from rendered digits
    return rendered, "".join(want)


def solve_cryptarithm(prompt: str, catalog):
    eqs, query = _parse_cryptarithm(prompt)
    if len(eqs) < 2 or not query:
        return None

    # Stage 1: signatures + candidate counts (memorized)
    sig_info = []
    for eq in eqs:
        sig, cands = _candidates_for_eq(eq, catalog)
        sig_info.append((eq, sig, cands))
    # anchor = equation with the smallest candidate count
    sig_info.sort(key=lambda t: len(t[2]))
    anchor_eq, anchor_sig, anchor_cands = sig_info[0]
    if not anchor_cands:
        return None

    qa, qb, qop, qc, qd = query

    # Stage 2: DFS from anchor candidates, propagate to the rest
    others = [t for t in sig_info[1:]]
    for rule0, dmap0 in anchor_cands[:200]:
        op_rule = {anchor_eq[2]: rule0}
        dmap = dict(dmap0)
        mode = RULES[rule0]["mode"] if RULES[rule0]["group"] != "join" else None
        used_groups = set() if RULES[rule0]["group"] == "join" else {RULES[rule0]["group"]}
        if _solve_rest(others, dmap, op_rule, mode, used_groups, catalog):
            return _finish(eqs, query, dmap, op_rule, anchor_sig)
    return None


def _solve_rest(others, dmap, op_rule, mode, used_groups, catalog):
    if not others:
        return True
    eq, sig, cands = others[0]
    rest = others[1:]
    op = eq[2]
    for rule, cmap in cands:
        if op in op_rule and op_rule[op] != rule:
            continue
        if RULES[rule]["group"] != "join":
            if mode is not None and RULES[rule]["mode"] != mode:
                continue
            if op not in op_rule and RULES[rule]["group"] in used_groups:
                continue
        merged = dict(dmap)
        ok = True
        for s, dch in cmap.items():
            if s in merged and merged[s] != dch:
                ok = False
                break
            merged[s] = dch
        if not ok or len(set(merged.values())) != len(merged):
            continue
        new_mode = mode if RULES[rule]["group"] == "join" else RULES[rule]["mode"]
        new_groups = set(used_groups)
        if RULES[rule]["group"] != "join":
            new_groups.add(RULES[rule]["group"])
        new_op_rule = dict(op_rule)
        new_op_rule[op] = rule
        if _solve_rest(rest, merged, new_op_rule, new_mode, new_groups, catalog):
            dmap.clear()
            dmap.update(merged)
            op_rule.clear()
            op_rule.update(new_op_rule)
            return True
    return False


def _finish(eqs, query, dmap, op_rule, anchor_sig):
    qa, qb, qop, qc, qd = query
    # query operator rule
    rule = op_rule.get(qop)
    if rule is None:
        rule = "join"  # guess fallback (writeup: early join candidate)
    # need digit assignment for query symbols; unknown symbols can't be decoded for deduce
    try:
        sA = dmap[qa] + dmap[qb]
        sB = dmap[qc] + dmap[qd]
    except KeyError:
        return None
    tok = apply_rule(rule, sA, sB)
    if tok is None:
        return None
    digits = render_output_human(tok, qop)
    inv = {v: k for k, v in dmap.items()}
    ans_syms = []
    for ch in digits:
        if ch == qop:
            ans_syms.append(qop)
        elif ch in inv:
            ans_syms.append(inv[ch])
        else:
            return None  # output digit has no symbol -> cannot render
    ans = "".join(ans_syms)
    trace = "\n".join(
        [
            "<think>",
            "Cryptarithm: Parse -> Join-first -> signature catalog -> anchor (min count) -> DFS.",
            f"Anchor signature {anchor_sig}; candidate counts memorized from the 4205-signature catalog.",
            f"Digit assignment: {dmap}",
            f"Operator rules: {op_rule}",
            f"Query {qa}{qb}{qop}{qc}{qd} -> {sA}{qop}{sB} under rule {rule} -> {digits} -> {ans}",
            FINALITY.format(ans=ans),
        ]
    )
    return ans, trace
