# Competition Test Cases

## Goal
Use past and open competitions as a regression suite for the platform.

## Test case levels

### Level 0: Tool smoke tests
Purpose: validate conversion, logging, and local execution.
- Convert Python to notebook and back.
- Run a tiny script.
- Parse metrics.
- Record a run.

### Level 1: Classic Kaggle tabular practice
Purpose: fast, deterministic end-to-end loop.
Examples:
- Titanic.
- House Prices.
- Digit Recognizer.

Expected checks:
- Download or locate data.
- Train baseline.
- Generate valid submission format.
- Do not submit unless human approves.

### Level 2: Notebook/kernel workflow
Purpose: validate kernel push/submission tooling.
Expected checks:
- Build notebook from source.
- Validate metadata.
- Dry-run push.
- Human approval gate before remote write.

### Level 3: Reasoning-heavy competition
Purpose: validate research, long-context reasoning, experiment tracking, and notebook execution.
Candidate examples:
- AI Mathematical Olympiad-style competitions.
- NVIDIA Nemotron Model Reasoning Challenge-style competitions.

Expected checks:
- Read competition page/rules.
- Extract metric and submission constraints.
- Create local evaluation harness where possible.
- Track hypotheses and results.
- Enforce daily submission budget.

### Level 4: Authorized CTF sandbox
Purpose: validate CTF workflow without unsafe real-world activity.
Expected checks:
- Use local challenge files or containers only.
- Record commands and writeup.
- Deny external scanning or credential theft.

## Regression rule
A test case should be considered passed only if the agent produces:
- A run directory.
- Metrics or explicit reason metrics are unavailable.
- A concise analysis note.
- A proposed next action.
- No unapproved external side effects.
