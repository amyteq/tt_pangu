"""T1 — index the public episodes dataset: who played, who won, how big.

Scans raw replay JSONs (kaggle/orbit-wars-episodes-*) into episodes_index.csv
so training/analysis can select games by player name / outcome / length.

Usage:
    python arena/episodes_index.py --data ../../data/orbit-wars-episodes \
        --out ~/work/episodes_index.csv --procs 22
"""

import argparse
import csv
import glob
import json
import os
from multiprocessing import Pool


def _scan(path):
    try:
        d = json.load(open(path))
        agents = [a.get("Name", "?") for a in d.get("info", {}).get("Agents", [])]
        if len(agents) != 2:
            return None  # 1v1 only (4p episodes exist but don't count on ladder)
        steps = d.get("steps", [])
        rewards = [s.get("reward") for s in steps[-1]] if steps else [None, None]
        last = steps[-1][0]["observation"] if steps else {}
        ships = [0.0, 0.0]
        for p in last.get("planets", []):
            if p[1] in (0, 1):
                ships[p[1]] += p[5]
        for f in last.get("fleets", []):
            if f[1] in (0, 1):
                ships[f[1]] += f[6]
        win = -1
        if rewards[0] is not None and rewards[1] is not None:
            win = 0 if rewards[0] > rewards[1] else (1 if rewards[1] > rewards[0] else -1)
        return [
            os.path.basename(path).split(".")[0],
            agents[0],
            agents[1],
            agents[win] if win >= 0 else "tie",
            len(steps),
            round(ships[0]),
            round(ships[1]),
        ]
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="episodes_index.csv")
    ap.add_argument("--procs", type=int, default=None)
    args = ap.parse_args()
    files = sorted(glob.glob(os.path.join(args.data, "*.json")))
    procs = args.procs or max(1, (os.cpu_count() or 2) - 1)
    print(f"indexing {len(files)} episodes, procs={procs}", flush=True)
    rows = []
    with Pool(procs) as pool:
        for r in pool.imap_unordered(_scan, files, chunksize=8):
            if r:
                rows.append(r)
    rows.sort(key=lambda r: r[0])
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["episode", "p0", "p1", "winner", "steps", "ships0", "ships1"])
        w.writerows(rows)
    names = {}
    for r in rows:
        if r[3] != "tie":
            names[r[3]] = names.get(r[3], 0) + 1
    top = sorted(names.items(), key=lambda kv: -kv[1])[:15]
    print(f"indexed {len(rows)} 1v1 episodes -> {args.out}")
    print("top winners:", top)


if __name__ == "__main__":
    main()
