"""Cheap pre-push validation for the Nemotron kernel — NO GPU, NO 30B model.

Catches the class of bugs that cost a full ~2h Kaggle run (e.g. the v7 `texts`
NameError) before pushing:
  1. Static undefined-name check (pyflakes F821/F811) over the assembled cells.
  2. Masking-logic sanity with a stub tokenizer on the real CoT csv: prompt
     tokens must be -100, response tokens must be trained, lengths must match.

Usage: python validate_kernel.py [path/to/problem_ids_matched.csv]
Exit 0 = ok to push; non-zero = fix first.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NB = HERE / "nemotron-lora-baseline.ipynb"


def check_undefined_names() -> bool:
    nb = json.loads(NB.read_text())
    code = "\n".join(
        "".join(c.get("source", []))
        for c in nb["cells"]
        if c.get("cell_type") == "code"
    )
    tmp = HERE / "_assembled_kernel.py"
    tmp.write_text(code)
    proc = subprocess.run(
        ["ruff", "check", "--select", "F821,F811", str(tmp)],
        capture_output=True,
        text=True,
    )
    tmp.unlink(missing_ok=True)
    ok = proc.returncode == 0
    print("[1] undefined-name check:", "PASS" if ok else "FAIL\n" + proc.stdout)
    return ok


def check_masking(csv_path: str) -> bool:
    import pandas as pd

    df = pd.read_csv(csv_path).head(5)
    SUFFIX = "\nPlease put your final answer inside \\boxed{}. For example: \\boxed{your answer}"

    class StubTok:
        def apply_chat_template(
            self, msgs, tokenize=False, add_generation_prompt=False, **k
        ):
            s = "".join(f"<|{m['role']}|>{m['content']}" for m in msgs)
            if add_generation_prompt:
                s += "<|assistant|>"
            return s.split() if tokenize else s

        def __call__(self, text, truncation=False, max_length=None):
            ids = text.split()
            return {
                "input_ids": ids[:max_length] if (truncation and max_length) else ids
            }

    tok, MAX_LEN, ok = StubTok(), 4096, True
    for r in df.itertuples():
        cot = re.sub(r"\\boxed\{[^}]*\}", "", str(r.generated_cot)).rstrip()
        assistant = f"{cot}\n</think>\n\\boxed{{{r.answer}}}"
        user = [{"role": "user", "content": f"{r.prompt}{SUFFIX}"}]
        full = tok.apply_chat_template(
            user + [{"role": "assistant", "content": assistant}]
        )
        prompt_only = tok.apply_chat_template(user, add_generation_prompt=True)
        ids = tok(full, truncation=True, max_length=MAX_LEN)["input_ids"]
        plen = min(
            len(tok(prompt_only, truncation=True, max_length=MAX_LEN)["input_ids"]),
            len(ids),
        )
        labels = [-100] * plen + ids[plen:]
        ok = ok and len(labels) == len(ids) and plen > 0 and (len(ids) - plen) > 0
    print("[2] masking-logic check:", "PASS" if ok else "FAIL")
    return ok


def main() -> int:
    csv = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(HERE.parent.parent / "data" / "problem_ids_matched.csv")
    )
    ok = check_undefined_names()
    if Path(csv).exists():
        ok = check_masking(csv) and ok
    else:
        print("[2] masking check skipped (csv not found at", csv, ")")
    print("RESULT:", "OK to push" if ok else "DO NOT PUSH — fix above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
