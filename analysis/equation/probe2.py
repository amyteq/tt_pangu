"""Probe the base-36 value-arithmetic hypothesis on the 7748 global pairs."""

import json
import collections

pairs = json.load(open("analysis/equation/global_pairs.json"))
keys = list(pairs)

# --- last/first char identity & suffix/prefix tests ---
last_id = sum(1 for k in keys if pairs[k][-1] == k[-1])
first_id = sum(1 for k in keys if pairs[k][0] == k[0])
suffix = sum(1 for k in keys if k.endswith(pairs[k]))
prefix = sum(1 for k in keys if k.startswith(pairs[k]))
n = len(keys)
print(f"last-char identity:  {last_id}/{n} ({100 * last_id / n:.1f}%)")
print(f"first-char identity: {first_id}/{n} ({100 * first_id / n:.1f}%)")
print(f"output is SUFFIX of input: {suffix}/{n} ({100 * suffix / n:.1f}%)")
print(f"output is PREFIX of input: {prefix}/{n} ({100 * prefix / n:.1f}%)")

# last-char identity broken down: when out and in last char differ, by how much (need sigma) - skip
# But: is the LAST output char a deterministic function of the last TWO input chars? (carry from pos -2)
print("\n[last-out char] determinism by last-k input chars:")
for k_in in (1, 2, 3):
    m = collections.defaultdict(collections.Counter)
    for key in keys:
        m[key[-k_in:]][pairs[key][-1]] += 1
    pure = sum(c.most_common(1)[0][1] for c in m.values())
    print(f"  by last {k_in} input chars: purity {pure / n:.3f} ({len(m)} contexts)")

# --- value hypothesis: assume an unknown sigma:glyph->0..35.
# Test the LINEAR signature of out = in mod M:  val(in) - val(out) must be divisible by M.
# We cannot compute val without sigma, BUT we can test a NECESSARY condition that is sigma-free:
# For out=in mod M with M a multiple of 36^t, the last t base-36 digits are preserved =>
# output's last t chars == input's last t chars. We measured suffix above.
#
# Alternative sigma-free invariant: if op preserves value mod 36 (out ≡ in mod 36 under sigma),
# then the MAP last_in_glyph -> last_out_glyph would be a PERMUTATION-with-carry-noise but the
# *identity* would dominate only if sigma-low-digit is preserved AND carries are rare.
# We see identity dominate -> test: is (in_last, out_last) pair set consistent with out_last
# being in_last shifted by a small carry? Build the confusion and see if it's near-diagonal
# under SOME glyph ordering. Try: does there exist ordering where out_last-in_last is small?

# Count, per input-last-glyph, the distribution of output-last-glyph; report identity fraction
ident_frac = []
for g in sorted(set(k[-1] for k in keys)):
    sub = [pairs[k][-1] for k in keys if k[-1] == g]
    c = collections.Counter(sub)
    ident_frac.append((g, c.get(g, 0) / len(sub), len(sub)))
avg_ident = sum(f for _, f, _ in ident_frac) / len(ident_frac)
print(f"\nper-glyph last-char identity fraction avg = {avg_ident:.3f}")
print("lowest-identity glyphs:", sorted(ident_frac, key=lambda x: x[1])[:5])
