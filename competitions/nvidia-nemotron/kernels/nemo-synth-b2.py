# Nemo Synth B2 — cryptarithm+bit synth (~1000, ~11%) on v14 backbone
# Nemo Synth V15 — v14 replay recipe + cryptarithm-weighted synthetic CoT.
# Identical to nemo-replay-v14 (CCE, MoE tying, seq8192, LR 3.5e-4, 7h deadline)
# except ~2.6k deterministic synthetic reasoning examples (60% cryptarithm) are
# tokenised in-kernel and interleaved into the Huikang+replay mix, to lift the
# bottleneck category. v14 scored LB 0.85.
#
# (original v14 header) reproduction of the public 0.86/0.87 "Replay" recipe
# (kuangyicheng/nemotron-087-training, itself a clean reproduction of
# mohamedamr992's Nemotron+Replay_Data 0.86), with a KCA wall-clock budget so
# the session stays under 8h (T8 mechanism; D8/D9 approved 2026-06-12).
# ruff: noqa: E402  (Kaggle kernel: imports follow env/setup cells)
import time as _wall

T0 = _wall.time()
TRAIN_DEADLINE_SEC = 25200  # stop TRAINING at 7h elapsed; save+zip fits in the rest

# %%
# Final fixed training configuration
LORA_RANK = 32
LORA_ALPHA = 32
LORA_DROPOUT = 0.0

MAX_SEQ_LEN = 8192
NUM_STEPS = 1000
BATCH_SIZE = 32
MICRO_BATCH_SIZE = 4
LEARNING_RATE = 3.5e-4
WARMUP_STEPS = 0
GRAD_CLIP_NORM = 1e9

MIN_CORPUS_EXAMPLES = 1000
TARGET_REPLAY_ANSWER_TOKENS = 2_000_000
MIN_REPLAY_ANSWER_TOKENS = 1_900_000
MIN_REPLAY_EXAMPLES = 100

MOE_TIE_WEIGHTS = True
SHUFFLE_DATASET = False

# v15 synthetic-data knobs.
SYNTH_SEED = 42
MIN_SYNTH_EXAMPLES = 750

TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "up_proj",
    "down_proj",
    "in_proj",
    "out_proj",
    "lm_head",
]


# %%
# ---- v15: embedded cryptarithm-weighted synthetic CoT generator ----------
# (adapted from public varianceofx/synthetic-dataset-generator-27k; long CoT
# with pre-computed intermediate values, finality lines, unseen-symbol queries.
# committed at kernels/synth/nemo_synth_gen.py)
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
    "cryptarithm_deduce": 350,
    "cryptarithm_guess": 300,
    "bit": 350,
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


# %%
import os

assert os.path.isdir("/kaggle/input"), "This final notebook is Kaggle-only and must run inside a Kaggle session."
print("Kaggle runtime detected.")


# %%
# Offline input discovery and dependency installation
import subprocess

from pathlib import Path

INPUT_ROOT = Path("/kaggle/input")


