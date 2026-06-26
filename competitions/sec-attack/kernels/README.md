# kernels/ — attack.py sources (sec-attack)

The Kaggle submission for this competition is a single **`attack.py`** defining
`AttackAlgorithm(AttackAlgorithmBase)`. We keep named variants here and copy/rename the chosen one to
`attack.py` at submit time (mirrors the nemo flat-kernels convention).

| File | What it is | Status |
|---|---|---|
| `attack_bypass.py` | **Bypass v1** — file-wash + http.post data-blind-spot exfil. Scores **18.0 vs `optimal_public`** (was 0.00). Validate with `../eval/validate_bypass.py`. | working |
| `attack_goexplore.py` | Trimmed Go-Explore floor (snapshot/restore + archive). Scores 0.00 vs `optimal_public` (blocked). | draft |

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
