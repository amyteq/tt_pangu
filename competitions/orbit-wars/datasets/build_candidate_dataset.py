"""Candidate-level dataset with FlightOracle safety/first-hit labels + teacher labels.

One row per (episode, step, player, candidate launch). Candidate = a my-planet -> non-mine
target launch; labeled by the FlightOracle (valid / eta / first-hit type / min-sun), by
core.state/features, by whether the teacher (the real player) actually launched it that step,
and by the future score delta (h20/h50) + terminal outcome. NOT a BC direct-policy clone — it
supports candidate scoring / value modeling / safety, per the task's anti-BC constraint.

  python build_candidate_dataset.py --replay-root <dir> --out-root <dir> [--use-flight-oracle] [--step-stride 10]

Full corpus -> snorlax (see datasets/README.md). Here: small fixture smoke.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
if COMP not in sys.path:
    sys.path.insert(0, COMP)

from _replay import iter_replays, parse_meta, board_at, action_at  # noqa: E402
from core.state import build_battlefield_state  # noqa: E402
from core.features import candidate_features  # noqa: E402
from core.oracle import FlightOracle  # noqa: E402

SHIP_BUCKETS = [(0, 20), (20, 50), (50, 120), (120, 10**9)]


def _bucket(n):
    for i, (lo, hi) in enumerate(SHIP_BUCKETS):
        if lo <= n < hi:
            return i
    return len(SHIP_BUCKETS) - 1


def _player_score_at(replay, t, seat, horizon=20):
    b = board_at(replay, t, seat=seat)
    if b is None:
        return None
    try:
        st = build_battlefield_state(b, horizon=horizon)
    except Exception:
        return None
    ps = st.players.get(seat)
    return ps.score_now if ps else None


def build(replay_root, out_root, use_oracle=True, stride=10, horizon=40, max_per_step=40, shard=None):
    """shard = (i, n): process only replays whose index %% n == i, writing candidates.shard{i}.jsonl
    (lets N processes build disjoint slices in parallel; concat the shards afterwards)."""
    os.makedirs(out_root, exist_ok=True)
    if shard is not None:
        out = os.path.join(out_root, f"candidates.shard{shard[0]}.jsonl")
    else:
        out = os.path.join(out_root, "candidates.jsonl")
    orc = FlightOracle()
    n = 0
    with open(out, "w") as fout:
        for ridx, (path, replay) in enumerate(iter_replays(replay_root)):
            if shard is not None and ridx % shard[1] != shard[0]:
                continue
            meta = parse_meta(path, replay)
            if meta.get("malformed"):
                continue
            ns = meta["num_steps"]
            rewards = meta["rewards"] or []
            winner_seat = meta.get("winner_seat")
            for t in range(0, ns, stride):
                board = board_at(replay, t, seat=0)
                if board is None:
                    continue
                for seat in range(meta["player_count"]):
                    pb = dict(board)
                    pb["player"] = seat
                    try:
                        st = build_battlefield_state(pb, horizon=horizon)
                    except Exception:
                        continue
                    mine = [p for p in st.planets.values() if p.owner == seat]
                    targets = [p for p in st.planets.values() if p.owner != seat]
                    if not mine or not targets:
                        continue
                    # teacher: decode the seat's actual launches this step -> first-hit targets
                    teacher = {}
                    for mv in action_at(replay, t, seat):
                        if not (isinstance(mv, list) and len(mv) == 3):
                            continue
                        src_id, ang, sh = int(mv[0]), float(mv[1]), int(mv[2])
                        fr = orc.first_hit(pb, src_id, ang, sh) if use_oracle else None
                        if fr and fr.first_hit_id is not None:
                            teacher[(src_id, fr.first_hit_id)] = sh
                    # future value delta for this seat
                    sc_now = st.players[seat].score_now if seat in st.players else 0.0
                    sc20 = _player_score_at(replay, t + 20, seat) if t + 20 < ns else None
                    sc50 = _player_score_at(replay, t + 50, seat) if t + 50 < ns else None
                    term = rewards[seat] if seat < len(rewards) else None
                    emitted = 0
                    for src in mine:
                        for tgt in targets:
                            if emitted >= max_per_step:
                                break
                            ships = max(1, int(src.ships) // 2 + 1)
                            cand = {"source": src.id, "target": tgt.id, "ships": ships}
                            feat = candidate_features(st, cand, pb, orc) if use_oracle else {}
                            sel = teacher.get((src.id, tgt.id))
                            row = {
                                "episode_id": meta["episode_id"],
                                "step": t,
                                "player_id": seat,
                                "source_planet_id": src.id,
                                "target_object_id": tgt.id,
                                "target_type": (
                                    "comet" if tgt.is_comet else "enemy" if tgt.owner not in (-1, seat) else "neutral"
                                ),
                                "ship_bucket": _bucket(ships),
                                "oracle_valid": feat.get("path_valid"),
                                "oracle_eta": feat.get("path_eta"),
                                "oracle_first_hit_type": feat.get("path_first_hit_type"),
                                "oracle_first_hit_id": feat.get("path_first_hit_id"),
                                "min_sun_distance": feat.get("path_min_sun_distance"),
                                "candidate_features_json": feat,
                                "seat_is_winner": int(winner_seat == seat),
                                "teacher_selected": int(sel is not None),
                                "teacher_ship_fraction": (
                                    round(sel / (src.ships + 1e-9), 3) if sel is not None else None
                                ),
                                "future_value_delta_h20": (round(sc20 - sc_now, 1) if sc20 is not None else None),
                                "future_value_delta_h50": (round(sc50 - sc_now, 1) if sc50 is not None else None),
                                "terminal_outcome": term,
                            }
                            fout.write(json.dumps(row) + "\n")
                            n += 1
                            emitted += 1
    print(f"candidates: {n} rows -> {out}")
    return n


def main():
    ap = argparse.ArgumentParser(description="Build candidate-level dataset with FlightOracle labels.")
    ap.add_argument("--replay-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--use-flight-oracle", action="store_true", default=True)
    ap.add_argument("--no-flight-oracle", dest="use_flight_oracle", action="store_false")
    ap.add_argument("--step-stride", type=int, default=10)
    ap.add_argument("--horizon", type=int, default=40)
    ap.add_argument("--max-per-step", type=int, default=40)
    ap.add_argument("--shard", default=None, help="i/n: process only replays with index %% n == i (parallel build)")
    args = ap.parse_args()
    shard = None
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        shard = (i, n)
    build(
        args.replay_root,
        args.out_root,
        args.use_flight_oracle,
        args.step_stride,
        args.horizon,
        args.max_per_step,
        shard,
    )


if __name__ == "__main__":
    main()
