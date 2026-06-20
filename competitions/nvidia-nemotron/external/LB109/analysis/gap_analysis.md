# LB109 / 109th Place — Gap analysis (us vs the 109th-place writeup)

> "our approach" cites `competitions/nvidia-nemotron/{notes,submissions,equation-frontier,bugs}.md`. "writeup" cites `../writeup/lb109-writeup.md`. Mostly an ideas writeup (final ~0.82).

| area | our approach | writeup approach | gap | lesson |
|---|---|---|---|---|
| bit manipulation | ~90% unsolved; enumeration. (notes.md:73) | 3-arg basis (1577/1602) + **ANF trick** (XOR-on-output table matching) + negation canonicalization; mostly unshipped. | We lack the ANF angle | Reduce 3-arg search to 2-arg table matching via ANF |
| cryptarithm | synth-only; 8%→71% local, total ~0.86 (B8). (bugs.md:14) | class-constrained deterministic search + **modular branch-cutting** (mod 10/37/11/100); solved 391 but overfit → 0.82. | We lack modular pruning | Mod-arithmetic carries let a deterministic search converge in 7k tokens |
| equation (guess) | global cipher (EQ-0/EQ-2′). (equation-frontier.md:209-228) | **sign-deduction (unused/opposite)** → +50 (the shipped win). | Premise corroboration (8th) | guess is inferable via unused/opposite operation |
| synthetic / training | c1/c2 verified-only; dilution. (submissions.md:31) | rushed cryptarithm training → **overfit (0.82)**. | Both risk overfit on hard-cat data | Set up training carefully; ship partial wins |
| validation | T12 late. (submissions.md:76-78) | investigator coverage only; no real CV; overfit not caught. | They lacked a CV | A CV would have caught the cryptarithm overfit |
| process | death-march on hard categories. | **chased perfection, didn't ship partial.** | Same trap | Ship the XOR3/mod-10 small wins first |

## Why our attempts didn't close the gap
- **bit:** we never tried the **ANF (algebraic normal form)** angle — partial-ANF + XOR-on-output table matching reduces the 3-arg search dramatically. A fresh lever for our ~10% bit solver.
- **cryptarithm:** **modular branch-cutting** (mod 10/37/11/100) is the search accelerator that lets a deterministic cryptarithm solver (LB3 CSP / LB6 DFS / ours) fit the token budget. Adopt it.
- **equation:** the **guess sign-deduction (unused/opposite)** is the 8th corroboration that equation guess is inferable; re-test our global-cipher premise (no GPU).
- **process:** LB109's "chased perfection, shipped nothing" is a mirror of our hard-category death-marches — ship XOR3/mod-10 partial wins, then iterate.

## High-value vs not-worth-it
**High value:** the **ANF trick** for bit (novel); **modular branch-cutting** for cryptarithm (mod 10/37/11/100); **negation canonicalization**; **equation/cryptarithm guess sign-deduction**; the **process lesson** (ship partial wins; score candidates by length+info-gain).
**Not worth:** chasing a perfect bit brute-force (token budget kills it — score/prune instead); rushing hard-cat training without a CV (overfit → 0.82).
