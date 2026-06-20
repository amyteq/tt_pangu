"""Equation_numeric structural solver (lb13-v1) — the batch's sharpest model.

Reproduces the LB13 / 13th-place equation model (method_summary.md / score_tricks.md;
deduce 95.3%, **guess 50.7% — highest in the batch**):

  * **4 mutually-exclusive operator categories** (families): SUB, ADD, MUL, CONCAT;
    each family is used at most once per prompt (exclusivity);
  * **reversal symmetry, shared across ALL examples**: a single global flag —
    either both inputs *and* the output are digit-reversed, or neither — decided by
    **majority vote** over the examples (not per-operator);
  * **robust aggregation**: an operator rule is valid if it matches **≥1 example**
    (not all) — tolerates symbol-transcription noise (LB13's key robustness fix);
  * **family-exclusion guessing** for an unseen query operator: pick from an unused
    family with tie priority **sub > add > mul > concat**.

This is a distinct re-expression of the per-prompt operator inventory (vs LB1's
24-rule catalog, LB5's 2-world/4-family/13-rule). The novel pieces are the *global*
majority-vote reversal and the *robust* (≥1-match) aggregation. Validated on
synthetic instances (incl. injected transcription noise to exercise robustness); the
shared real-`train.csv` premise re-test is `eq_reprobe.py`.
"""

from __future__ import annotations

import argparse
import random

# 4 mutually-exclusive families; tie priority sub > add > mul > concat.
FAMILIES = {
    "SUB": {
        "subab": lambda a, b: a - b,
        "subba": lambda a, b: b - a,
        "posabs": lambda a, b: abs(a - b),
        "mod": lambda a, b: a % b if b else 0,
    },
    "ADD": {"add": lambda a, b: a + b},
    "MUL": {"mul": lambda a, b: a * b},
    "CONCAT": {"concat": lambda a, b: int(f"{a}{b}")},
}
FAMILY_ORDER = ["SUB", "ADD", "MUL", "CONCAT"]  # tie priority
RULE_FAMILY = {r: fam for fam, rules in FAMILIES.items() for r in rules}
RULE_FN = {r: fn for rules in FAMILIES.values() for r, fn in rules.items()}
RULE_ORDER = [r for fam in FAMILY_ORDER for r in FAMILIES[fam]]


def _rev(s: str) -> str:
    return s[::-1]


def _render(rule: str, a_str: str, b_str: str, reverse: bool) -> str:
    """Apply a rule under the global reversal flag (both-in-out-or-neither)."""
    if reverse:
        a, b = int(_rev(a_str)), int(_rev(b_str))
        val = RULE_FN[rule](a, b)
        neg = val < 0
        return ("-" if neg else "") + _rev(str(abs(val)))
    a, b = int(a_str), int(b_str)
    return str(RULE_FN[rule](a, b))


def _matches(rule, examples, reverse, robust=True):
    """How many examples this rule explains under `reverse`. robust = count >=1 ok."""
    cnt = 0
    for a_str, b_str, out_str in examples:
        if _render(rule, a_str, b_str, reverse) == out_str:
            cnt += 1
    return cnt


def _resolve_world(by_glyph, reverse, robust=True):
    """Resolve each glyph to a rule under a fixed reversal flag, with exclusivity.

    Returns (assignment {glyph: rule}, total_example_matches). Robust aggregation:
    a rule is a candidate if it matches >=1 example; pick the best-matching rule from
    an unused family (tie priority sub>add>mul>concat).
    """
    assignment = {}
    used_families = set()
    total = 0
    # process glyphs deterministically
    for glyph in by_glyph:
        best = None
        best_cnt = 0
        for rule in RULE_ORDER:
            if RULE_FAMILY[rule] in used_families:
                continue
            cnt = _matches(rule, by_glyph[glyph], reverse, robust)
            need = 1 if robust else len(by_glyph[glyph])
            if cnt >= need and cnt > best_cnt:
                best, best_cnt = rule, cnt
        if best is not None:
            assignment[glyph] = best
            used_families.add(RULE_FAMILY[best])
            total += best_cnt
    return assignment, total


