"""ActionEmitter — layer [7] final emission (OW-ARCH-001).

Converts selected candidates into the Kaggle action list while PRESERVING intended target ids all
the way into the ActionSanitizer, so the sanitizer can block wrong-first-hit / landing-target
mismatch (opt-in) — not just sun/OOB. This is the single place a policy turns decisions into actions.

Behavior contract:
  - Always runs the FlightOracle sun/OOB gate (provably-fatal launches dropped).
  - Wrong-first-hit gate is OPT-IN (`block_wrong_first_hit=True`): only then are intended targets
    used to drop mismatches. Default OFF preserves a sanely-aimed agent's behavior exactly.
  - Accepts either CandidateAction objects (intent carried on the object) or parallel
    moves + targets lists.
"""

from __future__ import annotations

from .action_sanitizer import ActionSanitizer


class ActionEmitter:
    def __init__(self, sanitizer: ActionSanitizer | None = None, block_wrong_first_hit=False, horizon=60):
        self.sanitizer = sanitizer or ActionSanitizer()
        self.block_wrong_first_hit = block_wrong_first_hit
        self.horizon = horizon

    def emit(self, obs, selected, targets=None, counters=None):
        """selected: list of CandidateAction OR raw [src, angle, ships]. targets: optional parallel
        intended-target ids (used only when selected are raw moves). Returns clean Kaggle actions."""
        moves, tgts = [], []
        for i, item in enumerate(selected or []):
            if hasattr(item, "to_move"):  # CandidateAction
                moves.append(item.to_move())
                tgts.append(getattr(item, "target_id", None))
            else:  # raw [src, angle, ships]
                moves.append([int(item[0]), float(item[1]), int(item[2])])
                tgts.append(targets[i] if (targets is not None and i < len(targets)) else None)
        use_targets = tgts if self.block_wrong_first_hit else None
        clean, _c = self.sanitizer.sanitize(obs, moves, targets=use_targets, horizon=self.horizon, counters=counters)
        return clean
