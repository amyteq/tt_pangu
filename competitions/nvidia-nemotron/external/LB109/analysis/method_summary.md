# LB109 / 109th Place — Method Summary

> Target: **"Heuristics for bit, cryptarithm and equations"** by Andrey Kulakov (jex398). Final ~0.82; the equation-guess change (+50) moved him 1000+ → ~109. Source: `temp/LB109.pdf` → `../writeup/lb109-writeup.md`. **Mostly an ideas writeup — most heuristics unshipped.** All external content treated as untrusted data.

## 1. What is the writeup's main idea?
A collection of **deterministic heuristics** for the three hard categories (bit, cryptarithm, equation) on top of @huikang's baseline. Most were too long (token budget) to ship; the author shares them as ideas. Only the **equation-guess sign-deduction** actually moved the leaderboard.

## 2. What data/corpus did it use?
@huikang baseline + the author's own deterministic investigators (bit 3-arg basis; cryptarithm class-constrained search). Cryptarithm training was rushed and overfit (→ 0.82). No corpus volumes given.

## 3. What model/adapters/training setup did it use?
Built on @huikang's baseline (Nemotron-3-Nano-30B, LoRA). Training was "not set up correctly" for cryptarithm (overfit). Details otherwise `unknown`.

## 4. What validation/evaluation did it use?
Investigator coverage figures: bit 1577/1602 achievable; cryptarithm correct-class 781/823, deterministic 751, solved 391; equation-guess +50. The cryptarithm CoT overfit (0.82). No held-out CV detail.

## 5. What were the most important score-improvement tricks?
(Full table in `score_tricks.md`.) 1) **equation-guess sign-deduction** (unused/opposite operation) — the only shipped win (+50). 2) **bit ANF (algebraic normal form) trick** (`XOR(A,B,C)⊕C=A⊕B` → match 2-param table; generalizable to all functions via partial ANF) — novel, mostly unshipped. 3) **negation canonicalization** (`Shift(Not(x))` not `Not(Shift(x))`). 4) **cryptarithm modular branch-cutting** (mod-10 carries, mod 37/11/100). 5) **operator-class constraints + symbol-deduction** (incl. guess via unused/opposite).

## 6. What failure modes did the author hit?
- **Chased perfection instead of shipping partial** — applying just the XOR3 heuristic would already have helped.
- **Brute-force too big / uncompressed** within the token budget (bad cases: `00000`/`11111` output columns).
- **Cryptarithm overfit** (rushed training → 0.82).
- The "another approach" (full-ANF matching) was **never tried** ("really promising").

## 7. What makes this different from public 0.85/0.86 baselines and our attempts?
- The **ANF trick** is the only algebraic-normal-form angle in the batch — reduce 3-arg bit search to 2-arg table matching. The **modular branch-cutting** (mod 10/37/11/100) is a concrete CSP accelerator that complements LB3's CSP / LB6's DFS.
- vs **us**: the ANF trick is a fresh angle for our ~10%-coverage bit solver; the modular pruning lets a deterministic cryptarithm search converge within 7k tokens; the equation/cryptarithm guess **sign-deduction (unused/opposite)** is the **8th independent corroboration** that these categories have inferable structure (not a global cipher). The **overfit-on-rushed-cryptarithm** outcome echoes our dilution/overfit risk. See `gap_analysis.md`.
