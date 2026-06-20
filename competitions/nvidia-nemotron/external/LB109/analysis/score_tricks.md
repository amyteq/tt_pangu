# LB109 / 109th Place — Score-improvement tricks

> Evidence cites `../writeup/lb109-writeup.md` (= `temp/LB109.pdf`). Mostly ideas; **only equation-guess shipped.** "reusable by us" judged vs our repo.

| trick | description | evidence | shipped? | likely impact | reusable by us? | difficulty |
|---|---|---|---|---|---|---|
| **equation-guess sign-deduction** | Arithmetic sign → meaning; opposite sign → opposite meaning; else unused operation; else fallback. | §Equations | **YES** (the only shipped win) | **High** (+50 tasks; 1000+→~109) | **Yes — re-check EQ premise** | Low |
| **bit ANF (algebraic normal form) trick** | `XOR(A,B,C)⊕C=A⊕B` → match a 2-param XOR table; generalizable: write ANFs for OR/XOR_OR/Choice/Maj/OR_XNOR, partial-evaluate, XOR on output, match precomputed tables. | §Bit, §Another approach | No (mostly) | **High (potential)** | **Yes — novel angle for our bit solver** | High |
| **Negation canonicalization** | Apply negations before transformations (`Shift(Not(x))`, not `Not(Shift(x))`). | §Bit | Partial | **Medium** (smaller search) | **Yes — cheap** | Low |
| **cryptarithm modular branch-cutting** | mod-10 carry constraints + mod 37 (<5000 combos) + mod 11 (palindromes) + mod 100 (multiplication); branch on smallest set first; 13k-symbol cap. | §Cryptarithm | Yes (but overfit) | **Medium-High** (search accelerator) | **Yes — complements LB3 CSP / LB6 DFS** | Medium-High |
| **Operator-class constraints + symbol-deduction** | Concat/Mul±offset/Sum±offset/Sub classes; right-side-size mapping; guess = unused/opposite. | §Cryptarithm, §Equations | Yes | **Medium** | **Yes** | Medium |
| **bit 3-arg basis (XOR/MAJ/XOR_OR/OR/OR_XNOR/CHOICE)** | 1577/1602 with this basis; AND-3 useless (covered by MAJ). | §Bit | Investigator only | **Medium** | **Yes** | Medium |
| **Score candidates by length + info gain** (negative lesson) | Bad cases (`00000`/`11111`) blew up brute-force; should have scored/pruned candidates. | §Why it didn't work | No | **Medium (lesson)** | **Yes** | Low-Medium |
| **Ship partial wins, don't chase perfection** (process lesson) | Just XOR3 would have helped; perfectionism cost shipping. | §Why it didn't work | n/a | **High (process)** | **Yes** | n/a |

## Provenance / attribution
- Built on **@huikang's baseline**. The "Solved Bit Manipulation" team (@adityap97/@prateekagnihotri/@shubham068) is referenced (their bit approach unknown).
- **Novel to LB109:** the **ANF trick** (algebraic-normal-form matching for bit), **negation canonicalization**, and the **modular branch-cutting** stack (mod 10/37/11/100) for cryptarithm.
- **Cross-writeup convergence:** the equation/cryptarithm **guess sign-deduction (unused/opposite)** matches LB3/LB6/LB13 — equation/cryptarithm have inferable per-problem structure.
