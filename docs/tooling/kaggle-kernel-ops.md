# Kaggle kernel ops: versions, structure, concurrency & throughput

Operating model for Kaggle **code-competition** work (notebooks/kernels that
produce a `submission.zip` / agent file). Learned the hard way while running the
NVIDIA Nemotron and Orbit Wars competitions; encode it so we don't relearn it.

## 1. Kernel & version model — the API is *latest-run only*
Confirmed from the Kaggle CLI:

| Command | Scope |
|---|---|
| `kaggle kernels output` | **latest run only** — no `-v`/version selector |
| `kaggle kernels status` | **latest run only** |
| `kaggle kernels push` | creates a new version and runs it (becomes "latest") |
| `kaggle competitions submit -k <kernel> -v <N> -f <file>` | accepts a version, but only the **latest** run's output is retrievable via API |

**Implication:** an older version's artifact (e.g. `?scriptVersionId=…`) **cannot be
downloaded or inspected via the API**. Pinning a stale `-v` is unreliable. So:
- Submit the **just-pushed (latest)** version; with `kca kaggle submit --kernel …`
  you can **omit `--version`** to mean "latest".
- If you need an earlier candidate to stay retrievable/submittable, **give it its
  own kernel** (next section), don't rely on version numbers.

## 2. Flat structure: one kernel per candidate
Prefer **one kernel per candidate/direction**, with the variant encoded in the slug
(e.g. `nemotron-cot-r32-s400`, `nemotron-cot-r16-s800`), over one kernel with many
versions.

| | 1 kernel + many versions | **Flat: 1 kernel per candidate** |
|---|---|---|
| Retrieve any candidate's artifact | ❌ only latest is API-accessible | ✅ each is its own "latest" |
| Submit/compare an older candidate | ❌ must re-run to make it latest | ✅ submit any kernel directly |
| Run candidates in parallel | ❌ one version at a time | ✅ independent kernels (up to the session cap, §3) |
| Tidy history | ✅ one place | ➖ more kernels (track in KCA's `experiment_runs`) |

Use single-kernel-many-versions **only** for throwaway iteration where you will only
ever submit the latest.

## 3. Concurrency & quota limits (per *account*, global — NOT per competition)
- **Concurrent GPU sessions** are capped per account (recently ~1 on the standard
  tier), shared across *all* competitions.
- **GPU quota** is a floating ~30 h/week, resetting **Saturday 00:00 UTC**.
- Competition-provided accelerators (e.g. Nemotron's `NvidiaRtxPro6000`) *may* have a
  separate allocation — confirm per competition.
- **Submission limits** are **per competition team, per day** (separate from sessions).

Refs: [concurrent GPU session limits](https://www.kaggle.com/general/105509),
[floating GPU quota](https://www.kaggle.com/product-feedback/173129),
[efficient GPU usage](https://www.kaggle.com/docs/efficient-gpu-usage).

## 4. Maximising throughput within the limits
1. **Flat kernels** (§2) so multiple directions run as independent kernels that fill
   the concurrent-session budget instead of serialising versions in one kernel.
2. **Bounded runs** (fixed steps / shorter seq) so scarce GPU-hours cycle across more
   experiments per week.
3. **Keep non-GPU work off the quota** — e.g. Orbit Wars agents need no GPU, so they
   never compete with model-training comps.
4. **Overflow to other compute** (see #83 — explore free/cheaper GPU). **Compute
   targets:**
   - **Kaggle** — baseline; the constraints above.
   - **Local GPUs** (RTX 4090 / 3090, 24 GB) — for models that *fit* (≤~13B bf16,
     ~20B 4-bit, e.g. gpt-oss-20b). Train locally → upload the adapter as a Kaggle
     dataset → `kca kaggle submit --file`. (A 30B model won't fit 24 GB well.)
   - **External** (lightning.ai / Colab / Modal / RunPod / vast.ai) — under evaluation.
5. **Stagger submissions** within the per-day cap (the CLAUDE.md autonomous submission
   strategy already queues extras to the next day).

## 5. Pre-push hygiene (don't waste a multi-hour run)
- Run the **static lint** (`kca kaggle push` gate / `validate_kernel.py`): `ruff` F821
  catches undefined-name typos in seconds.
- **Fail-fast preflight** inside the kernel: exercise the generate/eval path on ONE
  example right after model load, before the long train — runtime type errors surface
  in minutes, not hours.
- **Isolate non-essential steps** (e.g. held-out eval) in their own `try/except` so a
  failure there can't mislabel a successful train or waste the saved adapter.

The `kg-submit` skill runs this section as its pre-push checklist — it is the home of the `kernel-prepush-validate` candidate registered in `competitions/_shared/skill-candidates.md`, whose evidence is that each of three nemotron run-time errors (F821, a `.shape` on the wrong object, a ptxas path) cost about two hours of GPU before it surfaced.

## 6. In-kernel data mount paths — resolve, never hardcode

Moved here from the retired `kaggle-tooling-integration` skill (issue #192). Since roughly February 2026 Kaggle adds a slug chunk to the input path, so the same competition data appears under either form depending on which sources the kernel has attached:

- Competition data: `/kaggle/input/competitions/<competition-slug>/` (newer) or `/kaggle/input/<competition-slug>/` (older).
- Datasets and models: `/kaggle/input/<owner>/<dataset-slug>/`. Utility-script and model mounts land under `/kaggle/usr/lib/...` with the slug **slugified to underscores** — `nvidia-utility-script` becomes `nvidia_utility_script`.

A literal path is therefore a run-time failure waiting for the next mount change. Glob instead, and print the candidates so a miss shows the real layout rather than an opaque "not found":

```python
import glob
cands = (glob.glob("/kaggle/input/competitions/*/train.csv")
         + glob.glob("/kaggle/input/*/train.csv")
         + glob.glob("/kaggle/input/**/train.csv", recursive=True))
train_csv = cands[0]  # raise if empty; print cands for diagnostics
```

A battle-tested resolver lives in `experiments/tpu-getting-started/baseline-tl/baseline.py` (`_resolve_kaggle_input_path`): try `/kaggle/input/<slug>`, then `/kaggle/input/competitions/<slug>`, and on a miss list `/kaggle/input` so the failure names what is actually mounted.
