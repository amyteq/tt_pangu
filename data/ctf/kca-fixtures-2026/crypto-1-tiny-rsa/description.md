# crypto-1-tiny-rsa

**Category:** crypto
**Points:** 100
**Author:** kca-fixtures (in-house, CC0-1.0 problem text + MIT runner code)

## Story

Alice wanted to encrypt her secret with RSA, but she was in a hurry and only
generated **72-bit primes** for her modulus. She published the ciphertext anyway.
A few seconds with `sympy.factorint` should be enough.

## Given

The values are committed to `attachments/params.json`:

- `n` — modulus (143-bit; trivially factorable)
- `e` — public exponent (`65537`)
- `c` — ciphertext, `c = pow(m, e, n)`, where `m = int.from_bytes(flag, 'big')`

## Goal

Recover the flag string. Flag format: `kca{...}`. ASCII-only inside the braces.

## Intended path

1. `factorint(n)` recovers `p, q`.
2. `phi = (p-1)*(q-1)`; `d = pow(e, -1, phi)`.
3. `m = pow(c, d, n)`; convert back to bytes.
4. Decode UTF-8.

No docker. Runs entirely in-process. `solver_template.py` sketches the math
and verifies the recovered flag's SHA-256 against `expected.sha256`.

## Out of scope

- The intentionally-weak parameters are pedagogical. Do NOT reuse this RSA key
  shape for anything that matters.
