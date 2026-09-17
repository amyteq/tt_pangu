# Kaggle Tooling Integration

## Goal
Integrate existing Kaggle helper scripts into the platform without giving the agent unrestricted shell access or undocumented side effects.

## Existing tool categories
Expected existing tools include:
- Python to notebook conversion.
- Notebook to Python conversion.
- Kaggle kernel/notebook push.
- Kaggle notebook submission.
- Competition data download.
- Submission creation and upload.
- Result/submission status retrieval.

## Integration pattern
Wrap scripts behind stable commands or typed tools.

The command namespace as it exists today (`tools/kca/`; the authoritative per-subcommand reference, including which subcommands are still stubs, is [`tools/kca/COMMANDS.md`](../../tools/kca/COMMANDS.md)):

```bash
kca nb to-ipynb path/to/script.py --output path/to/notebook.ipynb
kca nb to-py path/to/notebook.ipynb --output path/to/script.py
kca kaggle download --competition <slug> --path data/<slug>
kca kaggle push --kernel-dir kernels/<name> --dry-run
kca kaggle submit --competition <slug> --file submission.csv --message "..."
kca kaggle score --competition <slug>
kca run record-metric --run-dir runs/<slug>/<run_id> --key <metric> --value <float>
```

There is no `kca notebook` namespace — the converters live under `kca nb` (`tools/kca/nb.py:88-104`). There is no `--requires-approval` flag: approval is decided by Layer A's `KCA_POLICY` / `KCA_ALLOW_REMOTE` gate and the harness `permissions` lists, both documented in `COMMANDS.md` § Safety.

## Safety classes
Each tool must be labeled:
- `read-only`: no local or remote mutation.
- `local-write`: writes local files only.
- `remote-write`: pushes kernels, writes remote metadata, or uploads datasets.
- `submission`: submits to competition leaderboard or equivalent external evaluator.

## Approval policy
- `read-only`: allowed by default.
- `local-write`: allowed in project workspace.
- `remote-write`: human approval required.
- `submission`: human approval required and must include competition slug, file path, message, and expected validation score.

## Artifact layout
Use a standardized run directory:

```text
runs/<competition_slug>/<run_id>/
  config.yaml
  code_snapshot.patch
  metrics.json
  log.txt
  notes.md
  submission.csv
  notebook.ipynb
  artifacts/
```

## Supabase metadata
Record metadata in Supabase, but keep code and large artifacts outside the database. Suggested metadata fields:
- competition slug.
- run id.
- git commit.
- branch.
- model/provider.
- validation metric.
- public/private score if available.
- artifact URIs.
- human approval id.
