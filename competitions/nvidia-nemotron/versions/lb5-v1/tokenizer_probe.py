"""HEX-vs-raw-bits tokenizer probe (lb5-v1; the LB5 negative lesson).

LB5 found a token-saving 2-letter / merged encoding **broke the model** (e.g. `AB`
becomes a single BPE token), forcing a revert to **raw bits** — while LB1/LB3
succeeded with HEX. The resolution is tokenization granularity: an encoding is safe
only if each information-bearing symbol stays its own token (no BPE merge).

This probe checks an encoding's merge risk. If `transformers` + the Nemotron
tokenizer are available it measures real token counts; otherwise it falls back to a
documented structural heuristic (digit/space-separated = safe; adjacent letters =
merge risk). The recommendation: prefer encodings whose tokens-per-symbol ≈ 1.
"""

from __future__ import annotations

import argparse

SAMPLES = {
    "raw_bits": "0 1 0 1 1 0 1 0",  # spaced raw bits (LB5 kept)
    "raw_bits_nospace": "01011010",
    "hex_spaced": "5 A",  # spaced hex (proposed compromise)
    "hex_merged": "5A",
    "letters_merged": "AB",  # LB5's broken single-token case
}


def _heuristic_merge_risk(s: str) -> str:
    """Structural risk without a tokenizer: adjacent alphanumerics may BPE-merge."""
    compact = s.replace(" ", "")
    has_space = " " in s.strip()
    letterish = any(c.isalpha() for c in compact)
    if has_space:
        return "low (separated -> one token per symbol)"
    if letterish and len(compact) >= 2:
        return "HIGH (adjacent letters -> likely single BPE token; LB5's broken case)"
    if compact.isdigit() and len(compact) >= 2:
        return "medium (adjacent digits may merge depending on tokenizer)"
    return "low"


def _real_token_counts(model: str):
    try:
        from transformers import AutoTokenizer  # type: ignore
    except ImportError:
        return None
    try:
        tok = AutoTokenizer.from_pretrained(model)
    except Exception:
        return None
    return {name: len(tok.encode(s, add_special_tokens=False)) for name, s in SAMPLES.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="nvidia/Nemotron-3-Nano-30B-A3B")
    args = ap.parse_args()
    real = _real_token_counts(args.model)
    print("HEX-vs-raw-bits encoding probe (per-symbol token granularity):")
    if real:
        print(f"  (real tokenizer: {args.model})")
        for name, s in SAMPLES.items():
            nsym = len(s.replace(" ", ""))
            print(f"    {name:18s} {s!r:14s} tokens={real[name]:3d}  tokens/symbol={real[name] / max(nsym, 1):.2f}")
    else:
        print("  (transformers/tokenizer unavailable — structural heuristic; offline/CPU context)")
        for name, s in SAMPLES.items():
            print(f"    {name:18s} {s!r:14s} merge_risk={_heuristic_merge_risk(s)}")
    print("\n  recommendation: tokens/symbol ~ 1 is safe. Prefer spaced raw bits or spaced")
    print("  hex; avoid adjacent-letter codes (LB5: single-token 'AB' broke the model).")


if __name__ == "__main__":
    main()
