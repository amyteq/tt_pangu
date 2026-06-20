"""24-rule operator inventory for equation-numeric and cryptarithm (lb1-v1).

Faithful re-derivation of the 1st-place writeup's "24-rule inventory"
(`external/LB1/writeup/lb1-writeup.md` lines ~105-130). The competition is over;
this is reusable methodology, not a live solver.

A puzzle line is `AB op CD = output`, where ``AB`` and ``CD`` are 2-digit numbers
(written with a leading zero when < 10, e.g. ``07``). ``BA`` / ``DC`` are the
digit-reversed operands. ``rev(x)`` reverses the *decimal string* of a result
(``rev(143) -> "341"``, ``rev(119) -> "911"``). The operator symbol can act as a
**sign marker** on the output side (prefix/suffix); we represent any output-side
sign (an op marker or a negative sign) with the sentinel char ``SIGN``.

Each rule maps the two 2-char operand strings to an *output token string* over
``{'0'..'9', SIGN}`` (or ``None`` when the rule is undefined for that pair, e.g.
mod-by-zero). Higher-level code derives:
  * the **signature** = first-occurrence normalisation of ``sA + sB + output``
    (digits -> A,B,C,...; SIGN -> ``-``), and
  * the **slot digit string** = the digit characters of ``sA + sB + output``.

Verified against the writeup's own published catalog rows for signature
``ABCCCDD`` (see module-level doctests in tests/).
"""

from __future__ import annotations

SIGN = "#"  # internal sentinel for an output-side sign marker (op symbol / minus)


def _rev_str(n: int) -> str:
    """Reverse the decimal string of a non-negative integer (keeps result zeros)."""
    return str(n)[::-1]


def _digits_and_sign(value: int, *, prefix: bool = False, suffix: bool = False, only_if_nonzero: bool = False) -> str:
    """Render an integer as an output token string, optionally op-marked.

    The sign marker is emitted only when the value is nonzero if
    ``only_if_nonzero`` (matches "...prefix when abs(...) is nonzero").
    A natively negative value contributes a leading SIGN and its magnitude.
    """
    neg = value < 0
    mag = abs(value)
    body = str(mag)
    if neg:
        body = SIGN + body
    if (prefix or suffix) and (mag != 0 or not only_if_nonzero):
        if prefix:
            body = SIGN + body
        else:
            body = body + SIGN
    return body


def _rev_signed(value: int, *, prefix_if_neg: bool = False, suffix_if_neg: bool = False) -> str:
    """rev() of a value that may be negative, with optional op marker on the sign."""
    neg = value < 0
    body = _rev_str(abs(value))
    if neg:
        if prefix_if_neg:
            body = SIGN + body
        elif suffix_if_neg:
            body = body + SIGN
        else:
            body = SIGN + body
    return body


