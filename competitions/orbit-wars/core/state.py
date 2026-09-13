"""BattlefieldState — typed, deterministic battlefield awareness for rules + models.

Builds PlanetState / FleetState / PlayerState / GlobalState from a raw observation, using
the engine-verified ledger (projected owner/ships over a horizon) and the FlightOracle
(fleet first-hit decode). Every derived field is deterministic and explainable; the
strategic-value 1..100 is decomposable (its components are returned for debug dumps).

Fields that need information not in a single observation are set to a neutral default
and noted in `discussions/2026-06-16-battlefield-state-schema.md` (see "approximations").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import geometry as G
from .ledger import build_ledger
from .oracle import FlightOracle


@dataclass
class PlanetState:
    id: int
    owner: int
    x: float
    y: float
    radius: float
    ships: float
    production: int
    orbital_radius: float
    is_orbiting: bool
    # derived
    strategic_value_1_100: int = 1
    value_components: dict = field(default_factory=dict)
    roi_value: float = 0.0
    holdability: float = 0.0
    frontier_score: float = 0.0
    pressure_score: float = 0.0
    centrality: float = 0.0
    nearest_enemy_eta: float | None = None
    nearest_friendly_eta: float | None = None
    my_inbound: list = field(default_factory=list)
    enemy_inbound: list = field(default_factory=list)
    projected_owner: list = field(default_factory=list)
    projected_ships: list = field(default_factory=list)
    threat_window: int | None = None
    reinforcement_need: float = 0.0
    defense_slack: float = 0.0
    is_hub_candidate: bool = False
    is_frontline: bool = False
    is_safe_bank: bool = False
    is_comet: bool = False
    expires_in_if_comet: int | None = None


@dataclass
class FleetState:
    id: int
    owner: int
    x: float
    y: float
    angle: float
    ships: float
    speed: float
    source_planet_id: int
    decoded_first_hit_id: int | None = None
    decoded_target_type: str = "unknown"
    eta: int | None = None
    min_sun_distance: float | None = None
    path_safety: str = "unknown"  # ok | near_sun | sun | oob | none
    is_attack: bool = False
    is_reinforcement: bool = False
    is_expansion: bool = False
    is_hub_transfer: bool = False


@dataclass
class PlayerState:
    player_id: int
    planet_count: int = 0
    production_total: int = 0
    ships_on_planets: float = 0.0
    ships_in_flight: float = 0.0
    fleet_count: int = 0
    frontier_planets: int = 0
    hub_planets: int = 0
    safe_bank_ships: float = 0.0
    threatened_planets: int = 0
    attack_pressure: float = 0.0
    reinforcement_capacity: float = 0.0
    score_now: float = 0.0
    score_projected_H: float = 0.0
    rank_by_score: int = 0
    rank_by_production: int = 0
    leader_gap: float = 0.0
    elimination_risk: float = 0.0
    dogpile_risk: float = 0.0


@dataclass
class GlobalState:
    step: int
    remaining_steps: int
    player_count: int
    alive_players: list
    phase: str
    my_id: int
    leader_id: int | None
    nearest_enemy_id: int | None
    strongest_enemy_id: int | None
    weakest_enemy_id: int | None


@dataclass
class BattlefieldState:
    planets: dict  # pid -> PlanetState
    fleets: dict  # fid -> FleetState
    players: dict  # player_id -> PlayerState
    glob: GlobalState
    ledger: object


def _phase(step, total):
    f = step / max(1, total)
    return "opening" if f < 0.16 else ("midgame" if f < 0.6 else "endgame")


def _strategic_value(p_owner, prod, capture_cost, holdability, frontier, centrality, pressure):
    """Explainable, deterministic, bounded [1,100], decomposable.
    Weighted blend of normalized components; returns (value, components)."""
    roi = prod / (1.0 + max(0.0, capture_cost) / 20.0)  # production per (scaled) cost
    comp = {
        "prod_roi": min(1.0, roi / 5.0),  # prod in [1,5]
        "holdability": max(0.0, min(1.0, holdability)),
        "frontier_leverage": max(0.0, min(1.0, frontier)),
        "centrality_hubness": max(0.0, min(1.0, centrality)),
        "enemy_pressure": max(0.0, min(1.0, pressure)),
    }
    # pressure is a risk: high pressure reduces value unless we hold it
    score01 = (
        0.34 * comp["prod_roi"]
        + 0.24 * comp["holdability"]
        + 0.18 * comp["frontier_leverage"]
        + 0.14 * comp["centrality_hubness"]
        - 0.10 * comp["enemy_pressure"]
    )
    score01 = max(0.0, min(1.0, score01))
    return int(round(1 + 99 * score01)), comp


def build_battlefield_state(obs, horizon=80) -> BattlefieldState:
    planets_raw = [tuple(p) for p in obs.get("planets", [])]
    fleets_raw = [tuple(f) for f in obs.get("fleets", [])]
    init_by_id = {p[0]: tuple(p) for p in obs.get("initial_planets", [])}
    step = int(obs.get("step", 0))
    comet_ids = set(obs.get("comet_planet_ids", []) or [])
    me = obs.get("player", 0)
    led = build_ledger(obs, horizon=horizon)
    by_id = {p[0]: p for p in planets_raw}
    owners = sorted({p[1] for p in planets_raw if p[1] != -1})
    player_ids = sorted(set(owners) | {me})

    # --- planets ---
    pstates = {}
    for p in planets_raw:
        pid, owner, x, y, r, ships, prod = p
        orb = G.orbital_radius(init_by_id.get(pid, p)[2], init_by_id.get(pid, p)[3])
        orbiting = G.is_orbiting(init_by_id.get(pid, p)[2], init_by_id.get(pid, p)[3], r)
        # nearest enemy/friendly source ETA (rough: distance / speed of a token fleet)
        ne, nf = None, None
        for q in planets_raw:
            if q[0] == pid:
                continue
            d = math.hypot(q[2] - x, q[3] - y)
            eta = d / G.fleet_speed(max(1, int(q[5])))
            if q[1] == me:
                nf = eta if nf is None else min(nf, eta)
            elif q[1] != -1:
                ne = eta if ne is None else min(ne, eta)
        my_in = led.my_inbound(pid)
        en_in = led.enemy_inbound(pid)
        pow_ = led.projected_owner(pid)
        psh = led.projected_ships(pid)
        tw = led.threat_window(pid)
        slack = led.defense_slack(pid)
        # derived scores in [0,1]
        frontier = 1.0 / (1.0 + (ne if ne is not None else 50.0) / 10.0)
        centrality = 1.0 - min(1.0, orb / G.ROT_LIMIT)
        pressure = min(1.0, sum(en_in) / (ships + prod * 10 + 1.0))
        holdability = (
            1.0
            if (owner == me and tw is None)
            else (slack / (ships + 1.0) if owner == me else 1.0 / (1.0 + (ne or 50) / 20.0))
        )
        capture_cost = psh[min(int(ne or 1), len(psh) - 1)] if owner != me and psh else ships
        sv, comp = _strategic_value(owner, prod, capture_cost, holdability, frontier, centrality, pressure)
        pstates[pid] = PlanetState(
            id=pid,
            owner=owner,
            x=x,
            y=y,
            radius=r,
            ships=float(ships),
            production=prod,
            orbital_radius=orb,
            is_orbiting=orbiting,
            strategic_value_1_100=sv,
            value_components=comp,
            roi_value=prod / (1.0 + max(0.0, capture_cost) / 20.0),
            holdability=holdability,
            frontier_score=frontier,
            pressure_score=pressure,
            centrality=centrality,
            nearest_enemy_eta=ne,
            nearest_friendly_eta=nf,
            my_inbound=my_in,
            enemy_inbound=en_in,
            projected_owner=pow_,
            projected_ships=psh,
            threat_window=tw,
            reinforcement_need=led.reinforcement_need(pid),
            defense_slack=slack,
            is_hub_candidate=(owner == me and orbiting and centrality > 0.4 and slack > prod * 5),
            is_frontline=(owner == me and ne is not None and ne < 20),
            is_safe_bank=(owner == me and ne is not None and ne > 35 and tw is None),
            is_comet=(pid in comet_ids),
            expires_in_if_comet=None,  # blocker: comet path/expiry not modelled (see schema doc)
        )

    # --- fleets (FlightOracle decode of in-flight fleets' first hit) ---
    orc = FlightOracle()
    fstates = {}
    for f in fleets_raw:
        fid, fowner, fx, fy, fang, ffrom, fships = f
        # decode by tracing from the fleet's CURRENT (fx, fy) along its angle — NOT by relaunching
        # from the source planet (which restarts at source_radius+0.1 and mis-predicts an in-flight
        # fleet's first hit / ETA). Works even if the source planet has since been captured/gone.
        res = orc.decode_existing_fleet(obs, f)
        decoded_id, dtype, eta = res.first_hit_id, res.first_hit_type, res.eta
        minsun = res.min_sun_distance
        safety = (
            "sun"
            if dtype == "sun"
            else "oob"
            if dtype == "oob"
            else "near_sun"
            if res.near_sun
            else "none"
            if dtype == "none"
            else "ok"
        )
        tgt_owner = by_id.get(decoded_id, (None, None))[1] if decoded_id is not None else None
        fstates[fid] = FleetState(
            id=fid,
            owner=fowner,
            x=fx,
            y=fy,
            angle=fang,
            ships=float(fships),
            speed=G.fleet_speed(int(fships)),
            source_planet_id=ffrom,
            decoded_first_hit_id=decoded_id,
            decoded_target_type=dtype,
            eta=eta,
            min_sun_distance=minsun,
            path_safety=safety,
            is_attack=(fowner == me and tgt_owner not in (me, None)),
            is_reinforcement=(fowner == me and tgt_owner == me),
            is_expansion=(fowner == me and tgt_owner == -1),
            is_hub_transfer=False,  # set by higher layer when staging is modelled
        )

    # --- players ---
    scores = {}
    for pl in player_ids:
        own = [p for p in planets_raw if p[1] == pl]
        infl = [f for f in fleets_raw if f[1] == pl]
        thr = sum(1 for ps in pstates.values() if ps.owner == pl and ps.threat_window is not None)
        score_now = sum(p[5] for p in own) + sum(f[6] for f in infl)
        scores[pl] = score_now
    leader = max(scores, key=scores.get) if scores else None
    prod_rank = sorted(player_ids, key=lambda pl: -sum(p[6] for p in planets_raw if p[1] == pl))
    score_rank = sorted(player_ids, key=lambda pl: -scores.get(pl, 0))
    players = {}
    for pl in player_ids:
        own = [p for p in planets_raw if p[1] == pl]
        infl = [f for f in fleets_raw if f[1] == pl]
        players[pl] = PlayerState(
            player_id=pl,
            planet_count=len(own),
            production_total=sum(p[6] for p in own),
            ships_on_planets=sum(p[5] for p in own),
            ships_in_flight=sum(f[6] for f in infl),
            fleet_count=len(infl),
            frontier_planets=sum(1 for ps in pstates.values() if ps.owner == pl and ps.is_frontline),
            hub_planets=sum(1 for ps in pstates.values() if ps.owner == pl and ps.is_hub_candidate),
            safe_bank_ships=sum(ps.ships for ps in pstates.values() if ps.owner == pl and ps.is_safe_bank),
            threatened_planets=sum(1 for ps in pstates.values() if ps.owner == pl and ps.threat_window is not None),
            attack_pressure=sum(f[6] for f in infl),
            reinforcement_capacity=sum(ps.defense_slack for ps in pstates.values() if ps.owner == pl),
            score_now=scores.get(pl, 0.0),
            score_projected_H=sum(
                (ps.projected_ships[-1] if ps.projected_owner and ps.projected_owner[-1] == pl else 0)
                for ps in pstates.values()
            ),
            rank_by_score=score_rank.index(pl) + 1,
            rank_by_production=prod_rank.index(pl) + 1,
            leader_gap=(scores.get(leader, 0) - scores.get(pl, 0)) if leader is not None else 0.0,
            elimination_risk=(1.0 if len(own) == 0 else min(1.0, thr / max(1, len(own)))),
            dogpile_risk=(min(1.0, (len(player_ids) - 1) / 3.0) if pl == leader and len(player_ids) > 2 else 0.0),
        )

    alive = [pl for pl in player_ids if players[pl].planet_count > 0 or players[pl].fleet_count > 0]
    enemies = [pl for pl in player_ids if pl != me]
    glob = GlobalState(
        step=step,
        remaining_steps=max(0, G.EPISODE_STEPS - step),
        player_count=len(player_ids),
        alive_players=alive,
        phase=_phase(step, G.EPISODE_STEPS),
        my_id=me,
        leader_id=leader,
        nearest_enemy_id=min(enemies, key=lambda e: players[e].score_now) if enemies else None,
        strongest_enemy_id=max(enemies, key=lambda e: players[e].score_now) if enemies else None,
        weakest_enemy_id=min(enemies, key=lambda e: players[e].score_now) if enemies else None,
    )
    return BattlefieldState(planets=pstates, fleets=fstates, players=players, glob=glob, ledger=led)
