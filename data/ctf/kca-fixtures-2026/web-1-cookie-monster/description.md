# web-1-cookie-monster

**Category:** web
**Points:** 100
**Author:** kca-fixtures (in-house, CC0-1.0 problem text + MIT runner code)

## Story

Cookie Monster set up a tiny admin portal for managing his cookie stash. He swears
the site is secure — he even encoded the session cookie in base64 so nobody can
read it! Surely no one will figure out he forgot to *sign* it. Right?

## Goal

Recover the flag from the admin dashboard at `/admin`. The flag format is
`kca{...}`.

## Service

A Flask app brought up via `docker-compose up` on `http://localhost:18080`. The
service is bound to `localhost` only — no host port outside loopback.

Endpoints:

- `GET /` — public landing page.
- `POST /login` — accepts any non-empty `username` field and issues a session
  cookie. **No password check** (you don't need credentials).
- `GET /admin` — gated on the session cookie's `role` claim. If `role == "admin"`,
  returns the flag.

## Intended path

1. Log in as any non-admin user (`username=guest`).
2. Inspect the session cookie. Notice it is base64-encoded JSON, *not* signed.
3. Decode → flip `role` from `user` to `admin` → re-encode → resubmit.
4. `GET /admin` returns the flag.

The solver template (`solver_template.py`) sketches the HTTP flow with `httpx`.
M11-T005 fills in the actual exploit and asserts the recovered flag's SHA-256
matches `expected.sha256`.

## Out of scope

- The Docker container is meant for local solve only. No `EXPOSE` beyond what
  `docker-compose.yml` declares, and the compose file pins to `127.0.0.1:18080`.
- Do NOT pen-test the same vulnerability against any third-party site. The
  vulnerable pattern (unsigned session cookies) is shipped purely as an
  educational fixture.
