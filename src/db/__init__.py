"""src.db — first-class DB helpers package.

The canonical DB layer for kca is `tools/kca/db.py` (M2–M8). New milestone
schema modules may register their helpers here when the milestone task spec
calls for a package-style import path:

- `src.db.ctf` — M11-T001 CTF tables (`ctf_events`, `ctf_challenges`,
  `ctf_scopes`, `ctf_attempts`).
- `src.db.teams` — M12-T002 hackathon teams (`teams`, `team_memberships`).

Thin, intent-revealing wrappers over `tools.kca.db.get_conn()` so worker
code and tests can read / write specific tables without re-implementing
connection plumbing. Each submodule MUST import `tools/kca/db.py` (added
to sys.path by callers) to reuse the shared `get_conn()` +
connection-management primitives so the remote-write gate, autocommit
posture, and dict_row factory stay aligned.
"""
