"""Triage candidate gate agents: load OK? play vs starter without error? speed? result."""

import logging

logging.disable(logging.INFO)
import glob, os, sys, time
from kaggle_environments import make

HERE = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.normpath(os.path.join(HERE, "..", "agent", "versions", "suite"))
sys.path.insert(0, SUITE)

for path in sorted(glob.glob(SUITE + "/*.py")):
    name = os.path.basename(path)[:-3]
    try:
        env = make("orbit_wars", configuration={"seed": 7}, debug=True)
        t0 = time.perf_counter()
        env.run([path, "starter"])
        dt = time.perf_counter() - t0
        st = [s[0]["status"] for s in env.steps]
        bad = [s for s in st if s not in ("ACTIVE", "DONE", "INACTIVE")]
        r = env.steps[-1][0]["reward"]
        res = "WIN" if r == 1 else ("LOSS" if r == -1 else "TIE")
        nstep = len(env.steps)
        print(
            f"{name:14s}: {'OK ' if not bad else 'ERR'} vs starter={res:4s} "
            f"steps={nstep:3d} wall={dt:5.1f}s ~{dt / nstep * 1000:5.1f}ms/step"
        )
    except Exception as e:
        print(f"{name:14s}: LOAD/RUN FAIL — {type(e).__name__}: {str(e)[:80]}")
