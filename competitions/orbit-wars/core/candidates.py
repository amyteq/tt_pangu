"""Typed candidate representation for the layered policy (OW-ARCH-001, layer [3]).

A `CandidateAction` is a proposed launch carried through the pipeline with its intended target id
preserved end-to-end (state -> candidates -> features -> rule_engine/model -> emitter -> sanitizer),
so the final ActionSanitizer can validate first-hit/landing-target against the INTENDED target rather
than guessing from a raw [src, angle, ships] triple.

Candidate generation should produce these with intended target ids and leave final first-hit / path
authority to FlightOracle + ActionSanitizer (see core/oracle.py, core/action_sanitizer.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CandidateAction:
    source_id: int
    target_id: int
    angle: float
    ships: int
    eta: int | None = None
    # expand | attack | defend | reinforce | supply | comet | bank | consolidate | unknown
    candidate_type: str = "unknown"
    base_value: float = 0.0  # deterministic (v3.2) value, e.g. terminal differential advantage
    reason: str = ""
    features: dict | None = field(default=None)
    rule_weight: float = 1.0  # RuleEngine multiplier (1.0 = neutral)
    model_score: float | None = None  # advisory model probability in [0,1], or None
    final_score: float = 0.0

    def to_move(self) -> list:
        """The Kaggle action triple [source_id, angle, ships]."""
        return [int(self.source_id), float(self.angle), int(self.ships)]

    @classmethod
    def from_move(cls, move, target_id=None, **kw) -> "CandidateAction":
        """Wrap a raw [src, angle, ships] move, preserving the intended target id."""
        src, ang, ships = int(move[0]), float(move[1]), int(move[2])
        return cls(source_id=src, target_id=(target_id if target_id is not None else -1), angle=ang, ships=ships, **kw)
