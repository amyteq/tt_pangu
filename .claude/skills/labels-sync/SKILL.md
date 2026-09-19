---
name: labels-sync
description: Diff repo labels against .github/labels.yml and prepare a sync plan. Always dry-run by default. Live writes require human approval and the --i-mean-it confirmation token.
---

# labels-sync — preview and (with approval) apply repo label changes

Use this skill to keep GitHub repo labels aligned with `.github/labels.yml`.

## Inputs

- `.github/labels.yml` (source of truth).
- Live label list via `gh label list --json name,color,description`.

## How to run

```bash
# Default: dry-run
python scripts/sync_labels.py --dry-run

# Preview against an empty current set (offline, useful in tests)
python scripts/sync_labels.py --dry-run --no-gh

# Apply (REMOTE WRITE — requires explicit human approval BEFORE running)
python scripts/sync_labels.py --apply --i-mean-it
```

The script will refuse `--apply` without `--i-mean-it` (exit 2).

## Output

```
CREATE <name> (color)
UPDATE <name> (color)
... no-change entries omitted ...
plan: <n> create, <m> update, <k> no-change (of <total> desired)
```

When applied, prints one line per mutation.

## Must not

- Do not run `--apply --i-mean-it` without a human-recorded approval — labels affect every issue/PR that uses them.
- Do not delete labels via this skill. Deletion is an out-of-band human decision; the script intentionally does not implement delete.
- Do not edit `.github/labels.yml` to "match current GitHub state" — the YAML is the source of truth, drift the other way.
- Do not mass-apply labels to existing issues from this skill; that is a separate (and gated) workflow.
