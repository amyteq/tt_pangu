# Depth 2 — links from depth-1 pages (budget ≤20; 4 followed)

From @huikang's repo (the main fetchable depth-1 substrate):

| title | URL | type | fetchable | summary |
|---|---|---|---|---|
| bit solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/reasoners/bit_manipulation.py | code | YES | per-output-bit search; `_column_hash` = hex of bit-sum; left/right run detection. **No HEX-compression of columns, no signature/rule-seq catalog, no Hamming repair.** |
| cryptarithm solver | https://raw.githubusercontent.com/tonghuikang/nemotron/master/investigators/cryptarithm_deduce.py | code | YES | backtracking DFS w/ unique-digit constraints, ≤200 solutions. **No signature catalog, no candidate-count memorization.** |
| corpus builder | https://github.com/tonghuikang/nemotron/blob/master/corpus.py | code | YES | tokenized SFT segments from (problem, reasoning) pairs; 8192-token cap |
| training/sft dir | https://github.com/tonghuikang/nemotron/tree/master/training/sft | code | YES | timestamped run dirs (config.json / loss.jsonl), Mar–Jun 2026 |

These confirm the novelty attribution in `../source_index.md` and `../analysis/score_tricks.md`.
