# tool_smoke fixtures

Deterministic, checked-in fixtures used by the `tool-smoke` eval suite
(`tools/kca/eval/suites/tool_smoke/`).

These files MUST NOT be edited without bumping the suite version
(`tools/kca/eval/suites/tool_smoke/__init__.py::SUITE_VERSION`) — the
suite's expected outputs are byte-keyed against this directory.

Files:

- `sample.txt` — three lines, includes `unique-token-XYZ` for the
  grep_workspace match case.
