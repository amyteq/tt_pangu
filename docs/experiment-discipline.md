# Experiment discipline

> Interim home for the per-experiment checklist that used to live in `CLAUDE.md`
> ("Experiment discipline"), moved out by #188 to keep `CLAUDE.md` under 100 lines.
> This will be **absorbed into the ledger contracts ADR** (ADR-0023, issue #191),
> which defines the `Experiment` / `Run` split and the recorded field set. Until
> that ADR merges, this file is the reference and the fields below are the floor,
> not the ceiling.

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
- `docs/adr/0021-kca-autonomy-model.md` — when a recorded experiment is eligible
  for an autonomous submission, and the four-scenario daily strategy.
- Issue #191 — ledger contracts (Research / Idea / Decision / Strategy /
  Experiment / Run / Artifact / Submission / Score / Finding).
