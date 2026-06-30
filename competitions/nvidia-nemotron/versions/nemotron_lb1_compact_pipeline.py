#!/usr/bin/env python3
"""
Compact LB1-inspired pipeline for the NVIDIA Nemotron Model Reasoning Challenge.

One-file, practical scaffold that turns train.csv + optional verified synthetic
examples into SFT records, optionally trains a rank<=32 LoRA adapter, and packages
submission.zip.  It deliberately borrows the high-value ideas from the 1st-place
writeup and the lb3-v1 code archive:

  * solver-generated traces, not free-form LLM traces;
  * equation / cryptarithm 24-rule inventory;
  * cryptarithm signature-catalog narration and DFS-style trace shape;
  * bit manipulation HEX-compressed column traces and repair-style final answer;
  * response-only SFT labels and root-level adapter zip packaging.

This is not a byte-for-byte reproduction of the 1st-place system: the original
used very large corpora and long RTX PRO 6000 training.  This file is intended as
an auditable, concise starting point that Claude Code can extend into a stronger
repo implementation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

BOX_RE = re.compile(r"\\boxed\{([^{}]*)\}")
PROMPT_SUFFIX = (
    "\n\nPlease infer the hidden rule from the examples. Think step by step, "
    "then put the final answer inside \\boxed{} only once."
)


def boxed(answer: str) -> str:
    return f"\\boxed{{{str(answer).strip()}}}"


def final_trace(lines: Sequence[str], answer: str) -> str:
    body = "\n".join(str(x) for x in lines if str(x).strip() != "")
    return f"<think>\n{body}\n</think>\n{boxed(answer)}"


def read_train_csv(path: str | Path, max_rows: int = 0) -> List[dict]:
    rows: List[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "prompt" not in row or "answer" not in row:
                raise ValueError("train.csv must contain prompt and answer columns")
            rows.append(row)
            if max_rows and len(rows) >= max_rows:
                break
    return rows


def classify_prompt(prompt: str) -> str:
    p = prompt.lower()
    if "bit manipulation" in p or "8-bit binary" in p:
        return "bit"
    if "secret encryption" in p or "decrypt" in p:
        return "cipher"
    if "wonderland numeral" in p or "different numeral system" in p:
        return "numeral"
    if "unit conversion" in p or "convert the following measurement" in p:
        return "unit"
    if "gravitational constant" in p or "0.5*g*t^2" in p:
        return "gravity"
    if "transformation rules is applied to equations" in p:
        # numeric rows contain two literal digits before/after the operator.
        if re.search(r"^\s*\d{2}\S\d{2}\s*=", prompt, flags=re.M):
            return "equation_numeric"
        return "cryptarithm"
    return "unknown"


def maybe_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Roman / unit / gravity / cipher traces
# ---------------------------------------------------------------------------

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


def roman(n: int) -> str:
    out: List[str] = []
    for value, token in _ROMAN:
        while n >= value:
            out.append(token)
            n -= value
    return "".join(out)


def trace_numeral(prompt: str, answer: str) -> str:
    m = re.search(r"write the number\s+(\d+)", prompt, flags=re.I)
    if not m:
        return final_trace(
            ["The examples show Roman-numeral composition.", "Apply the same system to the query."], answer
        )
    n = int(m.group(1))
    parts = []
    rem = n
    for value, token in _ROMAN:
        if rem >= value:
            k, rem = divmod(rem, value)
            parts.append(f"{value}*{k}->{token * k}")
    return final_trace([f"Roman place-value decomposition for {n}: " + "; ".join(parts), f"result={roman(n)}"], answer)


def trace_unit(prompt: str, answer: str) -> str:
    pairs = [(float(a), float(b)) for a, b in re.findall(r"([0-9.]+)\s*m\s+becomes\s+([0-9.]+)", prompt)]
    mt = re.search(r"following measurement:\s*([0-9.]+)\s*m", prompt, flags=re.I)
    if not pairs or not mt:
        return final_trace(
            ["Estimate the constant unit-conversion coefficient from examples.", "Apply it to the query."], answer
        )
    ratios = [b / a for a, b in pairs if a]
    coeff = sum(ratios) / len(ratios)
    target = float(mt.group(1))
    pred = target * coeff
    lines = [
        "Compute output/input for each example: " + ", ".join(f"{b}/{a}={b / a:.5f}" for a, b in pairs[:5] if a),
        f"coefficient≈{coeff:.5f}",
        f"query {target:g}*{coeff:.5f}≈{pred:.2f}",
    ]
    return final_trace(lines, answer)


def trace_gravity(prompt: str, answer: str) -> str:
    pairs = [
        (float(t), float(d)) for t, d in re.findall(r"For t\s*=\s*([0-9.]+)s, distance\s*=\s*([0-9.]+)\s*m", prompt)
    ]
    mt = re.search(r"falling distance for t\s*=\s*([0-9.]+)s", prompt, flags=re.I)
    if not pairs or not mt:
        return final_trace(["Use d=0.5*g*t^2. Estimate g from examples and apply to query."], answer)
    gs = [2 * d / (t * t) for t, d in pairs if t]
    g = sum(gs) / len(gs)
    t = float(mt.group(1))
    pred = 0.5 * g * t * t
    lines = [
        "For each example, g=2*d/t^2: " + ", ".join(f"{v:.4f}" for v in gs[:5]),
        f"average g≈{g:.4f}",
        f"query d=0.5*{g:.4f}*{t:g}^2≈{pred:.2f}",
    ]
    return final_trace(lines, answer)


def trace_cipher(prompt: str, answer: str) -> str:
    word_map: Dict[str, str] = {}
    char_map: Dict[str, str] = {}
    for left, right in re.findall(r"^([^\n>-][^\n]*?)\s*->\s*([^\n]+)$", prompt, flags=re.M):
        lw, rw = left.strip().split(), right.strip().split()
        if len(lw) != len(rw):
            continue
        for a, b in zip(lw, rw):
            word_map[a] = b
            if len(a) == len(b):
                for ca, cb in zip(a, b):
                    char_map.setdefault(ca, cb)
    q = re.search(r"decrypt the following text:\s*([^\n]+)", prompt, flags=re.I)
    query = q.group(1).strip().split() if q else []
    decoded = []
    for w in query:
        if w in word_map:
            decoded.append(word_map[w])
        else:
            decoded.append("".join(char_map.get(c, "?") for c in w))
    lines = [
        f"Align example sentences word by word; collect {len(word_map)} word mappings and {len(char_map)} character mappings.",
        "Decode query words left to right: " + " ".join(f"{a}->{b}" for a, b in zip(query, decoded)),
        "Use the restricted train-side vocabulary and consistency when a character is still unknown.",
    ]
    return final_trace(lines, answer)


# ---------------------------------------------------------------------------
# 24-rule inventory for equation numeric and cryptarithm
# ---------------------------------------------------------------------------

SIGN = "#"  # output-side sign/op marker sentinel


def _rev_str(n: int) -> str:
    return str(abs(int(n)))[::-1]


def _digits(value: int, prefix: bool = False, suffix: bool = False, only_nonzero: bool = False) -> str:
    neg = value < 0
    body = str(abs(value))
    if neg:
        body = SIGN + body
    if (prefix or suffix) and (abs(value) != 0 or not only_nonzero):
        body = (SIGN + body) if prefix else (body + SIGN)
    return body


def _rev_signed(value: int, prefix_if_neg: bool = False, suffix_if_neg: bool = False) -> str:
    neg = value < 0
    body = _rev_str(value)
    if neg:
        if prefix_if_neg:
            return SIGN + body
        if suffix_if_neg:
            return body + SIGN
        return SIGN + body
    return body


def _mk_rules24() -> Dict[str, dict]:
    R: Dict[str, dict] = {}

    def reg(name: str, group: str, mode: str, fn: Callable[[int, int, int, int, str, str], Optional[str]]):
        R[name] = {"group": group, "mode": mode, "fn": fn}

    reg("join", "join", "join", lambda AB, CD, BA, DC, sA, sB: sA + sB)
    reg("join_swap", "join", "join", lambda AB, CD, BA, DC, sA, sB: sB + sA)
    reg("add", "add", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB + CD))
    reg("add+1", "add", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB + CD + 1))
    reg("add-1", "add", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB + CD - 1))
    reg("flip_add", "add", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA + DC))
    reg("flip_add+1", "add", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA + DC + 1))
    reg("flip_add-1", "add", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA + DC - 1) if BA + DC - 1 >= 0 else None)
    reg("sub", "sub", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB - CD))
    reg("absdiff", "sub", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(abs(AB - CD)))
    reg(
        "absdiff_prefix",
        "sub",
        "normal",
        lambda AB, CD, BA, DC, sA, sB: _digits(abs(AB - CD), prefix=True, only_nonzero=True),
    )
    reg(
        "maxmodmin",
        "sub",
        "normal",
        lambda AB, CD, BA, DC, sA, sB: None if min(AB, CD) == 0 else _digits(max(AB, CD) % min(AB, CD)),
    )
    reg("flip_sub_prefix", "sub", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_signed(BA - DC, prefix_if_neg=True))
    reg("flip_sub_suffix", "sub", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_signed(DC - BA, suffix_if_neg=True))
    reg("flip_absdiff", "sub", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(abs(BA - DC)))
    reg(
        "flip_absdiff_prefix",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: (SIGN + _rev_str(abs(BA - DC))) if abs(BA - DC) else "0",
    )
    reg(
        "flip_absdiff_suffix",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: (_rev_str(abs(BA - DC)) + SIGN) if abs(BA - DC) else "0",
    )
    reg(
        "flip_maxmodmin",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: None if min(BA, DC) == 0 else _rev_str(max(BA, DC) % min(BA, DC)),
    )
    reg("mul", "mul", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB * CD))
    reg("mul+1", "mul", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB * CD + 1))
    reg("mul-1", "mul", "normal", lambda AB, CD, BA, DC, sA, sB: _digits(AB * CD - 1))
    reg("flip_mul", "mul", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA * DC))
    reg("flip_mul+1", "mul", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA * DC + 1))
    reg("flip_mul-1", "mul", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA * DC - 1) if BA * DC - 1 >= 0 else None)
    return R


RULES24 = _mk_rules24()
JOIN_RULES = ("join", "join_swap")
NON_JOIN_RULES = tuple(k for k in RULES24 if k not in JOIN_RULES)


def apply24(name: str, a2: str, b2: str) -> Optional[str]:
    AB, CD = int(a2), int(b2)
    BA, DC = int(a2[::-1]), int(b2[::-1])
    return RULES24[name]["fn"](AB, CD, BA, DC, a2, b2)


def render_out(out: Optional[str], op: str) -> Optional[str]:
    if out is None:
        return None
    return out.replace(SIGN, op)


def norm_sig(seq: str, sign_chars: Iterable[str] = ()) -> str:
    sign_set = set(sign_chars)
    mp: Dict[str, str] = {}
    nxt = 0
    out = []
    for ch in seq:
        if ch in sign_set or ch == SIGN:
            out.append("-")
            continue
        if ch not in mp:
            mp[ch] = chr(ord("A") + nxt)
            nxt += 1
        out.append(mp[ch])
    return "".join(out)


def build_signature_catalog(row_cap: int = 64) -> Dict[str, List[Tuple[str, str]]]:
    """Precompute one-equation signatures from all 00..99 x 00..99 pairs.

    This mirrors the LB1 cryptarithm idea in compact form: train the model to
    recall that a symbolic signature has only a limited candidate set, then let
    the trace narrate DFS consistency checks for the remaining equations.
    """
    cat: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for a in range(100):
        sa = f"{a:02d}"
        for b in range(100):
            sb = f"{b:02d}"
            for rule in NON_JOIN_RULES:
                y = apply24(rule, sa, sb)
                if y is None:
                    continue
                sig = norm_sig(sa + sb + y, sign_chars={SIGN})
                slots = "".join(ch for ch in (sa + sb + y) if ch.isdigit())
                if len(cat[sig]) < row_cap:
                    cat[sig].append((rule, slots))
    return dict(cat)


_SIG_CATALOG: Optional[Dict[str, List[Tuple[str, str]]]] = None


def sig_catalog() -> Dict[str, List[Tuple[str, str]]]:
    global _SIG_CATALOG
    if _SIG_CATALOG is None:
        _SIG_CATALOG = build_signature_catalog()
    return _SIG_CATALOG


# ---------------------------------------------------------------------------
# Equation numeric traces
# ---------------------------------------------------------------------------


def parse_numeric_equations(prompt: str) -> Tuple[List[Tuple[str, str, str, str]], Optional[Tuple[str, str, str]]]:
    rows: List[Tuple[str, str, str, str]] = []
    for line in prompt.splitlines():
        m = re.match(r"^\s*(\d{2})(\S)(\d{2})\s*=\s*(\S+)\s*$", line)
        if m:
            rows.append(m.groups())
    mq = re.search(r"result for:\s*(\d{2})(\S)(\d{2})", prompt, flags=re.I)
    return rows, (mq.groups() if mq else None)


def trace_equation_numeric(prompt: str, answer: str) -> str:
    rows, query = parse_numeric_equations(prompt)
    by_op: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    for a, op, b, y in rows:
        by_op[op].append((a, b, y))
    lines = ["Parse each row as AB op CD = output."]
    resolved: Dict[str, List[str]] = {}
    used_groups: set = set()
    used_modes: set = set()
    for op, exs in by_op.items():
        cands = []
        for rule in RULES24:
            if all(render_out(apply24(rule, a, b), op) == y for a, b, y in exs):
                cands.append(rule)
        resolved[op] = cands
        if cands:
            r0 = cands[0]
            used_groups.add(RULES24[r0]["group"])
            used_modes.add(RULES24[r0]["mode"])
        lines.append(f"op {op}: candidates={cands[:8]}{'...' if len(cands) > 8 else ''}")
    lines.append("Use LB1 constraints: non-join operators share mode; non-join groups usually do not repeat.")
    if query:
        a, op, b = query
        if op in resolved and resolved[op]:
            rule = resolved[op][0]
            y = render_out(apply24(rule, a, b), op)
            lines.append(f"query operator {op} is seen; apply {rule}: {a}{op}{b}->{y}")
        else:
            lines.append(
                f"query operator {op} is unseen; infer from remaining mode/group priors and train-frequency priority."
            )
    return final_trace(lines, answer)


# ---------------------------------------------------------------------------
# Cryptarithm traces
# ---------------------------------------------------------------------------


def parse_symbolic_equations(prompt: str) -> Tuple[List[Tuple[str, str, str, str]], Optional[Tuple[str, str, str]]]:
    rows: List[Tuple[str, str, str, str]] = []
    for line in prompt.splitlines():
        if "=" not in line or "Now" in line or "content_copy" in line:
            continue
        left, right = line.split("=", 1)
        left, right = left.strip(), right.strip()
        if len(left) >= 5 and right and not re.search(r"[A-Za-z]", left + right):
            rows.append((left[:2], left[2], left[3:5], right.split()[0]))
    mq = re.search(r"result for:\s*(\S+)", prompt, flags=re.I)
    q = None
    if mq:
        left = mq.group(1).strip()
        if len(left) >= 5:
            q = (left[:2], left[2], left[3:5])
    return rows, q


def sym_signature(a: str, op: str, b: str, out: str) -> str:
    return norm_sig(a + b + out, sign_chars={op})


def trace_cryptarithm(prompt: str, answer: str) -> str:
    rows, query = parse_symbolic_equations(prompt)
    cat = sig_catalog()
    lines = [
        "Parse each symbolic equation as two symbols, operator, two symbols, then output.",
        "First check join/join_swap. If not join, use the 24-rule inventory and signature catalog.",
    ]
    scored = []
    for i, (a, op, b, out) in enumerate(rows):
        sig = sym_signature(a, op, b, out)
        n = len(cat.get(sig, []))
        scored.append((n, i, sig))
        rows_preview = ", ".join(f"{r}:{slots}" for r, slots in cat.get(sig, [])[:4])
        lines.append(f"eq{i}: {a}{op}{b}={out} signature={sig} catalog_rows={n} {rows_preview}")
    if scored:
        n, i, sig = sorted(scored)[0]
        lines.append(f"Choose anchor eq{i} with smallest catalog row count ({n}); enumerate candidate digit/rule rows.")
    lines.append(
        "DFS: keep a bijection symbol->digit and a consistent operator->rule assignment; reject mode/group contradictions."
    )
    if query:
        a, op, b = query
        lines.append(f"Query {a}{op}{b}: apply the recovered rule and map numeric digits back to symbols.")
    lines.append("If a short early join candidate exists, keep it as fallback, then replace it if DFS finishes.")
    return final_trace(lines, answer)


# ---------------------------------------------------------------------------
# Bit manipulation traces with HEX compression and repair narration
# ---------------------------------------------------------------------------


def bits_to_int(s: str) -> int:
    return int(s, 2)


def int_to_bits(x: int) -> str:
    return format(x & 255, "08b")


def col_hex(col_bits: str) -> str:
    width = max(1, math.ceil(len(col_bits) / 4))
    return f"{int(col_bits, 2):0{width}X}"


def parse_bit_prompt(prompt: str) -> Tuple[List[Tuple[str, str]], Optional[str]]:
    examples = re.findall(r"\b([01]{8})\s*->\s*([01]{8})\b", prompt)
    mq = re.search(r"(?:output for|result for):\s*([01]{8})", prompt, flags=re.I)
    return examples, (mq.group(1) if mq else None)


def _bit_at(s: str, i: int) -> int:
    return 1 if s[i] == "1" else 0


def bit_expr_candidates(examples: List[Tuple[str, str]], out_idx: int) -> List[str]:
    xs = [x for x, _ in examples]
    ys = [y[out_idx] for _, y in examples]

    def ok(fn: Callable[[str], int]) -> bool:
        return all(str(fn(x)) == y for x, y in zip(xs, ys))

    cands: List[str] = []
    for v in (0, 1):
        if ok(lambda x, v=v: v):
            cands.append(f"C{v}")
    for i in range(8):
        if ok(lambda x, i=i: _bit_at(x, i)):
            cands.append(f"I{i}")
        if ok(lambda x, i=i: 1 - _bit_at(x, i)):
            cands.append(f"~I{i}")
    for i in range(8):
        for j in range(8):
            if i == j:
                continue
            ops = [
                ("AND", lambda a, b: a & b),
                ("OR", lambda a, b: a | b),
                ("XOR", lambda a, b: a ^ b),
                ("XNOR", lambda a, b: 1 - (a ^ b)),
                ("AND-NOT", lambda a, b: a & (1 - b)),
                ("OR-NOT", lambda a, b: a | (1 - b)),
            ]
            for name, f in ops:
                if ok(lambda x, i=i, j=j, f=f: f(_bit_at(x, i), _bit_at(x, j))):
                    cands.append(f"{name}{i}{j}")
    # Small 3-input set: MAJ / PAR3 / choice-like proxy, enough to teach LB1 trace form.
    for i in range(8):
        for j in range(i + 1, 8):
            for k in range(j + 1, 8):
                if ok(lambda x, i=i, j=j, k=k: 1 if _bit_at(x, i) + _bit_at(x, j) + _bit_at(x, k) >= 2 else 0):
                    cands.append(f"MAJ{i}{j}{k}")
                if ok(lambda x, i=i, j=j, k=k: _bit_at(x, i) ^ _bit_at(x, j) ^ _bit_at(x, k)):
                    cands.append(f"PAR3{i}{j}{k}")
    return cands[:16]


def trace_bit(prompt: str, answer: str) -> str:
    examples, query = parse_bit_prompt(prompt)
    if not examples:
        return final_trace(["Infer the 8-bit transformation; use HEX-compressed columns to save token budget."], answer)
    lines = ["Use column-wise bit solving. Compress long bit columns as HEX to reduce token budget."]
    for label, idx_src in [("Output columns", 1), ("Input columns", 0)]:
        lines.append(label)
        for j in range(8):
            col = "".join(pair[idx_src][j] for pair in examples)
            lines.append(f"  {j}: {col}->{col_hex(col)}")
    seq = []
    for j in range(8):
        c = bit_expr_candidates(examples, j)
        seq.append(c[0] if c else "default1")
        if c:
            lines.append(f"match out{j}: {', '.join(c[:5])}")
        else:
            lines.append(f"match out{j}: none -> default1 before repair")
    lines.append("Selected local sequence: " + " ".join(seq))
    if any(s.startswith("default") for s in seq):
        lines.append(
            "Repair: project the selected 8-rule sequence to nearby valid catalog sequences and verify candidates against all examples."
        )
        lines.append("Use the first catalog candidate that matches every output bit; then apply it to the query.")
    if query:
        lines.append(f"Apply repaired sequence to query {query}; preserve all 8 bits including leading zeros.")
    return final_trace(lines, answer)


# ---------------------------------------------------------------------------
# Synthetic generators: verified small corpora to extend real train traces
# ---------------------------------------------------------------------------


def render_bit_prompt(examples: List[Tuple[str, str]], query: str) -> str:
    body = "\n".join(f"{x} -> {y}" for x, y in examples)
    return (
        "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers.\n"
        "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, NOT, majority, parity, or choice functions.\n"
        "Here are some examples of input -> output:\n" + body + f"\nNow, determine the output for: {query}"
    )


def rotl(x: int, k: int) -> int:
    k %= 8
    return ((x << k) | (x >> (8 - k))) & 255


def shl(x: int, k: int) -> int:
    return (x << k) & 255


def shr(x: int, k: int) -> int:
    return (x >> k) & 255


def synth_bit(rng: random.Random) -> Tuple[str, str, str]:
    bases = [
        ("not_rol1", lambda x: (~rotl(x, 1)) & 255),
        ("xor_rot", lambda x: x ^ rotl(x, 3)),
        ("or_not_shr", lambda x: x | ((~shr(x, 2)) & 255)),
        ("maj", lambda x: ((x & rotl(x, 1)) | (x & shr(x, 3)) | (rotl(x, 1) & shr(x, 3))) & 255),
        ("par3", lambda x: x ^ rotl(x, 2) ^ shr(x, 5)),
        (
            "sel_nand_xnor",
            lambda x: (
                (((~rotl(x, 1)) & ((~(shr(x, 3) & shl(x, 2))) & 255)) | (rotl(x, 1) & (~(shr(x, 3) ^ shl(x, 2)) & 255)))
                & 255
            ),
        ),
    ]
    _name, fn = rng.choice(bases)
    xs = rng.sample(range(256), 10)
    examples = [(int_to_bits(x), int_to_bits(fn(x))) for x in xs]
    q = rng.randrange(256)
    ans = int_to_bits(fn(q))
    p = render_bit_prompt(examples, int_to_bits(q))
    return p, ans, trace_bit(p, ans)


def synth_equation_numeric(rng: random.Random) -> Tuple[str, str, str]:
    glyphs = rng.sample(list("`~!@#$%^&*+/>?<\\|"), 3)
    rules = rng.sample(["join", "add", "sub", "absdiff", "mul", "flip_add", "flip_mul", "add+1", "mul-1"], 3)
    lines = [
        "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:"
    ]
    for g, r in zip(glyphs, rules):
        for _ in range(2):
            a, b = rng.randrange(10, 99), rng.randrange(10, 99)
            y = render_out(apply24(r, f"{a:02d}", f"{b:02d}"), g)
            if y is not None:
                lines.append(f"{a:02d}{g}{b:02d} = {y}")
    qg = rng.choice(glyphs)
    qa, qb = rng.randrange(10, 99), rng.randrange(10, 99)
    rule = rules[glyphs.index(qg)]
    ans = render_out(apply24(rule, f"{qa:02d}", f"{qb:02d}"), qg) or "0"
    lines.append(f"Now, determine the result for: {qa:02d}{qg}{qb:02d}")
    p = "\n".join(lines)
    return p, ans, trace_equation_numeric(p, ans)


def synth_cryptarithm(rng: random.Random) -> Tuple[str, str, str]:
    symbols = rng.sample(list("!@#$%^&*()_+-=[]{}|;:,.<>?/"), 12)
    digit_symbols = symbols[:10]
    op_symbols = symbols[10:]
    d2s = {str(d): digit_symbols[d] for d in range(10)}
    rules = rng.sample(["add", "flip_add", "mul", "flip_mul", "add+1", "mul-1"], 2)
    ops = op_symbols

    def enc_digits(s: str) -> str:
        return "".join(d2s[d] for d in s)

    lines = [
        "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:"
    ]
    examples = 0
    for op_sym, rule in zip(ops, rules):
        tries = 0
        while examples < 5 and tries < 200:
            tries += 1
            a, b = rng.randrange(10, 99), rng.randrange(10, 99)
            y = apply24(rule, f"{a:02d}", f"{b:02d}")
            if not y or SIGN in y or len(y) > 4:
                continue
            lines.append(f"{enc_digits(f'{a:02d}')}{op_sym}{enc_digits(f'{b:02d}')} = {enc_digits(y)}")
            examples += 1
            if examples >= 5:
                break
    qop = ops[0]
    rule = rules[0]
    while True:
        qa, qb = rng.randrange(10, 99), rng.randrange(10, 99)
        y = apply24(rule, f"{qa:02d}", f"{qb:02d}")
        if y and SIGN not in y and len(y) <= 4:
            break
    ans = enc_digits(y)
    lines.append(f"Now, determine the result for: {enc_digits(f'{qa:02d}')}{qop}{enc_digits(f'{qb:02d}')}")
    p = "\n".join(lines)
    return p, ans, trace_cryptarithm(p, ans)


def build_records(
    rows: List[dict], synthetic_per_cat: int = 0, seed: int = 42, include_answer_only: bool = True
) -> List[dict]:
    records: List[dict] = []
    for r in rows:
        prompt, answer = r["prompt"], str(r["answer"]).strip()
        cat = classify_prompt(prompt)
        if cat == "bit":
            trace = trace_bit(prompt, answer)
        elif cat == "equation_numeric":
            trace = trace_equation_numeric(prompt, answer)
        elif cat == "cryptarithm":
            trace = trace_cryptarithm(prompt, answer)
        elif cat == "cipher":
            trace = trace_cipher(prompt, answer)
        elif cat == "numeral":
            trace = trace_numeral(prompt, answer)
        elif cat == "unit":
            trace = trace_unit(prompt, answer)
        elif cat == "gravity":
            trace = trace_gravity(prompt, answer)
        else:
            trace = final_trace(["Infer the hidden rule from the examples and apply it to the query."], answer)
        records.append(
            {
                "id": r.get("id", ""),
                "category": cat,
                "prompt": prompt + PROMPT_SUFFIX,
                "response": trace,
                "answer": answer,
                "source": "train",
            }
        )
        if include_answer_only and cat in {"bit", "equation_numeric", "cryptarithm"}:
            records.append(
                {
                    "id": r.get("id", "") + ":answer",
                    "category": cat,
                    "prompt": prompt + PROMPT_SUFFIX,
                    "response": boxed(answer),
                    "answer": answer,
                    "source": "answer_only",
                }
            )

    rng = random.Random(seed)
    for i in range(synthetic_per_cat):
        for cat, gen in [
            ("bit", synth_bit),
            ("equation_numeric", synth_equation_numeric),
            ("cryptarithm", synth_cryptarithm),
        ]:
            p, ans, tr = gen(rng)
            records.append(
                {
                    "id": f"synth-{cat}-{i}",
                    "category": cat,
                    "prompt": p + PROMPT_SUFFIX,
                    "response": tr,
                    "answer": ans,
                    "source": "synthetic",
                }
            )
    return records


def write_jsonl(records: Sequence[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Optional LoRA training and packaging
# ---------------------------------------------------------------------------


class JsonlSFTDataset:  # torch Dataset, imported lazily inside train_lora
    def __init__(self, rows: List[dict], tokenizer, max_length: int):
        self.rows, self.tok, self.max_length = rows, tokenizer, max_length

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        r = self.rows[idx]
        prefix = f"User:\n{r['prompt']}\n\nAssistant:\n"
        full = prefix + r["response"]
        a = self.tok(prefix, add_special_tokens=False)
        b = self.tok(full, add_special_tokens=False, truncation=True, max_length=self.max_length)
        ids = b["input_ids"]
        labels = ids[:]
        cut = min(len(a["input_ids"]), len(labels))
        labels[:cut] = [-100] * cut
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}


def train_lora(jsonl_path: str, args) -> None:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    try:
        from transformers import BitsAndBytesConfig
    except Exception:
        BitsAndBytesConfig = None

    with open(jsonl_path, encoding="utf-8") as f:
        rows = [json.loads(x) for x in f]
    tok = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    qcfg = None
    if args.load_4bit and BitsAndBytesConfig is not None:
        qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        trust_remote_code=True,
        device_map="auto",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        quantization_config=qcfg,
    )
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    targets = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj", "out_proj", "up_proj", "down_proj", "gate_proj"]
    if args.include_lm_head:
        targets.append("lm_head")
    lcfg = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=targets,
        task_type=TaskType.CAUSAL_LM,
        bias="none",
    )
    model = get_peft_model(model, lcfg)
    ds = JsonlSFTDataset(rows, tok, args.max_length)

    def collate(batch):
        return tok.pad(batch, padding=True, return_tensors="pt")

    train_args = TrainingArguments(
        output_dir=args.adapter_out,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        bf16=torch.cuda.is_available(),
        logging_steps=10,
        save_steps=args.save_steps,
        save_total_limit=2,
        report_to="none",
        optim="adamw_torch",
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
    )
    trainer = Trainer(model=model, args=train_args, train_dataset=ds, data_collator=collate)
    trainer.train()
    model.save_pretrained(args.adapter_out)
    tok.save_pretrained(args.adapter_out)


def package_adapter(adapter_dir: str | Path, zip_path: str | Path) -> None:
    adapter_dir = Path(adapter_dir)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    required = ["adapter_config.json", "adapter_model.safetensors"]
    missing = [x for x in required if not (adapter_dir / x).exists()]
    if missing:
        raise FileNotFoundError(f"Missing adapter files in {adapter_dir}: {missing}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in adapter_dir.iterdir():
            if p.is_file() and p.name.startswith(("adapter_", "README", "tokenizer", "special_tokens_map")):
                z.write(p, p.name)
            elif p.name in required:
                z.write(p, p.name)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if any("/" in n for n in names):
            raise RuntimeError(f"Zip has nested paths: {names}")
        if not set(required).issubset(names):
            raise RuntimeError(f"Zip missing required files: {names}")
    print(f"wrote {zip_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Compact LB1-inspired Nemotron SFT/LoRA pipeline")
    ap.add_argument("--train-csv", default="train.csv")
    ap.add_argument("--corpus-out", default="lb1_compact_corpus.jsonl")
    ap.add_argument("--max-rows", type=int, default=0)
    ap.add_argument("--synthetic-per-cat", type=int, default=0, help="synthetic samples per hard category")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-answer-only", action="store_true")
    ap.add_argument("--train", action="store_true", help="train LoRA after writing corpus")
    ap.add_argument(
        "--base-model", default=os.getenv("BASE_MODEL", "metric/nemotron-3-nano-30b-a3b-bf16/transformers/default")
    )
    ap.add_argument("--adapter-out", default="adapter_lb1_compact")
    ap.add_argument("--zip-out", default="submission.zip")
    ap.add_argument("--max-length", type=int, default=4096)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--save-steps", type=int, default=200)
    ap.add_argument("--lora-rank", type=int, default=32)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.0)
    ap.add_argument(
        "--include-lm-head",
        action="store_true",
        help="LB1 trained lm_head; enable only if your submit loader accepts it",
    )
    ap.add_argument("--load-4bit", action="store_true")
    ap.add_argument("--package-only", action="store_true")
    args = ap.parse_args()

    if args.package_only:
        package_adapter(args.adapter_out, args.zip_out)
        return

    rows = read_train_csv(args.train_csv, max_rows=args.max_rows)
    records = build_records(
        rows, synthetic_per_cat=args.synthetic_per_cat, seed=args.seed, include_answer_only=not args.no_answer_only
    )
    random.Random(args.seed).shuffle(records)
    write_jsonl(records, args.corpus_out)
    cnt = Counter(r["category"] for r in records)
    print(f"wrote {len(records)} SFT records to {args.corpus_out}")
    print("category counts:", dict(sorted(cnt.items())))

    if args.train:
        if args.lora_rank > 32:
            raise ValueError("Competition requires LoRA rank <= 32")
        train_lora(args.corpus_out, args)
        package_adapter(args.adapter_out, args.zip_out)


if __name__ == "__main__":
    main()
