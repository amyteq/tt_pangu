"""submission_checklist — READ_ONLY inspector for hackathon submission packs.

Input:
  competition_id (uuid str)  — competitions.id
  run_id         (uuid str)  — experiment_runs.id (the run that built the pack)

Output (deterministic, JSON-serialisable):
  [{"item": <name>, "status": "done|todo|blocked", "evidence": <path-or-blank>}, ...]

The checklist is driven by the `competitions.submission_format` jsonb
column (populated by M12-T003's `register_competition`). Each key in
that jsonb list becomes a checklist item; the tool then scans
`runs/<slug>/<run_id>/submission_pack/` for a matching file. M12 ships
four standard items in addition to the per-platform `submission_format`
keys:

  - README.md
  - demo-plan.md
  - source/        (directory)
  - submission-checklist.json   (set by the skill on a subsequent pass)

For each item:
  * `done`   — file (or directory, for `source`) exists and is non-empty.
  * `todo`   — file is missing (or empty).
  * `blocked`— the submission_pack directory itself is missing or the
               competition row cannot be loaded. (Recorded once, against
               a sentinel `__pack__` item, so the caller knows whether
               to halt the skill outright.)

This module is READ_ONLY: it never writes to the DB, never mutates the
submission_pack, and never hits the network.

The function shape (`build_checklist`) is the testable surface; the
argparse `cmd_checklist` entry point is a thin wrapper for the CLI /
agent registry. Determinism is a load-bearing acceptance check
(M12-T008 downstream): same inputs ALWAYS produce the same list, with
the same ordering. We sort canonical items first (alphabetical), then
emit `submission_format` keys in source order with case-insensitive
dedup against the canonical set.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect


# The four canonical items every hackathon pack carries, independent of
# what competitions.submission_format declares. Ordering is fixed
# (alphabetical) so the test fixture stays stable.
CANONICAL_ITEMS: tuple[tuple[str, str], ...] = (
    # (display_name, relative_path_under_submission_pack)
    ("README.md", "README.md"),
    ("demo-plan.md", "demo-plan.md"),
    ("source/", "source"),
    ("submission-checklist.json", "submission-checklist.json"),
)


def _repo_root() -> Path:
    # tools/kca/submission_checklist.py -> repo root is parents[2]
    return Path(__file__).resolve().parents[2]


def _runs_root() -> Path:
    """Resolve runs/ relative to repo root, with KCA_RUNS_ROOT override.

    The env override lets the test suite point at a tmp_path-built
    fixture directory without touching the real runs/ tree.
    """
    override = os.environ.get("KCA_RUNS_ROOT")
    if override:
        return Path(override)
    return _repo_root() / "runs"


def _pack_dir(slug: str, run_id: str, *, runs_root: Path | None = None) -> Path:
    root = runs_root or _runs_root()
    return root / slug / run_id / "submission_pack"


def _status_for_path(p: Path) -> str:
    """`done` iff the path exists and is non-empty. Otherwise `todo`."""
    if not p.exists():
        return "todo"
    try:
        if p.is_dir():
            # A directory counts as `done` if it contains at least one
            # file (recursively). Empty `source/` is `todo`.
            for entry in p.rglob("*"):
                if entry.is_file():
                    return "done"
            return "todo"
        # Regular file: needs non-zero size to count as done.
        return "done" if p.stat().st_size > 0 else "todo"
    except OSError:
        return "todo"


def _evidence_for_path(p: Path, *, status: str, runs_root: Path) -> str:
    """Return a stable relative-evidence string. Empty when status='todo'."""
    if status != "done":
        return ""
    try:
        return str(p.relative_to(runs_root.parent))
    except ValueError:
        # Path is outside the runs_root.parent (e.g. tmp tests). Fall
        # back to a runs/<slug>/<run_id>/... relative shape.
        try:
            return str(p.relative_to(runs_root))
        except ValueError:
            return str(p)


def _dedup_format_keys(format_keys: Iterable[Any], canonical_paths: set[str]) -> list[str]:
    """Normalize `submission_format` items to strings, dedup case-insensitively.

    Drop any key whose lower-case form matches a canonical item's path /
    display name — we already emit those above, no need for a duplicate
    row.
    """
    canonical_lower = {p.lower().rstrip("/") for p in canonical_paths}
    canonical_lower |= {name.lower().rstrip("/") for name, _ in CANONICAL_ITEMS}
    out: list[str] = []
    seen: set[str] = set()
    for raw in format_keys or []:
        if raw is None:
            continue
        key = str(raw).strip()
        if not key:
            continue
        lower = key.lower()
        if lower in canonical_lower or lower in seen:
            continue
        seen.add(lower)
        out.append(key)
    return out


def build_checklist(
    *,
    slug: str,
    run_id: str,
    submission_format: list | None,
    runs_root: Path | None = None,
) -> list[dict[str, str]]:
    """Pure function: returns the deterministic checklist.

    Does not read the DB. Callers should load `competitions.submission_format`
    + `competitions.slug` and pass them in. This keeps the function
    test-friendly (no monkeypatching of `db.*`) and lets the CLI entry
    point handle the DB I/O once.
    """
    runs_root = runs_root or _runs_root()
    pack = _pack_dir(slug, run_id, runs_root=runs_root)

    items: list[dict[str, str]] = []

    # Sentinel: the pack directory itself.
    if not pack.is_dir():
        # Single blocked row; downstream callers halt the skill.
        return [
            {
                "item": "__pack__",
                "status": "blocked",
                "evidence": "",
            }
        ]

    # Canonical items first (alphabetical by display name, fixed order).
    for display, relpath in CANONICAL_ITEMS:
        target = pack / relpath
        status = _status_for_path(target)
        evidence = _evidence_for_path(target, status=status, runs_root=runs_root)
        items.append(
            {
                "item": display,
                "status": status,
                "evidence": evidence,
            }
        )

    # submission_format keys (source order, dedup vs canonical).
    canonical_paths = {relpath for _, relpath in CANONICAL_ITEMS}
    extra_keys = _dedup_format_keys(submission_format or [], canonical_paths)
    for key in extra_keys:
        # Treat the key as a filename under submission_pack/. Stable
        # mapping: lowercase, preserve as-is for human display.
        target = pack / key
        status = _status_for_path(target)
        evidence = _evidence_for_path(target, status=status, runs_root=runs_root)
        items.append(
            {
                "item": key,
                "status": status,
                "evidence": evidence,
            }
        )

    return items


def _load_competition_row(competition_id: str) -> dict[str, Any]:
    """Best-effort load of the competitions row by id.

    Returns a dict with at least `slug` and `submission_format`. Raises
    KeyError when the row is absent. The function only imports `db` at
    call time so the module stays importable in CI environments that
    have no DB driver.
    """
    import db as _db  # type: ignore

    with _db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, submission_format
                  FROM competitions
                 WHERE id = %s::uuid
                """,
                (competition_id,),
            )
            row = cur.fetchone()
    if not row:
        raise KeyError(f"competition id not found: {competition_id}")
    # psycopg's default cursor returns tuples; map to dict by column index.
    return {
        "id": str(row[0]),
        "slug": row[1],
        "submission_format": row[2],
    }


