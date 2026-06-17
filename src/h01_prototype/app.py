"""Minimal FastAPI app for the H0 ("Zero Stack") prototype.

Endpoints:
  - GET  /health        — liveness probe, no DB call.
  - POST /messages      — append a chat message; persist to Postgres.
  - GET  /messages      — list the latest N messages for a thread.

The schema is created on first call (idempotent) so a fresh Vercel
deploy against a fresh Postgres database boots without manual SQL.

This is **demo code**. It does not authenticate callers, does not rate
limit, and trusts the inbound `thread_id`. Do not run this against a
production secret store — the hackathon prompt is for a demo, not a
production service.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except Exception:  # pragma: no cover — kept importable in CI without fastapi
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment, misc]

    class BaseModel:  # type: ignore[no-redef]
        pass


DEFAULT_DB_URL = "SUPABASE_DB_URL"  # name of the env var read at runtime
_SCHEMA = """
create table if not exists h01_messages (
  id          uuid primary key,
  thread_id   text not null,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  created_at  timestamptz not null default now()
);
create index if not exists h01_messages_thread_idx
  on h01_messages (thread_id, created_at);
"""


def _ensure_schema(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(_SCHEMA)
    conn.commit()


def _connect() -> Any:
    """Lazily import psycopg so the module imports without the driver."""
    dsn = os.environ.get(DEFAULT_DB_URL)
    if not dsn:
        raise RuntimeError(f"{DEFAULT_DB_URL} not set in environment")
    import psycopg  # type: ignore

    return psycopg.connect(dsn)


def create_app() -> Any:
    if FastAPI is None:  # pragma: no cover
        raise RuntimeError("fastapi not installed; cannot build app")

    app = FastAPI(title="h0-zero-stack-prototype", version="0.1.0")

    class MessageIn(BaseModel):
        thread_id: str
        role: str
        content: str

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "h0-zero-stack-prototype"}

    @app.post("/messages")
    def post_message(msg: MessageIn) -> dict[str, str]:
        if msg.role not in ("user", "assistant"):
            raise HTTPException(status_code=400, detail="role must be user|assistant")
        conn = _connect()
        try:
            _ensure_schema(conn)
            mid = str(uuid.uuid4())
            with conn.cursor() as cur:
                cur.execute(
                    "insert into h01_messages (id, thread_id, role, content) values (%s::uuid, %s, %s, %s)",
                    (mid, msg.thread_id, msg.role, msg.content),
                )
            conn.commit()
        finally:
            conn.close()
        return {
            "id": mid,
            "thread_id": msg.thread_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/messages")
    def list_messages(thread_id: str, limit: int = 20) -> dict[str, Any]:
        limit = max(1, min(limit, 200))
        conn = _connect()
        try:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "select id::text, role, content, created_at"
                    " from h01_messages where thread_id = %s"
                    " order by created_at desc limit %s",
                    (thread_id, limit),
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        return {"thread_id": thread_id, "messages": [dict(r) for r in rows]}

    return app


app = create_app() if FastAPI is not None else None
