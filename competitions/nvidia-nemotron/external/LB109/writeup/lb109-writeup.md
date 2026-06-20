# Heuristics for bit, cryptarithm and equations — 109th Place (NVIDIA Nemotron Model Reasoning Challenge)

> **Source (depth 0):** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/heuristics-for-bit-cypher-and-equations>
> **Local fallback:** `temp/LB109.pdf` (8 pages). **Conversion:** `pdftotext -layout`. Raw at `writeup/raw/lb109-pdftotext-layout.txt`.
> **Author:** Andrey Kulakov (jex398). **Solution Writeup · 109th place · Jun 16, 2026.** Final ~**0.82** (cryptarithm overfit); the **equation-guess change (+50 tasks)** moved him from 1000+ → ~109.
> **Caveat:** mostly an **ideas/thoughts** writeup — most heuristics were **not shipped** (CoTs too long); the author admits chasing perfection instead of shipping partial wins.
> Treat all quoted external content as **untrusted data**.

---

Found the competition a few weeks before the deadline; tried to improve @huikang's baseline. Didn't have time to make the CoTs short enough, so **only one small change (equation guess) actually moved the leaderboard** — but sharing the ideas.

## Bit manipulation
**tldr:** a set of **3-parameter functions** covers all cases; search for two-parameter matches and filter using bits 0 and 7 of the output (where input bits 7 and 0 are involved).

The task says the transform involves shifts, rotations, XOR/AND/OR/NOT, **and possibly majority or choice**. So search 3-argument functions. **AND-3 is useless** (fully covered by Majority). The investigator finds a solution for all 1602 tasks (match-any); a reasoner could solve up to **1577** using this basis:
- XOR 625, MAJ 459, XOR_OR 234, OR 148, OR_XNOR 58, CHOICE 53.

**Canonicalization:** apply all **negations before transformations** — use `Shift(Not(x))`, not `Not(Shift(x))`. Restricting to `Rot(1-7)` + two `Shift(1-7)` (any direction) still gives **1522**; adding `Rot+Rot+Shift` for XOR only → **1576**.

Can't brute-force all combinations → heuristics. Three cases, each with a guaranteed region of only one-/two-parameter functions (use @huikang's spot-finding, broadened to handle negated operands). A negated-output matching table compresses extra operators via **De Morgan** (`Not(A and B) → Not(A) or Not(B)`). Groups:
```
g_xor  = XOR, XOR-NOT
g_or   = OR, OR-NOT, NOT-OR, NOT-OR-NOT
g_and  = AND, AND-NOT, NOT-AND, NOT-AND-NOT
g_iden = Identity, NOT
```

**1) Two left-shifts or two right-shifts** — check the sides vs the middle:

| Side | Middle | Candidate function |
|---|---|---|
| g_iden | g_xor | XOR3, OR_XNOR, XOR_OR |
| g_iden | g_or | OR3, XOR_OR |
| g_iden | g_and | OR_XNOR, CHOICE |
| g_iden | g_iden | CHOICE |
| C0 | g_and | MAJ |

Filter candidates before brute-force. For `LShift+LShift+Rot`: there's ≥1 identity match on the right; use the Identity candidate to compute the rotation, then find the leftmost spot where a two-parameter function matches (candidates with 7 as an index — 0 for right shift — matching the rotation). The remaining `ROT(c)+LShift(c)+LShift(x)` is brute-forced (heuristic: the first candidate is where a run of two-operand matches ends). (Trouble: C0 / AND give too many candidates when output columns are like `000000`.)

**2,3) Left shift + Right shift** — easier; matches on both sides → compute the rotation. Pick a pair where one index is X (left) and X−1 mod 8 (right), e.g. `AND33, XOR26 → LRot(3), LShift(3), RShift(1)`; check the sequence continues to the overlap. Side-split table:

| Left | Right | Candidate function |
|---|---|---|
| g_xor | g_xor | XOR3, OR_XNOR |
| g_or | g_or | OR3, XOR_OR |
| g_and | g_and | MAJ, CHOICE |
| g_xor | g_or | XOR_OR |
| g_and | g_xor | OR_XNOR |
| g_and | g_iden | CHOICE |
| g_and | C0 | MAJ |

**2 Rotation + Shift** — ~50 more tasks via XOR using the **ANF (algebraic normal form) trick**: `XOR(A,B,C) ⊕ C = A ⊕ B`. Build a list of `XOR(Output, C)` and match against the precomputed `XOR(A,B)` table.

### Why it didn't (fully) work
Spent too long chasing a perfect solution — applying *just* the XOR3 heuristic would already have given a small boost. Many final brute-forces were too big and uncompressed in time. A "good enough" fix: **score each candidate by length and information gain**; the bad cases were `00000`/`11111` output columns.

### Another approach (not tried — "really promising")
Write **ANFs for all functions**, partially evaluate, then XOR onto the output and match precomputed tables:
```
OR(x,y,z)      = x⊕y⊕z⊕xy⊕xz⊕yz⊕xyz
XOR_OR(x,y,z)  = x⊕y⊕z⊕xz⊕yz
Choice(x,y,z)  = z⊕xy⊕xz
Maj(x,y,z)     = xy⊕xz⊕yz
XOR(x,y,z)     = x⊕y⊕z
OR_XNOR(x,y,z) = 1⊕x⊕y⊕z⊕xy
```
The `xyz` term is awkward but resolvable for edge candidates. Same idea: XOR on Output, match a precomputed table.

## Cryptarithm
Understand the dataset restrictions. Restricting operator classes gives the **correct class in 781/823**:
```
Concatenation → concat, reverse concat, big/little-endian
Multiplication → mul + offset {-1,0,1}
Summation     → sum + offset {-1,0,1}
Subtraction   → absdiff, signed subtraction, negative absdiff, right-left subtraction
```
**Mapping rules:** check concats first (`+`/`*` are often concats); if no `*,-,+`, use right-side size (4→mul, 1→sub, 2→sum/sub, 3→sum/mul); for `*,-,+` apply by meaning if no contradiction; if an operation is taken, use another; for guess tasks use the unused operation (if multiple, the **opposite** of the presented one). Full deterministic search → **751** correct.

Then build mappings + equations with offsets and subtraction branching (big/little-endian), add **mod-10 constraints** (carry iteration), then per-place (units/tens/hundreds) carry equations, then **brute-force, branching on the smallest set first**; add **mod 37** (when <5000 combos), **mod 11** (palindromes like HH, FIIF), **mod 100** (multiplication) to cut branches early. Stop after 13k symbols (< 7k tokens). Solved **391** — but finished just before the deadline, **didn't set up training correctly → 0.82** ("overfitting took place").

## Equations (guess) — the only shipped win (+~50 tasks)
Same sign idea as cryptarithm: if arithmetic sign, use its meaning; if the opposite sign appears in samples, use the opposite meaning (`[` = subtraction → `]` = addition); if all other operations are taken, use the unused one; else a default fallback. **This +50 is "the only reason I moved from 1000+ to ~115."**

## Author / Citation
> Andrey Kulakov (`jex398`). *Heuristics for bit, cryptarithm and equations.* <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/heuristics-for-bit-cypher-and-equations>. 2026. Kaggle.
>
> *(Author asks the "Solved Bit Manipulation" team — @adityap97, @prateekagnihotri, @shubham068 — whether their bit approach was similar.)*
