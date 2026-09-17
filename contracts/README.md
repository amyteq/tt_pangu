# `contracts/` — the ledger contracts

One schema per ledger entity. These files are the **single definition** that phase 1 (Markdown/YAML records under `competitions/<slug>/`) and phase 2 (KCA on Supabase) both validate against. The decision record is [ADR-0023](../docs/adr/0023-ledger-contracts.md); the entity model comes from [discussion #185 §5](https://github.com/amyteq/tt_pangu/discussions/185).

Validate with:

```bash
kca contracts validate                              # every record the repository holds
kca contracts validate --competition nvidia-nemotron
kca contracts schemas                               # list entities, id prefixes and record paths
```

## Entities

| Entity | Schema | id prefix | Phase-1 record path |
|---|---|---|---|
| Competition | [`competition.yaml`](./competition.yaml) | *(the slug)* | `competitions/<slug>/competition.yaml` |
| ResearchItem | [`research-item.yaml`](./research-item.yaml) | `RI-` | `competitions/<slug>/ledger/research/<id>.yaml` |
| Idea | [`idea.yaml`](./idea.yaml) | `IDEA-` | `competitions/<slug>/ledger/ideas/<id>.yaml` |
| Decision | [`decision.yaml`](./decision.yaml) | `DEC-` | `competitions/<slug>/ledger/decisions/<id>.yaml` |
| Strategy | [`strategy.yaml`](./strategy.yaml) | `STRATEGY-` | `competitions/<slug>/ledger/strategies/<id>.yaml` |
| Experiment | [`experiment.yaml`](./experiment.yaml) | `EXP-` | `competitions/<slug>/ledger/experiments/<id>.yaml` |
| Run | [`run.yaml`](./run.yaml) | `RUN-` | `competitions/<slug>/ledger/runs/<id>.yaml` |
| Artifact | [`artifact.yaml`](./artifact.yaml) | `ART-` | `competitions/<slug>/ledger/artifacts/<id>.yaml` |
| Submission | [`submission.yaml`](./submission.yaml) | `INT-` | `competitions/<slug>/submissions/<utc-timestamp>-<ref>.yaml` |
| Score | [`score.yaml`](./score.yaml) | `SCORE-` | `competitions/<slug>/ledger/scores/<id>.yaml` |
| Finding | [`finding.yaml`](./finding.yaml) | `FIND-` | `competitions/<slug>/ledger/findings/<id>.yaml` |

The Submission path is **not** under `ledger/`: ADR-0022 §5 activation condition **A6** fixes it at `competitions/<slug>/submissions/<utc-timestamp>-<intent-id>.yaml`, and a merged ADR's path is not something this contract renames. ADR-0023 §4 pins the one part §5 left open — `<intent-id>` is the record's `ref`, verbatim, so that the file for a given ref can be found from the ref alone. That is the lookup reconciliation actually performs, and `<utc-timestamp>` is `YYYY-MM-DDTHHMMSSZ` so the directory sorts chronologically.

## What the schemas are, and what they are not

Every file is a standalone **JSON Schema 2020-12** document written in YAML — no `$ref`, no `$defs`, so any JSON Schema implementation can load one file on its own and any reader can follow it without resolving references.

The schemas describe **shape**: which keys exist, their types, their enums, their patterns. They deliberately do not try to express the ledger's **invariants** — id uniqueness, cross-record foreign keys, the retry rule, the `provenance` completeness rule. Those are cross-file and conditional on values; `kca contracts validate` checks them as a second pass, and ADR-0023 §5 lists them.

Two consequences worth knowing before editing a schema:

- **A declared property is `required`, and an unknown value is `null`, never a missing key.** A missing key is a bug, not a local override — the same rule ADR-0022 §6 states for the `budget:` block. So `type: [string, "null"]` is the normal shape of a value that may not be known yet. Nine properties are exempt and a test pins the list: `Competition`'s `aliases`, `tracking_issue` and its five side-state fields, plus `Submission.screen`'s `beats_best` and `min_margin` (ordering signals, not gates — ADR-0022 §5).
- **Ledger records are closed (`additionalProperties: false`); `Competition` is open (`additionalProperties: true`).** `competition.yaml` is a live, human-edited file that legitimately carries per-competition extras (`sdk:` for sec-attack, `prize_pool_usd:` for arc-agi2). Its *canonical* keys are still fixed.

## The keyword subset

`tools/kca/contracts.py` implements the subset these schemas use, with no third-party dependency, so `kca contracts validate` works from a bare checkout:

`type` · `enum` · `const` · `properties` · `required` · `additionalProperties` · `items` · `pattern` · `minimum` · `minItems` · `minLength`

`tests/test_contracts.py` asserts that the schemas use **nothing outside that list**, so a new keyword cannot be added without either extending the validator or failing CI. The same test re-validates every real record with the `jsonschema` library (a `dev` extra) so the subset stays standards-conformant rather than merely self-consistent.
