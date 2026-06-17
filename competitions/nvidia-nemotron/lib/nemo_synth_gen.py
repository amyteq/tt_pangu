"""Cryptarithm-weighted synthetic CoT generator for the Nemotron reasoning comp.

Generators adapted from the public varianceofx/synthetic-dataset-generator-27k
notebook (deterministic per-category puzzle + long chain-of-thought). T11 intent:
heavily weight the cryptarithm categories (the forum-consensus 0.86->0.89 lever),
keep the CoT long with every intermediate value pre-computed, end every trace
with a "no further revision" finality line, and inject unseen symbols into a
fraction of queries so the model learns the rule rather than a lookup table.

build_records(seed, mix) -> list[{id, prompt, answer, cot, category}].
"""

import random
import string  # noqa: F401  (used by the adapted generator functions)


ALICE_HEADER = "In Alice's Wonderland, "

NOUNS = [
    "alice",
    "hatter",
    "knight",
    "rabbit",
    "mouse",
    "turtle",
    "bird",
    "cat",
    "princess",
    "queen",
    "king",
    "wizard",
    "dragon",
    "student",
    "teacher",
]
VERBS = [
    "creates",
    "dreams",
    "found",
    "studies",
    "draws",
    "writes",
    "follows",
    "sees",
    "reads",
    "chases",
    "imagines",
    "discovers",
    "watches",
    "explores",
]
ADJECTIVES = [
    "colorful",
    "hidden",
    "silver",
    "dark",
    "bright",
    "wise",
    "strange",
    "curious",
    "clever",
    "golden",
    "magical",
    "mysterious",
    "ancient",
]
LOCATIONS = [
    "garden",
    "castle",
    "forest",
    "key",
    "puzzle",
    "book",
    "treasure",
    "mirror",
    "crystal",
    "door",
    "potion",
    "map",
    "story",
    "message",
    "cave",
    "island",
    "ocean",
    "palace",
    "valley",
    "village",
    "mountain",
    "library",
    "school",
    "tower",
]
PREPOSITIONS = ["in", "near", "inside", "through", "under", "above", "around", "beyond"]

SYMBOL_CHARS = list("!\"#$%&'()*+-/:;<>?@[\\]^`{|}")


# ── helpers ───────────────────────────────────────────────────────────────────