def solve(by_glyph, query, robust=True):
    """Majority-vote global reversal, then resolve under the winning flag.

    Returns (predicted_str, mode, rule, reverse). mode in {'deduce','guess'}.
    """
    qglyph, qa, qb = query
    # majority vote: the reversal flag that explains more example lines wins
    asg_n, tot_n = _resolve_world(by_glyph, reverse=False, robust=robust)
    asg_r, tot_r = _resolve_world(by_glyph, reverse=True, robust=robust)
    reverse = tot_r > tot_n
    assignment = asg_r if reverse else asg_n

    if qglyph in assignment:  # deduce
        rule = assignment[qglyph]
        return _render(rule, qa, qb, reverse), "deduce", rule, reverse
    if qglyph in by_glyph:  # seen but unresolved -> best-effort under flag
        for rule in RULE_ORDER:
            if _matches(rule, by_glyph[qglyph], reverse, robust) >= 1:
                return _render(rule, qa, qb, reverse), "deduce", rule, reverse

    # guess: family-exclusion with tie priority sub > add > mul > concat
    used_families = {RULE_FAMILY[r] for r in assignment.values()}
    for fam in FAMILY_ORDER:
        if fam in used_families:
            continue
        rule = next(iter(FAMILIES[fam]))
        return _render(rule, qa, qb, reverse), "guess", rule, reverse
    rule = "subab"
    return _render(rule, qa, qb, reverse), "guess", rule, reverse


_GLYPHS = list("@#$%&?!~^+=<>/")


def generate_problem(seed, n_glyphs=3, ex_per_glyph=5, deduce=True, noise=False):
    rng = random.Random(seed)
    glyphs = rng.sample(_GLYPHS, n_glyphs + (0 if deduce else 1))
    fams = rng.sample(FAMILY_ORDER, min(len(glyphs), len(FAMILY_ORDER)))
    while len(fams) < len(glyphs):
        fams.append(rng.choice(FAMILY_ORDER))
    reverse = rng.random() < 0.5  # ONE global flag (shared across examples)
    glyph_rule = {g: rng.choice(list(FAMILIES[f])) for g, f in zip(glyphs, fams)}
    seen = glyphs[:n_glyphs]
    by_glyph = {}
    for g in seen:
        rows = []
        for _ in range(ex_per_glyph):
            a, b = rng.randint(10, 99), rng.randint(10, 99)
            rows.append((str(a), str(b), _render(glyph_rule[g], str(a), str(b), reverse)))
        if noise and rows:  # inject one transcription error (robust aggregation must survive)
            i = rng.randrange(len(rows))
            a_str, b_str, _o = rows[i]
            rows[i] = (a_str, b_str, "999")  # corrupted output
        by_glyph[g] = rows
    qg = rng.choice(seen) if deduce else glyphs[-1]
    qa, qb = str(rng.randint(10, 99)), str(rng.randint(10, 99))
    truth = _render(glyph_rule[qg], qa, qb, reverse)
    return by_glyph, (qg, qa, qb), truth


def _measure(n, deduce, noise, robust):
    solved = 0
    for seed in range(n):
        by_glyph, query, truth = generate_problem(seed, deduce=deduce, noise=noise)
        pred, *_ = solve(by_glyph, query, robust=robust)
        if pred == truth:
            solved += 1
    return solved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    n = args.n
    print("LB13 equation solver (4 mutually-exclusive families, global majority-vote reversal):")
    print(
        f"  deduce (clean)        : {_measure(n, True, False, True)}/{n} = {100 * _measure(n, True, False, True) / n:5.1f}%   (writeup 95.3%)"
    )
    print(
        f"  guess  (clean)        : {_measure(n, False, False, True)}/{n} = {100 * _measure(n, False, False, True) / n:5.1f}%   (writeup 50.7%, batch-best)"
    )
    # robust aggregation: with one corrupted example, robust (>=1 match) beats strict (all-match)
    rob = _measure(n, True, True, True)
    strict = _measure(n, True, True, False)
    print(
        f"  deduce (noisy) robust : {rob}/{n} = {100 * rob / n:5.1f}%   vs strict all-match {strict}/{n} = {100 * strict / n:5.1f}%"
    )
    print(f"  families: {FAMILY_ORDER} (exclusivity); reversal = ONE global flag by majority vote")


if __name__ == "__main__":
    main()
