# LB92 gap analysis — Kawashima/MedudentYamatai's 92nd-place solution vs our 0.86

> Updated 2026-06-17 from the actual writeup (`temp/LB92.pdf`). The earlier version compared a generic
> "~0.86–0.89 band" (author/method `unknown`); the real solution has **concrete distinctive levers** — corrected
> here. External claims untrusted; our numbers from `tracking.md`.

## The framing
LB92 is a **data-engineering-first** solution at the same 0.86-tier root as us (huikang reasoner + public
0.85 notebooks). It deliberately **does not attack the hard categories** — it maximizes faithful reproduction
of the reasoner's 87.8% solve-rate via **more, statistics-matched synthetic data** + two stability tricks. Its
gaps-vs-us are **specific, cheap, and testable**, not a paradigm shift.

## Side-by-side

| dimension | LB92 (Kawashima/MedudentYamatai) | us | gap / takeaway |
|---|---|---|---|
| reasoner | huikang's, ~unchanged (87.8% train) | huikang corpus + our solver-CoT (c1/c2) | parity (same root) |
| synthetic data | **statistics-matched generator** (char freq / numeric ranges / transform-method dist) + **synthetic-vs-original gap QC loop**, final **2.5:1 synth:original** | naive cryptarithm/bit synth (b1/b2/v15) — **regressed/diluted** | **GAP: our synth wasn't statistics-matched or gap-validated** |
| tokenization | **per-char synthetic tokens** (force 1 symbol = 1 token; fixes BPE merges in cryptarithm) | default BPE | **GAP: novel, untried, directly relevant to our equation/cipher** |
| grad clipping | **1.5** (found 1e9 → instability + submission-to-submission variance) | **1e9 (off)**, like the public notebook they fixed | **GAP: a concrete fix for run-to-run variance** |
| RL | SimPO/ORPO **failed** (chosen/rejected too similar; rejected prob didn't drop) | never ran RL | agreement: RL doesn't beat SFT here |
| validation | train-synth/eval-original drifted from LB → **prioritized Public LB** | T12 hard-val proxy (also drifts; "trust the LB") | agreement (eval-mistrust) |
| hard cats | explicitly **do not solve** cryptarithm/equation; protect the easy cats | eq-aug coverage 0.86 (still bounded) | agreement: bounded wall |
| merge/soup | not used | **SVD soup → 0.86** | we lead on the soup |

## The four borrowable levers (ranked by EV)
1. **Per-character tokenization for the symbol categories** (HIGH EV, cheap, NOVEL). Force each symbol in
   equation/cipher/cryptarithm to encode as one token (synthetic tokens), so BPE doesn't merge `}!`-style pairs.
   Stabilizes learning on exactly the categories we struggle with — **we never tried this.**
2. **Gradient clipping at 1.5** (MEDIUM-HIGH EV, ~free). We (and the public notebook) use grad-clip = 1e9 = off.
   LB92 traced **submission-to-submission score variance to gradient explosions** (grad-norm 25,089 @ step 107)
   and fixed it with clip 1.5. Worth adopting to reduce our run-to-run noise. *(Note tension: mspawar/LB80 used
   grad-clip off without reporting this — but LB92's evidence (a spike → bad LB) is concrete; cheap to test.)*
3. **Statistics-matched synthetic + gap-closing validation** (MEDIUM EV). Refines our "synthetic dilutes"
   finding: our b1/b2/v15 synth *regressed*, but LB92's synth *helped* because it **matched train.csv
   statistics** (char freq, numeric ranges, transform-method distribution), used a **2.5:1 ratio**, and was
   **QC'd by the synthetic-vs-original eval-gap**. The methodology (train-synth / eval-both / close-the-gap) is
   a principled way to make synthetic data that *transfers*.
4. **Protect-the-easy-cats discipline** (free) — their explicit goal was "don't lose already-solvable problems",
   consistent with our T12 finding that augmentation *regresses* easy/hard cats.

## NOT a gap / we're ahead
- **Model soup** (our 0.86) — they don't use it.
- **Equation/cryptarithm** — they explicitly didn't crack it (the shared bounded wall; cf. LB80's offline-
  crackable-but-discovery-leaky finding, which is the more promising lead).
- **RL** — failed for them (SimPO/ORPO), as for LB80 (GRPO/DPO).

## Cross-writeup note
The grad-clip finding **conflicts with LB80/our "grad-clip off"** — resolve empirically (it's a cheap A/B). The
statistics-matched-synth lever **complements** LB80's "discovery-leakage / forward-executable CoT" lead: better
*coverage+format* data (LB92) + *discovery-not-verify* CoT (LB80) are orthogonal improvements to the same SFT data.
