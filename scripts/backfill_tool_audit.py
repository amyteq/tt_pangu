#!/usr/bin/env python
"""Backfill .agent/kca/audit.jsonl into agent_tool_audit.

Idempotent: de-duplicates by (session_id, timestamp, tool_name).
Reads from the JSONL file, inserts each line into the M8 audit table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make tools/kca importable when running from the repo root.
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "tools" / "kca") not in sys.path:
    sys.path.insert(0, str(REPO / "tools" / "kca"))

from tools.kca.db import get_conn  # noqa: E402


def existing_keys(conn) -> set[tuple]:
    with conn.cursor() as cur:
        cur.execute("SELECT session_id::text, ts, tool_name FROM agent_tool_audit")
        rows = cur.fetchall()
    return {(r["session_id"], r["ts"].isoformat(), r["tool_name"]) for r in rows}


def backfill(jsonl: Path, dry_run: bool = False) -> tuple[int, int]:
    if not jsonl.exists():
        print(f"no audit log at {jsonl}")
        return 0, 0
    conn = get_conn()
    try:
        seen = existing_keys(conn)
        inserted = 0
        skipped = 0
        with jsonl.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                key = (
                    rec.get("session_id"),
                    rec.get("timestamp"),
                    rec.get("tool_name"),
                )
                if key in seen:
                    skipped += 1
                    continue
                if dry_run:
                    inserted += 1
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO agent_tool_audit
                          (ts, session_id, job_id, skill_name, tool_name,
                           operation, decision, mode, policy_profile,
                           audit_required, args_hash, extra)
                        VALUES
                          (%s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            rec.get("timestamp"),
                            rec.get("session_id"),
                            rec.get("job_id"),
                            rec.get("skill_name"),
                            rec.get("tool_name"),
                            rec.get("operation"),
                            rec.get("decision"),
                            rec.get("mode", "default"),
                            rec.get("policy_profile", "default"),
                            bool(rec.get("audit_required", False)),
                            rec.get("args_hash", ""),
                            json.dumps(rec.get("extra") or {}),
                        ),
                    )
                    inserted += 1
        conn.commit()
        return inserted, skipped
    finally:
        conn.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", default=".agent/kca/audit.jsonl", type=Path)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    inserted, skipped = backfill(args.jsonl, dry_run=args.dry_run)
    print(f"inserted={inserted} skipped={skipped} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
