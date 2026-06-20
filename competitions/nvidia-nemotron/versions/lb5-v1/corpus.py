"""Demo corpus builder for lb5-v1 (CPU; wraps the no-leakage generator).

Provides `build_demo_corpus(n, seed)` -> [{category, answer, trace, origin_seed}]
for the scorer / validation self-checks. Delegates to `generator.build_corpus`
(equation + ternary-bit), the LB5 heavy categories. Every trace ends `\\boxed{...}`.
"""

from __future__ import annotations

import generator


def build_demo_corpus(n: int, seed: int = 0):
    return generator.build_corpus(n, seed=seed)


if __name__ == "__main__":
    from collections import Counter

    recs = build_demo_corpus(20, seed=1)
    print("demo corpus:", Counter(r["category"] for r in recs))
    print(recs[0]["trace"][:200])
