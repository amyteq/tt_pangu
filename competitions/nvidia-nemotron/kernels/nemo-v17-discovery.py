# Nemo v17-discovery — Saturday test version, Part A of the LB80 plan
# (competitions/nvidia-nemotron/external/LB80/analysis/next_version_plan.md).
# Backbone = the proven v14 Replay recipe (0.85), VERBATIM below. Adds the
# equation "discovery" lever (the highest-EV, novel borrow from mspawar/LB80):
#
#   PREMISE (locally validated — analysis/equation/probe_aopb.py): our `equation`
#   prompts ARE per-problem ciphers, NOT one global function (this CORRECTS our
#   EQ-0/EQ-2' framing). Each 5-char input is two 2-char operands + a middle char,
#   under a per-problem symbol->digit bijection; ~75% of problems have <=10 distinct
#   digit-symbols (a 0-9 cipher is feasible -> offline-crackable), with a ~25%
#   >10-symbol hard tail. The middle char is NOT a fixed operator (constant within a
#   problem only ~2% of the time) -> the OPERATION must be SEARCHED (answer-guided),
#   as in mspawar's ~83-op CP-SAT solver.
#
#   THE LEVER ("discovery leakage" fix): eq-aug capped because it memorised seen
#   pairs (taught VERIFY, not DISCOVER). Here we build a FORWARD-EXECUTABLE CoT that
#   shows the cipher+op DISCOVERY (enumerate hypotheses -> test each against the
#   example equations -> eliminate -> apply to the query), audited so the stated
#   mapping actually reproduces the boxed answer (mspawar: 93-97% of answer-guided
#   traces are internally inconsistent). Woven <=15% into v14 (DISCOVERY_COT_DOSE).
#
# [SCAFFOLD, default OFF] solve_equation_discovery() + build_discovery_cot_examples()
# implement the answer-guided per-problem solver + forward CoT. The full ~83-op
# CP-SAT solver (mspawar: 669 GPU-free minutes) + the >8192-token CoT-length control
# need completion on Saturday; default DISCOVERY_COT_DOSE=0 runs as a valid v14
# reproduction. Gate before submit (per plan): T12 equation up, no bit/cipher
# regression, every trace internal-consistency-audited.
# NOTE: analysis/prep artifact — NOT run or pushed to Kaggle here.
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

# --- v17-discovery lever (LB80 plan, Part A) ------------------------------
DISCOVERY_COT_DOSE = 0.0  # fraction of forward-executable equation discovery-CoT to weave (set <=0.15 Saturday)
DISCOVERY_OPS = (
    "+",
    "-",
    "*",
    "absdiff",
)  # seed op family; extend toward mspawar's ~83 ops on Saturday
DISCOVERY_MAX_SYMBOLS = (
    10  # skip problems with >10 distinct digit-symbols (the hard tail, ~25%)
)
# NemotronH gate_proj (MoE router) stays out of LoRA targets (LB80: avoids expert collapse) — already excluded above.

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
import os

assert os.path.isdir("/kaggle/input"), (
    "This final notebook is Kaggle-only and must run inside a Kaggle session."
)
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
            f"{label} is ambiguous for candidate {raw_candidate}: "
            f"{[str(path) for path in matches]}"
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
        and (
            (path.parent / "model.safetensors.index.json").is_file()
            or any(path.parent.glob("*.safetensors"))
        )
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
    lambda path: (
        path.is_dir()
        and (path / "tokens").is_dir()
        and (path / "logprobs/index.jsonl").is_file()
    ),
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
# ---- v17-discovery: answer-guided per-problem equation solver + forward CoT ----
import itertools as _it
import re as _re

_QRE = _re.compile(r"determine the result for:\s*(.+?)\s*$", _re.I)
_PRE = (
    "In Alice's Wonderland, a secret set of transformation rules is applied "
    "to equations. Below are a few examples:"
)
_OPFN = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "absdiff": lambda a, b: abs(a - b),
}


