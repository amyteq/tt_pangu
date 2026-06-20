# LB10 deterministic program-generated traces

- Per-category symbolic reasoners re-derive the answer from the prompt alone (never reading ground truth), emitting CoT ending `\boxed{}`. Full train, >8192-token filter, prompt-masked (train only on completions).
- Oracle coverage: bit 98.8%, cipher 100%, cryptarithm_deduce 9.0%, cryptarithm_guess 7.9%, equation_deduce 93.1%, equation_guess 41.2%, gravity/numeral/unit 100%; total 90.6%.
- **Keep failed / low-confidence (`rule_unknown`) traces** — excluding them DECREASED accuracy. Priority 2× for fragile modes; low-logprob problems re-added.
- Reasoner code unreleased; not downloaded.
