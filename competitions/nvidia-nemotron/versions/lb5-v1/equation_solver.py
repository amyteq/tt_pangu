"""2-world / 4-family / 13-rule equation solver (lb5-v1).

Reproduces the LB5 / 5th-place equation lever (method_summary.md / score_tricks.md;
oracle deduce ~95%, →96.2% with the phase-3 lookup string):

  * **2 worlds**: NORMAL (output as-is) and REVERSE (reverse the output's decimal
    string) — LB5's String/Integer reversal axis;
  * **4 families**: SUB, ADD, MUL, MIX;
  * **13 rules** total across the families, **≤1 rule per family** per prompt;
  * **deterministic priority** when several (rule, world) fit the examples:
    `REVERSE > NORMAL`, then the SUB intra-family order
    `subab > posabs > negabs > subba > mod` (writeup), then family order;
  * **operation-family guessing** for an unseen query operator: pick a rule from an
    UNUSED family (no SUB→subab, no ADD→add, no MUL→mul).

This is the LB5-specific *re-expression* of the per-prompt operator inventory (the
same hidden structure LB1's `rules24.py` encodes). Validated on synthetic instances
with known ground truth; the real-`train.csv` premise re-test is the shared
`eq_reprobe.py` (plan checklist #1, shared with lb1-v1 / lb3-v1).
"""

from __future__ import annotations

import argparse
import random

# --- base rules grouped into 4 families ------------------------------------- #
# Each base rule maps (a, b) -> int. World transform is applied on top.
FAMILIES = {
    "SUB": {
        "subab": lambda a, b: a - b,
        "posabs": lambda a, b: abs(a - b),
        "negabs": lambda a, b: -abs(a - b),
        "subba": lambda a, b: b - a,
        "mod": lambda a, b: a % b if b else 0,
    },
    "ADD": {
        "add": lambda a, b: a + b,
        "add1": lambda a, b: a + b + 1,
    },
    "MUL": {
        "mul": lambda a, b: a * b,
        "mul1": lambda a, b: a * b + 1,
        "mulm1": lambda a, b: a * b - 1,
    },
    "MIX": {
        "maxv": lambda a, b: max(a, b),
        "minv": lambda a, b: min(a, b),
        "concat": lambda a, b: int(f"{a}{b}"),
    },
}
RULE_FAMILY = {r: fam for fam, rules in FAMILIES.items() for r in rules}
RULE_FN = {r: fn for rules in FAMILIES.values() for r, fn in rules.items()}
assert len(RULE_FN) == 13, "13-rule inventory"

# intra-family deterministic order (writeup SUB order; others enumeration order)
INTRA_ORDER = [
    "subab",
    "posabs",
    "negabs",
    "subba",
    "mod",
    "add",
    "add1",
    "mul",
    "mul1",
    "mulm1",
    "maxv",
    "minv",
    "concat",
]
FAMILY_ORDER = ["SUB", "ADD", "MUL", "MIX"]
WORLDS = ["REVERSE", "NORMAL"]  # REVERSE > NORMAL priority


def _apply_world(val: int, world: str) -> str:
    """Render an int under a world. REVERSE reverses the decimal string (sign kept)."""
    neg = val < 0
    s = str(abs(val))
    if world == "REVERSE":
        s = s[::-1]
    return ("-" if neg else "") + s


def _render(rule: str, world: str, a: int, b: int) -> str:
    return _apply_world(RULE_FN[rule](a, b), world)


def _priority_key(rule_world):
    rule, world = rule_world
    return (WORLDS.index(world), INTRA_ORDER.index(rule))


def consistent(examples):
    """All (rule, world) combos matching ALL example (a,b,out_str) lines."""
    out = []
    for rule in RULE_FN:
        for world in WORLDS:
            if all(_render(rule, world, a, b) == out_s for a, b, out_s in examples):
                out.append((rule, world))
    return sorted(out, key=_priority_key)  # deterministic priority


def solve(by_glyph: dict, query):
    """by_glyph: {glyph: [(a,b,out_str), ...]}; query: (glyph, a, b).

    Returns (predicted_str, mode, rule, world). mode in {'deduce','guess'}.
    Enforces <=1 rule/family by consuming families in priority order.
    """
    qglyph, qa, qb = query
    resolved = {}
    used_families = set()
    # resolve seen glyphs in a stable order; respect <=1 rule/family
    for glyph in by_glyph:
        cands = consistent(by_glyph[glyph])
        cands = [rw for rw in cands if RULE_FAMILY[rw[0]] not in used_families] or cands
        if cands:
            rule, world = cands[0]
            resolved[glyph] = (rule, world)
            used_families.add(RULE_FAMILY[rule])

    if qglyph in by_glyph:  # deduce
        cands = consistent(by_glyph[qglyph])
        if cands:
            rule, world = cands[0]
            return _render(rule, world, qa, qb), "deduce", rule, world
        return None, "deduce", None, None

    # guess: unseen query glyph -> first rule of an unused family (priority order)
    for fam in FAMILY_ORDER:
        if fam in used_families:
            continue
        rule = next(iter(FAMILIES[fam]))
        return _render(rule, "NORMAL", qa, qb), "guess", rule, "NORMAL"
    rule = "subab"
    return _render(rule, "NORMAL", qa, qb), "guess", rule, "NORMAL"


_GLYPHS = list("@#$%&?!~^+=<>")


def generate_problem(seed: int, n_glyphs: int = 3, ex_per_glyph: int = 5, deduce: bool = True):
    rng = random.Random(seed)
    glyphs = rng.sample(_GLYPHS, n_glyphs + (0 if deduce else 1))
    # assign distinct families to glyphs (the generator samples 1 rule/family)
    fams = rng.sample(FAMILY_ORDER, min(len(glyphs), len(FAMILY_ORDER)))
    while len(fams) < len(glyphs):
        fams.append(rng.choice(FAMILY_ORDER))
    glyph_rw = {}
    for g, fam in zip(glyphs, fams):
        rule = rng.choice(list(FAMILIES[fam]))
        world = rng.choice(WORLDS)
        glyph_rw[g] = (rule, world)
    seen = glyphs[:n_glyphs]
    by_glyph = {}
    for g in seen:
        rule, world = glyph_rw[g]
        rows = []
        for _ in range(ex_per_glyph):
            a, b = rng.randint(10, 99), rng.randint(10, 99)
            rows.append((a, b, _render(rule, world, a, b)))
        by_glyph[g] = rows
    qg = rng.choice(seen) if deduce else glyphs[-1]
    qa, qb = rng.randint(10, 99), rng.randint(10, 99)
    rule, world = glyph_rw[qg]
    truth = _render(rule, world, qa, qb)
    return by_glyph, (qg, qa, qb), truth


def _measure(n, deduce):
    solved = 0
    for seed in range(n):
        by_glyph, query, truth = generate_problem(seed, deduce=deduce)
        pred, *_ = solve(by_glyph, query)
        if pred == truth:
            solved += 1
    return solved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    args = ap.parse_args()
    d = _measure(args.n, deduce=True)
    g = _measure(args.n, deduce=False)
    print("LB5 equation solver (2-world / 4-family / 13-rule, deterministic priority):")
    print(f"  deduce: {d}/{args.n} = {100 * d / args.n:5.1f}%   (writeup oracle ~95-96%)")
    print(f"  guess : {g}/{args.n} = {100 * g / args.n:5.1f}%   (family-guessing; writeup ~40%)")
    print(f"  inventory: {len(RULE_FN)} rules x {len(WORLDS)} worlds across {len(FAMILIES)} families")


if __name__ == "__main__":
    main()
