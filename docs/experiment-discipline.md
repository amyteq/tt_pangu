# Experiment discipline

> The human-readable summary of the per-experiment checklist that used to live in `CLAUDE.md` ("Experiment discipline"), moved out by #188 to keep `CLAUDE.md` under 100 lines. The **machine-checkable form is now the contract**: [ADR-0023](./adr/0023-ledger-contracts.md) with `contracts/experiment.yaml` and `contracts/run.yaml`, validated by `kca contracts validate`. Where this page and a contract disagree, the contract wins. Two things the contract adds that a checklist cannot: an `Experiment` is a hypothesis and a `Run` is one attempt at it (so several folds / seeds / accelerators are several runs of one experiment), and **a retry is a new `Run` that never overwrites the failed one's history** (ADR-0023 §2).

Referenced from `CLAUDE.md` operating principle 5 (reproducibility).

## Per-experiment record

Each experiment should have:

- hypothesis;
- code/data/config changes;
- command(s) run;
- random seed(s);
- local validation score and metric name;
- runtime and resource notes;
- output artifact paths;
- interpretation;
- whether it deserves a leaderboard submission.

## Where it is recorded

| Phase | Record |
|---|---|
| Phase 1 (long-run validation) | The competition's tracking issue + `competitions/<slug>/` — the tracking-issue body carries current direction / progress / results, the first comment carries history. |
| Phase 2 (KCA) | The Supabase control plane (`experiments` / `experiment_runs` / `submissions`) plus the run artifact directory `runs/<competition>/<run_id>/`. |

Do not mix the two state-of-record surfaces (see `CLAUDE.md` "Two phases").

## Related

- `docs/adr/0020-goal-driven-kaggle-loop.md` — goal/exploration-batch lifecycle.
- `docs/adr/0021-kca-autonomy-model.md` — when a recorded experiment is eligible for an autonomous submission, and the four-scenario daily strategy.
- `docs/adr/0023-ledger-contracts.md` — the ledger contracts (Competition / ResearchItem / Idea / Decision / Strategy / Experiment / Run / Artifact / Submission / Score / Finding), their record paths and their invariants; `contracts/README.md` is the entity index.
