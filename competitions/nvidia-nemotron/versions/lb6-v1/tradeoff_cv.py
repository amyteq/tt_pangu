"""Bit / cryptarithm data trade-off calibration (lb6-v1).

Reproduces the LB6 *regret* as a calibration model (method_summary.md §6): adding
cryptarithm data drops bit CV more than expected (their estimate was off, costing
2nd-3rd place). LB6 over-weights bit to ~69% of tokens because bit CV is fragile to
mix changes.

This module fits a simple linear sensitivity model from (bit_token_share -> bit_cv)
points and predicts the bit-CV drop when cryptarithm tokens are added (which lowers
the bit share). It is the calibration step the plan calls for BEFORE committing a
final dataset mix — so the trade-off is predicted, not discovered after submission.

Pure CPU; the model is illustrative (calibrate on real per-mix CV when available).
"""

from __future__ import annotations

import argparse


def fit_sensitivity(points):
    """points: [(bit_token_share, bit_cv)]. Least-squares slope/intercept of bit_cv
    vs bit_share. Returns (slope, intercept)."""
    n = len(points)
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] ** 2 for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def predict_bit_cv(share, slope, intercept):
    return slope * share + intercept


def trade_off(slope, intercept, share_before, crypto_tokens_added, total_tokens):
    """Predict the bit-CV drop when adding cryptarithm tokens (lowers bit share)."""
    bit_tokens = share_before * total_tokens
    share_after = bit_tokens / (total_tokens + crypto_tokens_added)
    drop = predict_bit_cv(share_before, slope, intercept) - predict_bit_cv(share_after, slope, intercept)
    return share_after, drop


def main():
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    # illustrative observed points (bit_share -> bit_cv); replace with real per-mix CV
    points = [(0.50, 0.86), (0.60, 0.90), (0.69, 0.935), (0.75, 0.95)]
    slope, intercept = fit_sensitivity(points)
    print("LB6 bit/cryptarithm trade-off calibration:")
    print(f"  fitted bit_cv = {slope:.3f} * bit_share + {intercept:.3f}  (from {len(points)} mix points)")
    # LB6 scenario: 0.25B set at 69% bit, then double cryptarithm (~+0.12B tokens)
    share_after, drop = trade_off(slope, intercept, 0.69, 0.12e9, 0.25e9)
    print(f"  scenario: 69% bit @0.25B + 0.12B cryptarithm -> bit_share {share_after:.2f}")
    print(
        f"  predicted bit-CV drop = {drop:.3f}  ({'> ' if drop > 0.01 else '<='}0.01 -> {'double bit to hold CV' if drop > 0.01 else 'safe'})"
    )
    print("  (LB6 regret: this drop was UNDER-estimated -> they shipped 2 seeds of 0.25B instead)")


if __name__ == "__main__":
    main()
