# Version ↔ submission ↔ episodes tracking (orbit5)

> Track each version's Kaggle submissionId so `ListEpisodes(submissionId)` + `ops/track_submission.py`
> can follow its match history. Profile name (in episode `TeamNames`) ≠ account name.

| submissionId | version | account | profile (TeamNames) | μ0 | notes |
|---|---|---|---|---|---|
| **53769740** | **v3.2 rotation-fix** (`v3_2_rotfix_submission.tar.gz`) | harrysun2006 | flyingfox | — | **2026-06-17 B11 fix** (planet-phase off-by-one; fixes fleet-into-sun). Validated +31pt vs evogen (13.8→45%). latest-1; replaces hybrid_v0 buggy probe. **Track:** `track_submission.py --once --submission-id 53769740` |
| **53769744** | **v3.2 rotation-fix** (`v3_2_rotfix_submission.tar.gz`) | firefly2006 | _tbd_ | — | **2026-06-17 B11 fix** (may lane). same tarball. latest-1. **Track:** `track_submission.py --once --submission-id 53769744` |
| **53767016** | **hybrid_v0** (`hybrid_v0_submission.tar.gz`) | harrysun2006 | flyingfox | — | **2026-06-17 ladder-probe** (OW-LADDER-LOOP-001). v3.2 + model candidate re-ranker (OW_HYBRID baked). latest-1; evicts kuni05 from scored latest-2. neutral, awaiting episodes. **Track:** `track_submission.py --once --submission-id 53767016` |
| **53767026** | **hybrid_v0** (`hybrid_v0_submission.tar.gz`) | firefly2006 | _tbd_ | — | **2026-06-17 ladder-probe** (may lane). same tarball. latest-1; evicts coarr from scored latest-2. neutral, awaiting episodes. **Track:** `track_submission.py --once --submission-id 53767026` |
| 53582503 | adapted-kuni05 (`submission_kuni.tar.gz`) | harrysun2006 | **flyingfox** | — | μ~1080; 229 eps; **evicted from scored latest-2 by 53767016** (2026-06-17, replaceable <1200) — re-lockable by re-submitting the tarball if the probe underperforms |
| **53730511** | **v4 Scheduler (`v4_scheduler.tar.gz`)** | harrysun2006 | **flyingfox** | 600 | orbit5: settled **~690–720 (peak 843)**; now latest-2 (with hybrid_v0) |
| 53730517 | v3 Forecast (`v3_forecast.py`) | firefly2006 | _tbd_ | — | may; ~678; now latest-2 (with hybrid_v0) |
| 53582925 | v3.2+coarr (`v3_2_coarr.py`) | firefly2006 | _tbd_ | — | ~644.6; **evicted from scored latest-2 by 53767026** (2026-06-17) |

**Loop:** every ~4 min, `python ops/track_submission.py --once --submission-id 53730511` downloads the next
unprocessed episode (oldest first), analyzes + tags it (sun/hard-bug/winner-reason), appends to
`live/track_53730511.csv`, and prints a keep/replace recommendation once ≥10 episodes are processed. Decide
early-stop / replace / focus-main-branch after 10–20 episodes.

## v4 (53730511) — first-10-episode tracking result + DECISION (2026-06-16)
- **μ trajectory:** 600 → 739.5 → 637.9 → 766.3 → **842.9 (peak)** → 754.1 → 676.7 → 724.2 → 702.7 → 689.9
  (**net +90 over the μ600 start**, oscillating, settling ~690–720).
- **Record:** 2p **4W-3L**; 4p **1×1st + 2×2nd** (4p is ~half the ladder and v4 places respectably).
- **Opponents seen:** self/teammate (flyingfox), Benaya Trabelsi, AlphaOrbit, HuaLQin, Liran, JojiZhou,
  Raiyan Bin Rafique, + 3 4p fields. Real pool, not just self-play.
- **🔑 Key finding (validates the orbit5 thesis):** the LOCAL arena called v4 "parity with v3.2" (~640), but the
  REAL ladder shows v4 settling **~690–720 (peaked 843) — our BEST own-agent ladder result to date**, clearly
  above old v3.2 (640) and the v3 peak (686). Confirms the local arena under-discriminates our cluster; the
  ladder is the right judge.
- **DECISION: KEEP v4 + FOCUS THE MAIN BRANCH (T20 early-game massing).** v4 won't reach the >1200 keep-a-slot
  bar (strong-tier cliff intact), so there is nothing to gain by replacing it — it is our strongest own agent
  and stays as the own-agent slot. No resubmit/spray. kuni05 anchor (53582503, 1079.7) + coarr untouched.
  Next dev effort goes to T20 (mass earlier from the opening), the empirically-pinpointed lever.
- **Tooling notes (minor):** (a) the 7 "hard-bug" tags are the BENIGN sun-proximity heuristic — worst dist always
  ≥10.0 (fleets survive), and the 3 losses had the FEWEST sun ticks (1–4), so it is NON-causal; the analyzer's
  `SUN_DANGER = SUN_R+2 = 12` threshold is over-sensitive. (b) `track_submission.py` mislabels the `profile`
  column on some 4p rows (reward-tie seat detection picks the wrong seat) — cosmetic; μ/placement come correctly
  from ListEpisodes. Both are low-priority tooling tweaks, not agent bugs.
