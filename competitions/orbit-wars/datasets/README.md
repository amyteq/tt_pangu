# Orbit Wars replay dataset pipeline (OW-P1-DATASET-001)

Turns the downloaded top-player replay corpus (~4k episodes / ~20 GB) + new ladder episodes
into clean tables for **candidate scoring / value modeling / safety labels** — NOT a BC
direct-policy clone. Stdlib-only (JSONL/CSV; parquet optional later). **No raw replay JSON is
committed** (`datasets/artifacts/`, `datasets/cache/`, `datasets/fixtures/*.json`, `replays/`
are gitignored).

## Pipeline
```
replays/*.json
  build_episode_index.py   -> episodes.{jsonl,csv} + summary   (metadata, winner, 2p/4p, top-player flag)
  build_step_table.py      -> step_table.csv                   (per (episode,step,player) via core.state.PlayerState)
  build_candidate_dataset.py -> candidates.jsonl               (per candidate launch; FlightOracle safety/first-hit
                                                                + core features + teacher_selected + future value delta)
  build_quality_report.py  -> reports/dataset_quality.md
```
Candidate labels use the deterministic **`core/oracle.py` FlightOracle** + `core/state.py`
features (built in OW-P0-STATE-LEDGER-001) — never duplicate path logic.

## Fixture smoke (this task — small only)
```bash
python -m py_compile competitions/orbit-wars/datasets/*.py
python competitions/orbit-wars/datasets/build_episode_index.py --help
python competitions/orbit-wars/datasets/build_quality_report.py --help
# with a fixture dir (e.g. a few fetched replays):
python competitions/orbit-wars/datasets/build_episode_index.py --replay-root <fixture-dir> --out-root /tmp/orbit_dataset_smoke
python competitions/orbit-wars/datasets/build_step_table.py     --replay-root <fixture-dir> --out-root /tmp/orbit_dataset_smoke --step-stride 20
python competitions/orbit-wars/datasets/build_candidate_dataset.py --replay-root <fixture-dir> --out-root /tmp/orbit_dataset_smoke --use-flight-oracle --step-stride 30 --max-per-step 20
python competitions/orbit-wars/datasets/build_quality_report.py --in-root /tmp/orbit_dataset_smoke --out competitions/orbit-wars/datasets/reports/dataset_quality.md
```
Fetch a replay fixture read-only: `python competitions/orbit-wars/ops/episode_fetch.py --episode-id <id>` (writes to gitignored `replays/`).

## Full 20G corpus (snorlax — do NOT run locally)
```bash
python competitions/orbit-wars/datasets/build_episode_index.py \
  --replay-root /path/to/top_player_replays --out-root /path/to/orbit_dataset_artifacts \
  --top-players "Isaiah,Jake Will,kuni05,..."
python competitions/orbit-wars/datasets/build_candidate_dataset.py \
  --replay-root /path/to/top_player_replays --out-root /path/to/orbit_dataset_artifacts/candidates \
  --use-flight-oracle --step-stride 5
python competitions/orbit-wars/datasets/build_quality_report.py \
  --in-root /path/to/orbit_dataset_artifacts --out competitions/orbit-wars/datasets/reports/dataset_quality.md
```
Input roots are configurable (`--replay-root` / `--out-root`); **no snorlax paths hardcoded**.

## Split / leakage
Split **by episode_id** (~80/10/10), stratified by 2p/4p + top-player flag; future-value labels
read only later steps of the SAME episode. See `schema.md` + `reports/dataset_quality.md`.
