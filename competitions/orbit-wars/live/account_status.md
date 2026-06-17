# Orbit Wars — live account status

> Read-only refresh. Secrets never printed. latest-2 are the scored active slots per account.
>
> **Cycle 2026-06-17 (prompt 07): fresh refresh BLOCKED by API rate-limit (HTTP 429).** This
> session made heavy read-only ListEpisodes use (266+44 episode discovery, BFS over 18 subs for the
> strong-tier corpus, 310-replay fetch), tripping the public endpoint's rate limit. Added 429
> exponential backoff to `ops/episode_discover.py` (still limited at cycle time). μ below = this
> session's **earlier successful** queries (kuni05 53582503: range 600–1103, median 1077; v4
> 53730511: 44 eps, peak 843, settling ~690–720). **Retry the live refresh next cycle after cooldown.**
> No credentials were read (refresh is the public endpoint; creds only needed for submit, which did
> not occur).

## harry (harrysun2006)
- submissions seen: 10

| slot | file | public μ | status |
|---|---|---:|---|
| latest1 | `submission_kuni.tar.gz` | 1086.5 | neutral |
| latest2 | `main.py` | 649.5 | neutral |

## may (firefly2006)
- submissions seen: 2

| slot | file | public μ | status |
|---|---|---:|---|
| latest1 | `v3_2_coarr.py` | 644.0 | neutral |
| latest2 | `main.py` | 630.1 | neutral |