# Each entry: name -> (group, mode, fn) where fn(AB, CD, BA, DC) -> token-string|None.
# AB,CD,BA,DC are ints; the 2-char operand strings are recovered by the caller.
def _build_rules():
    R = {}

    def reg(name, group, mode, fn):
        R[name] = {"group": group, "mode": mode, "fn": fn}

    # --- join group (the 2 join rules; excluded from the 22 non-join enumeration) -
    reg("join", "join", "join", lambda AB, CD, BA, DC, sA, sB: sA + sB)
    reg("join_swap", "join", "join", lambda AB, CD, BA, DC, sA, sB: sB + sA)

    # --- add group (normal) ---
    reg("add", "add", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB + CD))
    reg("add+1", "add", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB + CD + 1))
    reg("add-1", "add", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB + CD - 1))
    # --- add group (flip) ---
    reg("flip_add", "add", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA + DC))
    reg("flip_add+1", "add", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA + DC + 1))
    reg("flip_add-1", "add", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA + DC - 1) if BA + DC - 1 >= 0 else None)

    # --- sub group (normal) ---
    reg("sub", "sub", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB - CD))
    reg("absdiff", "sub", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(abs(AB - CD)))
    reg(
        "absdiff_prefix",
        "sub",
        "normal",
        lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(abs(AB - CD), prefix=True, only_if_nonzero=True),
    )
    reg(
        "maxmodmin",
        "sub",
        "normal",
        lambda AB, CD, BA, DC, sA, sB: None if min(AB, CD) == 0 else _digits_and_sign(max(AB, CD) % min(AB, CD)),
    )
    # --- sub group (flip) ---
    reg(
        "flip_sub_prefix",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: _rev_signed(BA - DC, prefix_if_neg=True),
    )
    reg(
        "flip_sub_suffix",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: _rev_signed(DC - BA, suffix_if_neg=True),
    )
    reg("flip_absdiff", "sub", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(abs(BA - DC)))
    reg(
        "flip_absdiff_prefix",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: (SIGN + _rev_str(abs(BA - DC))) if abs(BA - DC) != 0 else _rev_str(0),
    )
    reg(
        "flip_absdiff_suffix",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: (_rev_str(abs(BA - DC)) + SIGN) if abs(BA - DC) != 0 else _rev_str(0),
    )
    reg(
        "flip_maxmodmin",
        "sub",
        "flip",
        lambda AB, CD, BA, DC, sA, sB: None if min(BA, DC) == 0 else _rev_str(max(BA, DC) % min(BA, DC)),
    )

    # --- mul group (normal) ---
    reg("mul", "mul", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB * CD))
    reg("mul+1", "mul", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB * CD + 1))
    reg("mul-1", "mul", "normal", lambda AB, CD, BA, DC, sA, sB: _digits_and_sign(AB * CD - 1))
    # --- mul group (flip) ---
    reg("flip_mul", "mul", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA * DC))
    reg("flip_mul+1", "mul", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA * DC + 1))
    reg("flip_mul-1", "mul", "flip", lambda AB, CD, BA, DC, sA, sB: _rev_str(BA * DC - 1) if BA * DC - 1 >= 0 else None)

    return R


RULES = _build_rules()
JOIN_RULES = ("join", "join_swap")
NON_JOIN_RULES = tuple(r for r in RULES if r not in JOIN_RULES)
assert len(RULES) == 24, f"expected 24 rules, got {len(RULES)}"
assert len(NON_JOIN_RULES) == 22, f"expected 22 non-join rules, got {len(NON_JOIN_RULES)}"


def operands_from_strings(sA: str, sB: str):
    AB, CD = int(sA), int(sB)
    BA, DC = int(sA[::-1]), int(sB[::-1])
    return AB, CD, BA, DC


def apply_rule(rule: str, sA: str, sB: str):
    """Apply a rule to two 2-char operand strings; returns a token string or None.

    The token string is over digits plus the SIGN sentinel for op/negative markers.
    """
    AB, CD, BA, DC = operands_from_strings(sA, sB)
    out = RULES[rule]["fn"](AB, CD, BA, DC, sA, sB)
    return out


def normalize_signature(seq: str) -> str:
    """First-occurrence normalisation: digits -> A,B,C,...; SIGN -> '-'."""
    mapping = {}
    nxt = 0
    parts = []
    for ch in seq:
        if ch == SIGN:
            parts.append("-")
            continue
        if ch not in mapping:
            mapping[ch] = chr(ord("A") + nxt)
            nxt += 1
        parts.append(mapping[ch])
    return "".join(parts)


def signature_of(sA: str, sB: str, output: str) -> str:
    """Signature for an equation: normalise sA + sB + output."""
    return normalize_signature(sA + sB + output)


def digit_slots(sA: str, sB: str, output: str) -> str:
    """The digit characters of sA + sB + output (drops sign markers)."""
    return "".join(c for c in (sA + sB + output) if c.isdigit())


def render_output_human(output: str, op_symbol: str) -> str:
    """Render a token string for display, substituting the real operator symbol for SIGN."""
    return output.replace(SIGN, op_symbol)
