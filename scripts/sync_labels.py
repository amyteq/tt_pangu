#!/usr/bin/env python3
"""Sync GitHub repo labels from `.github/labels.yml`.

Default mode is `--dry-run`. Live writes require `--apply` AND a typed
confirmation token, because label mutations are remote writes that affect
shared collaboration state.

Usage:
  python scripts/sync_labels.py --dry-run                    # default; preview only
  python scripts/sync_labels.py --apply --i-mean-it          # actually mutate labels
  python scripts/sync_labels.py --apply                      # refused without the token

Behaviour:
  - Read `.github/labels.yml` (list of {name, color, description}).
  - Read current labels via `gh label list --json name,color,description`.
  - Print a diff: CREATE / UPDATE / NO-CHANGE per label.
  - With `--apply --i-mean-it`, call `gh label create` or `gh label edit`
    as needed. Never deletes labels (deletion is an out-of-band human
    decision).

Exit codes:
  0 — dry-run completed, or apply completed with no errors
  1 — input/CLI error
  2 — apply refused (missing --i-mean-it)
  3 — gh call failed
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    sys.stderr.write("PyYAML required: pip install -e '.[dev]' (already a project dep)\n")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = REPO_ROOT / ".github" / "labels.yml"


def load_desired() -> list[dict]:
    if not LABELS_PATH.is_file():
        sys.stderr.write(f"missing: {LABELS_PATH}\n")
        sys.exit(1)
    with LABELS_PATH.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, list):
        sys.stderr.write("labels.yml must be a top-level list\n")
        sys.exit(1)
    for entry in data:
        if not isinstance(entry, dict) or "name" not in entry or "color" not in entry:
            sys.stderr.write(f"invalid label entry: {entry!r}\n")
            sys.exit(1)
    return data


def gh(*args: str) -> str:
    """Run a `gh` command, return stdout. Exit 3 on failure."""
    cmd = ["gh", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(f"gh failed: {' '.join(cmd)}\n{result.stderr}")
        sys.exit(3)
    return result.stdout


def load_current() -> dict[str, dict]:
    raw = gh("label", "list", "--json", "name,color,description", "--limit", "500")
    return {row["name"]: row for row in json.loads(raw or "[]")}


def plan(desired: list[dict], current: dict[str, dict]) -> list[tuple[str, dict]]:
    """Return a list of (action, label_dict). Actions: create | update | nochange."""
    out: list[tuple[str, dict]] = []
    for entry in desired:
        name = entry["name"]
        existing = current.get(name)
        if existing is None:
            out.append(("create", entry))
            continue
        # Compare color/description; GitHub returns color without '#'.
        ex_color = (existing.get("color") or "").lower().lstrip("#")
        de_color = (entry.get("color") or "").lower().lstrip("#")
        ex_desc = existing.get("description") or ""
        de_desc = entry.get("description") or ""
        if ex_color == de_color and ex_desc == de_desc:
            out.append(("nochange", entry))
        else:
            out.append(("update", entry))
    return out


def apply_plan(actions: list[tuple[str, dict]]) -> int:
    n_create = n_update = 0
    for action, entry in actions:
        name = entry["name"]
        if action == "create":
            gh(
                "label",
                "create",
                name,
                "--color",
                entry["color"],
                "--description",
                entry.get("description", ""),
            )
            n_create += 1
            print(f"created: {name}")
        elif action == "update":
            gh(
                "label",
                "edit",
                name,
                "--color",
                entry["color"],
                "--description",
                entry.get("description", ""),
            )
            n_update += 1
            print(f"updated: {name}")
    print(f"\napplied: {n_create} created, {n_update} updated")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync repo labels from .github/labels.yml")
    parser.add_argument("--dry-run", action="store_true", default=True, help="(default) print plan only")
    parser.add_argument("--apply", action="store_true", help="execute the plan (requires --i-mean-it)")
    parser.add_argument(
        "--i-mean-it",
        action="store_true",
        help="confirmation token; required with --apply because label sync is a remote write",
    )
    parser.add_argument(
        "--no-gh",
        action="store_true",
        help="skip reading current labels (offline diff against empty set)",
    )
    args = parser.parse_args(argv)

    desired = load_desired()
    current: dict[str, dict] = {} if args.no_gh else load_current()
    actions = plan(desired, current)

    n = {"create": 0, "update": 0, "nochange": 0}
    for action, entry in actions:
        n[action] += 1
        if action != "nochange":
            print(f"{action.upper():>7}  {entry['name']}  ({entry['color']})")
    print(f"\nplan: {n['create']} create, {n['update']} update, {n['nochange']} no-change (of {len(desired)} desired)")

    if not args.apply:
        print("\n(dry-run; pass --apply --i-mean-it to write to GitHub)")
        return 0

    if not args.__dict__["i_mean_it"]:
        sys.stderr.write("\nrefusing to write: --apply requires --i-mean-it (remote write).\n")
        return 2

    return apply_plan(actions)


if __name__ == "__main__":
    sys.exit(main())
