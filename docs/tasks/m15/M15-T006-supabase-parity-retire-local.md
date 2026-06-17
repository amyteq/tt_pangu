# M15-T006: cloud Supabase migration parity check / retire local Docker (issue #64)

## Milestone
M15: close the goal loop on real LB signal + ADR-0018 hardening.

## Goal
Resolve the dual-DB-path tech-debt: verify cloud Supabase migration parity
(0001–0012 all applied on the cloud project) and **retire the local Docker
Supabase stack** docs/config (issue #64's recommended option (a)) — or document
the parity procedure if (b) is chosen. Update the docs that still point at the
retired local container.

Infra cleanup; sequence after the ADR-0018 schema work (T004 adds 0012) so the
parity check covers the final migration set.

## Read first
1. Issue #64 (acceptance criteria — pin to the issue body; note the (a)/(b)
   choice and the recommendation of (a)).
2. M15-T004 closeout (migration 0012 — the latest migration the parity check
   must cover).
3. `docs/milestone-loop-protocol.md` §3 (the DSN note that still points at the
   retired local `supabase-db` container — memory `reference_supabase_db`).
4. `docs/tooling/local-supabase.md` (the local Docker setup doc to update).
5. `supabase/migrations/` (full list 0001–0012) + `docker-compose.yml`
   (if present) + `README.md` install section.

## Scope
1. **Parity check**: verify migrations 0001–0012 are all applied on the cloud
   project (`qyoprtshfhfzrczlwbyv`); record the result.
2. **Decision (a or b)** per issue #64 (recommendation: (a) retire local):
   - If **(a)**: update `docs/milestone-loop-protocol.md` §3 to point at the
     cloud DSN as the sole DB path; update the `README.md` install section;
     remove or mark `docker-compose.yml` deprecated; confirm memory note already
     aligned. Update `docs/tooling/local-supabase.md` accordingly (retire /
     redirect).
   - If **(b)**: add a one-shot replay script (`scripts/local_db_sync.py`) that
     replays 0001–0012 against the local container + a CI "verify local
     container parity" check; document the parity precondition.

## Non-goals
- No schema changes (T004 owns 0012). No new migrations.
- No change to the cloud project's data — read-only parity verification.

## Acceptance criteria
_Pinned to issue #64:_
- Decision recorded (a or b).
- If (a): `docs/milestone-loop-protocol.md` §3 updated; `README.md` install
  section updated; `docker-compose.yml` removed or marked deprecated; memory
  note aligned.
- If (b): a one-shot script replays 0001–0012 against the local container; CI
  gains a "verify local container parity" check.
- Cloud parity (0001–0012 applied) verified and recorded.

## Allowed / forbidden paths
- ALLOWED: `docs/milestone-loop-protocol.md` (§3 DSN note),
  `docs/tooling/local-supabase.md`, `README.md` (install section),
  `docker-compose.yml` (remove / deprecate, if (a)),
  `scripts/local_db_sync.py` + `.github/workflows/*` (if (b)).
- FORBIDDEN: `supabase/migrations/**` (no new/edited migrations),
  `tools/kca/**` code changes.

## Permissions
- LOCAL_WRITE (Supabase) read-only for the parity check; pooler needs
  `dangerouslyDisableSandbox=true`.
- No real Kaggle / LLM.

## Closeout format
```
M15-T006 closeout
  Parity: migrations 0001–0012 applied on cloud (qyoprtshfhfzrczlwbyv) — verified
  Decision: (a) retire local Docker  [or (b) replay script + CI parity check]
  Docs: protocol §3 DSN note + docs/tooling/local-supabase.md + README install updated
  docker-compose.yml: removed/deprecated  [or local_db_sync.py + CI check added]
  Acceptance: PASS
  Next: M15-T007 (live autonomous submit validation)
```

## Related issues
- #64 (cloud Supabase migration parity check or retire local Docker container).

## Stop condition
Stop after 60 turns. HALT and ask if:
- The cloud parity check shows a migration is NOT applied — surface it; applying
  a missing migration is a schema action that needs explicit confirmation.
- Removing `docker-compose.yml` would break a CI job that still references the
  local container — pin the reference and ask before deleting.
