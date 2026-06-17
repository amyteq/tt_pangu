"""ArrivalLedger / ThreatLedger — projected per-planet owner/ships over a horizon.

Built on the engine-verified do-nothing projection (`geometry.project`): for horizon H
it gives, per planet and turn k, the projected owner + ships assuming nobody launches
anything new, plus the arrival schedule (which fleets land where/when). From that it
derives the threat window (when an owned planet flips), reinforcement need, and a
source's safe defense slack (max ships sheddable while the source stays held over H).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import geometry as G


@dataclass
class ArrivalLedger:
    horizon: int
    me: int
    traj: dict  # pid -> {"owner":[H+1], "ships":[H+1]}
    arrivals: dict  # pid -> [(k, owner, ships)]
    _owner0: dict = field(default_factory=dict)
    _ships0: dict = field(default_factory=dict)
    _prod: dict = field(default_factory=dict)

    def projected_owner(self, pid):
        return self.traj.get(pid, {}).get("owner", [])

    def projected_ships(self, pid):
        return self.traj.get(pid, {}).get("ships", [])

    def my_inbound(self, pid):
        """Per-turn ships arriving for ME at pid over the horizon: [H+1] list."""
        out = [0.0] * (self.horizon + 1)
        for k, o, s in self.arrivals.get(pid, []):
            if o == self.me and 0 <= k <= self.horizon:
                out[k] += s
        return out

    def enemy_inbound(self, pid):
        out = [0.0] * (self.horizon + 1)
        for k, o, s in self.arrivals.get(pid, []):
            if o != self.me and o != -1 and 0 <= k <= self.horizon:
                out[k] += s
        return out

    def threat_window(self, pid):
        """First turn k in 1..H at which a currently-MINE planet is projected to flip
        away from me; None if it holds the whole horizon (or isn't mine now)."""
        ow = self.projected_owner(pid)
        if not ow or ow[0] != self.me:
            return None
        for k in range(1, len(ow)):
            if ow[k] != self.me:
                return k
        return None

    def reinforcement_need(self, pid):
        """Min extra ships (rough) to keep pid mine through H: the largest projected
        enemy-arrival deficit. 0 if it already holds."""
        tw = self.threat_window(pid)
        if tw is None:
            return 0.0
        sh = self.projected_ships(pid)
        # ships just before the flip turn + that turn's enemy inbound
        pre = sh[tw - 1] if tw - 1 < len(sh) else 0.0
        ein = self.enemy_inbound(pid)[tw] if tw < len(self.enemy_inbound(pid)) else 0.0
        return max(0.0, ein - pre + 1.0)

    def defense_slack(self, pid):
        """Max ships a SOURCE can shed now while staying held (owner==me) every turn
        over H — the safe_drain bound. If it doesn't hold anyway, it can shed all."""
        ow = self.projected_owner(pid)
        sh = self.projected_ships(pid)
        if not ow or ow[0] != self.me:
            return 0.0
        # worst held-turn garrison; if it flips, the held-prefix minimum
        worst = sh[0]
        for k in range(1, len(ow)):
            if ow[k] != self.me:
                break
            worst = min(worst, sh[k])
        return max(0.0, worst)


def build_ledger(obs, horizon=80):
    planets = [tuple(p) for p in obs.get("planets", [])]
    fleets = [tuple(f) for f in obs.get("fleets", [])]
    init_by_id = {p[0]: tuple(p) for p in obs.get("initial_planets", [])}
    ang_vel = obs.get("angular_velocity", 0.0)
    step = int(obs.get("step", 0))
    comet_ids = set(obs.get("comet_planet_ids", []) or [])
    me = obs.get("player", 0)
    traj, arrivals = G.project(planets, fleets, ang_vel, init_by_id, step, horizon, comet_ids)
    led = ArrivalLedger(horizon=horizon, me=me, traj=traj, arrivals=arrivals)
    led._owner0 = {p[0]: p[1] for p in planets}
    led._ships0 = {p[0]: float(p[5]) for p in planets}
    led._prod = {p[0]: p[6] for p in planets}
    return led
