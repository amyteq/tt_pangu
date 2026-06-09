"""h01 prototype — minimum-viable demo for the H0 ("Zero Stack") hackathon.

This package is the *shippable* prototype that backs the M12 hackathon
regression. It is intentionally small: a single FastAPI app that proxies
a chat-style endpoint to whichever LLM provider is configured via env
vars, persists the conversation in Postgres (a stand-in for the
"AWS Database" rule), and exposes a JSON `/health` endpoint suitable
for a Vercel serverless deploy.

The Vercel deploy itself is a human-gated step (no Vercel CLI in the
agent sandbox); see `runs/h01/<run_id>/submission_pack/README.md` for
the manual instructions.

Public surface:
  - ``app``: the FastAPI instance (importable for both `uvicorn` and
    `vercel dev`).
  - ``DEFAULT_DB_URL``: the env var the deploy reads for its Postgres
    DSN (matches the existing `SUPABASE_DB_URL` shape so the same
    secret can be reused).
"""

from __future__ import annotations

from .app import DEFAULT_DB_URL, app

__all__ = ["app", "DEFAULT_DB_URL"]
