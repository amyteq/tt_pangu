"""Generate agent/versions/forecast_measure.py — a byte-identical-behavior twin of
forecast.py (v3.2) that, when OW_PATHLOG=1, logs every candidate dropped by the
main-loop _path_blocked check together with its would-be value, block cause
(sun vs planet id), and whether a re-timed clear path exists (the T16 upper
bound). It still `continue`s on block, so committed moves are unchanged — proven
by the identity check in measure_t16.py.
"""

import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "agent", "versions", "forecast.py"))
DST = os.path.normpath(os.path.join(HERE, "..", "agent", "versions", "forecast_measure.py"))

s = io.open(SRC, encoding="utf-8").read()

# 1) module state + helpers, injected right after _predict_pos definition block.
anchor = "def _point_to_segment(px, py, ax, ay, bx, by):"
inject = '''_PATHLOG = _os.environ.get("OW_PATHLOG", "")
_PLOG = []  # list of per-turn dicts (cleared by the runner between games)
_PLOG_TAG = {"opp": "?", "seed": -1}


def _pblock_cause(mx, my, tx, ty, mine_id, tgt_id, planets, comet_ids):
    """Like _path_blocked but returns (blocked, cause) — cause is 'sun' or the
    id of the first non-target planet the straight path clips."""
    if _point_to_segment(CENTER, CENTER, mx, my, tx, ty) < SUN_RADIUS:
        return True, "sun"
    for p in planets:
        if p.id == mine_id or p.id == tgt_id or p.id in comet_ids:
            continue
        if _point_to_segment(p.x, p.y, mx, my, tx, ty) < p.radius + PATH_CLEARANCE:
            return True, p.id
    return False, None


def _retime_clear(mx, my, src_id, tgt, needed, step, init_by_id, ang_vel, planets,
                  comet_ids, base_traj, player):
    """T16 re-aim upper bound: does some arrival turn T' in 1..PROJ_H give a
    sun/planet-clear straight path to tgt's predicted position that arrives
    before the game ends? Returns (geom_clear, useful_clear) where useful also
    requires tgt not already projected ours at T' (still worth taking).

    NOTE src_id MUST be excluded (the path starts at the source planet's center,
    so leaving it in always self-blocks and undercounts recoverable paths)."""
    geom = useful = False
    for tp in range(1, PROJ_H + 1):
        if step + tp > EPISODE_STEPS - 2:
            break
        pos = _predict_pos(tgt.id, step + tp, init_by_id, ang_vel)
        if pos is None:
            continue
        blocked, _c = _pblock_cause(
            mx, my, pos[0], pos[1], src_id, tgt.id, planets, comet_ids
        )
        if blocked:
            continue
        geom = True
        bt = base_traj.get(tgt.id)
        if bt is None or bt["owner"][min(tp, PROJ_H)] != player:
            useful = True
            break
    return geom, useful


def _point_to_segment(px, py, ax, ay, bx, by):'''
assert anchor in s and s.count(anchor) == 1
s = s.replace(anchor, inject, 1)

# 2) per-turn blocked buffer: declare it next to `candidates = []`.
a2 = "    candidates = []\n"
assert s.count(a2) == 1, "candidates init"
s = s.replace(a2, "    candidates = []\n    _blk = []  # T16 measurement buffer\n", 1)

# 3) instrument the main-loop block branch (the ONLY active path-block site in
#    v3.2: OPENING/COARRIVAL/CONSOLIDATE default OFF). Replace the plain
#    `if _path_blocked(...): continue` guarding the value computation.
old_block = """            if _path_blocked(
                mp.x, mp.y, pos[0], pos[1], mp.id, tgt.id, planets, comet_ids
            ):
                continue
            # Value = simulated differential advantage: replay the two touched planets"""
new_block = """            _blocked, _cause = _pblock_cause(
                mp.x, mp.y, pos[0], pos[1], mp.id, tgt.id, planets, comet_ids
            )
            if _blocked:
                if _PATHLOG:
                    _sw_o, _sw_s = _replay(
                        owner0_by_id[mp.id], ships0_by_id[mp.id] - needed,
                        prod_by_id[mp.id], base_arr.get(mp.id, []), PROJ_H,
                    )
                    _tw = base_arr.get(tgt.id, []) + [(eta_k, player, float(needed))]
                    _tw_o, _tw_s = _replay(
                        owner0_by_id[tgt.id], ships0_by_id[tgt.id],
                        prod_by_id[tgt.id], _tw, PROJ_H,
                    )
                    _v = (_term(_sw_o, _sw_s) + _term(_tw_o, _tw_s)) - (
                        base_src_adv + _base_adv(tgt.id)
                    )
                    _g, _u = _retime_clear(
                        mp.x, mp.y, mp.id, tgt, needed, step, init_by_id, ang_vel,
                        planets, comet_ids, base_traj, player,
                    )
                    _blk.append({
                        "src": mp.id, "tgt": tgt.id, "value": round(_v, 2),
                        "needed": int(needed), "eta": int(eta_k),
                        "cause": _cause, "is_def": bool(is_defense),
                        "retime_geom": bool(_g), "retime_useful": bool(_u),
                    })
                continue
            # Value = simulated differential advantage: replay the two touched planets"""
assert s.count(old_block) == 1, "main-loop block branch"
s = s.replace(old_block, new_block, 1)

# 4) push the per-turn record before `return moves` (final return).
old_ret = "\n    return moves\n"
assert s.endswith(old_ret) or ("    return moves\n" in s)
# replace only the LAST occurrence (the real function return)
idx = s.rfind("    return moves")
push = (
    "    if _PATHLOG:\n"
    "        _PLOG.append({\n"
    '            "opp": _PLOG_TAG["opp"], "seed": _PLOG_TAG["seed"],\n'
    '            "player": player, "step": step,\n'
    '            "committed": sorted(committed),\n'
    '            "top_cand": round(max([c[0] for c in candidates], default=0.0), 2),\n'
    '            "n_moves": len(moves), "blocked": _blk,\n'
    "        })\n"
    "    return moves"
)
s = s[:idx] + push + s[idx + len("    return moves") :]

io.open(DST, "w", encoding="utf-8").write(s)
print(f"wrote {DST} ({len(s.splitlines())} lines)")
