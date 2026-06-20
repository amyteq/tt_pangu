# Competition train.csv

- 9,500 labeled problems, 7 categories. Already in our local data.
- LB25's change #1 fixed a **local-eval bug** (validation prompt didn't box the answer though submission did) — the on-train/on-val evaluation must match the grader exactly (= our B4/T13 + INS-002).
