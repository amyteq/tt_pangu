# Orbit Wars — parallel work queue

> Commands the ladder loop (prompt 07) hands off to run alongside / between cycles. The ladder loop
> does not block on these. Foundation/model/data work parallelizable per the task's parallel policy.

## Queued 2026-06-17 (OW-LADDER-LOOP-001) — strong-tier-teacher corpus → stronger hybrid

**Why:** prompt-06 hybrid_v0 is arena-flat vs the strong tier because its teacher is our own μ~1077
play. The fix is a corpus of genuine strong-tier play (μ≥1200). The discovery manifest is **already
built** this cycle (`datasets/strong_corpus/manifest.json` — 1272 strong-vs-strong episodes, 649 2p /
623 4p, 1068 with a winning teacher seat). Remaining steps (gated on the ListEpisodes 429 cooldown
for the fetch):

```bash
source ~/.venvs/orbit-wars/bin/activate
cd competitions/orbit-wars

# 1. (optional) expand the manifest once the 429 clears — BFS hit the rate limit at 18 subs:
python ops/discover_strong_corpus.py --strong-mu 1200 --teacher-mu 1200 --max-subs 150

# 2. fetch the teacher replays (read-only, public store; bounded — winners-first ordering):
#    reuse the parallel fetcher pattern; cap to ~600 episodes (~3 GB, gitignored).
head -600 datasets/strong_corpus/episode_ids.txt > live/pending_episodes.txt
python ops/episode_fetch.py --drain-queue        # or the 8-worker parallel fetcher

# 3. build the candidate dataset RESTRICTED to teacher (strong) seats via the manifest:
#    build_candidate_dataset.py needs a --seat-manifest <manifest.json> option (TODO — small add:
#    restrict the per-episode seat loop to manifest[episode]["teacher_seats"]).
python datasets/build_candidate_dataset.py --replay-root replays \
  --out-root datasets/artifacts/strong --step-stride 3 --seat-manifest datasets/strong_corpus/manifest.json

# 4. retrain + export + A/B (CPU is fine; snorlax optional, GPU-useless for this MLP):
python models/train_candidate_scorer.py --data-root datasets/artifacts/strong \
  --out-root models/artifacts/<run_id> --max-epochs 80
python models/export_npz.py --run-root models/artifacts/<run_id>
cp models/artifacts/<run_id>/scorer.json agent/hybrid_weights.json
# then re-run the prompt-06 arena A/B harness: OW_HYBRID vs frozen v3.2 + evogen + kuni05 (240g/cell).
# SUBMIT only if it clears VALIDATION #3 (≥+7pt vs the strong tier).
```

**Status:** manifest DONE; fetch/build/train PENDING (429 cooldown + a small `--seat-manifest` add to
`build_candidate_dataset.py`). This is the highest-value runnable direction toward μ≥1200.

## snorlax
Not required for this corpus (CPU-bound dataset build + tiny MLP; numpy/pure-Python online runtime).
Use only if the corpus grows past local capacity. snorlax was OFF this session (paid Songguo card).
