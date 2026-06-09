"""DB helpers for M12 `teams` + `team_memberships` (read + insert only).

Schema source: `supabase/migrations/0009_m12_competition_type_teams.sql`.

These wrappers are intentionally minimal — M12 ships a read-only team
model (one team, one owner, zero or more members). The invite / role /
delete surface is deferred per ADR-0016 and the M12-T002 task spec
non-goals.

All helpers use `tools.kca.db.get_conn()` so they pick up the same
SUPABASE_DB_URL / REMOTE_WRITE gating as the rest of the kca CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Reuse the existing kca connection plumbing rather than duplicating it.
# tools/kca/db.py lives outside the `src/` package, so we make sure
# `tools/` is on sys.path before importing.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from kca.db import get_conn  # noqa: E402


def create_team(name: str, owner_user_id: str) -> str:
    """Insert a row in `teams` and return its uuid (as string).

    The migration sets `id` to `gen_random_uuid()` by default, so we
    rely on `RETURNING id` rather than generating client-side.
    """
    if not name:
        raise ValueError("team name must be non-empty")
    if not owner_user_id:
        raise ValueError("owner_user_id must be non-empty")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO teams (name, owner_user_id)
                VALUES (%s, %s::uuid)
                RETURNING id
                """,
                (name, owner_user_id),
            )
            row = cur.fetchone()
        conn.commit()
    if row is None:
        raise RuntimeError("INSERT INTO teams returned no row")
    # row_factory=dict_row in tools.kca.db.get_conn -> dict
    return str(row["id"])


def add_team_member(
    team_id: str,
    user_id: str,
    role: str = "member",
) -> None:
    """Insert a membership row. Idempotent on (team_id, user_id) PK."""
    if not team_id or not user_id:
        raise ValueError("team_id and user_id are required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO team_memberships (team_id, user_id, role)
                VALUES (%s::uuid, %s::uuid, %s)
                ON CONFLICT (team_id, user_id) DO NOTHING
                """,
                (team_id, user_id, role),
            )
        conn.commit()


def get_team_members(team_id: str) -> list[dict[str, Any]]:
    """Return all (user_id, role, joined_at) rows for a team."""
    if not team_id:
        raise ValueError("team_id is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT team_id, user_id, role, joined_at
                FROM team_memberships
                WHERE team_id = %s::uuid
                ORDER BY joined_at ASC
                """,
                (team_id,),
            )
            rows = cur.fetchall()
    # row_factory=dict_row gives us list[dict] already.
    return list(rows)
