# M11-T004: Frozen past-event challenge bundle (1 web + 1 crypto)

## Milestone
M11: authorized CTF / lab workflow.

## Goal
Bundle a small set of permissively licensed past-event CTF challenges under
`data/ctf/<event-slug>/<challenge-slug>/` so the M11 agent loop (T005), the
reviewer-gate exercise (T006), and the dry-run test suite (T008) all have
deterministic local fixtures. M11 ships **one web** + **one crypto**
challenge; pwn / rev / forensics / OSINT are taxonomy-supported but not
fixtured here.

## Read first

1. M11-T001 closeout (`ctf_events` / `ctf_challenges` / `ctf_scopes` shape)
2. M11-T003 closeout (`kca ctf event register` + `challenge add` flow)
3. `.gitignore` — current `data/` rules
4. `.claude/skills/ctf-sandbox/SKILL.md` — workflow expectations
5. The picoCTF archive (`https://picoctf.org/`) or another permissively
   licensed past-event source — research-brief licensing first.
6. `data/spaceship-titanic/manifest.json` (M9 manifest precedent)
7. `data/tpu-getting-started/manifest.json` (M10 manifest precedent,
   when T001 of M10 lands)

## Scope

1. **Licensing research-brief.** Use the `research-brief` skill against
   the candidate past-event source. Confirm:
   - License permits redistribution / inclusion in a CC-BY / Apache-2-
     compatible repo.
   - Source author attribution requirements (record in
     `data/ctf/README.md`).
   - The chosen challenges contain NO real-world flag values that
     might still be in active scoring elsewhere (use a past, closed
     event).

2. **Bundle layout.** For each of the two chosen challenges, create:

   ```text
   data/ctf/<event-slug>/<challenge-slug>/
     challenge.yaml          # metadata; canonical source of truth
     description.md          # human-readable challenge text
     attachments/            # files <1MB; bigger entries gitignored
     docker-compose.yml      # web challenge only
     solver_template.py      # T005 fills in
     expected.sha256         # checksum of the known-good flag (NOT the flag)
   ```

   `challenge.yaml` schema (validated by the `kca ctf challenge add`
   command):

   ```yaml
   slug: <slug>
   event: <event-slug>
   name: <name>
   category: web | crypto
   points: <int>
   description: <inline or @description.md>
   expected_flag_format: '^picoCTF\{[^}]+\}$'   # or event-specific regex
   attachments_path: ./attachments
   remote_endpoint: null                         # local-only
   scope_ref: ctf-local-<event-slug>             # the scope row slug
   license: <SPDX-id> (<attribution>)
   ```

3. **Web challenge.** Pick a challenge whose intended solution path is
   HTTP-only (auth bypass, IDOR, SSRF, command injection, etc.). The
   bundle ships a `docker-compose.yml` that brings up the vulnerable
   service on a private Docker network (no host port exposure beyond
   localhost). The solver_template.py uses `httpx` against
   `http://localhost:<port>` only.

4. **Crypto challenge.** Pick a small RSA / classical-cipher / weak-RNG
   challenge that runs entirely in-process (no docker). The solver_
   template.py imports `pycryptodome` / `sympy` as needed.

5. **Scope rows.** Insert one `ctf_scopes` row per challenge via
   `kca ctf scope set`:
   - web: `local-only=true`, `target_urls=["http://localhost:8080"]` (or
     whatever port the docker-compose exposes), `expires_at=null`.
   - crypto: `local-only=true`, `target_urls=[]` (no network).
   Both scope slugs are referenced from the matching `challenge.yaml`
   `scope_ref`.

6. **Event row.** Insert one `ctf_events` row for the past event via
   `kca ctf event register`. Record source attribution in the `notes`
   column.

7. **`data/ctf/README.md`.** Document the licensing chain, the two
   bundled challenges, and the `expected.sha256` convention (the hash
   covers the flag string, so anyone running the harness can verify
   a recovered flag without the bundle revealing the value).

8. **Gitignore additions.** Update `.gitignore` to gitignore
   `data/ctf/*/*/attachments/*.{bin,pcap,iso,img}` and any file >1MB
   under `data/ctf/`. Small text fixtures (HTML responses, ciphertext
   blobs) are committed.

## Non-goals

- Do not have the agent solve the challenges here. T005 owns the solve
  loop.
- Do not bundle more than 2 challenges. Web + crypto only.
- Do not bundle pwn / rev / forensics fixtures (out-of-scope follow-up).
- Do not register the chosen event as the live submission target —
  T007 picks a separate, **currently open** CTFtime event.
- Do not commit flag values, `expected.sha256` notwithstanding.

## Acceptance criteria

- `data/ctf/<event-slug>/<web-slug>/` and
  `data/ctf/<event-slug>/<crypto-slug>/` exist with all six files
  named in scope step 2.
- `kca ctf event list --json` shows the registered past event.
- `kca ctf challenge list --event <event-slug> --json` shows both
  challenges.
- `kca ctf scope list --json` shows both scope rows.
- `data/ctf/README.md` documents the licensing chain.
- `.gitignore` covers oversize / binary attachments.
- `git status` shows no untracked files >1MB under `data/ctf/`.
- No flag value is committed anywhere (manual grep:
  `grep -rE "(picoCTF|flag|FLAG)\{" data/ctf/` returns 0 lines, or only
  format-regex hits in `challenge.yaml`).

## Permissions

- Local file writes under `data/ctf/`, `.gitignore`,
  `data/ctf/README.md`.
- LOCAL_WRITE DB inserts via `kca ctf event register` / `challenge add`
  / `scope set`.
- `research-brief` skill invocation for licensing check.
- No real external network calls (the past-event source download can
  happen via `tools/kca/research_fetch.py` HTTP path — covered by
  the `web_fetch` allow gate).

## Closeout format

```
M11-T004 closeout
  Source: <event name> — <SPDX license> (<attribution>)
  Bundled: data/ctf/<event-slug>/{<web-slug>,<crypto-slug>}/
  Web: docker-compose up brings vulnerable service on localhost:<port>
  Crypto: in-process; <stdlib + extra deps>
  Scope rows: 2 (web local+localhost; crypto local-only no targets)
  Event row: <event-uuid>
  data/ctf/README.md: licensing + bundle list documented
  Gitignore additions: <list of new patterns>
  Flag-value grep: 0 hits (or N format-regex-only hits in challenge.yaml)
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M11-T005 ready to start
```

## Related issues

- M11 proposal issue (TBD). M11-T004 closes the "frozen bundle" bullet.

## Stop condition

Stop after 80 turns. If the chosen past-event source has license terms
that disallow inclusion in this repo, halt and propose an alternative
source (pwnable.kr / CSAW Quals / bespoke-author challenges). Do not
bundle anything with unclear licensing. If a candidate flag value
appears to still be in active scoring on the source site, switch to a
different challenge.
