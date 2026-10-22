# `competitions/` source-control policy

> Adopted from [#195](https://github.com/amyteq/tt_pangu/issues/195) — the source-of-truth answer to *"what belongs under `competitions/`, what does not, and where does rolling state live."* Referenced from [`CLAUDE.md`](../CLAUDE.md#repository-conventions) → *Repository conventions* and from [`competitions/README.md`](README.md) (top link).

`competitions/<slug>/` tracks the reproducible artifact of each competition, not its running commentary. Keep this tree small on purpose: the more rolling state that lives here, the more it drifts from `competition.yaml`, the tracking issue and the actual leaderboard.

## Keep / move out / do not track

| Class | Rule |
|---|---|
| Experiment / kernel / agent `.py` | **keep** — the reproducible artifact. |
| `competition.yaml`, `kca-<slug>.yaml` | **keep** — the Competition record + push config (ADR-0022 §3 rank 1). |
| `external/LB*/` writeups | **keep, untouched** — highest-value external evidence in the repo. |
| Postmortems and durable technical findings (`insights.md`, `bugs.md`, `equation-frontier.md`, `postmortems/*.md`) | **keep**, one file per competition — not a sprawl. |
| Rolling state — `tracking.md`, `tasks.md`, `submissions.md`, `strategy.md`, `notes*.md`, `explore.md`, `research.md`, `references.md` | **move out.** Body of the competition's tracking issue = current direction / progress / results; first comment = history. Until a per-competition tracking issue exists ([#199](https://github.com/amyteq/tt_pangu/issues/199) is the dashboard, not per-slug), archive under a clearly-marked history path rather than deleting. |
| Bilingual duplicates (`notes.md` + `notes_zh.md`, `tracking.md` + `tracking_zh.md`, `research_report_zh.md`, …) | **collapse** — [`CLAUDE.md`](../CLAUDE.md) § *Language* limits Chinese to project intro, experiment-result summaries and direction confirmation; the English original is authoritative and a `*_zh.md` sidecar is human-reading only. |
| Large binaries, datasets, model weights, run logs | **not tracked** — already covered by `.gitignore`; keep out of `competitions/` too. |

## Guardrails when acting on this policy

- Preserve history — use `git mv` for moves and the tracked-removal form of `git` for deletions; grep before deleting anything. `equation-frontier.md` and the nemotron LB writeups have already been the subject of a recorded mistake where existing work was rebuilt from scratch because nobody checked first. When in doubt, archive rather than delete.
- New competitions start from [`_templates/`](_templates/); the template file set is the ceiling for what a fresh slug should carry on day one. Any rolling-state file above that ceiling is a candidate for the *move out* row.

## Scope of this file

This document is only the *policy* half of [#195](https://github.com/amyteq/tt_pangu/issues/195). The rolling-state archive pass, the `_templates/` reduction, and the tracked-`.md`-count reduction are separate follow-ups. The CI gate for `status: open` with a past `deadline` is already covered by [PR #240](https://github.com/amyteq/tt_pangu/pull/240) / [PR #241](https://github.com/amyteq/tt_pangu/pull/241).
