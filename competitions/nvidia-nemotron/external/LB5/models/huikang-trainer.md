# @huikang training loop (modified)

- LB5 used a modified **@huikang training notebook** (github.com/tonghuikang/nemotron): changed LR, swapped in their synthetic data, added a stopper for Kaggle's 12h GPU limit; everything else = @huikang's defaults.
- No quantization, no packing (critical for Nemotron's Mamba SSM). A framework choice, not unique to LB5.
