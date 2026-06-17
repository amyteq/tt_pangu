"""Parallel arena engine — games are independent, so fan them across CPU cores.

The real `kaggle_environments` engine is pure-Python and CPU-bound; a GPU does not
help. Wall-clock is dominated by running many 500-step games serially, which this
module fixes by mapping games over a process Pool.

Env-var sweeps (OW_*): each task sets os.environ in its worker BEFORE env.run, and
kaggle_environments re-execs the agent file per run (verified: serial sweeps in one
process produced config-dependent results), so per-task config is honored. The
overrides apply process-wide for that game, so the OPPONENT must ignore the swept
keys (e.g. the v1 snapshot reads no env; the v2 snapshot predates the CAP_* knobs).
"""

import logging

logging.disable(logging.INFO)
import os
from multiprocessing import Pool

from kaggle_environments import make


def _final_scores(env):
    obs = env.steps[-1][0]["observation"]
    n = len(env.steps[-1])
    s = [0] * n
    for p in obs.get("planets", []):
        if p[1] >= 0:
            s[p[1]] += p[5]
    for f in obs.get("fleets", []):
        s[f[1]] += f[6]
    return s


import sys


def _ensure_on_path(*agents):
    """Add each file-path agent's directory to sys.path so package-based agents
    (e.g. kuni05's main.py that does `import orbit_lite`) import correctly."""
    for a in agents:
        if isinstance(a, str) and a.endswith(".py") and os.sep in a:
            d = os.path.dirname(os.path.abspath(a))
            if d not in sys.path:
                sys.path.insert(0, d)


def _play(task):
    a_seat, p0, p1, seed, overrides = task
    # Reset OW_* then apply this task's overrides so config is deterministic even
    # when a pool worker is reused across tasks with different configs.
    for k in [k for k in os.environ if k.startswith("OW_")]:
        del os.environ[k]
    if overrides:
        os.environ.update({k: str(v) for k, v in overrides.items()})
    _ensure_on_path(p0, p1)
    env = make("orbit_wars", configuration={"seed": seed})
    env.run([p0, p1])
    rewards = [s["reward"] for s in env.steps[-1]]
    return a_seat, rewards, _final_scores(env)


def h2h(agent_a, agent_b, seeds, overrides=None, procs=None):
    """Head-to-head over `seeds` x 2 seat orderings, in parallel.

    overrides: dict of OW_* env vars applied to the CANDIDATE side (agent_a). The
    opponent must ignore these keys. Returns a result dict from agent_a's view.
    """
    tasks = []
    for seed in seeds:
        tasks.append((0, agent_a, agent_b, seed, overrides))  # agent_a is P0
        tasks.append((1, agent_b, agent_a, seed, overrides))  # agent_a is P1
    procs = procs or max(1, (os.cpu_count() or 2) - 1)
    if procs > 1:
        with Pool(procs) as pool:
            results = pool.map(_play, tasks)
    else:
        results = [_play(t) for t in tasks]

    w = l = t = 0
    sf = sa = 0
    for a_seat, rewards, scores in results:
        ra, rb = rewards[a_seat], rewards[1 - a_seat]
        sf += scores[a_seat]
        sa += scores[1 - a_seat]
        if ra > rb:
            w += 1
        elif ra < rb:
            l += 1
        else:
            t += 1
    n = w + l + t
    return dict(
        w=w,
        l=l,
        t=t,
        n=n,
        winpct=100.0 * w / n if n else 0.0,
        score_for=sf / n if n else 0.0,
        score_against=sa / n if n else 0.0,
    )


def fmt(label, r):
    return (
        f"{label:26s}: {r['w']:>3}W {r['l']:>3}L {r['t']:>3}T  "
        f"win%={r['winpct']:5.1f}  avg {r['score_for']:6.0f} vs {r['score_against']:6.0f}  ({r['n']}g)"
    )


# ---------------------------------------------------------------------------
# 4-player free-for-all
# ---------------------------------------------------------------------------
def _play_ffa(task):
    seat, agents, seed, overrides = task
    for k in [k for k in os.environ if k.startswith("OW_")]:
        del os.environ[k]
    if overrides:
        os.environ.update({k: str(v) for k, v in overrides.items()})
    env = make("orbit_wars", configuration={"seed": seed})
    env.run(agents)
    rewards = [s["reward"] for s in env.steps[-1]]
    return seat, rewards, _final_scores(env)


def ffa(hero, field, seeds, overrides=None, procs=None):
    """4-player FFA: `hero` vs 3 opponents in `field` (list of 3 agents).

    The hero is rotated through all 4 seats per seed (home quadrants differ).
    overrides (OW_*) apply process-wide, so the field must ignore the swept keys.
    Returns hero win-rate (placed 1st, reward==1), avg finishing rank, avg score.
    """
    assert len(field) == 3, "4p field must list exactly 3 opponents"
    tasks = []
    for seed in seeds:
        for seat in range(4):
            agents = field[:seat] + [hero] + field[seat:]  # hero at index=seat
            tasks.append((seat, agents, seed, overrides))
    procs = procs or max(1, (os.cpu_count() or 2) - 1)
    if procs > 1:
        with Pool(procs) as pool:
            results = pool.map(_play_ffa, tasks)
    else:
        results = [_play_ffa(t) for t in tasks]

    wins = 0
    rank_sum = 0
    score_sum = 0.0
    n = len(results)
    for seat, rewards, scores in results:
        if rewards[seat] == 1:
            wins += 1
        hs = scores[seat]
        rank_sum += 1 + sum(1 for s in scores if s > hs)  # 1 = best
        score_sum += hs
    return dict(
        w=wins,
        n=n,
        winpct=100.0 * wins / n if n else 0.0,
        avg_rank=rank_sum / n if n else 0.0,
        avg_score=score_sum / n if n else 0.0,
    )


def fmt4(label, r):
    return (
        f"{label:30s}: win%={r['winpct']:5.1f}  avg_rank={r['avg_rank']:.2f}/4  "
        f"avg_score={r['avg_score']:6.0f}  ({r['n']}g)  [random≈25%, rank 2.5]"
    )
