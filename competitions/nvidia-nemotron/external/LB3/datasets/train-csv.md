# Competition train.csv

- 9,500 labeled problems, 7 categories. Already in our local data.
- LB3 holds out 10% stratified-by-category (954 val rows), excludes val rows AND augmented samples derived from them (leakage control). This validation **tracks the private LB**, not the public LB ("wall of 0.86").
