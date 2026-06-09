# data/ctf/ — frozen CTF challenge bundles

This directory holds **deterministic local fixtures** for the M11 CTF workflow
(authorized CTF / lab milestone). Each bundle is a past-event-style challenge
package the agent loop solves end-to-end under reviewer gates, with **zero**
real-network requirement.

Top-level layout:

```text
data/ctf/
  README.md                                  (this file)
  <event-slug>/
    <challenge-slug>/
      challenge.yaml          # metadata; canonical source of truth
      description.md          # human-readable challenge text
      attachments/            # files <1MB committed; bigger gitignored
      docker-compose.yml      # web challenges only
      solver_template.py      # T005 fills in
      expected.sha256         # sha256(<flag bytes>)  flag           ← flag VALUE is NEVER committed
```

## What lives here today (M11-T004)

| Event | Challenge | Category | License | Runtime |
|---|---|---|---|---|
| `kca-fixtures-2026` | `web-1-cookie-monster` | web | CC0-1.0 problem text + MIT runner code | docker-compose on `127.0.0.1:18080` |
| `kca-fixtures-2026` | `crypto-1-tiny-rsa`     | crypto | CC0-1.0 problem text + MIT runner code | in-process (Python + sympy) |

Both challenges are **bespoke, authored in-house** for the M11 milestone. See
`docs/evidence/m11/T004-licensing-brief.md` for the research-brief that
documents why we did not pull from picoCTF / pwnable.kr / CSAW / HackTheBox.

### Author attribution

The fixtures are dedicated under CC0-1.0 (problem text) + MIT (runner code).
No attribution is required for re-use. If you mirror these challenges in
another repo, a back-link is welcome but not mandated.

## `expected.sha256` convention

The flag VALUE for a challenge is **never** committed to this repo. Instead,
each challenge directory ships an `expected.sha256` file whose contents are:

```text
<lowercase hex sha256 digest>  flag
```

That is the literal `sha256sum`-compatible format. To verify a recovered flag
string `f` against the expected digest:

```python
import hashlib, pathlib
expected = pathlib.Path("expected.sha256").read_text().split()[0]
assert hashlib.sha256(f.encode("utf-8")).hexdigest() == expected
```

The solver templates in each challenge directory include this check. The
agent loop (M11-T005) and the e2e refusal-path tests (M11-T008) re-use the
same helper.

### Why hash-only

1. **Flag-value hygiene.** Committing the value would let any future repo
   reader (including the trained LLM!) submit the flag without solving the
   challenge. Hash-only forces "must solve to verify".
2. **Audit-grep gate.** The task spec for M11-T004 mandates that
   `grep -rE "(picoCTF|flag|FLAG)\{" data/ctf/` returns 0 lines other than
   the format-regex hit in each `challenge.yaml`. Hash-only keeps that
   gate green.
3. **Live-event compatibility.** When the same convention is reused for a
   live-event challenge (M11-T007), the expected hash can be left blank or
   computed at solve time — the bundle never has to "know" the flag.

## Web challenge runtime contract

`docker-compose.yml` in any web challenge directory MUST:

- Bind any exposed port to `127.0.0.1` only (NOT `0.0.0.0`). The
  `ctf_scopes` row for a web challenge has `target_urls=["http://localhost:<port>"]`
  and `local_only=true`, so the worker / scope checker refuses any other
  destination.
- Drop ALL Linux capabilities, run as a non-root user, mount the rootfs
  `read_only`, and `tmpfs` `/tmp` if writable scratch space is required.
- Read the flag value from a `FLAG` environment variable. The T005 harness
  generates the flag in-process, exports `KCA_FIXTURE_FLAG`, and `docker
  compose up`s. The flag NEVER appears on disk inside this repo.

## Crypto challenge runtime contract

Crypto challenges run **in-process** — no Docker, no network. The
`solver_template.py` imports `sympy` (and `pycryptodome` if the challenge
calls for AES / EC / etc.); both are pulled in by the project's
`requirements.txt`.

## Gitignore policy (cross-link)

The repo's top-level `.gitignore` includes:

```
data/ctf/*/*/attachments/*.bin
data/ctf/*/*/attachments/*.pcap
data/ctf/*/*/attachments/*.iso
data/ctf/*/*/attachments/*.img
# files >1MB anywhere under data/ctf/ — enforced by a pre-commit hook (TODO)
```

Small text attachments (HTML responses, JSON parameter dumps, ciphertext blobs
<1MB) are committed as-is. Anything larger is staged out-of-tree and the
relevant `challenge.yaml::attachments_path` documents how to obtain it.

## Adding a new bundle

1. Run `research-brief` on the source. Capture license + attribution under
   `docs/evidence/m11/T004-licensing-brief.md` (or a follow-up file for a
   later milestone).
2. Create `data/ctf/<event-slug>/<challenge-slug>/` with the six files in the
   layout above.
3. `kca ctf event register --slug <event-slug> --name '<name>' --notes
   '<license + author>'`
4. `kca ctf scope set --slug ctf-local-<event-slug>-<challenge-slug>
   --authorized '<rationale>' --target-urls '<urls or empty>' --local-only`
5. `kca ctf challenge add --event <event-slug> --slug <challenge-slug>
   --name '<name>' --category <web|crypto|...> --points <int>
   --description @description.md
   --expected-flag-format '<regex>'
   --attachments-path ./attachments
   --scope ctf-local-<event-slug>-<challenge-slug>`
6. Add the bundle's row to the table at the top of this README.

## Active-scoring collision policy

Challenges in `data/ctf/` MUST come from a **past, closed event** OR be
bespoke (authored in-house). Any candidate whose flag value might still be
submittable on a live mirror (picoCTF practice mode, CTFd-replay sites, etc.)
is out of scope. The licensing brief is the canonical record of how each
bundle satisfies this rule.
