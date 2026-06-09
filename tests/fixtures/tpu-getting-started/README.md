# tpu-getting-started — M13-T004 stub fixture

Minimal stub notebook used by the `kernel-dryrun` eval suite
(`tools/kca/eval/suites/kernel_dryrun/`).

M10-T007 has not yet landed on `main`; when it does, that task's
fixture should supersede this stub. The fixture is intentionally
tiny — one markdown cell plus two trivial code cells — because the
M13-T004 suite only needs a valid `.ipynb` for the kg-nb round-trip
case (no data, no model code, no actual TPU usage).

Files:

- `notebook.ipynb` — the source notebook the round-trip case
  converts to percent-format `.py` and back.

If M10-T007 later adds a richer fixture (real TPU starter notebook
+ supporting CSVs), drop this stub — the `kernel-dryrun` suite
only needs the path to resolve to a readable `.ipynb`.
