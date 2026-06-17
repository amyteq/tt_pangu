# Player identity map — Orbit Wars (OW-P0-RESEARCH-001, 2026-06-16)

> Resolves how Kaggle `username` / profile-display-name / team-name / leaderboard row /
> `submissionId` / replay `info.TeamNames[seat]` / replay `rewards[seat]` relate, so episode
> analysis attributes seats correctly. **Headline correction: `flyingfox` = our harrysun2006
> account's profile/display name — it is US, not an external opponent.**

## Identity table
| account alias | Kaggle username | profile / display name | replay `TeamNames` | known submissionIds | evidence | notes |
|---|---|---|---|---|---|---|
| `harry` (`.vscode/.env.harry`) | **harrysun2006** | **flyingfox** | `flyingfox` | **53582503** (adapted-kuni05, μ~1080), **53730511** (v4, μ~700) | Harry confirmed (2026-06-16) flyingfox=harrysun2006 profile; replay `80118852` `info.TeamNames[1]="flyingfox"` + `ListEpisodes(53582503/53730511)` return these as our submissions | **direct (user-confirmed)** — supersedes the earlier "external flyingfox" reading |
| `may` (`.vscode/.env.may`) | **firefly2006** | _tbd_ | _tbd_ | _tbd_ (v3_2_coarr, v3 submitted orbit5) | teamed teammate (`submissions.md`); profile name not yet observed | **inferred / open** — discover by decoding a may-account episode's `TeamNames`, or `ListEpisodes(<may sub id>)` |

## The mapping chain (how to attribute a replay seat to us)
1. **account alias → username:** `.vscode/.env.<alias>` sets `KAGGLE_USERNAME` (loaded read-only via `ops/kaggle_auth.py`; never printed).
2. **username ≠ display name.** The name shown in episodes / leaderboard / replay `TeamNames` is the Kaggle **profile/display name**, which can differ from the account username — this is the whole flyingfox trap (`harrysun2006` displays as `flyingfox`).
3. **submissionId → episodes:** `EpisodeService/ListEpisodes {submissionId}` (`ops/episode_discover.py`) returns `episodes[].agents[]` each with `submissionId`, `reward`, `initialScore`, `updatedScore`.
4. **replay → seat:** the replay JSON (`kaggleusercontent.com/episodes/<id>.json`) has seat-ordered `rewards[]` and `info.TeamNames[]` (+ `info.Agents[].Name`, `info.EpisodeId`).
5. **join:** find our agent in `ListEpisodes.agents` by `submissionId`; take its `reward`; the replay seat is the index in `rewards[]` matching that reward (**unique in 2p**; in **4p** rewards can tie — disambiguate by the known profile name in `TeamNames`, which is why step 2 matters). `ops/track_submission.py` auto-detects the profile this way (and has a known cosmetic mislabel on 4p reward-ties — use the profile name to fix).

## What the flyingfox correction changes (propagate)
- `tracking.md:9` / `EPISODES.md` #3 "verified from **flyingfox's** 205-episode history" = analysis of **our own** harrysun2006/kuni05 submission (`53582503`), **not** an external competitor. The 4p-format finding (ladder is ~half 4p, both update μ) **stands** — it was just mislabeled as external. Re-tag those references as "our kuni05 submission (flyingfox profile)".
- Episode `80118852` (4p FFA we **won**, seat `flyingfox`) is **our** kuni05's game — used in `insights.md` for the 多而小 opening finding.

## Inference vs direct
- `flyingfox=harrysun2006`: **direct** (user-confirmed + corroborated by replay TeamNames + ListEpisodes submissionId join).
- `firefly2006` profile name: **open** — mark any seat attribution on the may account as inferred until its `TeamNames` is observed. Do not assert false external identities.
