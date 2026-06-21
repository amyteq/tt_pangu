"""HEX compression for bit-manipulation traces (lb1-v1).

The Nemotron tokenizer is ~1 token per bit/digit character, so long binary
columns dominate the 7680-token budget. The 1st-place solution converts bit
strings of length >= 4 to hexadecimal, cutting median generated tokens
6771 -> 4888 (-27.8%). This module is the clean, exact part of the bit lever.

Convention (matches the writeup worked example): front-pad the bit string to a
multiple of 4, then map each nibble to a hex digit.
    "1101000001" (10 bits, a length-10 output-bit column across 10 examples)
      -> front-pad to "001101000001" -> 0011|0100|0001 -> "341"
"""

from __future__ import annotations

MIN_HEX_LEN = 4


def bits_to_hex(bits: str) -> str:
    """Compress a 0/1 string (len >= MIN_HEX_LEN) to hex; shorter strings pass through."""
    if len(bits) < MIN_HEX_LEN or any(c not in "01" for c in bits):
        return bits
    pad = (-len(bits)) % 4
    padded = "0" * pad + bits
    return "".join(f"{int(padded[i : i + 4], 2):x}" for i in range(0, len(padded), 4))


def hex_to_bits(hx: str, length: int) -> str:
    """Inverse of bits_to_hex given the original bit length (drops the front padding)."""
    full = "".join(f"{int(c, 16):04b}" for c in hx)
    return full[-length:]


def char_tokens(s: str) -> int:
    """Approximate Nemotron token count (~1 token / char) for a trace string."""
    return len(s)


def compression_ratio(bits: str) -> float:
    """Fraction of characters saved by HEX-compressing one bit string."""
    if len(bits) < MIN_HEX_LEN:
        return 0.0
    return 1.0 - len(bits_to_hex(bits)) / len(bits)


if __name__ == "__main__":
    # writeup unit check
    assert bits_to_hex("1101000001") == "341", bits_to_hex("1101000001")
    assert bits_to_hex("01101001") == "69"
    assert hex_to_bits("341", 10) == "1101000001"
    assert hex_to_bits("69", 8) == "01101001"
    print("hex_compress unit checks pass")
    print("  1101000001 ->", bits_to_hex("1101000001"), "(writeup: 341)")
    print("  01101001   ->", bits_to_hex("01101001"))
    print(f"  8-bit string compression: {compression_ratio('01101001'):.0%}")
    print(f"  64-bit column compression: {compression_ratio('0' * 64):.0%}")
