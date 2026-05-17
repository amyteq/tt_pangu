# KCA tool side-effect levels

This document defines the side-effect levels that M1 wrappers should use. It is intentionally conservative because `kca` will be callable by Claude Code and future runtime competition agents.

## Levels

| Level | Meaning | Examples | Default policy |
|---|---|---|---|
| `read-only` | Reads local files or public/listing data. Does not write files, upload data, submit predictions, or mutate remote state. | `kca tools list`, `kaggle competitions files`, `kaggle competitions submissions` | Allow if it does not read secrets. |
| `local-write` | Writes files inside repo, temp dirs, or configured run artifact roots. Does not mutate remote services. | `kca notebook to-ipynb`, `kca notebook to-script`, `kca runs init` | Allow inside bounded paths. |
| `remote-write` | Uploads, pushes, creates, updates, or deletes remote resources, but is not a formal competition submission. | `kaggle kernels push`, dataset upload/version commands | Require explicit human approval. |
| `submission` | Sends a competition submission or equivalent scored attempt. | `kaggle competitions submit` | Always require explicit human approval; block in automated tests. |

## M1 policy

M1 should implement only `read-only` and `local-write` wrapper behavior by default. `remote-write` and `submission` commands may be documented as reserved commands, but they must not execute without human approval.

## Reserved command examples

```bash
python -m tools.kca kaggle submit ...       # reserved for later; submission
python -m tools.kca kaggle kernel push ...  # reserved for later; remote-write
```

## Approval record placeholder

Until Supabase approval records exist, use local approval notes only when needed:

```text
runs/<competition>/<run_id>/approvals/
  YYYYMMDD-HHMMSS-approval-request.md
```

Do not treat the existence of a local approval note as permission to execute a remote command unless the human explicitly approves in the current session.
