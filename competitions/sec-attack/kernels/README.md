# kernels/ — attack.py sources (sec-attack)

The Kaggle submission for this competition is a single **`attack.py`** defining
`AttackAlgorithm(AttackAlgorithmBase)`. We keep named variants here and copy/rename the chosen one to
`attack.py` at submit time (mirrors the nemo flat-kernels convention).

| File | What it is | Status |
|---|---|---|
| `attack_kaggle.py` | **Kaggle submission attack** — verifies templates against the REAL in-kernel agent, keeps firing families, fans out across benign sinks. Embedded into `sec-attack-jed.ipynb`. | pushed |
| `sec-attack-jed.ipynb` + `kernel-metadata.json` | The submission notebook (T4 GPU, internet off, competition data attached) — runs `JEDAttackInferenceServer`. Built by `build_kaggle_nb.py`. | pushed |
| `attack_bypass.py` | **Bypass v1** — file-wash + http.post data-blind-spot exfil. Scores **18.0 vs `optimal_public`** (proxy). Validate with `../eval/validate_bypass.py`. | working |
| `attack_goexplore.py` | Trimmed Go-Explore floor (snapshot/restore + archive). Scores 0.00 vs `optimal_public` (blocked). | draft |

## Kaggle push
```bash
python competitions/sec-attack/kernels/build_kaggle_nb.py          # regenerate .ipynb + metadata
kaggle kernels push -p competitions/sec-attack/kernels             # push to harrysun2006/sec-attack-jed
```
The submission is a **notebook** that writes `attack_kaggle.py` to `/kaggle/working/attack.py` and runs the JED
inference server. Real scoring happens on the competition rerun (not "Save & Run All"). `attack_kaggle.py` is
**conservative on candidate count** (the replay phase hard-raises at its budget — too many multi-turn chains crashes
the eval to 0); tune `MAX_CANDIDATES` up after the first run's logs show real per-candidate replay time.

## Local workflow (no GPU needed for the deterministic agent)
```bash
pip install aicomp-sdk==3.1.2
cp competitions/sec-attack/kernels/attack_goexplore.py attack.py
aicomp validate redteam attack.py
aicomp evaluate redteam attack.py --env gym --agent deterministic --budget-s 60
python competitions/sec-attack/kernels/attack_goexplore.py   # quick smoke test (prints in-run finding count)
```
- Always trust **`aicomp evaluate`** (replay-based) over the in-`run()` finding count — only the replay scores.
- Use `--env gym` for Kaggle parity. Real-agent runs (`--agent gpt_oss`/`gemma_4`) need a GPU (snorlax 4090 / may 3090).

## Don'ts
- Don't rely on env state your message chain doesn't reproduce — candidates are replayed fresh.
- Don't generate breadth by appending counters to the same URL/query — cell features are bucketed (see `../research.md` §5).
