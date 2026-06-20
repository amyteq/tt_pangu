# Depth 2 — links from depth-1 pages (budget ≤20; 3 followed)

From @huikang's repo (the main fetchable depth-1 substrate; fetched in prior LB1 research):

| title | URL | type | fetchable | summary |
|---|---|---|---|---|
| bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | YES | per-output-bit search; LB3 extends it with hex+tail-bit columns + MAJ + OR-NOT-first ordering |
| cryptarithm solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/investigators/cryptarithm_deduce.py | code | YES | backtracking DFS; LB3 adds mul-pattern lookup + multi-example intersection + anchor + two-stage memory |
| training loop / corpus | https://github.com/tonghuikang/nemotron (train_sft.py, corpus.py) | code | YES | the CCE "manual training loop" LB3 reuses |

These confirm the novelty attribution in `../source_index.md` and `../analysis/score_tricks.md`.
