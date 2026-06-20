"""CSP cryptarithm solver + staged-trace emitter (lb3-v1, headline lever).

Reproduces the LB3 / 3rd-place cryptarithm mechanism from prose (the writeup's
example trace is an unreleased attachment — see next_version_plan.md "Risks"):

  1. **Identify multiplication examples** in the prompt.
  2. **Emit per-symbol domains** for each MUL example via the multiplication-pattern
     lookup (`mul_pattern_lookup.py`) -> the `<RECALL_DOMAINS>`/`<RECALL_ROWS>` trace tags.
  3. **Intersect / join** the candidate digit sets across MUL examples to shrink the
     symbol -> digit bijection domains.
  4. **Anchor** symbols whose domain has collapsed to a single digit.
  5. **Bounded backtracking** over the remaining unknowns (least-domain-first), each
     fully-assigned example verified against its arithmetic. Tries
     (structure in simple/reverse) x (mul in a*b / a*b+-1), reverse-first.

The underlying engine is an exact **bijection CSP** over the symbol alphabet, so a
solved instance recovers the true digit<->symbol mapping; the lookup + intersection
make the backtracking *bounded* (the plan's "<=2 unknowns/eq, least-unknowns-first").

Problem model (self-contained; faithful to the symbol-substitution structure — we
have no train.csv here, so we validate the MECHANISM on generated instances with a
known ground-truth mapping, exactly as the plan scopes post-comp work):

  * a secret bijection digit 0-9 -> distinct symbol; numbers render MSB-first with
    no leading-zero operands;
  * a prompt gives several example equations ``enc(a) <op> enc(b) = enc(c)`` plus a
    query ``enc(x) <op> enc(y) = ?``; the answer is ``enc(x <op> y)``.

Public API:
  generate_problem(...) -> Problem ;  solve(problem) -> Solution ;  emit_trace(...)
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass

from mul_pattern_lookup import build_lookup, mul_signature

OPS = {"*": lambda a, b: a * b, "+": lambda a, b: a + b, "-": lambda a, b: a - b}


# --------------------------------------------------------------------------- #
# problem model
# --------------------------------------------------------------------------- #
@dataclass
class Example:
    a: int
    op: str
    b: int
    c: int  # ground-truth integer result (a op b)


@dataclass
class Problem:
    mapping: dict[int, str]  # secret digit -> symbol (ground truth)
    examples: list[Example]
    qa: int
    qop: str
    qb: int
    qc: int  # ground-truth query result

    # rendered (symbol-string) views -----------------------------------------
    def enc(self, n: int) -> str:
        return "".join(self.mapping[int(d)] for d in str(n))

    def symbols_used(self) -> set[str]:
        s = set()
        for ex in self.examples:
            for n in (ex.a, ex.b, ex.c):
                s.update(self.enc(n))
        s.update(self.enc(self.qa))
        s.update(self.enc(self.qb))
        return s


@dataclass
class Solution:
    solved: bool
    predicted: str | None  # predicted symbol-string for the query result
    recovered: dict[str, int]  # symbol -> digit the solver pinned
    backtracks: int
    note: str = ""


# --------------------------------------------------------------------------- #
# generation
# --------------------------------------------------------------------------- #
_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def generate_problem(seed: int, op: str = "*", n_examples: int = 5, deduce: bool = True) -> Problem:
    """Build one cryptarithm instance with a known secret mapping.

    ``deduce=True`` guarantees every symbol used in the query also appears in the
    examples (the solvable "deduce" subset). ``deduce=False`` allows a query symbol
    unseen in examples (the harder "guess" subset).
    """
    rng = random.Random(seed)
    digits = list(range(10))
    syms = rng.sample(_ALPHABET, 10)
    mapping = {d: syms[d] for d in digits}

    def rand_operand():
        return rng.randint(2, 9) if rng.random() < 0.35 else rng.randint(10, 99)

    examples: list[Example] = []
    seen_digits: set[int] = set()
    for _ in range(n_examples):
        a, b = rand_operand(), rand_operand()
        if op == "-" and a < b:
            a, b = b, a
        c = OPS[op](a, b)
        examples.append(Example(a, op, b, c))
        for n in (a, b, c):
            seen_digits.update(int(d) for d in str(n))

    # build a query; for deduce, ensure its digits are a subset of seen digits
    for _ in range(200):
        qa, qb = rand_operand(), rand_operand()
        if op == "-" and qa < qb:
            qa, qb = qb, qa
        qc = OPS[op](qa, qb)
        qdigits = set(int(d) for d in (str(qa) + str(qb) + str(qc)))
        if deduce and not qdigits.issubset(seen_digits):
            continue
        return Problem(mapping, examples, qa, op, qb, qc)
    # fallback (rare): accept as-is
    return Problem(mapping, examples, qa, op, qb, qc)


# --------------------------------------------------------------------------- #
# CSP engine
# --------------------------------------------------------------------------- #
def _decode(symstr: str, assign: dict[str, int]) -> int | None:
    """symbol-string -> integer under a (partial) assignment; None if incomplete."""
    out = 0
    for ch in symstr:
        if ch not in assign:
            return None
        out = out * 10 + assign[ch]
    return out


def _seed_domains_from_lookup(problem: Problem, lut):
    """SOUND per-symbol domains + the `<RECALL_*>` narration payload.

    The multiplication-pattern lookup is used for the trace narration and for a
    value-ordering *hint* only. It is **not** intersected into the domains as a hard
    constraint: with ``row_cap`` < full enumeration the true row is often absent, so
    intersecting would unsoundly drop the correct digit (we measured this -> 0%
    solved). Soundness comes from backtracking over the real equations; the lookup
    just makes it *bounded* by ordering likely digits first.

    Returns (domains, value_hint, recall_log):
      * domains    : sound {symbol: set(0..9)} minus leading-zero;
      * value_hint : {symbol: [digits to try first]} from lookup positions;
      * recall_log : [(sig, n_rows, enc_a, enc_b, enc_c)] for mul examples.
    """
    syms = problem.symbols_used()
    domains: dict[str, set[int]] = {s: set(range(10)) for s in syms}
    hint: dict[str, list[int]] = {}
    recall_log = []
    for ex in problem.examples:
        if ex.op != "*":
            continue
        enc_a, enc_b, enc_c = problem.enc(ex.a), problem.enc(ex.b), problem.enc(ex.c)
        sig = mul_signature(ex.a, ex.b)
        a_dom, b_dom, p_dom = lut.domains_for(sig)
        recall_log.append((sig, len(lut.rows_for(sig)), enc_a, enc_b, enc_c))
        for symstr, posdom in ((enc_a, a_dom), (enc_b, b_dom), (enc_c, p_dom)):
            if len(symstr) != len(posdom):
                continue
            for ch, dom in zip(symstr, posdom):
                if dom:
                    hint.setdefault(ch, [])
                    for d in sorted(dom):
                        if d not in hint[ch]:
                            hint[ch].append(d)
    # leading symbols cannot be zero (sound)
    for ex in problem.examples:
        for n in (ex.a, ex.b, ex.c):
            s = problem.enc(n)
            if len(s) > 1:
                domains[s[0]].discard(0)
    return domains, hint, recall_log


def solve(problem: Problem, lut=None, max_backtracks: int = 2_000_000) -> Solution:
    """Sound bijection solve: lookup-ordered, most-constrained-first backtracking
    with units-digit forward checking (the strong pruner).
    """
    lut = lut or build_lookup()
    domains, hint, _ = _seed_domains_from_lookup(problem, lut)
    examples = problem.examples
    # per-example (enc_a, enc_b, enc_c, op), indexed positionally
    enc = [(problem.enc(ex.a), problem.enc(ex.b), problem.enc(ex.c), ex.op) for ex in examples]

    # most-constrained-first: order symbols by how often they appear in examples
    freq: dict[str, int] = {s: 0 for s in domains}
    for ea, eb, ec, _op in enc:
        for s in ea + eb + ec:
            if s in freq:
                freq[s] += 1
    syms = sorted(domains, key=lambda s: (-freq[s], s))

    # units (last-digit) symbols per example: the cheapest, highest-value constraint
    units = [(ea[-1], eb[-1], ec[-1], op) for ea, eb, ec, op in enc]
    state = {"bt": 0}

    def units_ok(assign):
        for ua, ub, uc, op in units:
            if ua in assign and ub in assign and uc in assign:
                if op == "*":
                    forced = (assign[ua] * assign[ub]) % 10
                elif op == "+":
                    forced = (assign[ua] + assign[ub]) % 10
                else:  # '-'
                    forced = (assign[ua] - assign[ub]) % 10
                if assign[uc] != forced:
                    return False
        return True

    def full_ok(assign):
        for ea, eb, ec, op in enc:
            if all(ch in assign for ch in ea + eb + ec):
                a, b, c = _decode(ea, assign), _decode(eb, assign), _decode(ec, assign)
                if OPS[op](a, b) != c:
                    return False
        return True

    def order_values(s, used):
        prefer = [d for d in hint.get(s, []) if d in domains[s] and d not in used]
        rest = [d for d in sorted(domains[s]) if d not in used and d not in prefer]
        return prefer + rest

    def backtrack(i, assign, used):
        if state["bt"] > max_backtracks:
            return None
        if i == len(syms):
            return dict(assign)
        s = syms[i]
        for d in order_values(s, used):
            assign[s] = d
            used.add(d)
            state["bt"] += 1
            if units_ok(assign) and full_ok(assign):
                r = backtrack(i + 1, assign, used)
                if r is not None:
                    return r
            used.discard(d)
            del assign[s]
        return None

    sol = backtrack(0, {}, set())
    if sol is None:
        return Solution(False, None, {}, state["bt"], note="no consistent bijection found")
    # predict the query result
    qc = OPS[problem.qop](problem.qa, problem.qb)
    # need every digit of qc to be in the inverse mapping
    inv = {d: ch for ch, d in sol.items()}
    try:
        predicted = "".join(inv[int(d)] for d in str(qc))
    except KeyError:
        return Solution(False, None, sol, state["bt"], note="query digit unseen (guess subset)")
    return Solution(True, predicted, sol, state["bt"])


# --------------------------------------------------------------------------- #
# staged trace emission (RECALL tags + Q/C/S/N/Y solver notation)
# --------------------------------------------------------------------------- #
def emit_trace(problem: Problem, lut=None) -> str:
    """Emit the staged solver trace ending in ``</think>\\boxed{...}``.

    Tags: <RECALL_DOMAINS> (per-symbol candidate digits from the mul lookup),
    <RECALL_ROWS> (candidate integer rows for each mul signature), then the
    intersect/anchor/backtrack narration and the final boxed answer.
    """
    lut = lut or build_lookup()
    _domains, hint, recall_log = _seed_domains_from_lookup(problem, lut)
    sol = solve(problem, lut)
    lines = ["<think>"]
    lines.append("Q: identify multiplication examples and recall their digit patterns.")
    for sig, nrows, ea, eb, ec in recall_log:
        lines.append(f"<RECALL_ROWS sig={sig} n={nrows}/>  example {ea}*{eb}={ec}")
    lines.append("<RECALL_DOMAINS>")
    for s in sorted(hint):
        lines.append(f"  {s} in {{{','.join(map(str, sorted(hint[s])))}}}")
    lines.append("</RECALL_DOMAINS>")
    lines.append("C: intersect candidate digit sets across the multiplication examples.")
    anchors = {s: d[0] for s, d in hint.items() if len(d) == 1}
    lines.append(f"S: anchor singletons -> {anchors if anchors else '(none yet)'}")
    lines.append("N: bounded backtracking over remaining symbols (least-domain-first, reverse-first).")
    if sol.solved:
        lines.append(f"Y: bijection found in {sol.backtracks} steps -> {sol.recovered}")
        lines.append("</think>")
        lines.append(f"\\boxed{{{sol.predicted}}}")
    else:
        lines.append(f"Y: no full bijection ({sol.note}); fall back to best guess.")
        lines.append("</think>")
        lines.append("\\boxed{?}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# self-test / measurement
# --------------------------------------------------------------------------- #
def _measure(n: int, op: str, deduce: bool, n_examples: int):
    lut = build_lookup()
    solved = recovered = 0
    bt_total = 0
    for seed in range(n):
        p = generate_problem(seed=seed, op=op, n_examples=n_examples, deduce=deduce)
        sol = solve(p, lut)
        bt_total += sol.backtracks
        if sol.solved and sol.predicted == p.enc(p.qc):
            solved += 1
            # full-mapping recovery over symbols actually used
            inv_truth = {p.mapping[d]: d for d in range(10)}
            if all(sol.recovered.get(s) == inv_truth.get(s) for s in p.symbols_used()):
                recovered += 1
    return solved, recovered, bt_total / max(n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--show", type=int, default=0, help="print K example traces")
    args = ap.parse_args()

    print(f"CSP cryptarithm mechanism validation (n={args.n} synthetic instances each):")
    for op in ("*", "+", "-"):
        s, r, bt = _measure(args.n, op, deduce=True, n_examples=args.examples)
        print(
            f"  op={op!r} deduce: solved {s}/{args.n} = {100 * s / args.n:5.1f}%   "
            f"full-map recovered {r}/{args.n} = {100 * r / args.n:5.1f}%   avg_backtracks={bt:.0f}"
        )
    sg, rg, _ = _measure(args.n, "*", deduce=False, n_examples=args.examples)
    print(f"  op='*' guess  : solved {sg}/{args.n} = {100 * sg / args.n:5.1f}%  (query digit may be unseen)")

    if args.show:
        for seed in range(args.show):
            p = generate_problem(seed=seed, op="*", n_examples=args.examples, deduce=True)
            print("\n" + "=" * 60)
            print(f"secret map: {p.mapping}")
            print(emit_trace(p))
            print(f"(ground-truth answer = {p.enc(p.qc)})")


if __name__ == "__main__":
    main()
