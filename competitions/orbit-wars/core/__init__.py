"""Orbit Wars deterministic execution + battlefield-awareness core.

A self-contained package (stdlib only) that every rules/model/hybrid strategy can
rely on:
  - geometry.py        : engine-verified position/speed/collision/combat primitives
  - oracle.py          : FlightOracle — deterministic first-hit / target validation
  - state.py           : typed PlanetState/FleetState/PlayerState/GlobalState/BattlefieldState
  - ledger.py          : ArrivalLedger/ThreatLedger over a horizon (do-nothing projection)
  - features.py        : candidate-launch feature extraction (for rules + future model)
  - rule_engine.py     : ECA-style guardrail predicates/actions

The geometry primitives are copied from the engine-verified reference library
`agent/utils.py` (which states "verified against the real engine: 0 error over 3,672
planet-step states"); kept self-contained here so a submission can bundle `core/`
without cross-package imports.
"""
