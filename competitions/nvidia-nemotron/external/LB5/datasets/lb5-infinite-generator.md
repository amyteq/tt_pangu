# LB5 infinite synthetic data generator (no train.csv leakage)

- LB5 trained on a **fully synthetic, infinite generator** and used `train.csv` **only for validation** → an honest, private-tracking CV.
- Per category, randomized to match train.csv statistics: gravity (g∈[4.9,19.6], t∈[1.0,5.0], +noise), conversion (value∈[5,50], mult∈[0.05,20], +noise), cipher (~80-word vocab, 4 sentence formats, single-answer when incomplete), roman (1–100), bit (7–10 examples, byte-level rules, Occam-compliant, unique answer), equation (1–3 operators, 3–5 examples, deduce-weighted), cryptarithm (equation→cipher-encrypt, C++ checker).
- ~2 billion tokens for the final submission. Generator/data linked in the writeup (JS/auth-gated); not downloaded.
