# tests_orbit fixtures

Smokes here mostly **generate** their own board states from the engine
(`kaggle_environments.make("orbit_wars")`) rather than committing large replay JSONs.

- **No large replay JSONs are committed.** `test_replay_79228928_decode_smoke` looks for
  `tests_orbit/fixtures/79228928.json` or `competitions/orbit-wars/replays/79228928.json`
  (the latter is gitignored) and **skips cleanly if absent**. To run it, fetch the replay
  read-only: `python competitions/orbit-wars/ops/episode_fetch.py --episode-id 79228928`
  (writes to the gitignored `replays/`), or drop a compact slice here as `79228928.json`.
- Hand fixtures (e.g. `test_ledger_handfixture_capture_matches_replay_planet`) are inline
  tiny cases cross-checked against `core.geometry.replay_planet`.

Run: `python -m pytest competitions/orbit-wars/tests_orbit -q`, or run a file directly:
`python competitions/orbit-wars/tests_orbit/test_flight_oracle.py`.
