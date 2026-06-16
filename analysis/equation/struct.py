"""EQ structural/sensitivity analysis on the 7748 global pairs.
No GPU. Guides the joint sigma+operation crack (EQ-2')."""

import json
import collections
import itertools
from collections import defaultdict

pairs = json.load(open("analysis/equation/global_pairs.json"))
items = list(pairs.items())
print("clean pairs", len(items))
ALPHA = sorted(set("".join(pairs)) | set("".join(pairs.values())))
print("alphabet(%d): %s" % (len(ALPHA), "".join(ALPHA)))
digits = [c for c in ALPHA if c.isdigit()]
print("digit glyphs:", digits, "count", len(digits))

keys = list(pairs)

# 1) Per-position influence on output LENGTH
print("\n[1] single-position-change neighbors -> output length change rate:")
for p in range(5):
    buckets = defaultdict(list)
    for k in keys:
        buckets[k[:p] + "\x00" + k[p + 1 :]].append(k)
    tot = chg = 0
    for group in buckets.values():
        if len(group) < 2:
            continue
        for a, b in itertools.combinations(group, 2):
            tot += 1
            if len(pairs[a]) != len(pairs[b]):
                chg += 1
    print(f"  pos {p}: {tot} pairs, len-change {chg} ({100 * chg / max(tot, 1):.1f}%)")

# 2) Output length vs which input positions -> guess MSB ordering
# For each position, does the GLYPH at that position predict output length well?
print("\n[2] mutual-info-ish: does glyph at pos p alone determine out-len?")
for p in range(5):
    by = defaultdict(collections.Counter)
    for k in keys:
        by[k[p]][len(pairs[k])] += 1
    # purity: average max-fraction
    pur = sum(c.most_common(1)[0][1] for c in by.values()) / len(keys)
    print(f"  pos {p}: out-len purity by single glyph = {pur:.3f}")

# 3) Does last char of input map stably to last char(s) of output? (LSB carry test)
print("\n[3] last-input-glyph -> last-output-glyph consistency:")
m = defaultdict(collections.Counter)
for k in keys:
    m[k[-1]][pairs[k][-1]] += 1
consistent = sum(1 for c in m.values() if len(c) == 1)
print(f"  {consistent}/{len(m)} last-input glyphs map to a unique last-output glyph")
# show a few
for g in list(m)[:6]:
    print("   ", repr(g), "->", dict(m[g].most_common(3)))
