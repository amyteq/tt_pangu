"""ARC-AGI-2 TTT solver — model-agnostic core.

This package holds the parts of the test-time-training pipeline that do NOT need a GPU and
are fully unit-testable on CPU:

  augment.py    D8 geometric transforms + color permutations, with exact inverses (AIRV)
  serialize.py  grid <-> compact string encoding + task prompt formatting
  ttt_data.py   leave-one-out augmented training-example construction for per-task TTT
  selection.py  Product-of-Experts / vote selection of the 2 pass@2 candidates
                (named `selection`, not `select`, to avoid shadowing the stdlib `select`)

The GPU layer (load base model, per-task LoRA fine-tune, DFS decode) plugs in on top via a
small interface and is selected once a base model + compute target are chosen (see
../ttt-recipe.md and ../tasks.md T2).
"""
