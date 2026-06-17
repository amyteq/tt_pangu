"""ActionSanitizer — the final emission gate. Every action passes through the FlightOracle
before it is emitted; provably-fatal actions (strict sun collision, out-of-bounds) are
dropped, and — when the caller supplies intended targets — wrong-first-hit actions too.

Design:
  - Block ONLY what is provably wasted/suicidal by default (sun, oob) so the gate can never
    remove a good action -> zero behavioral regression for an agent that already aims sanely.
  - Block wrong-first-hit ONLY when the caller passes the intended target per action (the
    hybrid policy will; a raw [src,angle,ships] list has no intent to check against).
  - `near_sun` (graze) is allowed but counted/flagged. `none` (no body within horizon) is
    counted but allowed by default (unreachable for sanely-aimed short-ETA launches).
  - Debug counters are returned but NOT logged unless explicitly enabled (off by default
    online): blocked_sun, blocked_oob, blocked_wrong_first_hit, blocked_no_target, emitted_valid.
"""

from __future__ import annotations

from .oracle import FlightOracle


def new_counters():
    return {
        "blocked_sun": 0,
        "blocked_oob": 0,
        "blocked_wrong_first_hit": 0,
        "blocked_no_target": 0,
        "near_sun": 0,
        "emitted_valid": 0,
    }


class ActionSanitizer:
    def __init__(self, oracle: FlightOracle | None = None, block_no_target=False):
        self.oracle = oracle or FlightOracle()
        self.block_no_target = block_no_target  # default False: 'none' is allowed (counted)

    def sanitize(self, obs, actions, targets=None, horizon=120, counters=None):
        """Return (clean_actions, counters). `actions` = [[src, angle, ships], ...];
        optional `targets[i]` = intended target planet id for actions[i] (enables the
        wrong-first-hit block). Malformed / non-positive-ship actions are dropped."""
        c = counters if counters is not None else new_counters()
        clean = []
        for i, mv in enumerate(actions or []):
            if not (isinstance(mv, (list, tuple)) and len(mv) == 3):
                continue
            try:
                src, ang, ships = int(mv[0]), float(mv[1]), int(mv[2])
            except (TypeError, ValueError):
                continue
            if ships <= 0:
                continue
            r = self.oracle.first_hit(obs, src, ang, ships, horizon)
            if r.first_hit_type == "sun":
                c["blocked_sun"] += 1
                continue
            if r.first_hit_type == "oob":
                c["blocked_oob"] += 1
                continue
            if r.first_hit_type == "none":
                if self.block_no_target:
                    c["blocked_no_target"] += 1
                    continue
                c["blocked_no_target"] += 1  # counted as a flag; still emitted below
            tgt = targets[i] if (targets is not None and i < len(targets)) else None
            if tgt is not None and r.first_hit_id != tgt:
                c["blocked_wrong_first_hit"] += 1
                continue
            if r.near_sun:
                c["near_sun"] += 1
            clean.append([src, ang, ships])
            c["emitted_valid"] += 1
        return clean, c


def sanitize_default(obs, actions, targets=None, oracle=None):
    """Convenience: block provably-fatal (sun/oob) emissions. Returns clean actions only
    (counters discarded). Safe to wrap a live agent's final emission with — it cannot drop
    a sanely-aimed move (those first-hit a planet within the horizon)."""
    san = ActionSanitizer(oracle)
    clean, _c = san.sanitize(obs, actions, targets=targets)
    return clean
