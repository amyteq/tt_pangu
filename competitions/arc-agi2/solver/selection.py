"""Pass@2 candidate selection — Product-of-Experts (PoE) over augmentations, with a vote
fallback.

After decoding each augmented prompt, every prediction is de-augmented (mapped back to the
original frame with the inverse of its augmentation) so that all candidates live in the same
coordinate/color space and can be compared. We then aggregate identical grids:

  * PoE score  = sum of per-augmentation log-probabilities for that grid (geometric mean of
                 probabilities, up to the shared count) -> rewards a grid the model is
                 confident about across many views.
  * votes      = how many augmentations produced that grid -> robust tiebreak / fallback when
                 log-probs are unavailable.

`select_top2` returns up to 2 distinct grids, best first. Grids are compared by value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .augment import Augmentation

Grid = list


@dataclass
class Candidate:
    """One raw decode in its augmented frame."""

    aug: Augmentation
    grid: Grid  # prediction in the AUGMENTED frame (de-augmented during aggregation)
    logprob: float | None = None  # total/avg log-prob of the decoded grid, if available


def _key(g: Grid) -> tuple:
    return tuple(tuple(int(c) for c in row) for row in g)


@dataclass
class _Agg:
    grid: Grid
    votes: int = 0
    logprob_sum: float = 0.0
    have_logprob: bool = False
    first_seen: int = field(default=0)


def aggregate(candidates: list[Candidate]) -> list[_Agg]:
    """De-augment every candidate and group identical grids."""
    groups: dict[tuple, _Agg] = {}
    order = 0
    for c in candidates:
        deaug = c.aug.invert(c.grid)
        k = _key(deaug)
        if k not in groups:
            groups[k] = _Agg(grid=deaug, first_seen=order)
            order += 1
        g = groups[k]
        g.votes += 1
        if c.logprob is not None:
            g.logprob_sum += c.logprob
            g.have_logprob = True
    return list(groups.values())


def select_top2(candidates: list[Candidate]) -> list[Grid]:
    """Return up to 2 distinct de-augmented grids, ranked by PoE log-prob when available,
    else by vote count. Stable: ties break by first-seen order.
    """
    aggs = aggregate(candidates)
    if not aggs:
        return []
    use_logprob = any(a.have_logprob for a in aggs)
    if use_logprob:
        # higher logprob_sum is better; -inf for groups that never had a logprob
        def rank(a: _Agg):
            score = a.logprob_sum if a.have_logprob else -math.inf
            return (-score, -a.votes, a.first_seen)
    else:

        def rank(a: _Agg):
            return (-a.votes, a.first_seen)

    aggs.sort(key=rank)
    return [a.grid for a in aggs[:2]]


def to_submission_entry(top2: list[Grid]) -> dict:
    """Format selected grids as a Kaggle attempt dict. Pads/duplicates to always give 2 attempts."""
    if not top2:
        return {"attempt_1": [[0]], "attempt_2": [[0]]}
    a1 = top2[0]
    a2 = top2[1] if len(top2) > 1 else top2[0]
    return {"attempt_1": a1, "attempt_2": a2}
