# Bugs — sec-attack

| ID | Status | Severity | Area | Summary | Evidence | Next action |
|---|---|---|---|---|---|---|
| — | — | — | — | (none yet) | — | — |

<!-- Status: open | investigating | fixed | wontfix | obsolete | unknown -->

## Watch-list (potential traps, not yet observed)
- **Cell-feature bucketing** — breadth generators that vary an un-hashed dimension (counter in same domain/query)
  produce identical cells → 0 breadth gain. Verify unique-cell count rises when sweeping. (`cells.py`)
- **Replay divergence** — a candidate scores in `run()` but 0 on replay (state not reproduced / guardrail blocks).
  Always re-score via `aicomp evaluate`, not the in-`run()` filter.
- **Archive memory blow-up** — Go-Explore keeps a full env snapshot per cell; RSS grows over 1800 s (in-code TODO).
- **Agent mismatch** — strong results on `deterministic` that collapse on the real LB agent.
