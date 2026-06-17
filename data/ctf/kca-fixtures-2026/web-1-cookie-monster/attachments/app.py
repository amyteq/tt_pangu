"""kca-fixtures-2026/web-1-cookie-monster — Flask service.

Deliberately vulnerable: the `session` cookie is a base64-encoded JSON blob
with NO signature. Tamper the `role` field from `user` → `admin`, resubmit,
and GET /admin returns the flag.

This source is committed to the repo as a fixture. The flag VALUE comes from
the FLAG environment variable, NEVER from this file. If FLAG is unset the
app refuses to start so a mis-wired solver run is loud, not silent.

License: MIT.
"""

from __future__ import annotations

import base64
import json
import os
import sys

from flask import Flask, make_response, redirect, request

app = Flask(__name__)

# Refuse to boot without a flag — see docker-compose.yml.
FLAG = os.environ.get("FLAG", "").strip()
if not FLAG:
    print(
        "FATAL: FLAG env var is empty. Refusing to start — see docker-compose.yml for the contract.",
        file=sys.stderr,
    )
    sys.exit(2)


def _encode_cookie(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cookie(token: str) -> dict | None:
    # Tolerant base64 decode — accept missing padding.
    if not token:
        return None
    pad = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode((token + pad).encode("ascii"))
        out = json.loads(raw.decode("utf-8"))
        return out if isinstance(out, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None


@app.route("/")
def root() -> str:
    return (
        "<h1>Cookie Monster's Stash</h1><p>Welcome. <a href='/login'>Log in</a> first; admins get the good stuff.</p>"
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return (
            "<form method='post'>"
            "<input name='username' placeholder='username'/>"
            "<button type='submit'>log in</button>"
            "</form>"
        )
    username = (request.form.get("username") or "").strip()
    if not username:
        return "username required", 400
    # Note the absence of any signing step. The base64 envelope is a fig
    # leaf, not a signature.
    token = _encode_cookie({"username": username, "role": "user"})
    resp = make_response(redirect("/me"))
    resp.set_cookie("session", token, httponly=False, samesite="Lax")
    return resp


@app.route("/me")
def me():
    token = request.cookies.get("session")
    payload = _decode_cookie(token or "")
    if not payload:
        return "no session", 401
    return (
        f"<p>Hello {payload.get('username', '?')!s}. "
        f"Your role is <code>{payload.get('role', '?')!s}</code>.</p>"
        f"<p>Want the cookie stash? Try <a href='/admin'>/admin</a>.</p>"
    )


@app.route("/admin")
def admin():
    token = request.cookies.get("session")
    payload = _decode_cookie(token or "")
    if not payload:
        return "no session", 401
    if payload.get("role") != "admin":
        return "forbidden — admins only", 403
    return f"<pre>FLAG: {FLAG}</pre>"


if __name__ == "__main__":
    # Bind to 0.0.0.0 inside the container; the host-side bind in
    # docker-compose.yml pins to 127.0.0.1 so this is loopback-only.
    app.run(host="0.0.0.0", port=8080)
