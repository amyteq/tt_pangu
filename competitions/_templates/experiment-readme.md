# Experiment: <name>

> 单个实验/假设/模型版本的说明。重产物(权重、日志)放 runs/ 或 object storage,不进 git。

- hypothesis:
- parent competition:
- code / config changes:
- command(s) run:
- random seed(s):
- local validation score (metric):
- runtime / resource notes:
- output artifact paths:
- interpretation:
- deserves a leaderboard submission? yes/no + why:

> The machine-readable form of this page is an `Experiment` record in `ledger/experiments/` plus one `Run` record per attempt in `ledger/runs/` — a retry is a new `Run`, never an edit to the failed one (ADR-0023 §2).
> See [`ledger/README.md`](./ledger/README.md) for the record skeletons and `kca contracts validate --competition <slug>` to check them.
