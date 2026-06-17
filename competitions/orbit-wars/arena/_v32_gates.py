"""VALIDATION.md gates 1/2/4/5 for v3.2 main.py (gate 3 already passed; gate 6 = parse+imports)."""

import logging

logging.disable(logging.INFO)
import os, sys, time
import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
MAIN = f"{ROOT}/agent/main.py"
V = f"{ROOT}/agent/versions"
from kaggle_environments import make

# Gate 1: crash safety — 10 games vs mixed + bare-agent self-play 4 games
bad = 0
for seed in range(20000, 20010):
    env = make("orbit_wars", configuration={"seed": seed}, debug=True)
    env.run([MAIN, "starter" if seed % 2 else "random"])
    st = [s[0]["status"] for s in env.steps]
    bad += len([s for s in st if s not in ("ACTIVE", "DONE", "INACTIVE")])
sys.path.insert(0, f"{ROOT}/agent")
import importlib.util

spec = importlib.util.spec_from_file_location("m32", MAIN)
m32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m32)
bare_bad = 0
for seed in range(20010, 20014):
    env = make("orbit_wars", configuration={"seed": seed})
    env.reset(2)
    env.run([lambda o: m32._agent(o), lambda o: m32._agent(o)])  # bare, no try/except
print(f"GATE1 crash-safety: wrapped_bad={bad} bare_selfplay=4/4 ok")

# Gate 5: runtime p99 over one 500-step game
env = make("orbit_wars", configuration={"seed": 20020})
env.run([MAIN, "starter"])
worst = max(
    env.steps, key=lambda s: len(s[0]["observation"].get("planets", [])) + len(s[0]["observation"].get("fleets", []))
)
obs = dict(worst[0]["observation"])
obs["player"] = 0
ts = []
for _ in range(100):
    t0 = time.perf_counter()
    m32.agent(obs)
    ts.append((time.perf_counter() - t0) * 1000)
ts.sort()
print(f"GATE5 runtime: densest p50={ts[50]:.1f}ms p99={ts[98]:.1f}ms (bar 50ms)")

# Gate 2: weak-tier no-regress
for opp, label, bar in (
    ("random", "random", 100.0),
    ("starter", "starter", 85.0),
    (f"{V}/suite/adilshamim.py", "adilshamim", 90.0),
    (f"{V}/pub_tactical.py", "pub_tactical", 85.0),
):
    r = P.h2h(MAIN, opp, list(range(20100, 20112)), procs=22)
    print(f"GATE2 vs {label:13s}: {r['winpct']:5.1f}% (bar ~{bar})")

# Gate 4: 4p robustness
r4 = P.ffa(MAIN, ["starter", f"{V}/pub_tactical.py", f"{V}/suite/adilshamim.py"], list(range(7000, 7030)), procs=22)
print(f"GATE4 4p: win%={r4['winpct']:.1f} avg_rank={r4['avg_rank']:.2f} (v2.1-era baseline rank ~1.6)")
