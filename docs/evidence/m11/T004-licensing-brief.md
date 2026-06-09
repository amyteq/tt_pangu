# M11-T004 — Licensing research-brief for the frozen CTF bundle

_Skill: `research-brief`. Task: pick a permissively licensed past-event source for the
M11 frozen challenge bundle (1 web + 1 crypto)._

## 1. Question answered

What past-event CTF source can we redistribute inside this repo (Apache-2 /
MIT-style root license posture) without (a) running into NC / SA / GPL viral
clauses, (b) attribution-formatting friction, or (c) the risk of accidentally
checking in a flag that is still being scored on some live mirror?

## 2. Sources reviewed (trust labels)

| Source | URL | Trust | Notes |
|---|---|---|---|
| picoCTF archive | https://picoctf.org/, github.com/picoCTF | trusted_public | Carnegie Mellon CMU CyLab. Challenge source is split — some labs MIT-licensed, the **picoctf-problems** repo carries `LICENSE: Creative Commons BY-NC-SA 3.0` for problem text + author attribution required per challenge. NC = problematic for a project that aspires to non-NC reuse, SA = viral. |
| pwnable.kr | https://pwnable.kr | community | No site-wide license posted; reuse of the binaries is unclear. Author-by-author opt-in. |
| CSAW Quals archive (CTFd export) | github.com/osirislab/CSAW-CTF-* | trusted_public | Per-year repo licenses vary — some MIT, some unlicensed. Each year needs an individual check. |
| ångstromCTF archive | github.com/ACMVIT/angstromctf-* | community | License varies per author. |
| Individual past-event releases (e.g. HackTheBox retired) | hackthebox.com | community | Site ToS forbids redistribution of full binaries; writeups OK. NOT redistributable. |
| **Bespoke / authored-in-house** | n/a | **official** (we are the author) | We pick license. Zero attribution friction. Zero active-scoring risk. Zero NC/SA viral risk. |

## 3. Key findings

- **picoCTF** is the canonical "permissively licensed past-event source" the task spec
  names as a candidate. In practice the **problem text** (description + flag layout) is
  under `CC BY-NC-SA 3.0`. NC means "non-commercial" — that's a friction point because
  this repo's root posture is permissive. SA means downstream re-use of the description
  inherits the same NC-SA, which would force `data/ctf/<event>/<challenge>/description.md`
  to carry that license and propagate up. The **infrastructure / runner code** in CMU's
  own picoctf repo is usually MIT, but the *challenges themselves* aren't.
- Many of the canonical picoCTF problems are still in active scoring on
  https://play.picoctf.org/practice (the same flags can be submitted year-round).
  That violates the task spec's "past, CLOSED event with no risk of active scoring"
  constraint.
- pwnable.kr / HackTheBox-retired explicitly disallow redistribution of the full
  challenge bundle; writeups only.
- CSAW Quals archives are year-by-year and many years carry no LICENSE file.
- **Authoring two bespoke challenges in-house under CC0 (problem text) + MIT
  (solver / docker-compose runner) is the lowest-friction path**. We are the author,
  we set the license, no NC clause, no attribution to manage, no active-scoring
  collision, and the bundle is unambiguously redistributable inside this repo.

## 4. Implications for our project / experiment

- **Decision**: M11-T004 ships **two bespoke past-event-style challenges** authored
  for this milestone, under a CC0-1.0 (problem text) + MIT (code) license combo.
- The "event" slug is `kca-fixtures-2026` to flag clearly that this is an in-house
  fixture suite, NOT a re-publication of someone else's past event.
- Document the licensing chain in `data/ctf/README.md` so a future reader doesn't
  have to re-derive that this fixture set is in-house and unencumbered.
- The picoCTF / CSAW / pwnable.kr / ångstromCTF options remain documented here so a
  future milestone (e.g. an M11-followup that wants more challenges) doesn't repeat
  this analysis. If a future milestone wants to add picoCTF challenges, it must:
  - confirm the challenge is from a **closed** event (not on play.picoctf.org practice);
  - copy the `CC BY-NC-SA 3.0` license verbatim into the challenge dir;
  - add per-challenge author attribution;
  - and accept the NC/SA constraint propagating to the bundle.

## 5. Open questions / verification needed

- None blocking T004. The bespoke path side-steps every open question.

## 6. Suggested next action

Proceed with the bespoke fixture bundle:
- Event: `kca-fixtures-2026` (notes: "in-house bespoke fixtures, CC0+MIT, authored
  for M11-T004").
- Web: `web-1-cookie-monster` — auth bypass via tampered admin cookie (HTTP-only,
  intended solution path; docker-compose on localhost:18080).
- Crypto: `crypto-1-tiny-rsa` — small-prime RSA decryption (in-process, sympy).
- License headers in every shipped file. `expected.sha256` carries the flag hash
  (not the value).
