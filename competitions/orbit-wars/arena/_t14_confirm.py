"""T2-R2 confirmation: t14 (snorlax top) vs baseline, FRESH seeds 15000+, 300 games each."""

import os, time
import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
FC = f"{V}/forecast.py"
EVO = f"{V}/suite/evogen1093.py"
CONFIGS = {
    "t14": {
        "OW_PROJ_H": 26,
        "OW_FRONTIER_FLOOR": 5,
        "OW_FRONTIER_DIST": 20.0,
        "OW_PROD_MULT": 0,
        "OW_REAR_FLOOR": 0,
        "OW_CAP_EARLY": 3.2,
        "OW_CAP_LATE": 1.3,
    },
    "baseline": {
        "OW_PROJ_H": 18,
        "OW_FRONTIER_FLOOR": 10,
        "OW_FRONTIER_DIST": 28.0,
        "OW_PROD_MULT": 0,
        "OW_REAR_FLOOR": 0,
        "OW_CAP_EARLY": 2.0,
        "OW_CAP_LATE": 1.0,
    },
}
seeds = list(range(15000, 15150))
st = list(range(15000, 15015))
t0 = time.perf_counter()
for name, cfg in CONFIGS.items():
    ov = {k: str(v) for k, v in cfg.items()}
    e = P.h2h(FC, EVO, seeds, overrides=ov, procs=23)
    s = P.h2h(FC, "starter", st, overrides=ov, procs=23)
    half = 1.96 * (e["winpct"] / 100 * (1 - e["winpct"] / 100) / e["n"]) ** 0.5 * 100
    print(f"{name:9s} evogen={e['winpct']:5.1f}% ±{half:.1f} ({e['w']}-{e['l']}/{e['n']})  starter={s['winpct']:5.1f}%")
print(f"[wall {time.perf_counter() - t0:.0f}s]")
