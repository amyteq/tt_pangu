# Submissions

> Reading view. The records are `submissions/<utc-timestamp>-<ref>.yaml` (the submission intent, written **before** dispatch — ADR-0022 §5 A6) and `ledger/scores/` (what the platform returned, including a private score released later).
> See [`ledger/README.md`](./ledger/README.md) for the record skeletons and `kca contracts validate --competition <slug>` to check them.

| Date | Version | Run/Experiment | Local CV | Public LB | Private LB | Submit/push type | Artifact | Notes |
|---|---|---|---:|---:|---:|---|---|---|

## Submission checklist
- [ ] local validation passed
- [ ] submission shape checked
- [ ] no secrets
- [ ] runtime acceptable
- [ ] approval obtained
- [ ] result recorded
