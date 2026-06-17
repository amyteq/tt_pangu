"""Phase 0 — three offline probes that decide whether the integrated opening planner
is worth building (designs/2026-06-16-opening-planner-scope.md). Zero agent change,
zero ladder cost. Reuses v4's exact _solve_intercept/_path_blocked and forecast_sim.

  P1 super-additivity : does a SET+ORDER search (captured-planet feedback, budget-
                        respecting) beat the GREEDY selection on controlled-production
                        at the opening horizon Ho?  KILL if median gain < 5%.
  P2 objective-divergence : does ranking grabs by controlled-production pick different
                        first-3 targets than the conservation-terminal (_term) greedy?
                        KILL if mean agreement > 80% (objective colinear).
  P3 conversion       : does our board-control at step 80 predict the terminal win
                        over logged games?  KILL if |point-biserial r| < 0.2.

Usage:
  python arena/opening_probes.py --selftest
  python arena/opening_probes.py --games 40 --procs 20
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMP = os.path.normpath(os.path.join(HERE, ".."))
V = os.path.join(COMP, "agent", "versions")
sys.path.insert(0, V)
# opponent (gitignored in this worktree) — fall back to the main checkout
MAIN_V = os.path.expanduser("~/test/tt_pangu/competitions/orbit-wars/agent/versions")
EVO = os.path.join(V, "suite", "evogen1093.py")
if not os.path.exists(EVO):
    EVO = os.path.join(MAIN_V, "suite", "evogen1093.py")
V4 = os.path.join(V, "v4.py")

import forecast_sim as fs  # noqa: E402
import v4 as v4mod  # noqa: E402  (module-level _solve_intercept/_predict_pos/_path_blocked)

try:
    from kaggle_environments.envs.orbit_wars.orbit_wars import Planet  # noqa: E402
except Exception:
    from collections import namedtuple

    Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])

GAMMA = 0.97
HO = 60  # opening control horizon
OPEN_STEPS = (20, 40)  # states for P1/P2
CTRL_STEP = 80  # state for P3


# ---------- board helpers ----------
def _obs_tuples(obs):
    planets = [Planet(*p) for p in obs["planets"]]  # namedtuples (.id/.x… AND indexable)
    fleets = [tuple(f) for f in obs.get("fleets", [])]
    init_by_id = {p[0]: tuple(p) for p in obs["initial_planets"]}
    return (
        planets,
        fleets,
        init_by_id,
        obs["angular_velocity"],
        int(obs["step"]),
        set(obs.get("comet_planet_ids", []) or []),
    )


def _controlled_production(owner_by_pid, prod_by_pid, me):
    """Σ_k γ^k Σ_p prod_p·[owner_k==me] over the trajectories (each owner list len Ho+1)."""
    total = 0.0
    g = 1.0
    for k in range(1, HO + 1):
        g *= GAMMA
        s = 0.0
        for pid, o in owner_by_pid.items():
            if o[k] == me:
                s += prod_by_pid[pid]
        total += g * s
    return total


def _candidate_grabs(planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj):
    """Reachable NEUTRAL grabs from our sources: best (min-eta) source per neutral,
    sized to the projected defender+1. Returns list of dicts."""
    mine = [p for p in planets if p[1] == me]
    neutrals = [p for p in planets if p[1] == -1 and p[0] not in comet_ids]
    cands = []
    for tgt in neutrals:
        best = None
        for src in mine:
            ships_guess = max(1, int(tgt[5]) + 1)
            sol = None
            needed = ships_guess
            eta_k = 1
            for _ in range(3):
                sol = v4mod._solve_intercept(src[2], src[3], tgt[0], ships_guess, step, init_by_id, ang_vel)
                if sol is None:
                    break
                _, t_ticks, _ = sol
                eta_k = max(1, min(int(t_ticks), HO))
                bt = base_traj.get(tgt[0])
                defender = bt["ships"][eta_k] if bt is not None else tgt[5]
                needed = int(defender) + 1
                if needed == ships_guess:
                    break
                ships_guess = needed
            if sol is None:
                continue
            angle, t_ticks, pos = sol
            if t_ticks > HO:
                continue
            if v4mod._path_blocked(src[2], src[3], pos[0], pos[1], src[0], tgt[0], planets, comet_ids):
                continue
            if best is None or eta_k < best["eta"]:
                best = {
                    "tgt": tgt[0],
                    "src": src[0],
                    "ships": int(needed),
                    "eta": eta_k,
                    "angle": angle,
                    "prod": tgt[6],
                }
        if best is not None:
            cands.append(best)
    return cands


def _eval_plan(plan, planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr):
    """Controlled-production at Ho for executing `plan` (list of grab dicts), evaluated
    jointly: debit each source, add each target's arrival, replay touched planets, use
    base trajectory for the rest."""
    owner0 = {p[0]: p[1] for p in planets}
    ships0 = {p[0]: float(p[5]) for p in planets}
    prod = {p[0]: p[6] for p in planets}
    debit = {}
    arr_add = {}
    for g in plan:
        debit[g["src"]] = debit.get(g["src"], 0.0) + g["ships"]
        arr_add.setdefault(g["tgt"], []).append((g["eta"], me, float(g["ships"])))
    touched = set(debit) | set(arr_add)
    owner_by = {}
    for pid in base_traj:
        if pid in touched:
            arrs = list(base_arr.get(pid, []))
            arrs += arr_add.get(pid, [])
            o, _s = fs.replay_planet(owner0[pid], ships0[pid] - debit.get(pid, 0.0), prod[pid], arrs, HO)
            owner_by[pid] = o
        else:
            owner_by[pid] = base_traj[pid]["owner"]
    return _controlled_production(owner_by, prod, me)


def _term_value(grab, planets, init_by_id, me, base_traj, base_arr):
    """The v4 conservation-terminal differential value of a single grab (k=HO net-ship,
    +mine -enemy, source debited + target arrival vs do-nothing baseline)."""
    owner0 = {p[0]: p[1] for p in planets}
    ships0 = {p[0]: float(p[5]) for p in planets}
    prod = {p[0]: p[6] for p in planets}

    def term(o, s):
        k = HO
        return s[k] if o[k] == me else (-s[k] if o[k] != -1 else 0.0)

    def base_adv(pid):
        bt = base_traj[pid]
        return term(bt["owner"], bt["ships"])

    so, ss = fs.replay_planet(
        owner0[grab["src"]], ships0[grab["src"]] - grab["ships"], prod[grab["src"]], base_arr.get(grab["src"], []), HO
    )
    tarr = list(base_arr.get(grab["tgt"], [])) + [(grab["eta"], me, float(grab["ships"]))]
    to, ts = fs.replay_planet(owner0[grab["tgt"]], ships0[grab["tgt"]], prod[grab["tgt"]], tarr, HO)
    return (term(so, ss) + term(to, ts)) - (base_adv(grab["src"]) + base_adv(grab["tgt"]))


def _greedy_select(cands, planets, me, key):
    """v4-style: rank by `key`, take non-conflicting (each source budget, each target once)."""
    ships_avail = {p[0]: float(p[5]) for p in planets if p[1] == me}
    ranked = sorted(cands, key=key, reverse=True)
    sel = []
    for g in ranked:
        if g["ships"] <= ships_avail.get(g["src"], 0):
            sel.append(g)
            ships_avail[g["src"]] -= g["ships"]
    return sel


def _search_best(
    cands, planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr, depth=3, beam=6
):
    """Beam search over SET+ORDER of grabs (budget-respecting), maximizing controlled
    production. Captured-planet feedback is implicit in the joint replay (a held target
    contributes its production; source contention is enforced by the ship budget)."""
    ships_avail0 = {p[0]: float(p[5]) for p in planets if p[1] == me}
    # state: (plan_list, remaining_avail dict, cp)
    init = (
        [],
        dict(ships_avail0),
        _eval_plan([], planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr),
    )
    frontier = [init]
    best = init
    for _d in range(depth):
        nxt = []
        for plan, avail, _cp in frontier:
            used_t = {g["tgt"] for g in plan}
            for g in cands:
                if g["tgt"] in used_t or g["ships"] > avail.get(g["src"], 0):
                    continue
                np_ = plan + [g]
                na = dict(avail)
                na[g["src"]] -= g["ships"]
                cp = _eval_plan(np_, planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr)
                nxt.append((np_, na, cp))
                if cp > best[2]:
                    best = (np_, na, cp)
        if not nxt:
            break
        nxt.sort(key=lambda x: x[2], reverse=True)
        frontier = nxt[:beam]
    return best


# ---------- data generation ----------
def _run_game(seed, opp):
    from kaggle_environments import make

    env = make("orbit_wars", configuration={"seed": seed})
    env.run([V4, opp])
    steps = env.steps
    rew = [s["reward"] for s in steps[-1]]
    rec = {"seed": seed, "reward0": rew[0], "reward1": rew[1], "n": len(steps)}
    for tag, st in (("s20", 20), ("s40", 40), ("s80", CTRL_STEP)):
        idx = st if st < len(steps) else len(steps) - 1
        rec[tag] = steps[idx][0]["observation"]
    return rec


def _gen(seeds, opp, procs):
    from multiprocessing import Pool

    with Pool(procs) as p:
        return p.starmap(_run_game, [(s, opp) for s in seeds])


# ---------- probes ----------
def _state_probe(obs, me=0):
    planets, fleets, init_by_id, ang_vel, step, comet_ids = _obs_tuples(obs)
    base_traj, base_arr = fs.project(planets, fleets, ang_vel, init_by_id, step, HO, comet_ids=comet_ids)
    cands = _candidate_grabs(planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj)
    if len(cands) < 2:
        return None
    cp_indep = {
        g["tgt"]: _eval_plan([g], planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr)
        - _eval_plan([], planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr)
        for g in cands
    }
    greedy_sel = _greedy_select(cands, planets, me, key=lambda g: cp_indep[g["tgt"]])
    cp_greedy = _eval_plan(greedy_sel, planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr)
    _plan, _av, cp_search = _search_best(
        cands, planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr
    )
    super_add = (cp_search - cp_greedy) / cp_greedy if cp_greedy > 1e-9 else 0.0
    # P2: first-3 by CP vs by conservation _term
    by_cp = [g["tgt"] for g in sorted(cands, key=lambda g: cp_indep[g["tgt"]], reverse=True)[:3]]
    tvals = {g["tgt"]: _term_value(g, planets, init_by_id, me, base_traj, base_arr) for g in cands}
    by_term = [g["tgt"] for g in sorted(cands, key=lambda g: tvals[g["tgt"]], reverse=True)[:3]]
    agree = len(set(by_cp) & set(by_term)) / max(1, len(by_cp))
    # P1b: CP of v4's ACTUAL conservation-greedy selection (value>0 gated) vs CP-search-optimal —
    # does a CP-planner control MORE production at Ho than what v4 currently picks?
    consv_sel = _greedy_select([g for g in cands if tvals[g["tgt"]] > 0], planets, me, key=lambda g: tvals[g["tgt"]])
    cp_consv = _eval_plan(consv_sel, planets, fleets, init_by_id, ang_vel, step, comet_ids, me, base_traj, base_arr)
    super_consv = (cp_search - cp_consv) / cp_consv if cp_consv > 1e-9 else 0.0
    return {
        "super_add": super_add,
        "super_consv": super_consv,
        "agree": agree,
        "ncand": len(cands),
        "n_consv": len(consv_sel),
        "n_search": 0,
        "cp_greedy": cp_greedy,
        "cp_search": cp_search,
        "cp_consv": cp_consv,
    }


def _board_control(obs, me=0):
    planets = obs["planets"]
    return sum(p[6] for p in planets if p[1] == me), sum(1 for p in planets if p[1] == me)


def _point_biserial(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    my = sum(ys) / n
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    if sx < 1e-9 or sy < 1e-9:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    return cov / (sx * sy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--starter-games", type=int, default=20)
    ap.add_argument("--procs", type=int, default=20)
    ap.add_argument("--seed0", type=int, default=50000)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        recs = _gen([args.seed0, args.seed0 + 1], EVO, 2)
        print("selftest games:", [(r["seed"], r["reward0"], r["n"]) for r in recs])
        for r in recs:
            for tag in ("s20", "s40"):
                pr = _state_probe(r[tag])
                print(f"  {r['seed']} {tag}: {pr}")
        return

    evo = _gen(list(range(args.seed0, args.seed0 + args.games)), EVO, args.procs)
    sta = _gen(list(range(args.seed0, args.seed0 + args.starter_games)), "starter", args.procs)
    print(
        f"games: evogen={len(evo)} (won {sum(1 for r in evo if r['reward0'] > r['reward1'])}), "
        f"starter={len(sta)} (won {sum(1 for r in sta if r['reward0'] > r['reward1'])})",
        flush=True,
    )

    # P1 + P2 over opening states (evogen games)
    sadds, sconsv, agrees = [], [], []
    for r in evo:
        for tag in ("s20", "s40"):
            pr = _state_probe(r[tag])
            if pr:
                sadds.append(pr["super_add"])
                sconsv.append(pr["super_consv"])
                agrees.append(pr["agree"])
    sadds.sort()
    sconsv.sort()
    med_sa = sadds[len(sadds) // 2] if sadds else 0.0
    med_sc = sconsv[len(sconsv) // 2] if sconsv else 0.0
    mean_ag = sum(agrees) / len(agrees) if agrees else 1.0
    print(
        f"\nP1 super-additivity: n={len(sadds)} states | median Δ(CP-search vs CP-greedy)={med_sa * 100:+.1f}% "
        f"| frac>5%={sum(1 for x in sadds if x > 0.05) / max(1, len(sadds)) * 100:.0f}%"
    )
    print(
        f"   P1b Δ(CP-search vs v4 conservation-greedy)={med_sc * 100:+.1f}% (does a CP-planner control MORE @Ho than v4 picks?)"
    )
    print(
        f"   VERDICT: {'KILL (search ≈ greedy → set+order planner redundant)' if med_sa < 0.05 else 'PASS (search beats greedy ≥5%)'}"
    )
    print(
        f"\nP2 objective-divergence: n={len(agrees)} states | mean first-3 agreement(CP vs _term)={mean_ag * 100:.0f}%"
    )
    print(
        f"   VERDICT: {'KILL (objectives colinear → OW_OPENING-with-a-sort)' if mean_ag > 0.80 else 'PASS (CP ranks differently)'}"
    )

    # P3 conversion over all games: board-control@80 vs win
    xs, ys = [], []
    for r in evo + sta:
        prodc, _cnt = _board_control(r["s80"])
        xs.append(prodc)
        ys.append(1.0 if r["reward0"] > r["reward1"] else 0.0)
    # evogen-only (the discriminating tier)
    xe, ye = [], []
    for r in evo:
        prodc, _cnt = _board_control(r["s80"])
        xe.append(prodc)
        ye.append(1.0 if r["reward0"] > r["reward1"] else 0.0)
    r_all = _point_biserial(xs, ys)
    r_evo = _point_biserial(xe, ye) if len(set(ye)) > 1 else float("nan")
    print(
        f"\nP3 conversion: control@80 vs win | r(all {len(xs)})={r_all:+.2f} | r(evogen {len(xe)})={r_evo:+.2f} "
        f"| evogen wins={int(sum(ye))}/{len(ye)}"
    )
    print(
        f"   VERDICT: {'KILL (control@80 does not predict win)' if abs(r_all) < 0.2 else 'PASS (control@80 predicts win)'}"
    )
    print("\n=== PROBES COMPLETE ===")


if __name__ == "__main__":
    main()
