# External attributed sources — Orbit Wars

> Read-only references to **public, attributed** third-party agents studied for design
> learning. Raw pulled source is **NOT vendored** here (kept out of git, like
> `agent/versions/kuni05/`); only attribution + a re-pull command are recorded.

## kuni05 "Producer Agent" (LB 1240.5)
- **Kernel:** `kuni05/lb-1240-5-orbit-wars-producer-agent-submission` (id **121702304**, author **kuni05**)
- **URL:** https://www.kaggle.com/code/kuni05/lb-1240-5-orbit-wars-producer-agent-submission
- **Availability (2026-06-16):** public, read-only pull **OK** (notebook + metadata).
- **Re-pull (read-only):**
  ```bash
  kaggle kernels pull kuni05/lb-1240-5-orbit-wars-producer-agent-submission -p <dest> -m
  ```
- **Local reconstruction:** `agent/versions/kuni05/` (gitignored; rebuilt via `arena/_reconstruct_pkg.py`). Requires `torch`.
- **System study:** `discussions/2026-06-16-kuni05-system-study.md` (rules + exact flow-diff planner; not a NN).
- **Reuse policy:** conceptual learning only; any code reuse must be labeled attributed-public-source, not our from-scratch agent.