def _parse_eq(prompt, answer):
    ex = []
    for ln in prompt.split("\n"):
        if " = " in ln and "determine" not in ln.lower():
            lhs, rhs = ln.split(" = ", 1)
            ex.append((lhs, rhs))
    m = _QRE.search(prompt)
    return ex, ((m.group(1), str(answer).strip()) if m else None)


def solve_equation_discovery(pairs):
    """Answer-guided per-problem crack. Model (validated by probe_aopb.py): 5-char
    input = 2-char operand A (pos 0,1) + middle + 2-char operand B (pos 3,4) under a
    per-problem symbol->digit bijection; result is op(A,B) re-encoded via the same
    map. The operation is SEARCHED (the middle char is not a fixed operator). Returns
    (opname, digit_map) consistent with ALL pairs, or None.

    SATURDAY: replace the brute-permutation inner loop with OR-Tools CP-SAT +
    answer-first pruning and extend _OPFN toward mspawar's ~83-op family
    (mul_add1/sub1, reversed operands/result, etc.); cap distinct symbols and time."""
    need = set()
    for lhs, rhs in pairs:
        need |= {lhs[0], lhs[1], lhs[3], lhs[4]} | set(rhs)
    need = sorted(need)
    if len(need) > DISCOVERY_MAX_SYMBOLS:
        return None  # hard tail (>10 distinct digit symbols, ~25%)
    for opname in DISCOVERY_OPS:
        op = _OPFN[opname]
        for perm in _it.permutations(range(10), len(need)):
            d = dict(zip(need, perm))
            ok = True
            for lhs, rhs in pairs:
                a = d[lhs[0]] * 10 + d[lhs[1]]
                b = d[lhs[3]] * 10 + d[lhs[4]]
                try:
                    r = op(a, b)
                except Exception:
                    ok = False
                    break
                if r < 0 or "".join(str(d[c]) for c in rhs) != str(r):
                    ok = False
                    break
            if ok:
                return (opname, d)
    return None


def _forward_cot(examples, query_lhs, opname, d):
    """Forward-EXECUTABLE discovery CoT: show the hypothesis search, not the answer.
    Internal-consistency is guaranteed because we re-apply (op, d) to produce the box."""
    inv = {v: k for k, v in d.items()}
    a = d[query_lhs[0]] * 10 + d[query_lhs[1]]
    b = d[query_lhs[3]] * 10 + d[query_lhs[4]]
    r = _OPFN[opname](a, b)
    ans = "".join(inv[int(ch)] for ch in str(r))
    lines = [
        "I must DISCOVER the per-symbol digit map and the operation from the examples.",
        f"Hypothesise digit map: {', '.join(f'{k}->{v}' for k, v in sorted(d.items(), key=lambda kv: kv[1]))}.",
        f"Test operation '{opname}' on each example (operands = first two and last two symbols):",
    ]
    for lhs, rhs in examples:
        ea = d[lhs[0]] * 10 + d[lhs[1]]
        eb = d[lhs[3]] * 10 + d[lhs[4]]
        er = _OPFN[opname](ea, eb)
        enc = "".join(inv[int(ch)] for ch in str(er))
        lines.append(
            f"  {lhs}: {ea} {opname} {eb} = {er} -> '{enc}' (want '{rhs}') {'OK' if enc == rhs else 'X'}"
        )
    lines.append(
        f"All examples consistent. Apply to query {query_lhs}: {a} {opname} {b} = {r} -> '{ans}'."
    )
    return "\n".join(lines), ans


