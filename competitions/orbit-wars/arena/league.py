"""Version league — round-robin among online + candidate versions (issue #87).

Supports the submission-slot strategy: every entry is a FILE with baked
defaults (no env overrides — overrides leak to both seats in a mirror pair),
so what plays here is exactly what would be submitted. Writes/updates the
markdown table in competitions/orbit-wars/LEAGUE.md.

Usage:
    python arena/league.py --games 30 --seed0 20000 --procs 23
"""

import argparse
import datetime
import os
import time

import pool as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
V = os.path.join(ROOT, "agent", "versions")

# label -> (file, status) ; ONLINE = currently holding a ladder slot
ENTRIES = [
    ("kuni05", f"{V}/kuni05/main.py", "online(harry#1)"),
    ("v3.2", f"{V}/v3_2.py", "online(harry#2, may#1)"),
    ("v3.2+coarr", f"{V}/v3_2_coarr.py", "online(may#2)"),
    ("v3.2+supply", f"{V}/v3_2_supply.py", "candidate"),
    ("evogen1093", f"{V}/suite/evogen1093.py", "anchor(LB~1093)"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=30, help="seeds per pair (x2 seats)")
    ap.add_argument("--seed0", type=int, default=20000)
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "LEAGUE.md"))
    args = ap.parse_args()
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    seeds = list(range(args.seed0, args.seed0 + args.games))
    entries = [(n, p, st) for n, p, st in ENTRIES if os.path.exists(p)]

    names = [n for n, _, _ in entries]
    cell = {}
    t0 = time.perf_counter()
    for i, (na, pa, _) in enumerate(entries):
        for j, (nb, pb, _) in enumerate(entries):
            if j <= i:
                continue
            r = P.h2h(pa, pb, seeds, procs=procs)
            cell[(na, nb)] = r["winpct"]
            cell[(nb, na)] = 100.0 - r["winpct"] - 100.0 * r["t"] / r["n"]
            print(
                f"{na} vs {nb}: {r['winpct']:.1f}% ({r['w']}-{r['l']}-{r['t']})",
                flush=True,
            )

    avg = {n: sum(cell[(n, m)] for m in names if m != n) / (len(names) - 1) for n in names}
    rank = sorted(names, key=lambda n: -avg[n])

    lines = [
        "# Orbit Wars — 版本联赛表(提交位决策支持)",
        "",
        f"> 更新:{datetime.datetime.now():%Y-%m-%d %H:%M} · {args.games}×2 局/对 · 种子 {args.seed0}+ · 行 vs 列 = 行的胜率%",
        "",
        "| 版本(状态) | " + " | ".join(names) + " | **平均** |",
        "|---|" + "---|" * (len(names) + 1),
    ]
    status = {n: st for n, _, st in entries}
    for n in rank:
        row = [f"**{n}**({status[n]})"]
        for m in names:
            row.append("—" if m == n else f"{cell[(n, m)]:.0f}")
        row.append(f"**{avg[n]:.1f}**")
        lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        "状态:online = 占用天梯槽位;candidate = 待提交;anchor = 天梯锚点(LB 分数已知,用于校准)。",
        f"耗时 {time.perf_counter() - t0:.0f}s。",
    ]
    with open(args.out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {args.out}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
