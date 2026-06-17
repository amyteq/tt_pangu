"""T11 powered A/B: ledger-constrained avail (OW_LEDGER) on the baked t14 baseline.
Fresh seeds 16000+, 300 games vs evogen + starter no-regress, both arms."""

import os, time
import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
FC = f"{V}/forecast.py"
EVO = f"{V}/suite/evogen1093.py"
seeds = list(range(16000, 16150))
st = list(range(16000, 16015))
t0 = time.perf_counter()
for name, ov in (("ledger=0 (v3.2 base)", {"OW_LEDGER": "0"}), ("ledger=1 (T11)", {"OW_LEDGER": "1"})):
    e = P.h2h(FC, EVO, seeds, overrides=ov, procs=23)
    s = P.h2h(FC, "starter", st, overrides=ov, procs=23)
    half = 1.96 * (e["winpct"] / 100 * (1 - e["winpct"] / 100) / e["n"]) ** 0.5 * 100
    print(
        f"{name:20s} evogen={e['winpct']:5.1f}% ±{half:.1f} ({e['w']}-{e['l']}/{e['n']})  starter={s['winpct']:5.1f}%"
    )
print(f"[wall {time.perf_counter() - t0:.0f}s]")
