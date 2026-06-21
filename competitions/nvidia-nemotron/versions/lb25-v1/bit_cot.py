"""Reorganized, own-solver-verified bit-manipulation CoT (lb25-v1 — LB25 lever #5).

LB25 change #5 restructures the bit trace for clarity. We keep the realized
v16-evalfix bit solver (the LB25-borrow kernel that actually ran): bounded search
over single structural ops (shift / rotate / NOT / bit-reverse / nibble-swap /
XOR·AND·OR with a constant) and structural∘mask 2-ops, then a **reorganized CoT**
that prints the search → full per-example verification → apply-to-query → boxed.

Only grader-faithful traces are kept: `bit_verify` is the official metric's
leading-zero-aware check (`01000011` != `1000011`), so a row is used as an SFT
teacher only when the solver's answer matches gold under the SAME check the grader
uses — the LB25/INS-002 discipline (v16-evalfix's stricter `_bit_verify` dropped a
poison row the lib's lax numeric check had kept).

`bit_solve(prompt) -> (answer_8bit, reorganized_cot) | None`; `bit_verify(pred, gt)`.
"""

from __future__ import annotations

import math
import re


def _rotl(x, k):
    return ((x << k) | (x >> (8 - k))) & 0xFF


def _rotr(x, k):
    return ((x >> k) | (x << (8 - k))) & 0xFF


def _structural_ops():
    ops = [
        ("identity", lambda x: x),
        ("NOT", lambda x: (~x) & 0xFF),
        ("reverse_bits", lambda x: int(f"{x:08b}"[::-1], 2)),
        ("swap_nibbles", lambda x: ((x & 0x0F) << 4) | ((x >> 4) & 0x0F)),
    ]
    for k in range(1, 8):
        ops.append((f"SHL {k}", lambda x, k=k: (x << k) & 0xFF))
        ops.append((f"SHR {k}", lambda x, k=k: x >> k))
        ops.append((f"ROTL {k}", lambda x, k=k: _rotl(x, k)))
        ops.append((f"ROTR {k}", lambda x, k=k: _rotr(x, k)))
    return ops


def _solve_mask(kind, ins, outs):
    """Constant c s.t. (in OP c) == out for all pairs, per output bit; or None."""
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


def bit_solve(prompt):
    """Return (answer_8bit_str, reorganized_cot) if a consistent rule is found, else None."""
    ex = re.findall(r"([01]{8})\s*->\s*([01]{8})", prompt)
    m = re.search(r"determine the output for:\s*([01]{8})", prompt)
    if len(ex) < 2 or not m:
        return None
    ins = [int(a, 2) for a, _ in ex]
    outs = [int(b, 2) for _, b in ex]
    q = int(m.group(1), 2)
    structural = _structural_ops()

    candidates = list(structural)
    for kind in ("XOR", "AND", "OR"):
        c = _solve_mask(kind, ins, outs)
        if c is not None:
            candidates.append(
                (f"{kind} 0x{c:02X}", lambda x, k=kind, cc=c: {"XOR": x ^ cc, "AND": x & cc, "OR": x | cc}[k] & 0xFF)
            )
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
    for label, fn in candidates + two:
        if all(fn(i) == o for i, o in zip(ins, outs)):
            ans = f"{fn(q) & 0xFF:08b}"
            checks = "\n".join(
                f"  {i:08b} -> {o:08b}: rule gives {fn(i) & 0xFF:08b} {'OK' if (fn(i) & 0xFF) == o else 'X'}"
                for i, o in zip(ins, outs)
            )
            cot = (
                "Treat each line as an 8-bit input -> output pair and search for one bitwise rule "
                "consistent with EVERY pair. Try single operations (shifts, rotations, NOT, bit-reverse, "
                "nibble-swap, or XOR/AND/OR with a constant); if none fits, try a structural op followed "
                "by a mask.\n"
                f"The unique rule consistent with all {len(ins)} examples is: {label}\n"
                "Verify it on each example:\n"
                f"{checks}\n"
                f"All examples match, so apply the rule to the query {q:08b}: {ans}\n"
                f"Final answer: \\boxed{{{ans}}}"
            )
            return ans, cot
    return None


_LZ = re.compile(r"0\d+")


def bit_verify(pred, gt):
    """Official-metric verify: leading-zero binary string-matched; else numeric 1e-2; else string."""
    pred = str(pred).strip()
    gt = str(gt).strip()
    if not _LZ.fullmatch(gt) and not _LZ.fullmatch(pred):
        try:
            return math.isclose(float(pred), float(gt), rel_tol=1e-2, abs_tol=1e-5)
        except (ValueError, TypeError):
            pass
    return pred.lower() == gt.lower()


if __name__ == "__main__":
    # a determined transform (XOR 0xFF = NOT) so the search is unambiguous
    ins = [0b00010101, 0b11000101, 0b10100010, 0b00111111]
    prompt = (
        "8-bit binary numbers. Here are some examples of input -> output:\n"
        + "\n".join(f"{i:08b} -> {(~i) & 0xFF:08b}" for i in ins)
        + "\nNow, determine the output for: 01101001"
    )
    out = bit_solve(prompt)
    assert out is not None and out[0] == f"{(~0b01101001) & 0xFF:08b}", out
    assert bit_verify(out[0], out[0]) and not bit_verify("1000011", "01000011")
    print("bit_cot self-check OK; answer:", out[0])
    print(out[1][:200])
