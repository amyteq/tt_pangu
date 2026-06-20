"""Stage-1 memorize-drill generator (lb3-v1, two-stage training stage 1).

The LB3 headline lever is **two-stage training**: stage 1 pretrains the adapter to
*recall the lookup table* via `<RECALL_DOMAINS>`/`<RECALL_ROWS>` completion drills,
**16 packed per sample** with the **request portion masked from the loss**; stage 2
inits from the stage-1 adapter and trains real traces (+ ~3K retained drills). This
module builds the stage-1 drill corpus (CPU) from the multiplication-pattern lookup.

Each emitted sample is a *packed* concatenation of 16 drill items. Every item has a
``request`` (masked: loss=0) and a ``completion`` (the recalled rows; loss=1). We
carry an explicit ``loss_mask`` segment list so the trainer can mask requests —
exactly the writeup's "request masked from loss". No tokenizer here; masking is at
the character-segment level (the kernel re-tokenizes).

Output: JSONL of {text, segments:[{role, span:[s,e], loss}]}.
"""

from __future__ import annotations

import argparse
import json
import random

from mul_pattern_lookup import build_lookup

PACK = 16  # drill items per packed sample (writeup)


def _drill_item(sig, rows):
    # Rows are (a, b, product) members of the signature, where product may be from
    # the a*b / a*b±1 families. Render as (a,b)->p RECALL tuples (not "a*b=p") so the
    # drill never asserts false arithmetic for the ±1 families — it is a table-recall
    # target keyed by the length signature, exactly as the CSP solver consumes it.
    la, lb, lp = sig
    request = f"<RECALL_DOMAINS sig=({la},{lb},{lp})>"
    body = " ; ".join(f"({a},{b})->{p}" for a, b, p in rows)
    completion = f"<RECALL_ROWS>{body}</RECALL_ROWS>"
    return request, completion


def build_drill_samples(n_samples: int, lut=None, rows_per_item: int = 6, seed: int = 42):
    lut = lut or build_lookup()
    sigs = lut.signatures()
    rng = random.Random(seed)
    samples = []
    for _ in range(n_samples):
        text_parts = []
        segments = []
        cursor = 0
        for _ in range(PACK):
            sig = rng.choice(sigs)
            rows = lut.rows_for(sig)
            rows = rng.sample(rows, min(rows_per_item, len(rows)))
            request, completion = _drill_item(sig, rows)
            # request segment (masked: loss 0)
            seg = request + "\n"
            segments.append({"role": "request", "span": [cursor, cursor + len(seg)], "loss": 0})
            text_parts.append(seg)
            cursor += len(seg)
            # completion segment (loss 1)
            seg = completion + "\n"
            segments.append({"role": "completion", "span": [cursor, cursor + len(seg)], "loss": 1})
            text_parts.append(seg)
            cursor += len(seg)
        samples.append({"text": "".join(text_parts), "segments": segments})
    return samples


def masked_fraction(samples) -> float:
    masked = total = 0
    for s in samples:
        for seg in s["segments"]:
            ln = seg["span"][1] - seg["span"][0]
            total += ln
            if seg["loss"] == 0:
                masked += ln
    return masked / total if total else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200, help="number of packed samples")
    ap.add_argument("--out", default="", help="write JSONL here (default: report only)")
    args = ap.parse_args()
    samples = build_drill_samples(args.n)
    mf = masked_fraction(samples)
    items = sum(len(s["segments"]) // 2 for s in samples)
    print(f"stage-1 drill corpus: {len(samples)} packed samples x {PACK} items = {items} drill items")
    print(f"masked (request) fraction of chars: {100 * mf:.1f}%  (loss only on recalled rows)")
    if args.out:
        with open(args.out, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")
        print(f"wrote {args.out}")
    else:
        print("\nsample[0] first 300 chars:\n" + samples[0]["text"][:300])


if __name__ == "__main__":
    main()