def int_to_roman(n: int) -> str:
    vals = [
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
    result = ""
    for v, sym in vals:
        while n >= v:
            result += sym
            n -= v
    return result


def rotate_left(x: int, n: int, bits: int = 8) -> int:
    n %= bits
    return ((x << n) | (x >> (bits - n))) & 0xFF


def rotate_right(x: int, n: int, bits: int = 8) -> int:
    n %= bits
    return ((x >> n) | (x << (bits - n))) & 0xFF


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 1: Bit Manipulation
# ══════════════════════════════════════════════════════════════════════════════


class BitManipOp:
    def __init__(self, name: str, fn):
        self.name = name
        self.fn = fn

    def apply(self, x: int) -> int:
        return self.fn(x) & 0xFF


def _make_bit_ops(rng: random.Random) -> list:
    xor_mask = rng.randint(1, 255)
    and_mask = rng.randint(1, 254)
    or_mask = rng.randint(1, 255)
    rot_l_n = rng.randint(1, 7)
    rot_r_n = rng.randint(1, 7)
    shift_l_n = rng.randint(1, 4)
    shift_r_n = rng.randint(1, 4)

    return [
        BitManipOp(f"XOR 0x{xor_mask:02X}", lambda x, m=xor_mask: x ^ m),
        BitManipOp(f"AND 0x{and_mask:02X}", lambda x, m=and_mask: x & m),
        BitManipOp(f"OR  0x{or_mask:02X}", lambda x, m=or_mask: x | m),
        BitManipOp("NOT", lambda x: (~x) & 0xFF),
        BitManipOp(f"ROTATE LEFT {rot_l_n}", lambda x, n=rot_l_n: rotate_left(x, n)),
        BitManipOp(f"ROTATE RIGHT {rot_r_n}", lambda x, n=rot_r_n: rotate_right(x, n)),
        BitManipOp(f"SHIFT LEFT {shift_l_n}", lambda x, n=shift_l_n: (x << n) & 0xFF),
        BitManipOp(f"SHIFT RIGHT {shift_r_n}", lambda x, n=shift_r_n: x >> n),
        BitManipOp(
            "MAJORITY(x, ROTL1, ROTR1)",
            lambda x: (x & rotate_left(x, 1)) | (x & rotate_right(x, 1)) | (rotate_left(x, 1) & rotate_right(x, 1)),
        ),
        BitManipOp(
            "CHOICE(x, ROTL2, NOT)",
            lambda x: (x & rotate_left(x, 2)) | ((~x & 0xFF) & rotate_right(x, 2)),
        ),
    ]


def make_bit_puzzle(rng: random.Random) -> tuple:
    ops = _make_bit_ops(rng)
    chosen = rng.sample(ops, rng.randint(2, 4))

    def transform(x: int) -> int:
        for op in chosen:
            x = op.apply(x)
        return x

    seen_inputs: set = set()
    examples: list = []
    while len(examples) < rng.randint(8, 11):
        inp = rng.randint(0, 255)
        if inp in seen_inputs:
            continue
        seen_inputs.add(inp)
        examples.append((inp, transform(inp)))

    query_val = rng.randint(0, 255)
    while query_val in seen_inputs:
        query_val = rng.randint(0, 255)
    answer_val = transform(query_val)

    ex_lines = "\n".join(f"{format(i, '08b')} -> {format(o, '08b')}" for i, o in examples)
    prompt = (
        f"{ALICE_HEADER}a secret bit manipulation rule transforms 8-bit binary numbers. "
        "The transformation involves operations like bit shifts, rotations, XOR, AND, OR, "
        "NOT, and possibly majority or choice functions.\n\n"
        f"Here are some examples of input -> output:\n{ex_lines}\n\n"
        f"Now, determine the output for: {format(query_val, '08b')}"
    )
    answer = format(answer_val, "08b")
    ops_str = " -> ".join(op.name for op in chosen)
    e0_in, e0_out = examples[0]
    e1_in, e1_out = examples[1]

    # FIX: Explicit bit-by-bit verification in CoT to prevent off-by-one errors
    cot = (
        f"I need to infer the hidden rule from the examples.\n\n"
        f"Observing example 1: {format(e0_in, '08b')} ({e0_in}) -> {format(e0_out, '08b')} ({e0_out})\n"
        f"Observing example 2: {format(e1_in, '08b')} ({e1_in}) -> {format(e1_out, '08b')} ({e1_out})\n\n"
        f"Testing candidate operations step by step...\n"
        f"The rule that fits all examples is: {ops_str}\n\n"
        f"Verification on example 1 ({format(e0_in, '08b')}):\n"
    )
    x_check = e0_in
    for op in chosen:
        x_prev = x_check
        x_check = op.apply(x_check)
        cot += f"  {op.name}: {format(x_prev, '08b')} ({x_prev}) -> {format(x_check, '08b')} ({x_check})\n"
    cot += f"  Final: {format(x_check, '08b')} == {format(e0_out, '08b')} ✓\n\n"

    cot += f"Applying confirmed rule to query {format(query_val, '08b')} ({query_val}):\n"
    x = query_val
    for op in chosen:
        x_prev = x
        x = op.apply(x)
        cot += (
            f"  Step: {op.name}\n"
            f"    Input : {format(x_prev, '08b')} (decimal {x_prev})\n"
            f"    Output: {format(x, '08b')} (decimal {x})\n"
        )
    cot += f"\nFinal answer: {format(x, '08b')}\nThis is the definitive result. No further revision."
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 2: Text Encryption
# ══════════════════════════════════════════════════════════════════════════════


def _random_substitution(rng: random.Random) -> dict:
    alphabet = list(string.ascii_lowercase)
    shuffled = alphabet[:]
    rng.shuffle(shuffled)
    return dict(zip(alphabet, shuffled))


def _encrypt_word(word: str, sub: dict) -> str:
    return "".join(sub.get(c, c) for c in word)


def _make_sentence(rng: random.Random, n_words: int) -> list:
    if n_words == 3:
        return [rng.choice(NOUNS), rng.choice(VERBS), rng.choice(LOCATIONS + NOUNS)]
    elif n_words == 4:
        template = rng.choice(["the", "adj_obj", "prep_loc"])
        if template == "the":
            return [rng.choice(NOUNS), rng.choice(VERBS), "the", rng.choice(LOCATIONS)]
        elif template == "adj_obj":
            return [
                rng.choice(NOUNS),
                rng.choice(VERBS),
                rng.choice(ADJECTIVES),
                rng.choice(LOCATIONS),
            ]
        else:
            return [
                rng.choice(NOUNS),
                rng.choice(VERBS),
                rng.choice(PREPOSITIONS),
                rng.choice(LOCATIONS),
            ]
    else:
        if rng.random() < 0.5:
            return [
                rng.choice(NOUNS),
                rng.choice(VERBS),
                "the",
                rng.choice(ADJECTIVES),
                rng.choice(LOCATIONS),
            ]
        return [
            rng.choice(NOUNS),
            rng.choice(VERBS),
            rng.choice(ADJECTIVES),
            rng.choice(NOUNS),
            rng.choice(LOCATIONS),
        ]


def make_encryption_puzzle(rng: random.Random) -> tuple:
    sub = _random_substitution(rng)
    examples = []
    for _ in range(rng.randint(3, 5)):
        nw = rng.choice([3, 4, 5])
        plain_words = _make_sentence(rng, nw)
        cipher_words = [_encrypt_word(w, sub) for w in plain_words]
        examples.append((cipher_words, plain_words))

    q_nw = rng.choice([3, 4, 5])
    q_plain = _make_sentence(rng, q_nw)
    q_cipher = [_encrypt_word(w, sub) for w in q_plain]

    ex_lines = "\n".join(f"{' '.join(c)} -> {' '.join(p)}" for c, p in examples)
    query_str = " ".join(q_cipher)
    prompt = (
        f"{ALICE_HEADER}secret encryption rules are used on text. "
        f"Here are some examples:\n{ex_lines}\n"
        f"Now, decrypt the following text: {query_str}"
    )
    answer = " ".join(q_plain)

    learned: dict = {}
    for cipher_words, plain_words in examples:
        for cw, pw in zip(cipher_words, plain_words):
            for cc, pc in zip(cw, pw):
                learned[cc] = pc

    # FIX: Explicit letter-by-letter decoding with position tracking
    cot = "Each letter maps to a fixed letter. Recovering the mapping:\n"
    for cc, pc in sorted(learned.items()):
        cot += f"  '{cc}' -> '{pc}'\n"
    cot += f"\nDecoding '{query_str}' character by character:\n"
    decoded_chars = []
    for cc in query_str:
        if cc == " ":
            decoded_chars.append(" ")
            cot += "  ' ' -> ' ' (space preserved)\n"
        else:
            mapped = learned.get(cc, cc)
            decoded_chars.append(mapped)
            cot += f"  '{cc}' -> '{mapped}'\n"
    decoded = "".join(decoded_chars)
    cot += (
        f"\nConcatenating all decoded characters: '{decoded}'\n"
        f"Result: {answer}\n"
        f"This is the definitive result. No further revision."
    )
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 3: Numeral System
# ══════════════════════════════════════════════════════════════════════════════


def make_numeral_puzzle(rng: random.Random) -> tuple:
    pool = list(range(1, 101))
    rng.shuffle(pool)
    n_examples = rng.randint(3, 5)
    example_nums = pool[:n_examples]
    query_num = pool[n_examples]

    ex_lines = "\n".join(f"{n} -> {int_to_roman(n)}" for n in example_nums)
    prompt = (
        f"{ALICE_HEADER}numbers are secretly converted into a different numeral system. "
        f"Some examples are given below:\n{ex_lines}\n"
        f"Now, write the number {query_num} in the Wonderland numeral system."
    )
    answer = int_to_roman(query_num)

    cot = f"The examples show decimal -> Roman numeral conversion.\nBreaking down {query_num}:\n"
    vals = [
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
    remaining = query_num
    for v, sym in vals:
        while remaining >= v:
            cot += f"  {remaining} >= {v}: append '{sym}', remainder {remaining - v}\n"
            remaining -= v
    cot += f"Result: {answer}"
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 4: Unit Conversion
# ══════════════════════════════════════════════════════════════════════════════


def make_unit_puzzle(rng: random.Random) -> tuple:
    multiplier = round(rng.uniform(0.50, 2.00), 4)
    n_examples = rng.randint(3, 5)
    example_inputs = [round(rng.uniform(1.0, 50.0), 2) for _ in range(n_examples)]
    query_input = round(rng.uniform(1.0, 50.0), 2)

    ex_lines = "\n".join(f"{v} m becomes {round(v * multiplier, 2)}" for v in example_inputs)
    prompt = (
        f"{ALICE_HEADER}a secret unit conversion is applied to measurements. "
        f"For example:\n{ex_lines}\n"
        f"Now, convert the following measurement: {query_input} m"
    )
    answer = str(round(query_input * multiplier, 2))
    v0 = example_inputs[0]
    out0 = round(v0 * multiplier, 2)
    cot = (
        f"Finding the conversion factor from examples:\n"
        f"  {out0} / {v0} = {multiplier}\n"
        f"Verifying with another example:\n"
        f"  {example_inputs[1]} × {multiplier} = "
        f"{round(example_inputs[1] * multiplier, 2)} ✓\n"
        f"Applying to {query_input}:\n"
        f"  {query_input} × {multiplier} = {answer}"
    )
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 5: Gravity
# FIX: Pre-compute ALL intermediate values, eliminate inline arithmetic,
#      add explicit finality guard against self-revision
# ══════════════════════════════════════════════════════════════════════════════


def make_gravity_puzzle(rng: random.Random) -> tuple:
    g = round(rng.uniform(4.91, 19.58), 2)
    n_examples = rng.randint(3, 5)
    example_ts = [round(rng.uniform(1.0, 5.0), 2) for _ in range(n_examples)]
    query_t = round(rng.uniform(1.0, 5.0), 2)

    def dist(t: float) -> float:
        return round(0.5 * g * t**2, 2)

    ex_lines = "\n".join(f"For t = {t}s, distance = {dist(t)} m" for t in example_ts)
    prompt = (
        f"{ALICE_HEADER}the gravitational constant has been secretly changed. "
        f"Here are some example observations:\n{ex_lines}\n"
        f"Now, determine the falling distance for t = {query_t}s "
        f"given d = 0.5*g*t^2."
    )

    # FIX: Pre-compute every intermediate value as a named Python variable
    # so no arithmetic happens inside f-string expressions
    answer_val = round(0.5 * g * query_t**2, 2)
    answer = str(answer_val)

    t0 = example_ts[0]
    d0 = dist(t0)
    t0_sq = round(t0**2, 4)
    g_check = round(2 * d0 / t0_sq, 2)

    t1 = example_ts[1]
    d1 = dist(t1)
    t1_sq = round(t1**2, 4)
    g_check2 = round(2 * d1 / t1_sq, 2)

    qt_sq = round(query_t**2, 4)
    half_g = round(0.5 * g_check, 4)
    final_result = round(half_g * qt_sq, 2)

    # FIX: CoT uses only pre-computed variables, ends with unambiguous statement
    cot = (
        f"Using d = 0.5*g*t², rearrange to g = 2d / t².\n\n"
        f"From example t={t0}s, d={d0}m:\n"
        f"  t² = {t0_sq}\n"
        f"  g = 2 × {d0} / {t0_sq} = {g_check}\n\n"
        f"Verifying with t={t1}s, d={d1}m:\n"
        f"  t² = {t1_sq}\n"
        f"  g = 2 × {d1} / {t1_sq} = {g_check2}\n"
        f"  Consistent: g = {g_check} ✓\n\n"
        f"For query t={query_t}s:\n"
        f"  t² = {qt_sq}\n"
        f"  d = 0.5 × {g_check} × {qt_sq}\n"
        f"  d = {half_g} × {qt_sq}\n"
        f"  d = {final_result}\n\n"
        f"The falling distance is {final_result} m.\n"
        f"Final answer: {final_result}\n"
        f"This is the definitive result. No further revision."
    )
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 6: Symbol Transformation
# ══════════════════════════════════════════════════════════════════════════════


def _random_bijective_sym_map(rng: random.Random, charset: list) -> dict:
    shuffled = charset[:]
    rng.shuffle(shuffled)
    return dict(zip(charset, shuffled))


def _apply_sym_map(s: str, char_map: dict) -> str:
    return "".join(char_map.get(c, c) for c in s)


def _gen_sym_string(rng: random.Random, length: int, charset: list = SYMBOL_CHARS) -> str:
    return "".join(rng.choices(charset, k=length))


def make_symbol_puzzle(rng: random.Random) -> tuple:
    char_map = _random_bijective_sym_map(rng, SYMBOL_CHARS)
    n_examples = rng.randint(3, 5)
    examples = []
    seen = set()
    while len(examples) < n_examples:
        inp = _gen_sym_string(rng, 5)
        if inp in seen:
            continue
        seen.add(inp)
        examples.append((inp, _apply_sym_map(inp, char_map)))

    q_inp = _gen_sym_string(rng, 5)
    while q_inp in seen:
        q_inp = _gen_sym_string(rng, 5)
    q_out = _apply_sym_map(q_inp, char_map)

    ex_lines = "\n".join(f"{i} = {o}" for i, o in examples)
    prompt = (
        f"{ALICE_HEADER}a secret set of transformation rules is applied to symbol strings. "
        f"Below are a few examples:\n{ex_lines}\n"
        f"Now, determine the result for: {q_inp}"
    )
    learned: dict = {}
    for inp, out in examples:
        for ci, co in zip(inp, out):
            learned[ci] = co

    cot = "Each character maps to a unique fixed character. Recovering the map:\n"
    for ci, co in sorted(learned.items()):
        cot += f"  '{ci}' -> '{co}'\n"
    cot += f"\nApplying to '{q_inp}' position by position:\n"
    result_chars = []
    for pos, ci in enumerate(q_inp):
        mapped = learned.get(ci, ci)
        result_chars.append(mapped)
        cot += f"  Position {pos}: '{ci}' -> '{mapped}'\n"
    cot += "\nConcatenating in order: " + " + ".join(f"'{c}'" for c in result_chars) + f" = '{q_out}'\nResult: {q_out}"
    return prompt, q_out, cot


# ══════════════════════════════════════════════════════════════════════════════
# SYMBOLIC EXPRESSION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

_SYM_EXPR_CHARS = list("!\"#$%&'()*+,-./:;<=>?@[\\]^`{|}")
_SYM_OPERATORS = ["+", "-", "*", "/"]

_RULE_REGISTRY = {
    "concat_ab": lambda a, b: a + b,
    "concat_ba": lambda a, b: b + a,
    "interleave": lambda a, b: a[0] + b[0] + a[1] + b[1],
    "swap_inner": lambda a, b: a[0] + b[0] + b[1] + a[1],
    "reverse_ab": lambda a, b: a[::-1] + b,
    "reverse_ba": lambda a, b: a + b[::-1],
    "left_dup": lambda a, b: a + a,
    "right_dup": lambda a, b: b + b,
}

_RULE_NAMES = list(_RULE_REGISTRY.keys())

_RULE_DESCRIPTIONS = {
    "concat_ab": "concatenate A then B → result is A followed by B (A comes first, B comes second)",
    "concat_ba": "concatenate B then A → result is B followed by A (B comes first, A comes second)",
    "interleave": "interleave characters → position 0=a[0], position 1=b[0], position 2=a[1], position 3=b[1]",
    "swap_inner": "swap inner characters → position 0=a[0], position 1=b[0], position 2=b[1], position 3=a[1]",
    "reverse_ab": "reverse A then append B → result is rev(A) followed by B (reversed-A comes first)",
    "reverse_ba": "append reversed B to A → result is A followed by rev(B) (A comes first, reversed-B comes second)",
    "left_dup": "duplicate left operand → result is A followed by A (ignore B entirely)",
    "right_dup": "duplicate right operand → result is B followed by B (ignore A entirely)",
}


def _apply_rule(rule_name: str, a: str, b: str) -> str:
    return _RULE_REGISTRY[rule_name](a, b)


def _make_sym_operand(rng: random.Random, pool: list) -> str:
    return rng.choice(pool) + rng.choice(pool)


def _build_sym_expr_puzzle(rng: random.Random, force_unknown: bool = False) -> dict:
    """
    FIX: Added force_unknown parameter.
    When True, the query uses at least one symbol NOT seen in examples,
    forcing deduction purely from operator rule rather than direct lookup.
    """
    n_ops = rng.randint(2, 4)
    ops_used = rng.sample(_SYM_OPERATORS, n_ops)
    op_rules = {op: rng.choice(_RULE_NAMES) for op in ops_used}

    pool_size = rng.randint(6, 10)
    sym_pool = rng.sample(_SYM_EXPR_CHARS, min(pool_size, len(_SYM_EXPR_CHARS)))

    # FIX: Reserve some symbols exclusively for unknown-symbol queries
    known_pool = sym_pool[: max(4, len(sym_pool) - 3)]
    unknown_pool = [c for c in _SYM_EXPR_CHARS if c not in sym_pool]

    n_examples = rng.randint(3, 5)
    examples = []
    seen_exprs: set = set()
    attempts = 0

    while len(examples) < n_examples and attempts < 300:
        attempts += 1
        op = rng.choice(ops_used)
        a = _make_sym_operand(rng, known_pool)
        b = _make_sym_operand(rng, known_pool)
        expr = a + op + b
        if expr in seen_exprs:
            continue
        seen_exprs.add(expr)
        result = _apply_rule(op_rules[op], a, b)
        examples.append((expr, result, op, a, b))

    if len(examples) < 2:
        raise ValueError("Could not generate enough examples")

    q_op = rng.choice(ops_used)

    # FIX: For unknown-symbol puzzles, inject an unseen symbol into the query
    if force_unknown and unknown_pool:
        unknown_char = rng.choice(unknown_pool)
        # Place the unknown char in operand A or B, rest from known_pool
        if rng.random() < 0.5:
            q_a = unknown_char + rng.choice(known_pool)
        else:
            q_a = rng.choice(known_pool) + unknown_char
        q_b = _make_sym_operand(rng, known_pool)
    else:
        q_a = _make_sym_operand(rng, known_pool)
        q_b = _make_sym_operand(rng, known_pool)

    q_expr = None
    q_result = None
    for _ in range(200):
        qe = q_a + q_op + q_b
        if qe not in seen_exprs:
            q_expr = qe
            q_result = _apply_rule(op_rules[q_op], q_a, q_b)
            break
        # Re-randomise operands if collision
        if force_unknown and unknown_pool:
            unknown_char = rng.choice(unknown_pool)
            q_a = unknown_char + rng.choice(known_pool)
            q_b = _make_sym_operand(rng, known_pool)
        else:
            q_a = _make_sym_operand(rng, known_pool)
            q_b = _make_sym_operand(rng, known_pool)

    if q_expr is None:
        raise ValueError("Could not generate query")

    return {
        "ops_used": ops_used,
        "op_rules": op_rules,
        "sym_pool": sym_pool,
        "known_pool": known_pool,
        "unknown_pool": unknown_pool,
        "examples": examples,
        "q_expr": q_expr,
        "q_result": q_result,
        "q_op": q_op,
        "q_a": q_a,
        "q_b": q_b,
        "has_unknown": force_unknown and bool(unknown_pool),
    }


def _build_expr_cot(puzzle: dict) -> str:
    """
    FIX: CoT now explicitly:
    1. States operand order (A=left, B=right) at the top
    2. Shows character-by-character construction with position indices
    3. Handles unknown symbols explicitly by reasoning from operator rule
    4. Ends with unambiguous finality statement
    """
    op_rules = puzzle["op_rules"]
    examples = puzzle["examples"]
    q_expr = puzzle["q_expr"]
    q_a = puzzle["q_a"]
    q_b = puzzle["q_b"]
    q_op = puzzle["q_op"]
    q_result = puzzle["q_result"]
    has_unknown = puzzle.get("has_unknown", False)

    lines = [
        "IMPORTANT: In every expression 'A op B':",
        "  - A is the LEFT operand (characters before the operator)",
        "  - B is the RIGHT operand (characters after the operator)",
        "  - The operator rule determines how A and B combine",
        "  - Character order in the result depends ONLY on the rule, not on lookup",
        "",
        "Each operator has a hidden transformation rule.",
        "I will infer the rule for each operator from the examples.",
        "",
    ]

    for op in puzzle["ops_used"]:
        op_exs = [(e, r, a, b) for e, r, eo, a, b in examples if eo == op]
        if not op_exs:
            continue
        rule = op_rules[op]
        desc = _RULE_DESCRIPTIONS[rule]
        lines.append(f"Operator '{op}':")
        for e, r, a, b in op_exs[:2]:
            lines.append(f"  Example: {e} = {r}")
            lines.append(f"    A='{a}' (left), B='{b}' (right)")
            lines.append(f"    Result='{r}'")

        # FIX: Show explicit position-by-position construction
        e0, r0, a0, b0 = op_exs[0]
        computed = _apply_rule(rule, a0, b0)
        lines.append(f"  Pattern detected: {desc}")
        lines.append(f"  Position-by-position for '{e0}':")
        for pos, ch in enumerate(computed):
            lines.append(f"    result[{pos}] = '{ch}'")
        lines.append(f"  Verify: result = '{computed}' == '{r0}' ✓")
        lines.append("")

    rule_used = op_rules[q_op]
    desc_used = _RULE_DESCRIPTIONS[rule_used]

    lines.append(f"Applying to query '{q_expr}':")
    lines.append(f"  Left operand  A = '{q_a}'")
    lines.append(f"  Right operand B = '{q_b}'")
    lines.append(f"  Operator '{q_op}' → rule: {desc_used}")

    # FIX: If unknown symbol present, explicitly note it doesn't affect result
    if has_unknown:
        lines.append("  NOTE: Some characters in this query may not appear in examples.")
        lines.append("  This does NOT matter — the rule operates on positions, not lookups.")
        lines.append(f"  We apply the rule directly to A='{q_a}' and B='{q_b}'.")

    lines.append("  Computing result position by position:")
    for pos, ch in enumerate(q_result):
        lines.append(f"    result[{pos}] = '{ch}'")
    lines.append(f"  Concatenating: '{q_result}'")
    lines.append("")
    lines.append(f"The answer is '{q_result}'.")
    lines.append("This is the definitive result. No further revision.")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 7: Cryptarithm Deduce
# FIX: 30% of puzzles use force_unknown=True to train unknown-symbol handling
# ══════════════════════════════════════════════════════════════════════════════


def make_cryptarithm_deduce_puzzle(rng: random.Random) -> tuple:
    # FIX: 30% chance of unknown-symbol puzzle
    force_unknown = rng.random() < 0.30
    puzzle = _build_sym_expr_puzzle(rng, force_unknown=force_unknown)

    ex_lines = "\n".join(f"{expr} = {result}" for expr, result, _, _, _ in puzzle["examples"])
    prompt = (
        f"{ALICE_HEADER}a secret set of transformation rules is applied to equations. "
        f"Below are a few examples:\n{ex_lines}\n"
        f"Now, determine the result for: {puzzle['q_expr']}"
    )
    answer = puzzle["q_result"]
    cot = _build_expr_cot(puzzle)
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 8: Cryptarithm Guess
# FIX: Same unknown-symbol treatment + explicit ordering in CoT
# ══════════════════════════════════════════════════════════════════════════════


def make_cryptarithm_guess_puzzle(rng: random.Random) -> tuple:
    force_unknown = rng.random() < 0.20
    puzzle = _build_sym_expr_puzzle(rng, force_unknown=force_unknown)
    examples = puzzle["examples"]

    hide_idx = rng.randint(0, len(examples) - 1)

    ex_lines_parts = []
    for i, (expr, result, op, a, b) in enumerate(examples):
        if i == hide_idx:
            ex_lines_parts.append(f"{expr} = ?")
        else:
            ex_lines_parts.append(f"{expr} = {result}")
    ex_lines = "\n".join(ex_lines_parts)

    hidden_expr = examples[hide_idx][0]
    hidden_result = examples[hide_idx][1]
    hidden_op = examples[hide_idx][2]
    hidden_a = examples[hide_idx][3]
    hidden_b = examples[hide_idx][4]

    prompt = (
        f"{ALICE_HEADER}a secret set of transformation rules is applied to equations. "
        f"Below are a few examples (one result is missing):\n{ex_lines}\n"
        f"What is the result of: {hidden_expr}"
    )
    answer = hidden_result

    op_rules = puzzle["op_rules"]
    rule = op_rules[hidden_op]
    desc = _RULE_DESCRIPTIONS[rule]

    other_exs = [
        (expr, result, op, a, b)
        for i, (expr, result, op, a, b) in enumerate(examples)
        if i != hide_idx and op == hidden_op
    ]

    # FIX: Explicit ordering emphasis in CoT
    lines = [
        "IMPORTANT: In every expression 'A op B':",
        "  - A is the LEFT operand (before the operator)",
        "  - B is the RIGHT operand (after the operator)",
        "  - Order matters: the rule specifies exactly which position each character occupies",
        "",
        f"I need to find the missing result for '{hidden_expr}'.",
        f"  Left operand  A = '{hidden_a}'",
        f"  Right operand B = '{hidden_b}'",
        f"  Operator = '{hidden_op}'",
        "",
        f"Finding the rule for operator '{hidden_op}' from other examples:",
    ]
    if other_exs:
        for expr, result, op, a, b in other_exs[:2]:
            lines.append(f"  {expr} = {result}")
            lines.append(f"    A='{a}' (left), B='{b}' (right) → result='{result}'")
        lines.append(f"  Rule identified: {desc}")
    else:
        lines.append(f"  Using rule inferred from context: {desc}")

    lines += [
        "",
        f"Applying rule to A='{hidden_a}', B='{hidden_b}':",
    ]
    for pos, ch in enumerate(hidden_result):
        lines.append(f"  result[{pos}] = '{ch}'")
    lines += [
        f"  Concatenating: '{hidden_result}'",
        "",
        f"The answer is '{hidden_result}'.",
        "This is the definitive result. No further revision.",
    ]
    cot = "\n".join(lines)
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 9: Equation Numeric Deduce
# ══════════════════════════════════════════════════════════════════════════════


def _make_linear_rule(rng: random.Random):
    a, b = rng.randint(2, 9), rng.randint(-10, 10)
    return (
        lambda x, a=a, b=b: a * x + b,
        f"f(x) = {a}*x + ({b})" if b < 0 else f"f(x) = {a}*x + {b}",
        {"type": "linear", "a": a, "b": b},
    )


def _make_quadratic_rule(rng: random.Random):
    c = rng.randint(-5, 20)
    return (
        lambda x, c=c: x * x + c,
        f"f(x) = x^2 + {c}" if c >= 0 else f"f(x) = x^2 - {abs(c)}",
        {"type": "quadratic", "c": c},
    )


def _make_floor_div_rule(rng: random.Random):
    k = rng.randint(2, 7)
    return (lambda x, k=k: x // k, f"f(x) = floor(x / {k})", {"type": "floor", "k": k})


def _make_arithmetic_seq(rng: random.Random):
    a0, d = rng.randint(1, 20), rng.randint(2, 15)
    return (
        lambda n, a0=a0, d=d: a0 + n * d,
        f"a(n) = {a0} + {d}*n",
        {"type": "arith", "a0": a0, "d": d},
    )


def _make_geometric_seq(rng: random.Random):
    a0, r = rng.randint(1, 5), rng.randint(2, 4)
    return (
        lambda n, a0=a0, r=r: a0 * (r**n),
        f"a(n) = {a0} * {r}^n",
        {"type": "geom", "a0": a0, "r": r},
    )


def make_equation_numeric_deduce_puzzle(rng: random.Random) -> tuple:
    rule_makers = [
        _make_linear_rule,
        _make_quadratic_rule,
        _make_floor_div_rule,
        _make_arithmetic_seq,
        _make_geometric_seq,
    ]
    fn, desc, params = rng.choice(rule_makers)(rng)

    used: set = set()
    examples: list = []
    while len(examples) < rng.randint(4, 6):
        x = rng.randint(1, 20)
        if x in used:
            continue
        used.add(x)
        try:
            out = fn(x)
            if abs(out) > 50000:
                continue
            examples.append((x, out))
        except Exception:
            continue

    qx = rng.randint(1, 20)
    while qx in used:
        qx = rng.randint(1, 20)
    answer_val = fn(qx)

    ex_lines = "\n".join(f"f({x}) = {o}" for x, o in examples)
    prompt = (
        f"{ALICE_HEADER}a secret mathematical rule maps numbers to outputs.\n"
        f"Here are some examples:\n{ex_lines}\n\n"
        f"What is f({qx})?"
    )
    answer = str(answer_val)
    x0, y0 = examples[0]
    x1, y1 = examples[1]
    ptype = params["type"]

    if ptype == "linear":
        a, b = params["a"], params["b"]
        cot = (
            f"Testing f(x) = a*x + b:\n"
            f"  From f({x0})={y0}: {a}*{x0} + b = {y0} → b = {y0 - a * x0}\n"
            f"  From f({x1})={y1}: {a}*{x1} + b = {y1} → b = {y1 - a * x1}\n"
            f"Rule confirmed: {desc}\n"
            f"f({qx}) = {a}*{qx} + ({b}) = {answer_val}"
        )
    elif ptype == "quadratic":
        c = params["c"]
        cot = (
            f"Testing f(x) = x^2 + c:\n"
            f"  From f({x0})={y0}: {x0}^2 + c = {x0**2} + c = {y0} → c = {c}\n"
            f"Rule confirmed: {desc}\n"
            f"f({qx}) = {qx}^2 + {c} = {qx**2} + {c} = {answer_val}"
        )
    elif ptype == "floor":
        k = params["k"]
        cot = (
            f"Testing f(x) = floor(x / k):\n"
            f"  From f({x0})={y0}: floor({x0}/{k}) = {x0 // k} ✓\n"
            f"Rule confirmed: {desc}\n"
            f"f({qx}) = floor({qx}/{k}) = {answer_val}"
        )
    elif ptype == "arith":
        a0, d = params["a0"], params["d"]
        cot = (
            f"Testing arithmetic sequence a(n) = a0 + d*n:\n"
            f"  Consecutive difference: {y1} - {y0} = {y1 - y0} = d\n"
            f"  a0 = {a0} (extrapolated)\n"
            f"Rule confirmed: {desc}\n"
            f"f({qx}) = {a0} + {d}*{qx} = {answer_val}"
        )
    else:
        a0, r = params["a0"], params["r"]
        ratio = round(y1 / y0, 4) if y0 != 0 else r
        cot = (
            f"Testing geometric sequence a(n) = a0 * r^n:\n"
            f"  Ratio {y1}/{y0} = {ratio} ≈ {r}\n"
            f"Rule confirmed: {desc}\n"
            f"f({qx}) = {a0} * {r}^{qx} = {answer_val}"
        )
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════
# TYPE 10: Equation Numeric Guess
# ══════════════════════════════════════════════════════════════════════════════


def make_equation_numeric_guess_puzzle(rng: random.Random) -> tuple:
    seq_type = rng.choice(["arithmetic", "geometric", "quadratic", "fibonacci"])

    if seq_type == "arithmetic":
        a0, d, n = rng.randint(1, 30), rng.randint(2, 20), rng.randint(6, 9)
        seq = [a0 + i * d for i in range(n)]
        cot_rule = f"Arithmetic sequence: each term increases by {d}."

    elif seq_type == "geometric":
        a0, r, n = rng.randint(1, 5), rng.randint(2, 4), rng.randint(5, 7)
        seq = [a0 * (r**i) for i in range(n)]
        if max(seq) > 100000:
            a0, d, n = rng.randint(1, 20), rng.randint(2, 15), rng.randint(6, 9)
            seq = [a0 + i * d for i in range(n)]
            cot_rule = f"Arithmetic sequence: each term increases by {d}."
        else:
            cot_rule = f"Geometric sequence: each term multiplied by {r}."

    elif seq_type == "quadratic":
        a, b, c, n = (
            rng.randint(1, 3),
            rng.randint(0, 5),
            rng.randint(0, 10),
            rng.randint(6, 8),
        )
        seq = [a * i * i + b * i + c for i in range(1, n + 1)]
        cot_rule = f"Quadratic sequence: second differences are constant = {2 * a}. Rule: f(n) = {a}n^2 + {b}n + {c}."

    else:
        a0, a1, n = rng.randint(1, 5), rng.randint(1, 5), rng.randint(7, 9)
        seq = [a0, a1]
        for _ in range(n - 2):
            seq.append(seq[-1] + seq[-2])
        cot_rule = f"Fibonacci-like: each term = sum of two preceding. Starts {a0}, {a1}."

    hide_idx = rng.randint(2, len(seq) - 2)
    answer_val = seq[hide_idx]
    seq_str = ", ".join("?" if i == hide_idx else str(v) for i, v in enumerate(seq))
    prompt = (
        f"{ALICE_HEADER}a secret number sequence follows a hidden rule.\n"
        f"Here is the sequence (one value is missing):\n"
        f"{seq_str}\n\n"
        f"What is the missing value (shown as ?)?"
    )
    answer = str(answer_val)
    before = seq[hide_idx - 1]
    after = seq[hide_idx + 1]
    cot = (
        f"Sequence: {seq_str}\n"
        f"Analysing known terms to find the pattern...\n"
        f"{cot_rule}\n\n"
        f"The term before the gap is {before}, after is {after}.\n"
        f"Position {hide_idx} (0-indexed) = {answer_val}.\n\n"
        f"The missing value is {answer_val}."
    )
    return prompt, answer, cot


# ══════════════════════════════════════════════════════════════════════════════

# ---------------------------------------------------------------------------
# v15 wrapper: category registry, cryptarithm-weighted mix, build + validate.
# ---------------------------------------------------------------------------

PUZZLE_MAKERS = {
    "cryptarithm_deduce": make_cryptarithm_deduce_puzzle,
    "cryptarithm_guess": make_cryptarithm_guess_puzzle,
    "equation_numeric_deduce": make_equation_numeric_deduce_puzzle,
    "equation_numeric_guess": make_equation_numeric_guess_puzzle,
    "bit": make_bit_puzzle,
    "symbol": make_symbol_puzzle,
    "encrypt": make_encryption_puzzle,
    "numeral": make_numeral_puzzle,
    "unit": make_unit_puzzle,
    "gravity": make_gravity_puzzle,
}

# Cryptarithm-heavy (~60%): it is the bottleneck category, but keep every other
# format present at lower volume so the adapter does not skew to one prompt shape.
DEFAULT_MIX = {
    "cryptarithm_deduce": 900,
    "cryptarithm_guess": 700,
    "equation_numeric_deduce": 200,
    "equation_numeric_guess": 200,
    "bit": 150,
    "symbol": 150,
    "encrypt": 100,
    "numeral": 80,
    "unit": 80,
    "gravity": 80,
}

# Exact-string categories: the CoT must literally contain the boxed answer.
# (gravity/unit/equation involve float rounding so we only soft-check those.)
EXACT_CATEGORIES = {
    "cryptarithm_deduce",
    "cryptarithm_guess",
    "numeral",
    "symbol",
    "encrypt",
}


def build_records(seed=42, mix=None):
    mix = mix or DEFAULT_MIX
    rng = random.Random(seed)
    records = []
    for cat, n in mix.items():
        maker = PUZZLE_MAKERS[cat]
        made = 0
        attempts = 0
        while made < n and attempts < n * 20:
            attempts += 1
            try:
                prompt, answer, cot = maker(rng)
            except Exception:
                continue
            if not prompt or not str(answer).strip() or not cot:
                continue
            records.append(
                {
                    "id": f"syn_{cat}_{made:06d}",
                    "prompt": prompt,
                    "answer": str(answer).strip(),
                    "cot": cot,
                    "category": cat,
                }
            )
            made += 1
    rng.shuffle(records)
    return records


def validate(records):
    from collections import Counter

    hist = Counter(r["category"] for r in records)
    exact_total = exact_ok = 0
    for r in records:
        if r["category"] in EXACT_CATEGORIES:
            exact_total += 1
            if r["answer"] in r["cot"]:
                exact_ok += 1
    assert exact_total == 0 or exact_ok == exact_total, (
        f"CoT/answer mismatch on exact categories: {exact_ok}/{exact_total}"
    )
    return {
        "n": len(records),
        "by_category": dict(hist),
        "exact_ok": f"{exact_ok}/{exact_total}",
    }


if __name__ == "__main__":
    recs = build_records()
    stats = validate(recs)
    print("records:", stats["n"])
    print("by_category:", stats["by_category"])
    print("exact CoT-answer consistency:", stats["exact_ok"])
    # unseen-symbol fraction across cryptarithm
    cry = [r for r in recs if r["category"].startswith("cryptarithm")]
    print(f"cryptarithm records: {len(cry)}")
    for r in recs[:2]:
        print("\n=== sample:", r["category"], "answer=", r["answer"], "===")
        print(r["prompt"][:300])
        print("--- cot ---")
        print(r["cot"][:500])
