"""Preflight validation for lb1-v1 (fail-fast, runs before any long/remote step).

Mirrors the repo's INS-001 push-time preflight + the submission preflight gate in
`wiki/26.LB1_coding_task.md`. Pure-local; no GPU. Checks:
  1. `\\boxed{}` extraction + binary leading-zero exactness (official metric);
  2. one-example fail-fast on a synthetic record (solver trace verifies);
  3. adapter rank <= 32 (from adapter_config.json);
  4. submission.zip ROOT structure (required files at root, not nested);
  5. no obvious secrets / local paths inside the zip.

    python validate.py --zip submission.zip      # validate a built zip
    python validate.py --self                     # extraction + fail-fast only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "eval"))
from official_metric import extract_final_answer, verify  # noqa: E402

MAX_RANK = 32
REQUIRED_FILES = ("adapter_config.json", "adapter_model.safetensors")
_SECRET_HINTS = ("kaggle.json", ".env", "KAGGLE_KEY", "ANTHROPIC_API_KEY", "/home/", "id_rsa", "AKIA")


class Check:
    def __init__(self):
        self.results = []

    def add(self, name, ok, detail=""):
        self.results.append((name, bool(ok), detail))
        return ok

    def report(self):
        print(f"{'PASS' if self.ok() else 'FAIL'} — lb1-v1 preflight")
        for name, ok, detail in self.results:
            print(f"  [{'x' if ok else ' '}] {name}{(' — ' + detail) if detail else ''}")
        return self.ok()

    def ok(self):
        return all(ok for _, ok, _ in self.results)


def check_extraction(chk: Check):
    cases = [
        ("</think>\n\\boxed{341}", "341", True),
        ("noise \\boxed{01000011} end", "01000011", True),  # binary leading-zero exact
        ("\\boxed{1000011}", "01000011", False),  # 1000011 != 01000011 (binary)
        ("the final answer is: 42", "42", True),
        ("\\boxed{:![}", ":![", True),  # string symbols exact
    ]
    ok = True
    for text, gold, expect in cases:
        got = verify(gold, extract_final_answer(text))
        ok = ok and (got == expect)
    chk.add("boxed/binary/string extraction", ok)


def check_fail_fast(chk: Check):
    try:
        import synth_gen

        recs, _ = synth_gen.build_corpus(8, seed=123)
        ok = len(recs) > 0 and all(verify(r["answer"], extract_final_answer(r["trace"])) for r in recs)
        chk.add("one-example fail-fast (synth traces verify)", ok, f"{len(recs)} records")
    except Exception as e:  # noqa: BLE001
        chk.add("one-example fail-fast (synth traces verify)", False, str(e)[:80])


def check_zip(chk: Check, zip_path: str):
    if not os.path.exists(zip_path):
        chk.add("submission.zip exists", False, zip_path)
        return
    size = os.path.getsize(zip_path)
    chk.add("submission.zip exists & non-empty", size > 0, f"{size} bytes")
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        # root structure: required files at root (no leading dir component)
        root_ok = all(any(n == rf for n in names) for rf in REQUIRED_FILES)
        nested = [n for n in names if "/" in n]
        chk.add("required files at zip root (not nested)", root_ok and not nested, f"names={names}")
        # rank <= 32
        try:
            with z.open("adapter_config.json") as f:
                cfg = json.load(f)
            r = cfg.get("r", cfg.get("lora_rank"))
            chk.add(f"adapter rank <= {MAX_RANK}", r is not None and r <= MAX_RANK, f"r={r}")
        except Exception as e:  # noqa: BLE001
            chk.add(f"adapter rank <= {MAX_RANK}", False, str(e)[:80])
        # no secrets / local paths
        blob = " ".join(names)
        for n in names:
            if n.endswith(".json") or n.endswith(".txt"):
                try:
                    blob += " " + z.read(n).decode("utf-8", "ignore")
                except Exception:  # noqa: BLE001
                    pass
        leaked = [h for h in _SECRET_HINTS if h in blob]
        chk.add("no secrets / local paths in zip", not leaked, f"hits={leaked}" if leaked else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", help="submission.zip to validate")
    ap.add_argument("--self", action="store_true", help="extraction + fail-fast only")
    args = ap.parse_args()

    chk = Check()
    check_extraction(chk)
    check_fail_fast(chk)
    if args.zip:
        check_zip(chk, args.zip)
    elif not args.self:
        print("(no --zip given; running self checks only. Pass --zip to gate a submission.)")
    ok = chk.report()
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
