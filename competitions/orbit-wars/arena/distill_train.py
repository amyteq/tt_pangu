"""T12 phase B — behavior-clone kuni05's launch policy from the pair dataset.

Tiny MLP (16 -> 64 -> 64 -> {launch logit, frac}) so the student can later run
as pure-stdlib matrix math inside a single-file agent (no torch needed on the
eval side). Trains in minutes on snorlax CPU/GPU.

Split is GROUPED BY GAME (game idx % 10 == 0 -> val) so near-duplicate turns
from one game never straddle the split. Launch head uses pos_weight to offset
the ~0.3% positive rate; frac head trains on positive rows only.

Outputs:
    <out>.pt   torch checkpoint (resume / inspection)
    <out>.npz  weights + feature mean/std for the stdlib student

Usage:
    python arena/distill_train.py --pairs ~/work/distill_pairs.npz \
        --out ~/work/distill_student --epochs 6
"""

import argparse
import os

import numpy as np
import torch
import torch.nn as nn

HID = 64


class Student(nn.Module):
    def __init__(self, nfeat):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(nfeat, HID), nn.ReLU(), nn.Linear(HID, HID), nn.ReLU())
        self.head_launch = nn.Linear(HID, 1)
        self.head_frac = nn.Linear(HID, 1)

    def forward(self, x):
        h = self.body(x)
        return self.head_launch(h).squeeze(-1), torch.sigmoid(self.head_frac(h)).squeeze(-1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=os.path.expanduser("~/work/distill_pairs.npz"))
    ap.add_argument("--out", default=os.path.expanduser("~/work/distill_student"))
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=65536)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--lost-weight", type=float, default=0.5)
    ap.add_argument(
        "--neg-ratio",
        type=int,
        default=0,
        help="train-set negatives kept per positive (0 = all; use ~25 for "
        "datasets too big for RAM — val split stays untouched)",
    )
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    d = np.load(args.pairs, allow_pickle=True)
    X, yl, yf = d["X"], d["y_launch"], d["y_frac"]
    game, won = d["game"], d["won"]
    val_m = game % 10 == 0
    tr_m = ~val_m
    if args.neg_ratio:
        rng = np.random.default_rng(args.seed)
        tr_idx = np.flatnonzero(tr_m)
        pos_idx = tr_idx[yl[tr_idx] > 0]
        neg_idx = tr_idx[yl[tr_idx] == 0]
        keep_neg = rng.choice(
            neg_idx,
            size=min(len(neg_idx), args.neg_ratio * len(pos_idx)),
            replace=False,
        )
        keep = np.concatenate([pos_idx, keep_neg])
        sub = np.zeros(len(yl), dtype=bool)
        sub[keep] = True
        tr_m = sub
        print(
            f"neg-ratio {args.neg_ratio}: train rows {len(keep)} ({len(pos_idx)} pos + {len(keep_neg)} neg)",
            flush=True,
        )
    mean, std = X[tr_m].mean(0), X[tr_m].std(0) + 1e-6
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(
        f"pairs={len(X)} train={tr_m.sum()} val={val_m.sum()} pos={yl.mean() * 100:.2f}% dev={dev}",
        flush=True,
    )

    # normalize per split (never materialize a full normalized copy of X)
    xt = torch.tensor((X[tr_m] - mean) / std)
    lt = torch.tensor(yl[tr_m])
    ft = torch.tensor(yf[tr_m])
    wt = torch.tensor(np.where(won[tr_m] > 0, 1.0, args.lost_weight).astype("float32"))
    val_idx = np.flatnonzero(val_m)
    if len(val_idx) > 2_000_000:  # cap val for memory; fixed seed = comparable runs
        val_idx = np.random.default_rng(11).choice(val_idx, 2_000_000, replace=False)
    xv = torch.tensor((X[val_idx] - mean) / std).to(dev)
    lv = torch.tensor(yl[val_idx]).to(dev)

    model = Student(X.shape[1]).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    pos_w = torch.tensor(min(100.0, float((lt == 0).sum() / max(1, lt.sum())))).to(dev)
    bce = nn.BCEWithLogitsLoss(pos_weight=pos_w, reduction="none")

    n = len(xt)
    for ep in range(args.epochs):
        model.train()
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, args.batch):
            idx = perm[i : i + args.batch]
            xb, lb = xt[idx].to(dev), lt[idx].to(dev)
            fb, wb = ft[idx].to(dev), wt[idx].to(dev)
            logit, frac = model(xb)
            loss_l = (bce(logit, lb) * wb).mean()
            pos = lb > 0
            loss_f = ((frac[pos] - fb[pos]) ** 2 * wb[pos]).mean() if pos.any() else torch.tensor(0.0, device=dev)
            loss = loss_l + loss_f
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(idx)
        # val: recall@precision proxy — rank by logit, take top-N (N = true positives)
        model.eval()
        with torch.no_grad():
            vl, _ = model(xv)
            k = int(lv.sum())
            top = torch.topk(vl, k).indices
            hit = float(lv[top].sum()) / max(1, k)
        print(
            f"epoch {ep + 1}: train_loss={tot / n:.4f}  val_recall@k={hit:.3f} (k={k})",
            flush=True,
        )

    torch.save(model.state_dict(), args.out + ".pt")
    sd = {k: v.cpu().numpy() for k, v in model.state_dict().items()}
    np.savez(
        args.out + ".npz",
        w0=sd["body.0.weight"],
        b0=sd["body.0.bias"],
        w1=sd["body.2.weight"],
        b1=sd["body.2.bias"],
        wl=sd["head_launch.weight"],
        bl=sd["head_launch.bias"],
        wf=sd["head_frac.weight"],
        bf=sd["head_frac.bias"],
        mean=mean,
        std=std,
        feats=d["feats"],
    )
    print(f"saved {args.out}.pt / .npz", flush=True)


if __name__ == "__main__":
    main()
