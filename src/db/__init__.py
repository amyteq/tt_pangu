"""src.db — first-class DB helpers package.

The canonical DB layer for kca is `tools/kca/db.py` (M2–M8). New milestone
schema modules may register their helpers here when the milestone task spec
calls for a package-style import path (e.g. M11-T001 → `src.db.ctf`).

Each submodule MUST import `tools/kca/db.py` (added to sys.path by callers)
to reuse the shared `get_conn()` + connection-management primitives so the
remote-write gate, autocommit posture, and dict_row factory stay aligned.
"""