def build_discovery_cot_examples(tokenizer, dose):
    """Run the answer-guided solver over real train.csv equation prompts; for each
    crack, emit a forward-executable, internal-consistency-audited discovery CoT
    (user = original prompt + SUFFIX; assistant = CoT + \\boxed{answer}); return up to
    dose * |corpus| response-masked examples. Default dose=0 -> []."""
    if dose <= 0:
        return []
    import csv as _csv

    train_csv = globals()["TRAIN_CSV_PATH"]
    eqrows = [
        r
        for r in _csv.DictReader(open(train_csv, encoding="utf-8"))
        if "transformation rules is applied to equations" in r["prompt"].lower()
    ]
    SUFFIX = (
        "\nPlease put your final answer inside \\boxed{}. "
        "For example: \\boxed{your answer}"
    )
    out, audited_fail = [], 0
    for rec in eqrows:
        ex, q = _parse_eq(rec["prompt"], rec["answer"])
        if not q or not all(len(lhs) == 5 for lhs, _ in (ex + [q])):
            continue
        sol = solve_equation_discovery(ex + [q])
        if not sol:
            continue
        opname, d = sol
        cot, ans = _forward_cot(ex, q[0], opname, d)
        if ans != q[1]:  # internal-consistency audit (must reproduce the gold box)
            audited_fail += 1
            continue
        msgs = [{"role": "user", "content": rec["prompt"] + SUFFIX}]
        pids = tokenizer.apply_chat_template(
            msgs, tokenize=True, add_generation_prompt=True
        )
        if hasattr(pids, "keys"):
            pids = pids["input_ids"]
        if pids and isinstance(pids[0], (list, tuple)):
            pids = pids[0]
        pids = list(pids)
        resp = cot + "\n\\boxed{" + ans + "}"
        rids = list(tokenizer(resp, add_special_tokens=False)["input_ids"])
        eos = tokenizer.eos_token_id
        if eos is not None:
            rids = rids + [eos]
        full = pids + rids
        if len(full) > MAX_SEQ_LEN:
            continue  # SATURDAY: compress the search CoT to fit 8192 (length is the key risk)
        mask = [0] * len(pids) + [1] * (len(full) - len(pids))
        out.append(
            {
                "problem_id": "eq_discovery",
                "tokens": full[:-1],
                "targets": full[1:],
                "weights": [float(m) for m in mask[1:]],
            }
        )
    print(
        f"discovery-CoT: solver cracked {len(out)} of {len(eqrows)} equation prompts "
        f"(consistency-audited; {audited_fail} dropped as inconsistent)"
    )
    return out


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
    print(
        f"mamba_ssm={mamba_ssm.__version__}, causal_conv1d={causal_conv1d.__version__}"
    )
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
    print(
        f"Loaded {len(ordered_ids)} problem_ids in training order from "
        f"{TRAIN_ORDER_PATH}"
    )

    for sid in ordered_ids:
        seg_path = os.path.join(CORPUS_PATH, sid, "synthetic.json")
        assert os.path.isfile(seg_path), (
            f"problem_id {sid} from training order missing in corpus: {seg_path}"
        )
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
    print(
        f"Loaded {len(examples)} examples, {total_tokens:,} tokens "
        f"(unmasked={total_unmasked:,.0f})"
    )

    assert len(ordered_ids) >= MIN_CORPUS_EXAMPLES, (
        f"Corpus order is unexpectedly small: {len(ordered_ids)} ids; "
        f"expected at least {MIN_CORPUS_EXAMPLES}."
    )
    assert len(examples) >= MIN_CORPUS_EXAMPLES, (
        f"Corpus produced only {len(examples)} examples; "
        f"expected at least {MIN_CORPUS_EXAMPLES}."
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
        out = tokenizer.apply_chat_template(
            msgs, tokenize=True, add_generation_prompt=add_gen
        )
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
                    f"replay row 0: keys={sorted(row.keys())}, "
                    f"prompt_ids={len(prompt_ids)}, full_ids={len(full_ids)}"
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

    assert len(replay_examples) >= MIN_REPLAY_EXAMPLES, (
        f"Only {len(replay_examples)} replay examples were tokenized."
    )
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
    print(
        f"Replay inserted every ~{replay_every} Huikang examples; "
        f"mixed total={len(examples)}"
    )

    # v17-discovery lever (default OFF): weave forward-executable equation discovery CoT.
    if DISCOVERY_COT_DOSE > 0:
        disc = build_discovery_cot_examples(tokenizer, DISCOVERY_COT_DOSE)
        woven: list[dict] = []
        di = 0
        every = max(1, len(examples) // max(1, len(disc)))
        for i, ex in enumerate(examples):
            woven.append(ex)
            if (i + 1) % every == 0 and di < len(disc):
                woven.append(disc[di])
                di += 1
        woven.extend(disc[di:])
        examples = woven
        print(
            f"discovery-CoT woven: {len(disc)} (dose={DISCOVERY_COT_DOSE}); total={len(examples)}"
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
            assert param.dtype == torch.float32, (
                f"LoRA param {name} expected fp32, got {param.dtype}"
            )
            continue

        is_router = (
            ".mixer.gate." in name
        )  # NemotronHTopkRouter.weight + e_score_correction_bias
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
            assert param.dtype == torch.float32, (
                f"param {name} expected fp32, got {param.dtype}"
            )
            continue

        assert param.dtype == torch.bfloat16, (
            f"param {name} expected bf16, got {param.dtype}"
        )
        continue

    print("Verified: LoRA params fp32, base params bf16 (MoE router fp32)")

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"Model: {trainable:,} trainable / {total:,} total parameters")

    # -- Patch forward with Cut Cross-Entropy -------------------------
    _base = model
    while hasattr(_base, "model"):
        _base = _base.model

    def _patched_causal_forward(
        input_ids=None, attention_mask=None, labels=None, **kwargs
    ):
        backbone_out = _base.backbone(
            input_ids=input_ids,
            attention_mask=attention_mask,
            **{
                k: v
                for k, v in kwargs.items()
                if k in ("position_ids", "past_key_values", "use_cache")
            },
        )
        hidden_states = backbone_out[0]
        lm_head = _base.lm_head
        base_w = lm_head.base_layer.weight
        lora_A = lm_head.lora_A["default"].weight
        lora_B = lm_head.lora_B["default"].weight
        scaling = lm_head.scaling["default"]
        lm_weight = base_w + scaling * lora_B @ lora_A
        if labels is not None:
            per_token_ce = linear_cross_entropy(
                hidden_states, lm_weight, labels, reduction="none"
            )
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

    trainable_names = [
        name for name, param in model.named_parameters() if param.requires_grad
    ]
    assert trainable_names, "No trainable LoRA parameters found"
    assert all(".lora_" in name for name in trainable_names), (
        "Unexpected non-LoRA trainable tensors: "
        f"{[name for name in trainable_names if '.lora_' not in name][:20]}"
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

    assert examples, (
        "No Huikang training examples loaded from the required token corpus."
    )
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
        f"Training: {num_steps} steps, batch_size={BATCH_SIZE}, "
        f"micro_batch_size={MICRO_BATCH_SIZE}, lr={LEARNING_RATE}"
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

            padded_input = torch.zeros(
                n_micro, max_len, dtype=torch.long, device=device
            )
            padded_targets = torch.zeros(
                n_micro, max_len, dtype=torch.long, device=device
            )
            padded_weights = torch.zeros(
                n_micro, max_len, dtype=torch.float32, device=device
            )
            attention_mask = torch.zeros(
                n_micro, max_len, dtype=torch.long, device=device
            )
            for i in range(n_micro):
                seq_len = len(mb_toks[i])
                padded_input[i, :seq_len] = torch.tensor(mb_toks[i], dtype=torch.long)
                padded_targets[i, :seq_len] = torch.tensor(mb_tgts[i], dtype=torch.long)
                padded_weights[i, :seq_len] = torch.tensor(
                    mb_wts[i], dtype=torch.float32
                )
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
                loss = (
                    loss_sum_t / weight_sum_t if weight_sum_t > 0 else loss_sum_t * 0.0
                )
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
        _log(
            f"  step {step}/{num_steps}: "
            f"loss:mean={loss_mean:.6f}, grad_norm={grad_norm:.4f}, lr={lr:.2e}"
        )

    print(
        f"\nTraining complete. Peak VRAM: {torch.cuda.max_memory_allocated() / 1e9:.1f} GB"
    )

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
        k.replace("base_model.model.lm_head.", "base_model.model.backbone.lm_head."): v
        for k, v in tensors.items()
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
    print(
        "Submission validation OK: root files only, "
        f"rank={LORA_RANK}, alpha={LORA_ALPHA}"
    )
    print(f"submission.zip sha256={digest.hexdigest()}")
    print("Training complete.")


# %%
# Start the single public-recipe reproduction run.
run_training()
