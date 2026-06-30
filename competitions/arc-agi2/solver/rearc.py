"""RE-ARC integration — generate ARC-format tasks from Michael Hodel's procedural generators.

RE-ARC (github.com/michaelhodel/re-arc, MIT) ships, for each of the 400 ARC-AGI-1 training
tasks, a `generate_<key>(diff_lb, diff_ub)` that samples a fresh (input, output) example of
that task's rule, and a `verify_<key>(input)` that recomputes the correct output. This lets us
synthesize *unlimited* correct examples per rule — the data that teaches a model to EXECUTE
transformations rather than memorize tasks (the missing lever from the rung-1/2 0% runs;
see ../tracking.md and ../how-it-works.md §5).

This module:
  * loads the generators/verifiers (stubbing matplotlib, which re-arc's utils imports only for
    plotting — generation never touches it);
  * generates verified, non-degenerate, de-duplicated examples per task key;
  * assembles them into ARC-format *tasks* ({"train": k demos, "test": [1 pair]}) so the same
    pretrain/TTT code path (build_pretrain_examples / load_tasks_dir) consumes them unchanged.

Generation is pure-Python CPU — runs locally, no GPU.
"""

from __future__ import annotations

import random
import sys
import types
from pathlib import Path

Grid = list

_HERE = Path(__file__).resolve().parent
DEFAULT_REARC_DIR = _HERE.parent / "data" / "re-arc"


def _install_matplotlib_stub() -> None:
    """re-arc's utils.py does `import matplotlib.pyplot as plt` at module load (for plot_task).
    Generation never calls it, so inject a no-op stub to avoid a heavy plotting dependency."""
    if "matplotlib" in sys.modules:
        return
    mpl = types.ModuleType("matplotlib")
    plt = types.ModuleType("matplotlib.pyplot")
    colors = types.ModuleType("matplotlib.colors")
    colors.ListedColormap = lambda *a, **k: None
    colors.Normalize = lambda *a, **k: None
    mpl.pyplot = plt
    mpl.colors = colors
    sys.modules["matplotlib"] = mpl
    sys.modules["matplotlib.pyplot"] = plt
    sys.modules["matplotlib.colors"] = colors


def load_generators_verifiers(rearc_dir: str | Path = DEFAULT_REARC_DIR):
    """Return ({key: generate_fn}, {key: verify_fn}) from the re-arc checkout."""
    rearc_dir = Path(rearc_dir)
    if not (rearc_dir / "generators.py").exists():
        raise FileNotFoundError(f"{rearc_dir}/generators.py not found. Run solver/fetch_rearc.py first.")
    _install_matplotlib_stub()
    if str(rearc_dir) not in sys.path:
        sys.path.insert(0, str(rearc_dir))
    import generators
    import verifiers

    g = {n[len("generate_") :]: getattr(generators, n) for n in dir(generators) if n.startswith("generate_")}
    v = {n[len("verify_") :]: getattr(verifiers, n) for n in dir(verifiers) if n.startswith("verify_")}
    return g, v


def _to_list_grid(grid) -> Grid:
    return [list(row) for row in grid]


def _valid(grid) -> bool:
    if not grid or not grid[0]:
        return False
    w = len(grid[0])
    for row in grid:
        if len(row) != w:
            return False
        if any(not (0 <= int(c) <= 9) for c in row):
            return False
    return True


def generate_examples(gen, ver, n: int, diff_lb: float, diff_ub: float, max_attempts: int):
    """Generate up to `n` verified, non-degenerate, de-duplicated examples for one task.

    Mirrors re-arc's own generate_dataset acceptance loop: keep an example only if the verifier
    reproduces its output, input != output, and the input grid is new (dedup by value).
    Returns a list of {"input": list-grid, "output": list-grid}. May return < n if the
    generator is slow/failing within max_attempts (caller logs the shortfall).
    """
    out = []
    seen = set()
    attempts = 0
    while len(out) < n and attempts < max_attempts:
        attempts += 1
        try:
            ex = gen(diff_lb, diff_ub)
            i, o = ex["input"], ex["output"]
            if ver(i) != o:
                continue
            if i == o:
                continue
            key = i  # tuple-of-tuples, hashable
            if key in seen:
                continue
            li, lo = _to_list_grid(i), _to_list_grid(o)
            if not (_valid(li) and _valid(lo)):
                continue
            seen.add(key)
            out.append({"input": li, "output": lo})
        except Exception:
            continue
    return out


def build_tasks_for_key(gen, ver, n_tasks: int, demos: int, diff_lb: float, diff_ub: float, max_attempts: int):
    """Assemble `n_tasks` ARC-format tasks for one key: each = `demos` train pairs + 1 test pair,
    all sampled from the SAME generator (so a single consistent rule per task)."""
    need = n_tasks * (demos + 1)
    examples = generate_examples(gen, ver, need, diff_lb, diff_ub, max_attempts)
    tasks = []
    per = demos + 1
    for start in range(0, len(examples) - per + 1, per):
        chunk = examples[start : start + per]
        tasks.append({"train": chunk[:demos], "test": [chunk[demos]]})
    return tasks


def generate_corpus(
    out_dir: str | Path,
    rearc_dir: str | Path = DEFAULT_REARC_DIR,
    n_tasks_per_key: int = 8,
    demos: int = 4,
    diff_lb: float = 0.0,
    diff_ub: float = 1.0,
    seed: int = 0,
    max_attempts_factor: int = 40,
    keys: list[str] | None = None,
    log=print,
):
    """Generate a corpus of ARC-format tasks under out_dir/<key>_<n>.json. Returns counts."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    g, v = load_generators_verifiers(rearc_dir)
    random.seed(seed)
    all_keys = sorted(g.keys()) if keys is None else keys
    import json

    n_written = 0
    short = []
    for ki, key in enumerate(all_keys):
        need = n_tasks_per_key * (demos + 1)
        tasks = build_tasks_for_key(
            g[key], v[key], n_tasks_per_key, demos, diff_lb, diff_ub, max_attempts=need * max_attempts_factor
        )
        if len(tasks) < n_tasks_per_key:
            short.append((key, len(tasks)))
        for ti, task in enumerate(tasks):
            (out_dir / f"{key}_{ti:03d}.json").write_text(json.dumps(task))
            n_written += 1
        if (ki + 1) % 50 == 0:
            log(f"  {ki + 1}/{len(all_keys)} keys, {n_written} tasks written")
    if short:
        log(
            f"NOTE: {len(short)} keys produced fewer than {n_tasks_per_key} tasks (slow/failing generators): "
            f"{short[:8]}{'...' if len(short) > 8 else ''}"
        )
    return {"keys": len(all_keys), "tasks_written": n_written, "short_keys": len(short)}
