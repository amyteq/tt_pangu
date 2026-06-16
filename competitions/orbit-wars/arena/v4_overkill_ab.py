"""OVERKILL revival A/B — concentration->heavy-strike inside the v4 scheduler
(issue #87 follow-up, 2026-06-16).

Two scoped revivals of the refuted standalone OW_OVERKILL multiplier, each gated
and measured against the v4 baseline on the ladder-predictive suite per the T2
power protocol (>= 150 paired seeds = 300 games, +-3.5pt 95% CI), plus a starter
no-regress check (>= 85%):

  v4a  OW_V4A=1  counter-attack-window hammer (policy layer: band bump + exposed-
                 target re-rank + neutral-hammer gate-slack when enemy committed)
  v4f  OW_V4F=1  FM3 opponent-response value (nearest enemy reinforcement appended
                 to the target's arrival schedule when valuing any strike)
  v4c  OW_V4C=1  cluster-targeted hammer (re-rank toward dense enemy/neutral cluster)
  v4i  OW_V4I=1  Isaiah two-band sizing (full-drain band early/mid, half late)

NOTE: v4a (null −0.3pt) and v4f (−9.0pt) already gated 2026-06-16 and REFUTED;
re-listed here only so re-runs reproduce them. v4c / v4i are the new sub-cuts.

Candidate = agent/versions/v4.py (OW_V4=1 default). Opponent = evogen1093 / starter
(neither reads OW_* keys, so process-wide overrides give a clean A/B). Fresh seed
block 21000+ (18000s burned by the original OVERKILL test, 19000s by SUPPLY).

Usage:
    python arena/v4_overkill_ab.py --seeds 40 --seed0 21000        # smoke
    python arena/v4_overkill_ab.py --seeds 150 --procs 23          # gate
"""

import argparse
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.normpath(os.path.join(HERE, "..", "agent", "versions"))
V4 = f"{V}/v4.py"
KUNI = f"{V}/kuni05/main.py"  # strong tier (~1240) — the discriminating opponent
EVO = f"{V}/suite/evogen1093.py"  # mid tier — no-regress only (v4 saturates it)

CONFIGS = [
    ("baseline", None),
    ("v4a", {"OW_V4A": "1"}),
    ("v4f", {"OW_V4F": "1"}),
    ("v4c", {"OW_V4C": "1"}),  # cluster-targeted hammer
    ("v4i", {"OW_V4I": "1"}),  # Isaiah two-band sizing
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=150)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--seed0", type=int, default=21000)
    args = ap.parse_args()
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    # evogen is the proven discriminating gate (~18% v4 baseline, T2/t8 protocol).
    # kuni05 (~1240) floors at 0% — v4 is still below the cliff, so it gives no
    # gradient; kept as a small reference tracker only. starter = no-regress.
    evo_seeds = list(range(args.seed0, args.seed0 + args.seeds))
    ref_seeds = list(range(args.seed0, args.seed0 + max(30, args.seeds // 3)))

    print(
        f"=== v4 OVERKILL A/B: {len(evo_seeds)}x2 vs evogen (GATE, +7pt bar) + "
        f"{len(ref_seeds)}x2 vs starter (no-regress) + kuni05 (cliff ref) per config, "
        f"procs={procs}, seeds {args.seed0}+ ===",
        flush=True,
    )
    base = None
    for name, ov in CONFIGS:
        t0 = time.perf_counter()
        e = P.h2h(V4, EVO, evo_seeds, overrides=ov, procs=procs)
        s = P.h2h(V4, "starter", ref_seeds, overrides=ov, procs=procs)
        k = P.h2h(V4, KUNI, ref_seeds, overrides=ov, procs=procs)
        dt = time.perf_counter() - t0
        if name == "baseline":
            base = e["winpct"]
        delta = "" if base is None else f"  d={e['winpct'] - base:+5.1f}pt"
        print(
            f"{name:9s} evogen={e['winpct']:5.1f}% ({e['w']}-{e['l']}-{e['t']}/{e['n']})  "
            f"starter={s['winpct']:5.1f}%  kuni05={k['winpct']:4.1f}%"
            f"{delta}  [{dt:.0f}s]",
            flush=True,
        )


if __name__ == "__main__":
    main()
