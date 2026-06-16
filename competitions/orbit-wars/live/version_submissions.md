# Version ↔ submission ↔ episodes tracking (orbit5)

> Track each version's Kaggle submissionId so `ListEpisodes(submissionId)` + `ops/track_submission.py`
> can follow its match history. Profile name (in episode `TeamNames`) ≠ account name.

| submissionId | version | account | profile (TeamNames) | μ0 | notes |
|---|---|---|---|---|---|
| 53582503 | adapted-kuni05 (`submission_kuni.tar.gz`) | harrysun2006 | **flyingfox** | — | μ~1080; 229 eps (112 2p / 117 4p); the prior "flyingfox history" = US |
| **53730511** | **v4 Scheduler (`v4_scheduler.tar.gz`)** | harrysun2006 | **flyingfox** | 600 | orbit5 candidate UNDER TRACK; loop = `ops/track_submission.py --once --submission-id 53730511` |
| _(may v3)_ | v3 Forecast (`v3_forecast.py`) | firefly2006 | _tbd_ | — | submitted orbit5; id/profile to be discovered if tracked |

**Loop:** every ~4 min, `python ops/track_submission.py --once --submission-id 53730511` downloads the next
unprocessed episode (oldest first), analyzes + tags it (sun/hard-bug/winner-reason), appends to
`live/track_53730511.csv`, and prints a keep/replace recommendation once ≥10 episodes are processed. Decide
early-stop / replace / focus-main-branch after 10–20 episodes.
