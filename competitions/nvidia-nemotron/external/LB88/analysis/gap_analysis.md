# LB88 / 88th Place — Gap analysis (us vs the 88th-place writeup)

> **Same writeup as LB92** — this is a condensed gap analysis; the fuller prior pass is `../LB92/analysis/gap_analysis.md`.
> "our approach" cites `competitions/nvidia-nemotron/{notes,submissions,equation-frontier,bugs}.md`. "writeup" cites `../writeup/lb88-writeup.md`.

| area | our approach | writeup approach | gap | lesson |
|---|---|---|---|---|
| corpus construction | huikang corpus + small synth (diluted). (submissions.md:31) | Statistics-matched synthetic, 2.5:1 synth:original, gap-QC'd. | Ours diluting; theirs matched + validated | Match train statistics; validate the synth-vs-original gap |
| reasoning traces | bit 10%, equation 0.4% coverage. (notes.md:72-73) | OPP reasoner unchanged (87.8%); focus on faithful reproduction. | We change the recipe; they protect the reasoner | "Don't lose solvable problems" |
| synthetic data | b1/b2/v15 regressed. (submissions.md:31) | Statistics-matched + gap QC + 2.5:1 → transfers. | The exact fix for our dilution | Statistics-matched, gap-validated synth can help |
| cryptarithm / bit | ~10% / ~90% unsolved. (bugs.md:14, notes.md:73) | ~9% / 85.1% (reasoner unchanged; chose not to attack). | Both weak | cryptarithm/bit is the wall (LB1/LB3 needed) |
| equation | global cipher (EQ-0/EQ-2′). (equation-frontier.md:209-228) | equation_deduce 90.8% (OPP baseline). | Premise corroboration (7th) | equation deduce solvable |
| tokenization | default BPE. (notes.md) | **Per-character synthetic tokens** for symbols. | We never tried per-char | Novel lever on our symbol weak spot |
| training stability | grad-clip 1e9-off. (notes.md) | **grad-clip 1.5**. | Cheap A/B | Tame submission variance |
| validation | T12 late; trust LB aggregate. (submissions.md:76-78) | train-synth/eval-original; overfit → prioritize Public LB late. | Both end at "trust unseen LB" | A train-derived metric overfits as the generator improves |
| RL | never ran. (notes.md:107) | SimPO/ORPO failed (chosen≈rejected). | RL didn't pay off | Skip RL here (cf. LB5) |
| merge | soup +0.01. (insights.md:44) | no merge. | — | — |

## Why our attempts didn't close the gap
- **synthetic (b1/b2/v15):** diluting; LB88's **statistics-matched + gap-QC + 2.5:1** is the fix.
- **equation:** equation_deduce 90.8% — 7th corroboration that deduce is solvable (re-test, no GPU).
- **tokenization:** we never tried **per-character tokens** for symbols — a concrete untried lever.
- **stability:** our 1e9-off grad clip may cause submission variance; A/B clip 1.5.

## High-value vs not-worth-it
**High value:** statistics-matched synthetic + synth-vs-original gap QC + 2.5:1; **per-character tokenization** for symbols; **grad-clip 1.5**; protect already-solvable categories.
**Not worth:** RL (SimPO/ORPO — chosen≈rejected); attacking new bit/cryptarithm without LB1/LB3 structure.