def list_input_tree(root, max_depth=4, limit=250):
    root = Path(root)
    rows = []
    stack = [(root, 0)]
    while stack and len(rows) < limit:
        base, depth = stack.pop()
        if depth >= max_depth:
            continue
        try:
            children = sorted(base.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for child in children:
            rows.append(str(child))
            if child.is_dir():
                stack.append((child, depth + 1))
            if len(rows) >= limit:
                break
    return rows


def find_path(label, candidates, predicate=lambda path: True, required=True):
    import glob

    # Candidates are ordered from exact/cheap to broad/recursive. Stop at the
    # first valid candidate so standard mounts do not trigger a full tree scan.
    for raw_candidate in candidates:
        candidate = Path(raw_candidate)
        if any(char in str(candidate) for char in "*?["):
            matches = sorted(
                {
                    path.resolve()
                    for path in map(
                        Path,
                        glob.glob(
                            str(candidate),
                            recursive="**" in str(candidate),
                        ),
                    )
                    if predicate(path)
                }
            )
        else:
            matches = [candidate.resolve()] if predicate(candidate) else []

        if not matches:
            continue
        if len(matches) > 1:
            preferred = [
                path
                for path in matches
                if any(
                    token in str(path).lower()
                    for token in (
                        "nemotron-3-nano-30b-a3b-bf16",
                        "huikang-nemotron-repository-snapshot",
                        "nvidia-nemotron-model-reasoning-challenge",
                        "replay-math",
                    )
                )
            ]
            if len(preferred) == 1:
                matches = preferred
        if len(matches) > 1 and not required:
            print(
                f"Optional {label} matched multiple paths; using {matches[0]}. "
                f"All matches: {[str(path) for path in matches]}"
            )
            matches = [matches[0]]
        assert len(matches) == 1, (
            f"{label} is ambiguous for candidate {raw_candidate}: {[str(path) for path in matches]}"
        )
        return matches[0]

    message = (
        f"{label} not found using candidates {[str(x) for x in candidates]}. "
        f"/kaggle/input tree sample: {list_input_tree(INPUT_ROOT)}"
    )
    if required:
        raise AssertionError(message)
    print(f"Optional input skipped: {message}")
    return None


def find_unique(label, candidates, predicate=lambda path: True):
    return find_path(label, candidates, predicate, required=True)


PACKAGES_DIR = find_unique(
    "nemotron offline packages",
    [
        "/kaggle/input/datasets/mayukh18/nemotron-packages/packages",
        "/kaggle/input/datasets/mayukh18/nemotron-packages/*/packages",
    ],
    lambda path: path.is_dir(),
)
CAUSAL_WHEEL = find_unique(
    "causal_conv1d wheel",
    [
        "/kaggle/input/datasets/mayukh18/nemotron-packages/causal_conv1d-*.whl",
        "/kaggle/input/datasets/mayukh18/nemotron-packages/*/causal_conv1d-*.whl",
    ],
    lambda path: path.is_file(),
)
MAMBA_WHEEL = find_unique(
    "mamba_ssm wheel",
    [
        "/kaggle/input/datasets/mayukh18/nemotron-packages/mamba_ssm-*.whl",
        "/kaggle/input/datasets/mayukh18/nemotron-packages/*/mamba_ssm-*.whl",
    ],
    lambda path: path.is_file(),
)
RTX_WHEELS_DIR = find_unique(
    "RTX wheels directory",
    [
        "/kaggle/input/datasets/llkh0a/rtx-wheels/wheels",
        "/kaggle/input/datasets/llkh0a/rtx-wheels/*/wheels",
    ],
    lambda path: path.is_dir(),
)
MODEL_CONFIG = find_unique(
    "Nemotron BF16 base model",
    [
        "/kaggle/input/models/metric/nemotron-3-nano-30b-a3b-bf16/transformers/default/1/config.json",
        "/kaggle/input/models/metric/nemotron-3-nano-30b-a3b-bf16/transformers/default/*/config.json",
    ],
    lambda path: (
        path.is_file()
        and ((path.parent / "model.safetensors.index.json").is_file() or any(path.parent.glob("*.safetensors")))
    ),
)
MODEL_PATH = str(MODEL_CONFIG.parent)
TRAIN_CSV = find_unique(
    "competition train.csv",
    [
        "/kaggle/input/competitions/nvidia-nemotron-model-reasoning-challenge/train.csv",
    ],
    lambda path: path.is_file(),
)
TRAIN_CSV_PATH = str(TRAIN_CSV)
with TRAIN_CSV.open(encoding="utf-8") as train_file:
    train_header = train_file.readline().strip().split(",")
assert train_header == ["id", "prompt", "answer"], train_header
MATH_REPLAY_FILE = find_unique(
    "math replay JSONL",
    [
        "/kaggle/input/datasets/mohamedamr992/replay-math/nemotron_math_1gb.jsonl",
        "/kaggle/input/datasets/mohamedamr992/replay-math/*/nemotron_math_1gb.jsonl",
        "/kaggle/input/datasets/mohamedamr992/**/nemotron_math_1gb.jsonl",
    ],
    lambda path: path.is_file() and path.stat().st_size > 100_000_000,
)
MATH_REPLAY_PATH = str(MATH_REPLAY_FILE)
HUIKANG_SFT_DIR = find_unique(
    "Huikang 04-08-16-14 corpus",
    [
        "/kaggle/input/datasets/huikang/huikang-nemotron-repository-snapshot/nemotron-master/training/sft/04-08-16-14",
        "/kaggle/input/datasets/huikang/huikang-nemotron-repository-snapshot/*/nemotron-master/training/sft/04-08-16-14",
        "/kaggle/input/huikang-nemotron-repository-snapshot/nemotron-master/training/sft/04-08-16-14",
        "/kaggle/input/datasets/huikang/*/nemotron-master/training/sft/04-08-16-14",
        "/kaggle/input/datasets/huikang/*/*/nemotron-master/training/sft/04-08-16-14",
        "/kaggle/input/datasets/huikang/**/nemotron-master/training/sft/04-08-16-14",
    ],
    lambda path: path.is_dir() and (path / "tokens").is_dir() and (path / "logprobs/index.jsonl").is_file(),
)
CORPUS_PATH = str(HUIKANG_SFT_DIR / "tokens")
TRAIN_ORDER_PATH = str(HUIKANG_SFT_DIR / "logprobs/index.jsonl")

discovered_inputs = {
    "packages": PACKAGES_DIR,
    "causal wheel": CAUSAL_WHEEL,
    "mamba wheel": MAMBA_WHEEL,
    "RTX wheels": RTX_WHEELS_DIR,
    "base model": MODEL_PATH,
    "train.csv": TRAIN_CSV_PATH,
    "math replay": MATH_REPLAY_PATH,
    "Huikang tokens": CORPUS_PATH,
    "Huikang order": TRAIN_ORDER_PATH,
}

print("Mounted Kaggle Inputs were discovered and validated.")
for label, path in discovered_inputs.items():
    print(f"  {label}: {path}")

subprocess.run(
    f"pip install -q --no-index --find-links {PACKAGES_DIR} "
    "unsloth trl peft transformers datasets accelerate bitsandbytes",
    shell=True,
    check=True,
)
subprocess.run(
    f"pip install -q {CAUSAL_WHEEL}",
    shell=True,
    check=True,
)
subprocess.run(
    f"pip install -q {MAMBA_WHEEL}",
    shell=True,
    check=True,
)
for _wd in [str(RTX_WHEELS_DIR)]:
    if os.path.isdir(_wd):
        subprocess.run(
            [
                "pip",
                "install",
                "-q",
                "--no-index",
                "--find-links",
                _wd,
                "protobuf==6.33.5",
                "sentencepiece",
                "safetensors",
                "huggingface_hub",
            ],
            check=False,
        )
subprocess.run("rm -rf /kaggle/tmp/*", shell=True, check=True)


# %%
def run_training() -> None:
    """Reproduce the public fresh rank-32 Replay-Math LoRA recipe."""
    import gc
    import json
    import math
    import random
    import sys
    import time

    from unsloth import FastLanguageModel

    import torch
    from cut_cross_entropy import linear_cross_entropy
    from peft import LoraConfig
    from peft.tuners.lora import Linear as LoraLinear

    # -- Validated Kaggle input paths ---------------------------------
    CORPUS_PATH = globals()["CORPUS_PATH"]
    TRAIN_ORDER_PATH = globals()["TRAIN_ORDER_PATH"]
    # (train.csv is validated at input-discovery time above; not used in training)
    MODEL_PATH = globals()["MODEL_PATH"]
    MATH_REPLAY_PATH = globals()["MATH_REPLAY_PATH"]
    print("Fresh LoRA training: no external adapter or warm start")

    # -- GPU + kernel sanity check -------------------------------------
    import causal_conv1d
    import mamba_ssm

    cc = torch.cuda.get_device_capability(0)
    print(f"GPU: {torch.cuda.get_device_name(0)}, sm_{cc[0] * 10 + cc[1]}")
    print(f"torch={torch.__version__}, cuda={torch.version.cuda}")
    print(f"mamba_ssm={mamba_ssm.__version__}, causal_conv1d={causal_conv1d.__version__}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    assert cc == (12, 0), f"Expected sm_120 (RTX PRO 6000), got sm_{cc[0] * 10 + cc[1]}"
    from causal_conv1d import causal_conv1d_fn

    _x = torch.randn(1, 256, 32, device="cuda", dtype=torch.bfloat16)
    _w = torch.randn(256, 4, device="cuda", dtype=torch.bfloat16)
    causal_conv1d_fn(_x, _w, None, activation="silu")
    print("causal_conv1d CUDA kernel: OK")

    # -- Load corpus into `examples` list -----------------------------
    examples: list[dict] = []

    # Load problem_ids in training order from logprobs/index.jsonl (epoch 0).
    # Each entry has {epoch, step, problem_id, ...}; epoch-0 entries are the
    # original training order, which we replay here.
    ordered_ids: list[str] = []
    seen: set[str] = set()
    with open(TRAIN_ORDER_PATH) as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("epoch", 0) != 0:
                continue
            pid = rec["problem_id"]
            if pid in seen:
                continue
            seen.add(pid)
            ordered_ids.append(pid)
    print(f"Loaded {len(ordered_ids)} problem_ids in training order from {TRAIN_ORDER_PATH}")

    for sid in ordered_ids:
        seg_path = os.path.join(CORPUS_PATH, sid, "synthetic.json")
        assert os.path.isfile(seg_path), f"problem_id {sid} from training order missing in corpus: {seg_path}"
        with open(seg_path) as f:
            rec = json.load(f)
        tokens = rec["tokens"]
        mask = rec["mask"]
        if not tokens:
            continue
        if len(tokens) > MAX_SEQ_LEN:
            tokens = tokens[:MAX_SEQ_LEN]
            mask = mask[:MAX_SEQ_LEN]
        if not any(mask):
            continue
        examples.append(
            {
                "problem_id": sid,
                "tokens": tokens[:-1],
                "targets": tokens[1:],
                "weights": [float(m) for m in mask[1:]],
            }
        )
    total_unmasked = sum(sum(e["weights"]) for e in examples)
    total_tokens = sum(len(e["tokens"]) for e in examples)
    print(f"Loaded {len(examples)} examples, {total_tokens:,} tokens (unmasked={total_unmasked:,.0f})")

    assert len(ordered_ids) >= MIN_CORPUS_EXAMPLES, (
        f"Corpus order is unexpectedly small: {len(ordered_ids)} ids; expected at least {MIN_CORPUS_EXAMPLES}."
    )
    assert len(examples) >= MIN_CORPUS_EXAMPLES, (
        f"Corpus produced only {len(examples)} examples; expected at least {MIN_CORPUS_EXAMPLES}."
    )

    # -- Load base model ----------------------------------------------
    gc.collect()
    torch.cuda.empty_cache()

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_PATH,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=False,
        load_in_8bit=False,
        full_finetuning=False,
        trust_remote_code=True,
        unsloth_force_compile=True,
        attn_implementation="eager",
        dtype=torch.bfloat16,
    )
    replay_examples: list[dict] = []
    replay_answer_tokens = 0
    replay_skipped = 0
    replay_truncated = 0

    def _template_ids(msgs, add_gen):
        # v14 v1 failed with "0 replay examples": on the current Kaggle image
        # apply_chat_template(tokenize=True) returns a BatchEncoding, so
        # len(full_ids) <= len(prompt_ids) compared DICT KEY COUNTS (2 <= 2)
        # and silently skipped every row. Unwrap to a flat token list.
        out = tokenizer.apply_chat_template(msgs, tokenize=True, add_generation_prompt=add_gen)
        if hasattr(out, "keys"):
            out = out["input_ids"]
        if out and isinstance(out[0], (list, tuple)):
            out = out[0]
        return list(out)

    _first_row_logged = False
    with open(MATH_REPLAY_PATH, encoding="utf-8") as replay_file:
        for line in replay_file:
            row = json.loads(line)
            messages = row.get("messages")
            if not messages or len(messages) < 2:
                replay_skipped += 1
                continue

            prompt_ids = _template_ids(messages[:-1], True)
            full_ids = _template_ids(messages, False)
            if not _first_row_logged:
                _first_row_logged = True
                print(
                    f"replay row 0: keys={sorted(row.keys())}, prompt_ids={len(prompt_ids)}, full_ids={len(full_ids)}"
                )
            if len(full_ids) <= len(prompt_ids):
                replay_skipped += 1
                continue
            if len(full_ids) > MAX_SEQ_LEN:
                full_ids = full_ids[:MAX_SEQ_LEN]
                replay_truncated += 1

            prompt_len = min(len(prompt_ids), len(full_ids))
            mask = [0] * prompt_len + [1] * (len(full_ids) - prompt_len)
            if len(full_ids) < 2 or not any(mask[1:]):
                replay_skipped += 1
                continue

            replay_examples.append(
                {
                    "problem_id": "replay_math",
                    "tokens": full_ids[:-1],
                    "targets": full_ids[1:],
                    "weights": [float(m) for m in mask[1:]],
                }
            )
            replay_answer_tokens += sum(mask)
            if replay_answer_tokens >= TARGET_REPLAY_ANSWER_TOKENS:
                break

    assert len(replay_examples) >= MIN_REPLAY_EXAMPLES, f"Only {len(replay_examples)} replay examples were tokenized."
    assert replay_answer_tokens >= MIN_REPLAY_ANSWER_TOKENS, (
        f"Only {replay_answer_tokens:,} supervised replay answer tokens; "
        f"expected at least {MIN_REPLAY_ANSWER_TOKENS:,}."
    )

    mixed_examples: list[dict] = []
    replay_idx = 0
    replay_every = max(1, len(examples) // len(replay_examples))
    for i, example in enumerate(examples):
        mixed_examples.append(example)
        if (i + 1) % replay_every == 0 and replay_idx < len(replay_examples):
            mixed_examples.append(replay_examples[replay_idx])
            replay_idx += 1
    mixed_examples.extend(replay_examples[replay_idx:])
    examples = mixed_examples

    print(
        f"Math replay: {len(replay_examples)} examples, "
        f"{replay_answer_tokens:,} supervised answer tokens, "
        f"skipped={replay_skipped}, truncated={replay_truncated}"
    )
    print(f"Replay inserted every ~{replay_every} Huikang examples; mixed total={len(examples)}")

    # ---- v15: cryptarithm-weighted synthetic CoT, tokenised + interleaved -----
    # Same masking convention as the replay block (reasoning_content + boxed
    # content, prompt tokens masked out). The user turn carries the eval SUFFIX
    # so the trained prompt shape matches the grader exactly.
    SYNTH_SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"
    synth_records = build_records(seed=SYNTH_SEED)
    synth_examples: list[dict] = []
    synth_skipped = 0
    synth_truncated = 0
    _synth_first = False
    for rec in synth_records:
        messages = [
            {"role": "user", "content": rec["prompt"] + SYNTH_SUFFIX},
            {
                "role": "assistant",
                "reasoning_content": rec["cot"],
                "content": f"\\boxed{{{rec['answer']}}}",
            },
        ]
        prompt_ids = _template_ids(messages[:-1], True)
        full_ids = _template_ids(messages, False)
        if not _synth_first:
            _synth_first = True
            print(f"synth row 0 ({rec['category']}): prompt_ids={len(prompt_ids)}, full_ids={len(full_ids)}")
        if len(full_ids) <= len(prompt_ids):
            synth_skipped += 1
            continue
        if len(full_ids) > MAX_SEQ_LEN:
            full_ids = full_ids[:MAX_SEQ_LEN]
            synth_truncated += 1
        prompt_len = min(len(prompt_ids), len(full_ids))
        mask = [0] * prompt_len + [1] * (len(full_ids) - prompt_len)
        if len(full_ids) < 2 or not any(mask[1:]):
            synth_skipped += 1
            continue
        synth_examples.append(
            {
                "problem_id": "synth_" + rec["category"],
                "tokens": full_ids[:-1],
                "targets": full_ids[1:],
                "weights": [float(m) for m in mask[1:]],
            }
        )
    assert len(synth_examples) >= MIN_SYNTH_EXAMPLES, (
        f"only {len(synth_examples)} synthetic examples tokenised (skipped={synth_skipped})"
    )
    if synth_examples:
        synth_every = max(1, len(examples) // len(synth_examples))
        woven: list[dict] = []
        si = 0
        for i, ex in enumerate(examples):
            woven.append(ex)
            if (i + 1) % synth_every == 0 and si < len(synth_examples):
                woven.append(synth_examples[si])
                si += 1
        woven.extend(synth_examples[si:])
        examples = woven
    print(
        f"Synthetic: {len(synth_examples)} examples "
        f"(skipped={synth_skipped}, truncated={synth_truncated}); "
        f"interleaved every ~{synth_every}; total examples now {len(examples)}"
    )

    # -- Wrap in LoRA -------------------------------------------------
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_RANK,
        target_modules=TARGET_MODULES,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing=True,
        random_state=42,
    )
    FastLanguageModel.for_training(model)

    # -- Patch Mamba CUDA fast path -----------------------------------
    nemotron_mod = None
    for _name, _m in sys.modules.items():
        if "modeling_nemotron_h" in _name and hasattr(_m, "is_fast_path_available"):
            nemotron_mod = _m
            break
    assert nemotron_mod is not None, "Could not find modeling_nemotron_h module"
    print(f"is_fast_path_available was: {nemotron_mod.is_fast_path_available}")
    nemotron_mod.is_fast_path_available = True  # type: ignore[attr-defined]
    print("Patched is_fast_path_available = True")

    # -- Manually add lm_head LoRA (Unsloth drops it for MoE) ---------
    _causal_lm = model
    while hasattr(_causal_lm, "model"):
        _causal_lm = _causal_lm.model
    _lm_head = _causal_lm.lm_head
    if not isinstance(_lm_head, LoraLinear):
        _cfg = LoraConfig(r=LORA_RANK, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT)
        model.base_model._create_and_replace(
            _cfg,
            "default",
            target=_lm_head,
            target_name="lm_head",
            parent=_causal_lm,
        )
        print("Manually added LoRA to lm_head")
    else:
        print("lm_head already has LoRA")

    # -- Cast LoRA params to fp32 (base model stays bf16 except MoE router) --
    for name, param in model.named_parameters():
        if ".lora_" in name:
            param.data = param.data.to(torch.float32)

    for name, param in model.named_parameters():
        if ".lora_" in name:
            assert param.dtype == torch.float32, f"LoRA param {name} expected fp32, got {param.dtype}"
            continue

        is_router = ".mixer.gate." in name  # NemotronHTopkRouter.weight + e_score_correction_bias
        # Nemotron-H loads the MoE router (`mixer.gate`) in fp32 on purpose.
        # Ref: transformers/src/transformers/models/nemotron_h/modeling_nemotron_h.py
        #
        #   class NemotronHPreTrainedModel(PreTrainedModel):
        #       _keep_in_fp32_modules_strict = ["e_score_correction_bias"]
        #
        #   class NemotronHTopkRouter(nn.Module):
        #       def __init__(self, config):
        #           self.weight = nn.Parameter(torch.empty((self.n_routed_experts, config.hidden_size)))
        #           self.register_buffer("e_score_correction_bias", torch.zeros(self.n_routed_experts))
        #       def forward(self, hidden_states):
        #           router_logits = F.linear(
        #               hidden_states.type(torch.float32),
        #               self.weight.type(torch.float32),
        #           )
        #           return router_logits
        #
        # The per-forward fp32 cast on `self.weight` plus the strict list entry
        # mean the gate weight is promoted to fp32 at load time.
        if is_router:
            assert param.dtype == torch.float32, f"param {name} expected fp32, got {param.dtype}"
            continue

        assert param.dtype == torch.bfloat16, f"param {name} expected bf16, got {param.dtype}"
        continue

    print("Verified: LoRA params fp32, base params bf16 (MoE router fp32)")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Model: {trainable:,} trainable / {total:,} total parameters")

    # -- Patch forward with Cut Cross-Entropy -------------------------
    _base = model
    while hasattr(_base, "model"):
        _base = _base.model

    def _patched_causal_forward(input_ids=None, attention_mask=None, labels=None, **kwargs):
        backbone_out = _base.backbone(
            input_ids=input_ids,
            attention_mask=attention_mask,
            **{k: v for k, v in kwargs.items() if k in ("position_ids", "past_key_values", "use_cache")},
        )
        hidden_states = backbone_out[0]
        lm_head = _base.lm_head
        base_w = lm_head.base_layer.weight
        lora_A = lm_head.lora_A["default"].weight
        lora_B = lm_head.lora_B["default"].weight
        scaling = lm_head.scaling["default"]
        lm_weight = base_w + scaling * lora_B @ lora_A
        if labels is not None:
            per_token_ce = linear_cross_entropy(hidden_states, lm_weight, labels, reduction="none")
            loss = per_token_ce.mean()
        else:
            per_token_ce = None
            loss = None
        model._cached_per_token_ce = per_token_ce  # type: ignore[attr-defined]
        return loss

    _base.forward = _patched_causal_forward
    print("Patched CausalLM.forward with CCE (no logits materialization)")

    # Fresh initialization is intentional; no adapter is loaded here.
    print("Fresh rank-32 LoRA initialization confirmed")

    trainable_names = [name for name, param in model.named_parameters() if param.requires_grad]
    assert trainable_names, "No trainable LoRA parameters found"
    assert all(".lora_" in name for name in trainable_names), (
        f"Unexpected non-LoRA trainable tensors: {[name for name in trainable_names if '.lora_' not in name][:20]}"
    )
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    print(f"  {trainable_params:,} trainable / {frozen_params:,} frozen")
    print(f"  trainable tensors: {len(trainable_names)}")

    # -- Shared-expert MoE tied-weight parameters ----------------------
    # Tie whichever LoRA side touches the hidden dimension:
    #   gate_up_proj / up_proj / w1 / gate_proj  -> tie A (input/hidden side)
    #   down_proj / w2                           -> tie B (output/hidden side)
    # We keep Unsloth's batched [num_experts, ...] tensor layout; "tying" means
    # all 128 expert slices are kept identical. Saving the adapter naturally
    # emits 128 per-expert copies, so submission.zip is untied downstream.
    moe_tied_params: list[torch.Tensor] = []
    if MOE_TIE_WEIGHTS:
        w1_proj_names = ("gate_up_proj", "up_proj", "gate_proj", ".w1.")
        w2_proj_names = ("down_proj", ".w2.")
        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue
            if ".experts." not in name or ".lora_" not in name:
                continue
            is_w1 = any(p in name for p in w1_proj_names)
            is_w2 = any(p in name for p in w2_proj_names)
            is_A = ".lora_A." in name
            is_B = ".lora_B." in name
            should_tie = (is_w1 and is_A) or (is_w2 and is_B)
            if not should_tie:
                continue
            if param.dim() < 2 or param.shape[0] <= 1:
                continue
            moe_tied_params.append(param)

        def _tie_param_init() -> None:
            """Make all 128 expert slices identical (mean-and-broadcast)."""
            with torch.no_grad():
                for p in moe_tied_params:
                    mean = p.data.mean(dim=0, keepdim=True)
                    p.data.copy_(mean.expand_as(p.data))

        def _tie_grads() -> None:
            # Sum (not mean) across the expert dim: if W is the shared LoRA factor
            # and each expert uses a copy W_i = W, chain rule gives
            # dL/dW = sum_i dL/dW_i. Inactive experts contribute 0 and router
            # weights are already baked into active g_i, so there's no
            # double-counting. Summing keeps all 128 slices identical after each
            # AdamW step and reproduces the true shared-weight update; mean would
            # be off by a 1/128 lr rescale (and not exactly equivalent under
            # AdamW's eps/weight-decay).
            with torch.no_grad():
                for p in moe_tied_params:
                    if p.grad is None:
                        continue
                    grad_sum = p.grad.sum(dim=0, keepdim=True)
                    p.grad.copy_(grad_sum.expand_as(p.grad))

        print(f"MoE weight tying: {len(moe_tied_params)} params identified for tying")
        if moe_tied_params:
            print(f"  example shapes: {[tuple(p.shape) for p in moe_tied_params[:3]]}")
        _tie_param_init()  # start from a tied state
    else:

        def _tie_grads() -> None:
            pass

    # -- Training loop ------------------------------------------------
    gc.collect()
    torch.cuda.empty_cache()

    device = next(model.parameters()).device
    optimizer: torch.optim.AdamW | None = None

    assert examples, "No Huikang training examples loaded from the required token corpus."
    indices = list(range(len(examples)))
    if SHUFFLE_DATASET:
        rng = random.Random(0)
        rng.shuffle(indices)
        print(f"SHUFFLE_DATASET=True: shuffled {len(indices)} examples (seed=0)")
    else:
        print(f"SHUFFLE_DATASET=False: keeping corpus order ({len(indices)} examples)")

    training_log: list[str] = []

    def _log(msg: str) -> None:
        print(msg, flush=True)
        training_log.append(msg)

    # Match the public 0.86 recipe: train full batches only.
    max_steps = len(examples) // BATCH_SIZE
    num_steps = NUM_STEPS
    if num_steps > max_steps:
        _log(
            f"WARNING: NUM_STEPS={NUM_STEPS} exceeds max_steps={max_steps} "
            f"({len(examples)} examples // {BATCH_SIZE} batch). Clamping to {max_steps}."
        )
        num_steps = max_steps

    _log(
        f"Training: {num_steps} steps, batch_size={BATCH_SIZE}, micro_batch_size={MICRO_BATCH_SIZE}, lr={LEARNING_RATE}"
    )

    step = 0
    for batch_start in range(0, len(indices), BATCH_SIZE):
        if step >= num_steps:
            break
        # KCA wall-clock budget: Kaggle sessions hard-stop and lose everything;
        # stop training in time to always reach save + zip (deadline measured
        # from kernel start, so pip/model/corpus load all count against it).
        if _wall.time() - T0 > TRAIN_DEADLINE_SEC:
            _log(
                f"WALL-CLOCK BUDGET hit at step {step}/{num_steps} "
                f"({_wall.time() - T0:.0f}s elapsed) — stopping to save adapter"
            )
            break
        batch_indices = indices[batch_start : batch_start + BATCH_SIZE]
        batch = [examples[i] for i in batch_indices]
        batch_tokens = [e["tokens"] for e in batch]
        batch_targets = [e["targets"] for e in batch]
        batch_weights = [e["weights"] for e in batch]

        n = len(batch)
        n_accum = math.ceil(n / MICRO_BATCH_SIZE)
        total_loss_sum = 0.0
        total_weight_sum = 0.0

        for mb_start in range(0, n, MICRO_BATCH_SIZE):
            mb_end = min(mb_start + MICRO_BATCH_SIZE, n)
            mb_toks = batch_tokens[mb_start:mb_end]
            mb_tgts = batch_targets[mb_start:mb_end]
            mb_wts = batch_weights[mb_start:mb_end]

            n_micro = len(mb_toks)
            max_len = max(len(t) for t in mb_toks)
            total_len = sum(len(t) for t in mb_toks)

            padded_input = torch.zeros(n_micro, max_len, dtype=torch.long, device=device)
            padded_targets = torch.zeros(n_micro, max_len, dtype=torch.long, device=device)
            padded_weights = torch.zeros(n_micro, max_len, dtype=torch.float32, device=device)
            attention_mask = torch.zeros(n_micro, max_len, dtype=torch.long, device=device)
            for i in range(n_micro):
                seq_len = len(mb_toks[i])
                padded_input[i, :seq_len] = torch.tensor(mb_toks[i], dtype=torch.long)
                padded_targets[i, :seq_len] = torch.tensor(mb_tgts[i], dtype=torch.long)
                padded_weights[i, :seq_len] = torch.tensor(mb_wts[i], dtype=torch.float32)
                attention_mask[i, :seq_len] = 1

            t0 = time.time()
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                model(
                    input_ids=padded_input,
                    attention_mask=attention_mask,
                    labels=padded_targets,
                    use_cache=False,
                )
                per_token_ce = model._cached_per_token_ce  # type: ignore[attr-defined]
                weighted_loss = per_token_ce * padded_weights
                weight_sum_t = padded_weights.sum()
                loss_sum_t = weighted_loss.sum()
                loss = loss_sum_t / weight_sum_t if weight_sum_t > 0 else loss_sum_t * 0.0
                assert torch.isfinite(loss), f"Non-finite loss at step {step}"

            (loss / n_accum).backward()
            total_loss_sum += loss_sum_t.item()
            total_weight_sum += weight_sum_t.item()
            del loss, per_token_ce, weighted_loss

            t_end = time.time()
            peak_gb = torch.cuda.max_memory_allocated() / 1e9
            mem_gb = torch.cuda.memory_allocated() / 1e9
            mb_idx = mb_start // MICRO_BATCH_SIZE
            print(
                f"    micro-batch {mb_idx}: {n_micro} seqs, max_len={max_len}, "
                f"total_len={total_len}, wall={t_end - t0:.1f}s, "
                f"peak={peak_gb:.1f}GB, mem={mem_gb:.1f}GB"
            )

        if optimizer is None:
            optimizer = torch.optim.AdamW(
                [p for p in model.parameters() if p.requires_grad],
                lr=LEARNING_RATE,
                betas=(0.9, 0.95),
                eps=1e-8,
                weight_decay=0.0,
            )
        if step < WARMUP_STEPS:
            lr = LEARNING_RATE * (step + 1) / WARMUP_STEPS
        else:
            decay_steps = max(1, num_steps - WARMUP_STEPS)
            decay_progress = (step - WARMUP_STEPS) / decay_steps
            lr = LEARNING_RATE * max(0.0, 1.0 - decay_progress)
        for pg in optimizer.param_groups:
            pg["lr"] = lr
        _tie_grads()  # sum tied-expert grads before the optimizer step
        grad_norm = torch.nn.utils.clip_grad_norm_(
            [p for p in model.parameters() if p.requires_grad],
            max_norm=GRAD_CLIP_NORM,
        )
        optimizer.step()
        optimizer.zero_grad()
        loss_mean = total_loss_sum / total_weight_sum if total_weight_sum > 0 else 0
        step += 1
        _log(f"  step {step}/{num_steps}: loss:mean={loss_mean:.6f}, grad_norm={grad_norm:.4f}, lr={lr:.2e}")

    print(f"\nTraining complete. Peak VRAM: {torch.cuda.max_memory_allocated() / 1e9:.1f} GB")

    # -- Save adapter + rename lm_head keys (identical on both sides) --
    from safetensors.torch import load_file, save_file

    save_dir = "/kaggle/working"
    os.makedirs(save_dir, exist_ok=True)
    for _f in os.listdir(save_dir):
        if _f.startswith("adapter"):
            os.remove(os.path.join(save_dir, _f))
    model.save_pretrained(save_dir)
    st_path = os.path.join(save_dir, "adapter_model.safetensors")
    tensors = load_file(st_path)
    renamed = {
        k.replace("base_model.model.lm_head.", "base_model.model.backbone.lm_head."): v for k, v in tensors.items()
    }
    save_file(renamed, st_path)

    # -- Clean unsloth compiled cache (runs on both) ------------------
    _ucache = "unsloth_compiled_cache"
    if os.path.isdir(_ucache):
        import shutil as _sh

        _sh.rmtree(_ucache)

    # -- Package and validate the only submission artifact -------------
    import hashlib
    import zipfile

    adapter_files = sorted(f for f in os.listdir(save_dir) if f.startswith("adapter"))
    assert adapter_files == [
        "adapter_config.json",
        "adapter_model.safetensors",
    ], adapter_files

    submission_zip = "/kaggle/working/submission.zip"
    with zipfile.ZipFile(submission_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in adapter_files:
            zf.write(os.path.join(save_dir, filename), filename)

    with zipfile.ZipFile(submission_zip, "r") as zf:
        zip_names = set(zf.namelist())
        assert zip_names == {
            "adapter_config.json",
            "adapter_model.safetensors",
        }, zip_names
        saved_config = json.loads(zf.read("adapter_config.json"))
        assert saved_config.get("r") == LORA_RANK == 32, saved_config
        assert saved_config.get("lora_alpha") == LORA_ALPHA == 32, saved_config
        assert zf.getinfo("adapter_model.safetensors").file_size > 1_000_000

    digest = hashlib.sha256()
    with open(submission_zip, "rb") as submission_file:
        for chunk in iter(lambda: submission_file.read(1024 * 1024), b""):
            digest.update(chunk)

    for filename in adapter_files:
        os.remove(os.path.join(save_dir, filename))

    print(f"Wrote {submission_zip}")
    print(f"Submission validation OK: root files only, rank={LORA_RANK}, alpha={LORA_ALPHA}")
    print(f"submission.zip sha256={digest.hexdigest()}")
    print("Training complete.")


# %%
# Start the single public-recipe reproduction run.
run_training()
