---
name: inventory-drift-audit
description: Scan docs / code / tests / config / schema / inventory for drift; produce evidence-backed drift findings and propose drift.yml issues. Does not edit files.
---

# inventory-drift-audit — find contradictions, propose drift issues

Use this skill to scan the repo for drift — places where one source claims X while another implements Y.

## Inputs

- Read access to the entire repo (excluding the secret paths in `docs/milestone-loop-protocol.md §6`).
- `docs/milestones/README.md`, `PROJECT_STATE.md`, ADRs under `docs/adr/`, inventory maps if any.

## Drift categories

- **docs vs code** — claim in `docs/` that the code disagrees with.
- **docs vs docs** — two docs claiming opposite things.
- **tests vs behaviour** — test name / assertion implies a behaviour the code no longer exhibits.
- **config vs runtime** — `env.example` lists a variable the code does not read, or the code reads a variable not documented.
- **schema vs DB layer** — a column in `supabase/migrations/` not used in the DB layer, or vice versa.
- **inventory vs repo state** — inventory map references a path that no longer exists, or a path missing from the map.

## Method

1. Pick a category and a target source (e.g. `docs/architecture/*.md`).
2. For each factual claim, grep the repo for the implementation it implies.
3. Record only **contradictions of fact**, not stylistic differences.
4. For each finding, decide whether the resolution is mechanical (auto-promotable to `ai:ready`) or requires a human decision (`decision:needed` + `ai:blocked`).

## Output

Per finding:

```
Title: ...
Location A: <file:line> — "<quote>"
Location B: <file:line> — "<quote>"
Drift type: docs-vs-code | docs-vs-docs | ...
Proposed resolution: <one paragraph>
Source of truth: A | B | decision:needed
Suggested labels: type:drift, area:..., decision:needed?, ai:blocked?
```

End with:

- Count by category.
- Audit gaps you saw but did not investigate (so the next pass can re-scope).

## Must not

- Do not "fix" the drift by editing code or docs — propose only.
- Do not file issues without human approval — surface proposed bodies.
- Do not flag style differences (formatting, prose voice) as drift.
- Do not chase secrets: skip `.env*`, `kaggle.json`, `id_rsa`, `id_ed25519`, `~/.aws/**`, `~/.config/gcloud/**`, `secrets/**`.
