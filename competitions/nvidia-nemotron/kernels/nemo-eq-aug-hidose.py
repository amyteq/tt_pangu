# Nemo EQ-Aug-Hidose — equation-specialist VARIANT (EQ-3 / nemo5). The coverage×dose
# corner of the grid: FULL-COVERAGE rotation (eq-aug: ~7,814 supervised targets, every
# (lhs,rhs) pair of each real prompt used as the query in turn, eval-faithful format) AND
# the equation targets repeated EQ_REPEAT× to push the dose even higher. Tests whether
# max coverage + max dose of the global cipher beats eq-aug (coverage only) and eq-hidose
# (dose only). Same machinery; rank-32 LoRA → late-submission eval + soup-with-v14.
# Original C1/V14 headers preserved below.
# ---
# Nemo Solver C1 — v14 backbone + verified real-prompt CoT (balanced ~1800)
# Nemo Replay V14 — reproduction of the public 0.86/0.87 "Replay" recipe
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

# equation-specialist knobs: train on ALL real equation prompts (~1555) → ~16% dose,
# matching the test category share; woven into the v14 replay recipe (keep general ability).
SYNTH_SEED = 42
MIN_EQ_EXAMPLES = 1000

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
# ---- Option C: embedded real-prompt solver (verified vs train.csv answers) --
# committed at competitions/nvidia-nemotron/lib/nemo_solver.py
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

    # ---- equation specialist: REAL equation prompts → \boxed{answer} ------------
    # EQ-0 found `equation` is one GLOBAL deterministic function (5-char→1-4-char, secret
    # 36-symbol cipher; the hand-crack resisted). So we teach the model the function from
    # the real train.csv prompts: user = full prompt (4 examples + query) + eval SUFFIX,
    # assistant = \boxed{answer} (answer-only — we can't write a rule CoT). Each prompt
    # embeds 4 in-context observations of the global function; covering all 1,555 prompts
    # exposes the whole 36-symbol alphabet. Generalisation to hidden inputs is the open
    # question — measured by late submission. Response-only masked; woven into v14 replay.
    import csv as _csv
    import glob as _glob

    _train_csv = _glob.glob("/kaggle/input/competitions/*/train.csv") or _glob.glob(
        "/kaggle/input/**/train.csv", recursive=True
    )
    assert _train_csv, "competition train.csv not found"
    _eqrows = [
        r
        for r in _csv.DictReader(open(_train_csv[0], encoding="utf-8"))
        if "transformation rules is applied to equations" in r["prompt"].lower()
    ]
    print(f"equation prompts in train.csv: {len(_eqrows)}")

    # eq-AUG: rotate every real prompt so each of its 5 (lhs,rhs) pairs becomes the
    # supervised query in turn (other 4 stay as in-context examples). Eval-faithful
    # format, REAL data lines only. ~7,775 supervised targets (vs 1,555 in eq-spec).
    import re as _re

    _PRE = (
        "In Alice's Wonderland, a secret set of transformation rules is applied to equations. Below are a few examples:"
    )
    _QRE = _re.compile(r"determine the result for:\s*(.+?)\s*$", _re.I)

    def _parse_eq(prompt, answer):
        ps = []
        for ln in prompt.split("\n"):
            if " = " in ln and "determine" not in ln.lower():
                lhs, rhs = ln.split(" = ", 1)
                ps.append((lhs, rhs))
        m = _QRE.search(prompt)
        if m:
            ps.append((m.group(1), answer.strip()))
        return ps

    def _build_eq_prompt(ctx_pairs, query_lhs):
        body = "\n".join(f"{lhs} = {rhs}" for lhs, rhs in ctx_pairs)
        return f"{_PRE}\n{body}\nNow, determine the result for: {query_lhs}"

    _aug = []
    for r in _eqrows:
        ps = _parse_eq(r["prompt"], r["answer"])
        if len(ps) < 2:
            continue
        for ti in range(len(ps)):
            tgt_lhs, tgt_rhs = ps[ti]
            ctx = [ps[j] for j in range(len(ps)) if j != ti]
            _aug.append((_build_eq_prompt(ctx, tgt_lhs), tgt_rhs))
    print(f"eq-aug: {len(_aug)} rotated supervised targets from {len(_eqrows)} prompts")

    _eos = tokenizer.eos_token_id
    SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"

    def _ptoks(problem):
        msgs = [{"role": "user", "content": problem + SUFFIX}]
        out = tokenizer.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True)
        if hasattr(out, "keys"):
            out = out["input_ids"]
        if out and isinstance(out[0], (list, tuple)):
            out = out[0]
        return list(out)

    solver_examples: list[dict] = []
    _sv_skipped = 0
    _sv_first = False
    for _prob, _ans in _aug:
        resp = "\\boxed{" + _ans.strip() + "}"
        prompt_ids = _ptoks(_prob)
        resp_ids = list(tokenizer(resp, add_special_tokens=False)["input_ids"])
        if _eos is not None:
            resp_ids = resp_ids + [_eos]
        full_ids = prompt_ids + resp_ids
        if len(full_ids) > MAX_SEQ_LEN:
            full_ids = full_ids[:MAX_SEQ_LEN]
            if len(full_ids) <= len(prompt_ids):
                _sv_skipped += 1
                continue
        prompt_len = min(len(prompt_ids), len(full_ids))
        mask = [0] * prompt_len + [1] * (len(full_ids) - prompt_len)
        if len(full_ids) < 2 or not any(mask[1:]):
            _sv_skipped += 1
            continue
        if not _sv_first:
            _sv_first = True
            print(f"eq row 0: prompt_ids={len(prompt_ids)}, full_ids={len(full_ids)}, resp={resp!r}")
        solver_examples.append(
            {
                "problem_id": "eq",
                "tokens": full_ids[:-1],
                "targets": full_ids[1:],
                "weights": [float(m) for m in mask[1:]],
            }
        )
    print(f"equation training examples: {len(solver_examples)} (skipped {_sv_skipped})")
    assert len(solver_examples) >= MIN_EQ_EXAMPLES, (
        f"only {len(solver_examples)} equation examples (skipped={_sv_skipped})"
    )
    # eq-aug-hidose: on top of full-coverage rotation, repeat targets to raise the dose.
    EQ_REPEAT = 2
    solver_examples = solver_examples * EQ_REPEAT
    print(f"eq-aug-hidose: dose repeat x{EQ_REPEAT} -> {len(solver_examples)} targets")
    sv_every = max(1, len(examples) // len(solver_examples))
    woven: list[dict] = []
    si = 0
    for i, ex in enumerate(examples):
        woven.append(ex)
        if (i + 1) % sv_every == 0 and si < len(solver_examples):
            woven.append(solver_examples[si])
            si += 1
    woven.extend(solver_examples[si:])
    examples = woven
    print(
        f"v11 self-distillation: {len(solver_examples)} verified examples woven "
        f"(skipped={_sv_skipped}, every ~{sv_every}); total now {len(examples)}"
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
