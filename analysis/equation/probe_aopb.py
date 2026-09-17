"""v17-discovery premise check (LB80 plan): does `equation` fit mspawar's
"A1A2 OP B1B2 + per-problem symbol->digit cipher" model, and is it offline-crackable?
CPU-only, read-only on train.csv. Run: python analysis/equation/probe_aopb.py

FINDINGS (2026-06-17, first 400 equation prompts):
  - inputs are ALWAYS 5 chars (consistent with two 2-char operands + 1 middle char).
  - distinct DIGIT symbols/problem (operand pos 0,1,3,4 + result chars, EXCLUDING the
    middle char): <=10 in ~75% of problems (dist ~ {8:22, 9:85, 10:195, 11:97}). So a
    per-problem 0-9 bijection is FEASIBLE for ~75% -> the cipher IS crackable offline
    for the majority (this CORRECTS EQ-2's "single global, uncrackable" verdict). The
    ~25% with >10 digit symbols are the genuine hard tail (cf. mspawar's >10-symbol
    unsolvables; ours is a bigger tail).
  - the middle char (pos 2) is CONSTANT within a problem only ~2% of the time -> it is
    NOT a fixed operator we can read off; the operation must be SEARCHED (answer-guided),
    exactly why mspawar's solver enumerates an ~83-op family with answer-first pruning.
  => v17-discovery is worth building, but the solver needs (a) answer-guided op search
     (not a fixed operator), (b) a forward-executable CoT that shows that search, and
     (c) handling for the >10-symbol hard tail. NOT a trivial fixed-form crack.
"""

import csv
import re
from collections import Counter

D = "/home/harry/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv"
QRE = re.compile(r"determine the result for:\s*(.+?)\s*$", re.I)


def parse(prompt, answer):
    ex = []
    for ln in prompt.split("\n"):
        if " = " in ln and "determine" not in ln.lower():
            lhs, rhs = ln.split(" = ", 1)
            ex.append((lhs, rhs))
    m = QRE.search(prompt)
    q = (m.group(1), answer.strip()) if m else None
    return ex, q


def main():
    rows = [r for r in csv.DictReader(open(D)) if "transformation rules is applied to equations" in r["prompt"].lower()]
    sample = rows[:400]
    len5 = 0
    digit_counts = []
    op_constant = 0
    n = 0
    for r in sample:
        ex, q = parse(r["prompt"], r["answer"])
        pairs = ex + ([q] if q else [])
        if all(len(lhs) == 5 for lhs, _ in pairs):
            len5 += 1
        else:
            continue
        n += 1
        digs, ops = set(), set()
        for lhs, rhs in pairs:
            digs |= {lhs[0], lhs[1], lhs[3], lhs[4]} | set(rhs)
            ops.add(lhs[2])
        digit_counts.append(len(digs))
        if len(ops) == 1:
            op_constant += 1
    ddc = Counter(digit_counts)
    le10 = sum(v for k, v in ddc.items() if k <= 10)
    print(f"sample={len(sample)} inputs-all-5-char={len5}")
    print(f"DIGIT symbols/problem (excl middle char): <=10 in {le10}/{n} ({100 * le10 // max(1, n)}%)")
    print(f"  distribution: {dict(sorted(ddc.items()))}")
    print(f"middle char (pos 2) constant within problem: {op_constant}/{n} -> operation must be searched")


if __name__ == "__main__":
    main()
