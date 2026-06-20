# LB109 heuristic investigators (mostly unshipped)

- **bit:** 3-arg basis (XOR/MAJ/XOR_OR/OR/OR_XNOR/CHOICE → 1577/1602); negation canonicalization (`Shift(Not(x))`); spot-finding + side/middle candidate tables; **ANF trick** (`XOR(A,B,C)⊕C=A⊕B` → 2-param table match; full-ANF matching planned, not done).
- **cryptarithm:** class constraints (concat/mul±/sum±/sub) → correct class 781/823, deterministic 751; big/little-endian formulas + **mod-10 carries + mod 37/11/100** branch-cutting; solved 391 but overfit → 0.82.
- **equation (guess):** sign-deduction (unused/opposite) → +50 (the only shipped win).
- Reasoner code unreleased; not downloaded.