def _emit(payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


def cmd_checklist(args: argparse.Namespace) -> int:
    """CLI entry: `kca submission checklist --competition-id ... --run-id ...`.

    DB-gated path: if SUPABASE_DB_URL is unset and the caller didn't
    provide `--slug` + `--submission-format-json`, we return EXIT_RUNTIME
    with a clear error. This keeps the no-DB unit-test path purely
    function-level (build_checklist) and gates the CLI on a configured DB.
    """
    competition_id = args.competition_id
    run_id = args.run_id

    slug = getattr(args, "slug", None)
    submission_format: list | None = None
    if slug is None:
        if not os.environ.get("SUPABASE_DB_URL"):
            return _emit(
                {
                    "ok": False,
                    "error": "SUPABASE_DB_URL not set; pass --slug + --submission-format-json to skip DB.",
                    "side_effect": SideEffect.READ_ONLY.value,
                },
                EXIT_RUNTIME,
            )
        try:
            row = _load_competition_row(competition_id)
        except KeyError as exc:
            return _emit(
                {
                    "ok": False,
                    "error": str(exc),
                    "side_effect": SideEffect.READ_ONLY.value,
                },
                EXIT_RUNTIME,
            )
        except Exception as exc:
            return _emit(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "side_effect": SideEffect.READ_ONLY.value,
                },
                EXIT_RUNTIME,
            )
        slug = row["slug"]
        submission_format = row["submission_format"]
    else:
        sf_json = getattr(args, "submission_format_json", None)
        if sf_json:
            try:
                submission_format = json.loads(sf_json)
            except json.JSONDecodeError as exc:
                return _emit(
                    {
                        "ok": False,
                        "error": f"--submission-format-json: {exc}",
                        "side_effect": SideEffect.READ_ONLY.value,
                    },
                    EXIT_RUNTIME,
                )

    checklist = build_checklist(
        slug=slug,
        run_id=run_id,
        submission_format=submission_format,
    )
    return _emit(
        {
            "ok": True,
            "competition_id": competition_id,
            "run_id": run_id,
            "slug": slug,
            "checklist": checklist,
            "side_effect": SideEffect.READ_ONLY.value,
        }
    )


def add_parsers(sub: argparse._SubParsersAction) -> None:
    """Wire `kca submission checklist` into the top-level CLI."""
    p = sub.add_parser(
        "submission",
        help="Submission-pack inspector (READ_ONLY; M12-T004).",
    )
    sp = p.add_subparsers(dest="submission_cmd", required=True)
    chk = sp.add_parser(
        "checklist",
        help="Emit a per-item checklist for a run's submission_pack.",
    )
    chk.add_argument("--competition-id", dest="competition_id", required=True)
    chk.add_argument("--run-id", dest="run_id", required=True)
    chk.add_argument(
        "--slug",
        default=None,
        help="Override the slug lookup; required when SUPABASE_DB_URL is unset.",
    )
    chk.add_argument(
        "--submission-format-json",
        dest="submission_format_json",
        default=None,
        help="Inline JSON list of submission_format keys; pairs with --slug.",
    )
    chk.set_defaults(func=cmd_checklist)


# Re-exported for tests + the agent tool registry.
__all__ = [
    "CANONICAL_ITEMS",
    "add_parsers",
    "build_checklist",
    "cmd_checklist",
]
