"""Find v1's losses vs starter and trace the failure mode."""

import logging, os

logging.disable(logging.INFO)
from kaggle_environments import make

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.normpath(os.path.join(HERE, "..", "agent", "main.py"))


def scores_at(step_state):
    obs = step_state[0]["observation"]
    n = len(step_state)
    planets_s = [0] * n
    fleets_s = [0] * n
    pcount = [0] * n
    for p in obs.get("planets", []):
        if p[1] != -1:
            planets_s[p[1]] += p[5]
            pcount[p[1]] += 1
    for f in obs.get("fleets", []):
        fleets_s[f[1]] += f[6]
    return planets_s, fleets_s, pcount


def trace(agents, seed, v1_seat):
    env = make("orbit_wars", configuration={"seed": seed}, debug=False)
    env.run(agents)
    last = env.steps[-1]
    rewards = [s["reward"] for s in last]
    nsteps = len(env.steps)
    # sample trajectory
    print(f"  seed={seed} v1_seat={v1_seat} ended step {nsteps} rewards={rewards}")
    print(f"  {'step':>4} | {'P0 plan+fleet(#pl)':>22} | {'P1 plan+fleet(#pl)':>22}")
    for st in range(0, nsteps, max(1, nsteps // 12)):
        ps, fs, pc = scores_at(env.steps[st])
        print(f"  {st:>4} | {ps[0]:>6}+{fs[0]:<5}({pc[0]:>2})        | {ps[1]:>6}+{fs[1]:<5}({pc[1]:>2})")
    ps, fs, pc = scores_at(last)
    print(f"  {'END':>4} | {ps[0]:>6}+{fs[0]:<5}({pc[0]:>2})        | {ps[1]:>6}+{fs[1]:<5}({pc[1]:>2})")
    return rewards, nsteps


def main():
    games = 8
    losses = []
    for g in range(games):
        seed = 1000 + g
        # ordering 1: v1 = player 0
        env = make("orbit_wars", configuration={"seed": seed})
        env.run([MAIN, "starter"])
        r = [s["reward"] for s in env.steps[-1]]
        if r[0] < r[1]:
            losses.append((seed, 0, [MAIN, "starter"]))
        # ordering 2: v1 = player 1
        env = make("orbit_wars", configuration={"seed": seed})
        env.run(["starter", MAIN])
        r = [s["reward"] for s in env.steps[-1]]
        if r[1] < r[0]:
            losses.append((seed, 1, ["starter", MAIN]))
    print(f"Found {len(losses)} v1 losses vs starter (P{[(s, seat) for s, seat, _ in losses]})\n")
    for seed, seat, agents in losses:
        print(f"=== LOSS: seed={seed}, v1 is player {seat}, order={['v1' if a == MAIN else a for a in agents]}")
        trace(agents, seed, seat)
        print()


if __name__ == "__main__":
    main()
