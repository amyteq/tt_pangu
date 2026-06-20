# LB13 rebalanced teacher traces

- @huikang-style synthetic with improved reasoners. **Rebalanced so teacher-correct : teacher-incorrect = 1:1** (fallback tasks were overrepresented) — i.e. **keeps incorrect traces** (echoes LB10's "excluding failures hurts").
- **Robust aggregation**: an operation is a valid candidate if it matches ≥1 relevant example (not all) — tolerates symbol transcription errors.
- Cryptarithm augmented ~3× using equation_numeric problems as seeds. Teacher oracle: bit 89.7%, equation_deduce 95.3%, equation_guess 50.7%, cipher/trivials 100%, cryptarithm ~10%; total 89.4%.
- Reasoner code unreleased; not downloaded.
