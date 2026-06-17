"""kca explore: exploration-batch lifecycle for the goal-driven loop (M14-T003).

Implements ADR-0020 §4 (search-space YAML cross-product) + §5 (batch
lifecycle: init -> fan-out -> screen -> rank -> promote). This module owns the
``kca explore`` CLI surface and the search-space expansion / dir-templating /
fake-screening logic; every DB write goes through the T001 helpers in
``db.py`` (``create_experiment`` / ``create_experiment_run`` /
``record_metric`` / ``set_run_analysis_jsonb`` / ``get_run_analysis_jsonb`` /
``get_active_goal``).

Subcommands:
  - ``kca explore init``  — expand the search-space, mint ``exploration_batch_id``,
    write ``batch.yaml`` + one ``experiments/<comp>/<run-id>/`` per cell with a
    templated ``baseline.py`` + ``cell.yaml``, and create one ``experiment_runs``
    row per cell with ``status='planned'`` + ``analysis_jsonb.exploration_batch_id``.
    Refuses with ``ACTIVE_BATCH_EXISTS`` if the goal already has a batch whose
    runs are still ``planned`` / ``screened`` (init/fan-out/screen states).
  - ``kca explore run``   — fan out local screenings via a process pool with a
    GPU-memory check; ``--dry-run`` produces synthetic, deterministic metrics
    with NO real training and NO Kaggle call. Each cell gets ``holdout_accuracy``,
    ``macro_f1``, ``train_seconds`` recorded and ``status`` flipped to ``screened``.
  - ``kca explore rank``  — list screened cells sorted by ``holdout_accuracy``,
    marking which qualify (``holdout >= goal_screen_threshold``, default
    0.90 x ``target_lb_score``).
  - ``kca explore prune`` — GC ``status='planned'`` runs that were never screened.

NO Kaggle push / submit anywhere in this module (T004 / T008 own pushes). The
fan-out's ``--dry-run`` path never imports tensorflow or touches the network.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import shutil
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect

# Batch lifecycle stage (ADR-0020 §5). The DB ``run_status`` enum only knows
# {queued,running,succeeded,failed,cancelled} (no planned/screened), so the
# explore-specific lifecycle stage lives in analysis_jsonb.explore_stage and
# the enum column carries a faithful mechanical state. See M14-T009 finding #2.
STAGE_PLANNED = "planned"
STAGE_SCREENED = "screened"
# Enum value written to experiment_runs.status for each stage.
_ENUM_FOR_STAGE = {
    STAGE_PLANNED: "queued",  # row created, cell not yet screened
    STAGE_SCREENED: "succeeded",  # screened (dry-run trainer ran)
}
# A batch is "active" (refuses a second init) while it owns runs in any of
# these stages — the init/fan-out/screen window of ADR-0020 §5.
_ACTIVE_RUN_STAGES = (STAGE_PLANNED, STAGE_SCREENED)

# Default screen threshold = 0.90 x target_lb_score (ADR-0020 §5 step 4).
_DEFAULT_SCREEN_FRACTION = 0.90

# Per-cell VRAM estimate (MiB) for the concurrency cap (ADR-0020 §5 step 2).
_EST_CELL_VRAM_MIB = 4096


def _emit(ok: bool, payload: dict, exit_code: int = EXIT_OK) -> int:
    print(json.dumps({"ok": ok, **payload}, ensure_ascii=False, default=str))
    return exit_code


def _load_db():
    import db as _db

    return _db


def _repo_root() -> Path:
    # tools/kca/explore.py -> repo root is two parents up from tools/kca/.
    return Path(__file__).resolve().parent.parent.parent


def _comp_dir(slug: str) -> Path:
    return _repo_root() / "experiments" / slug


# ---------------------------------------------------------------------------
# Minimal YAML reader for the search-space axes file (ADR-0020 §4).
#
# We avoid a hard PyYAML dependency: the axes file is a small, well-shaped
# document (a few list axes + a sample directive + a seed_template path). A
# tiny purpose-built parser keeps `kca explore` importable on a bare env and
# keeps the expansion deterministic + testable. If PyYAML is installed we use
# it (more permissive); otherwise the fallback handles the documented shape.
# ---------------------------------------------------------------------------


def _load_search_space(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("search-space YAML must be a mapping at top level")
        return data
    except ImportError:
        return _parse_search_space_fallback(text)


def _coerce_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw in ("", "null", "~"):
        return None
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if (raw[0], raw[-1]) in (("'", "'"), ('"', '"')) and len(raw) >= 2:
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_inline_list(raw: str) -> list:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    return [_coerce_scalar(p) for p in inner.split(",")]


def _parse_inline_map(raw: str) -> dict:
    inner = raw.strip()[1:-1].strip()
    out: dict = {}
    if not inner:
        return out
    for part in inner.split(","):
        if ":" not in part:
            continue
        k, _, v = part.partition(":")
        out[k.strip()] = _coerce_scalar(v)
    return out


def _parse_search_space_fallback(text: str) -> dict:
    """Parse the documented axes shape without PyYAML.

    Supported (ADR-0020 §4):
      axes:
        backbone:    [a, b, c]      # inline list
        image_size:  [192, 224]
      sample:        full           # or {random: N, seed: S}
      seed_template: path/to/baseline.py
    """
    data: dict = {"axes": {}}
    lines = text.splitlines()
    in_axes = False
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped.startswith("axes:"):
            in_axes = True
            rest = stripped[len("axes:") :].strip()
            if rest:  # inline `axes: {...}` not supported in fallback
                raise ValueError("inline axes mapping unsupported; use a block")
            continue
        if indent == 0:
            in_axes = False
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if key == "sample":
                if val.startswith("{"):
                    data["sample"] = _parse_inline_map(val)
                else:
                    data["sample"] = _coerce_scalar(val)
            elif key == "seed_template":
                data["seed_template"] = _coerce_scalar(val)
            elif key:
                data[key] = _coerce_scalar(val)
            continue
        if in_axes and indent > 0:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("[") and val.endswith("]"):
                data["axes"][key] = _parse_inline_list(val)
            else:
                data["axes"][key] = [_coerce_scalar(val)]
    return data


# ---------------------------------------------------------------------------
# Cross-product expansion (deterministic) — ADR-0020 §4.
# ---------------------------------------------------------------------------


def expand_cells(spec: dict) -> list[dict]:
    """Expand the axes mapping into an ordered list of cell dicts.

    Full cross-product by default. ``sample: {random: N, seed: S}`` draws N
    cells deterministically (sorted full product, seeded shuffle, take N, then
    re-sorted by the original product order so output ordering is stable).
    """
    axes = spec.get("axes") or {}
    if not isinstance(axes, dict) or not axes:
        raise ValueError("search-space must declare a non-empty 'axes' mapping")
    axis_names = list(axes.keys())
    value_lists = []
    for name in axis_names:
        vals = axes[name]
        if not isinstance(vals, (list, tuple)):
            vals = [vals]
        if len(vals) == 0:
            raise ValueError(f"axis '{name}' has no values")
        value_lists.append(list(vals))

    product = [dict(zip(axis_names, combo)) for combo in itertools.product(*value_lists)]

    sample = spec.get("sample", "full")
    if sample in (None, "full", "all"):
        return product
    if isinstance(sample, dict):
        n = sample.get("random")
        if n is None:
            raise ValueError("sample mapping must set 'random: N'")
        n = int(n)
        seed = int(sample.get("seed", 0))
        if n >= len(product):
            return product
        # Deterministic: index the product, shuffle indices with the seed, take
        # the first N, then re-sort by original index so output order is stable.
        rng = random.Random(seed)
        indices = list(range(len(product)))
        rng.shuffle(indices)
        chosen = sorted(indices[:n])
        return [product[i] for i in chosen]
    raise ValueError(f"unsupported sample directive: {sample!r}")


def _cell_run_id(batch_id: str, cell: dict) -> str:
    """Stable, human-readable run id for a cell within a batch.

    ``<batch8>-<axis-value-slug>`` keeps dirs sortable + diff-reviewable; a
    short hash suffix guarantees uniqueness if two cells slugify identically.
    """
    parts = [f"{k}{_slug(v)}" for k, v in cell.items()]
    base = "-".join(parts)[:48]
    h = hashlib.sha1((batch_id + json.dumps(cell, sort_keys=True)).encode("utf-8")).hexdigest()[:6]
    return f"{batch_id[:8]}-{base}-{h}"


def _slug(value: Any) -> str:
    s = str(value)
    return "".join(c if c.isalnum() else "_" for c in s).strip("_")


# ---------------------------------------------------------------------------
# baseline.py templating from the seed (ADR-0020 §4).
# ---------------------------------------------------------------------------

_BACKBONE_KERAS = {
    "mobilenet_v2": "MobileNetV2",
    "mobilenetv2": "MobileNetV2",
    "efficientnet_b0": "EfficientNetB0",
    "efficientnetb0": "EfficientNetB0",
    "resnet50": "ResNet50",
    "densenet121": "DenseNet121",
    "xception": "Xception",
}


def _render_cell_baseline(seed_src: str, cell: dict, run_id: str) -> str:
    """Prepend an axis-override header to the seed baseline source.

    The seed reads module-level constants (IMAGE_SIZE, EPOCHS) and selects a
    backbone in build_model(). Rather than rewrite the seed, we prepend a
    generated header that the seed picks up: we re-assign IMAGE_SIZE / EPOCHS /
    BATCH_SIZE after the seed sets them by appending an override block. Since
    the seed defines constants top-down and uses them lower in the file, the
    clean approach is to make the cell's baseline import the seed values then
    override. To stay a single self-contained file (Kaggle kernel push later),
    we instead substitute the axis constants inline via a header that the
    templated copy applies BEFORE the seed body, and the seed body is included
    verbatim with its constant lines neutralised.
    """
    header_lines = [
        "# === kca explore cell override (M14-T003) — GENERATED, do not edit ===",
        f"# run_id: {run_id}",
        f"# cell: {json.dumps(cell, sort_keys=True)}",
        "# These constants override the seed's defaults for this search-space cell.",
        "import os as _kca_os",
        f"_KCA_CELL = {json.dumps(cell, sort_keys=True)}",
    ]
    if "image_size" in cell:
        size = int(cell["image_size"])
        header_lines.append(f"_KCA_IMAGE_SIZE = ({size}, {size})")
    if "epochs" in cell:
        header_lines.append(f"_KCA_EPOCHS = {int(cell['epochs'])}")
    if "batch_size" in cell:
        header_lines.append(f"_KCA_BATCH_SIZE = {int(cell['batch_size'])}")
    if "backbone" in cell:
        keras_name = _BACKBONE_KERAS.get(str(cell["backbone"]).lower(), "MobileNetV2")
        header_lines.append(f"_KCA_BACKBONE = {keras_name!r}")
    header_lines.append("# The seed body follows; its constant defaults are overridden where the")
    header_lines.append("# seed reads _KCA_* (the templated copy rewrites the matching lines).")
    header_lines.append("# =====================================================================")
    header = "\n".join(header_lines) + "\n\n"

    body = seed_src
    # Rewrite the seed's constant defaults to consume the cell overrides when
    # present. These are line-anchored substitutions against the known seed
    # shape; if the seed changes shape the override simply no-ops (the cell.yaml
    # remains the source of truth for what was requested).
    if "image_size" in cell:
        body = body.replace(
            "IMAGE_SIZE = (192, 192)",
            "IMAGE_SIZE = _KCA_IMAGE_SIZE  # kca: overridden by search-space cell",
        )
    if "epochs" in cell:
        body = body.replace(
            "EPOCHS = 3  # local sanity: 3; Kaggle kernel runner may bump (see KERNEL_EPOCHS)",
            "EPOCHS = _KCA_EPOCHS  # kca: overridden by search-space cell",
        )
    if "backbone" in cell:
        keras_name = _BACKBONE_KERAS.get(str(cell["backbone"]).lower(), "MobileNetV2")
        body = body.replace(
            "    base = tf.keras.applications.MobileNetV2(",
            f"    base = tf.keras.applications.{keras_name}(  # kca: cell backbone",
        )
    return header + body


# ---------------------------------------------------------------------------
# Fake / dry-run screening — synthetic, deterministic, NO training, NO Kaggle.
# ---------------------------------------------------------------------------


def fake_screen(cell: dict, run_id: str, seed: int = 0) -> dict:
    """Deterministic synthetic screening metrics for a cell.

    Pure function of (cell, run_id, seed): no training, no GPU, no network.
    Produces plausible holdout_accuracy / macro_f1 / train_seconds so tests +
    the dry-run path exercise the full pipeline without a backbone train.
    """
    digest = hashlib.sha256(
        (json.dumps(cell, sort_keys=True) + "|" + run_id + "|" + str(seed)).encode("utf-8")
    ).hexdigest()
    # Map two hex windows into [0,1) deterministically.
    acc_jitter = int(digest[:8], 16) / 0xFFFFFFFF
    f1_jitter = int(digest[8:16], 16) / 0xFFFFFFFF
    sec_jitter = int(digest[16:24], 16) / 0xFFFFFFFF
    holdout = round(0.55 + 0.40 * acc_jitter, 4)  # in [0.55, 0.95)
    macro_f1 = round(max(0.0, holdout - 0.05 * f1_jitter), 4)
    # Bigger images / more epochs cost more "time" (still synthetic).
    base_sec = 30.0 + 120.0 * sec_jitter
    base_sec *= 1.0 + 0.5 * (int(cell.get("epochs", 3)) / 3.0)
    base_sec *= (int(cell.get("image_size", 192)) / 192.0) ** 2
    return {
        "holdout_accuracy": holdout,
        "macro_f1": macro_f1,
        "train_seconds": round(base_sec, 1),
    }


# Module-level worker so ProcessPoolExecutor can pickle it.
def _screen_cell_worker(payload: dict) -> dict:
    """Process-pool entry point. Dry-run only in this task; real path is a TODO.

    payload: {run_id, run_db_id, cell, dry_run, seed}. Returns the metric dict
    plus the run identifiers so the parent can record them.
    """
    cell = payload["cell"]
    run_id = payload["run_id"]
    if payload.get("dry_run", True):
        metrics = fake_screen(cell, run_id, seed=int(payload.get("seed", 0)))
    else:  # pragma: no cover - real training path, never run in M14-T003
        raise NotImplementedError(
            "real local-screening training is documented but not executed in "
            "M14-T003; use --dry-run. The real path would invoke the templated "
            "baseline.py against the local data slice (see docstring)."
        )
    return {
        "run_id": run_id,
        "run_db_id": payload.get("run_db_id"),
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# GPU-memory-aware concurrency cap (ADR-0020 §5 step 2).
# ---------------------------------------------------------------------------


def _free_vram_mib() -> int | None:
    """Best-effort free VRAM in MiB via nvidia-smi; None if no GPU / no tool."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        import subprocess

        out = subprocess.run(
            [exe, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0:
            return None
        # Sum across GPUs is misleading for a single-process cap; take the max
        # single-GPU free pool (a process lands on one device).
        vals = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        return max(vals) if vals else None
    except Exception:
        return None


def resolve_max_concurrent(requested: int | None, n_cells: int) -> tuple[int, str]:
    """Return (max_concurrent, reason).

    - Explicit ``requested`` is honoured (clamped to [1, n_cells]).
    - Else GPU-memory aware: ``free_vram // est_cell_vram`` clamped to
      [1, n_cells].
    - CPU-only host (no nvidia-smi): serial (1) with a logged reason.
    """
    if requested is not None:
        val = max(1, min(int(requested), n_cells))
        return val, f"explicit --max-concurrent={requested} (clamped to {val})"
    free = _free_vram_mib()
    if free is None:
        return 1, "no GPU detected (nvidia-smi absent) — serial screening"
    cap = max(1, free // _EST_CELL_VRAM_MIB)
    val = max(1, min(cap, n_cells))
    return val, (f"GPU free={free}MiB / est_cell={_EST_CELL_VRAM_MIB}MiB -> {cap}; clamped to {val}")


# ---------------------------------------------------------------------------
# Batch <-> DB glue.
# ---------------------------------------------------------------------------


def _experiments_for_competition(_db, competition_id: str) -> list[str]:
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text FROM experiments WHERE competition_id = %s::uuid",
                (competition_id,),
            )
            return [r["id"] for r in cur.fetchall()]
    finally:
        conn.close()


def _batch_runs(_db, batch_id: str) -> list[dict]:
    """Return experiment_runs rows whose analysis_jsonb.exploration_batch_id matches."""
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, status, metrics, analysis_jsonb, run_dir
                  FROM experiment_runs
                 WHERE analysis_jsonb ->> 'exploration_batch_id' = %s
                 ORDER BY created_at ASC
                """,
                (batch_id,),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["stage"] = (d.get("analysis_jsonb") or {}).get("explore_stage")
                rows.append(d)
            return rows
    finally:
        conn.close()


def _competition_has_active_batch(_db, competition_id: str) -> str | None:
    """Return the active batch id for this competition, or None.

    A batch is active while it owns runs in the init/fan-out/screen window
    (explore_stage in planned/screened). Rank/promote does not change the stage,
    so a ranked-but-not-promoted batch still reads active until pruned/closed —
    this matches ADR-0020 §5's "one active batch per goal" guard.
    """
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT er.analysis_jsonb ->> 'exploration_batch_id' AS batch_id
                  FROM experiment_runs er
                  JOIN experiments e ON e.id = er.experiment_id
                 WHERE e.competition_id = %s::uuid
                   AND er.analysis_jsonb ->> 'exploration_batch_id' IS NOT NULL
                   AND er.analysis_jsonb ->> 'explore_stage' = ANY(%s)
                 LIMIT 1
                """,
                (competition_id, list(_ACTIVE_RUN_STAGES)),
            )
            row = cur.fetchone()
            return row["batch_id"] if row else None
    finally:
        conn.close()


def tried_cells_for_competition(_db, competition_id: str) -> list[dict]:
    """Return the distinct ``analysis_jsonb.cell`` dicts already tried for a comp.

    Reads every ``experiment_runs`` row that belongs to one of the competition's
    experiments and carries an ``exploration_batch_id`` (i.e. an exploration
    cell). Used by ``propose-next`` to de-dup proposals against prior batches.
    Only counts a cell as "tried" once regardless of how many batches touched it.
    """
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT er.analysis_jsonb -> 'cell' AS cell
                  FROM experiment_runs er
                  JOIN experiments e ON e.id = er.experiment_id
                 WHERE e.competition_id = %s::uuid
                   AND er.analysis_jsonb ->> 'exploration_batch_id' IS NOT NULL
                   AND er.analysis_jsonb -> 'cell' IS NOT NULL
                """,
                (competition_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    seen: set[str] = set()
    cells: list[dict] = []
    for r in rows:
        cell = r["cell"]
        if not isinstance(cell, dict):
            continue
        key = json.dumps(cell, sort_keys=True)
        if key not in seen:
            seen.add(key)
            cells.append(cell)
    return cells


def _set_run_status(_db, run_id: str, status: str) -> None:
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE experiment_runs SET status = %s WHERE id = %s::uuid",
                (status, run_id),
            )
        conn.commit()
    finally:
        conn.close()


def _set_run_stage(_db, run_id: str, stage: str) -> None:
    """Set the explore lifecycle stage (analysis_jsonb.explore_stage) and the
    matching run_status enum value. The enum is the schema-faithful column; the
    stage carries the explore-specific planned/screened semantics."""
    _set_run_status(_db, run_id, _ENUM_FOR_STAGE[stage])
    _db.set_run_analysis_jsonb(run_id, explore_stage=stage)


def _delete_planned_runs(_db, batch_id: str) -> int:
    conn = _db.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM experiment_runs
                 WHERE analysis_jsonb ->> 'exploration_batch_id' = %s
                   AND analysis_jsonb ->> 'explore_stage' = %s
                """,
                (batch_id, STAGE_PLANNED),
            )
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    slug = args.competition
    spec_path = Path(args.search_space)
    try:
        _db = _load_db()
        comp = _db.get_competition_by_slug(slug)
    except KeyError:
        return _emit(
            False,
            {
                "error": f"competition '{slug}' not registered; run `kca competition register` first",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )
    except Exception as exc:
        return _emit(
            False,
            {"error": str(exc), "side_effect": SideEffect.LOCAL_WRITE.value},
            EXIT_RUNTIME,
        )

    if not spec_path.exists():
        return _emit(
            False,
            {
                "error": f"search-space file not found: {spec_path}",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )

    # Refuse a second batch while one is active (ADR-0020 §5).
    try:
        active = _competition_has_active_batch(_db, comp["id"])
    except Exception as exc:
        return _emit(
            False,
            {"error": str(exc), "side_effect": SideEffect.LOCAL_WRITE.value},
            EXIT_RUNTIME,
        )
    if active is not None:
        return _emit(
            False,
            {
                "error": "ACTIVE_BATCH_EXISTS",
                "competition": slug,
                "active_batch_id": active,
                "message": (
                    "an exploration batch is still active (planned/screened "
                    "runs); `kca explore prune` or finish it first"
                ),
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )

    try:
        spec = _load_search_space(spec_path)
        cells = expand_cells(spec)
    except Exception as exc:
        return _emit(
            False,
            {
                "error": f"search-space parse/expand failed: {exc}",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )

    # Resolve the seed template.
    seed_template = spec.get("seed_template")
    if seed_template:
        seed_path = Path(str(seed_template).replace("<comp>", slug))
        if not seed_path.is_absolute():
            seed_path = _repo_root() / seed_path
    else:
        seed_path = _comp_dir(slug) / "baseline-tl" / "baseline.py"
    if not seed_path.exists():
        return _emit(
            False,
            {
                "error": f"seed_template not found: {seed_path}",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )
    seed_src = seed_path.read_text(encoding="utf-8")

    batch_id = str(uuid.uuid4())
    goal = None
    try:
        goal = _db.get_active_goal(comp["id"])
    except Exception:
        goal = None

    # One experiments row carries the whole batch; each cell is an
    # experiment_runs row under it. Use the M4 helper so experiments.competition_id
    # is set — the active-batch guard and the rank threshold lookup both join
    # experiment_runs -> experiments -> competition on that FK.
    try:
        experiment_id = _db.create_experiment(
            comp["id"],
            f"M14 exploration batch {batch_id} for {slug}",
            branch=f"explore-{slug}-{batch_id[:8]}",
            config={
                "exploration_batch_id": batch_id,
                "competition": slug,
                "axes": spec.get("axes", {}),
                "sample": spec.get("sample", "full"),
            },
        )
    except Exception as exc:
        return _emit(
            False,
            {
                "error": f"failed to create batch experiment: {exc}",
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )

    comp_dir = _comp_dir(slug)
    batch_dir = comp_dir / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    cell_records: list[dict] = []
    for cell in cells:
        run_id = _cell_run_id(batch_id, cell)
        run_dir = comp_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        # cell.yaml — the axis values requested for this cell.
        _write_cell_yaml(run_dir / "cell.yaml", batch_id, run_id, cell)
        # baseline.py templated from the seed.
        (run_dir / "baseline.py").write_text(_render_cell_baseline(seed_src, cell, run_id), encoding="utf-8")
        # experiment_runs row: enum status=queued + explore_stage=planned in
        # analysis_jsonb, plus analysis_jsonb.exploration_batch_id.
        run_db_id = _db.create_experiment_run(
            experiment_id=experiment_id,
            external_run_id=run_id,
            run_dir=str(run_dir.relative_to(_repo_root())),
            command="kca explore run (planned)",
        )
        _set_run_stage(_db, run_db_id, STAGE_PLANNED)
        _db.set_run_analysis_jsonb(
            run_db_id,
            exploration_batch_id=batch_id,
            cell=cell,
        )
        cell_records.append(
            {
                "run_id": run_id,
                "run_db_id": run_db_id,
                "run_dir": str(run_dir.relative_to(_repo_root())),
                "cell": cell,
            }
        )

    # batch.yaml manifest.
    _write_batch_yaml(
        batch_dir / "batch.yaml",
        slug=slug,
        batch_id=batch_id,
        experiment_id=experiment_id,
        goal_id=str(goal["id"]) if goal else None,
        spec=spec,
        cells=cell_records,
    )

    return _emit(
        True,
        {
            "competition": slug,
            "exploration_batch_id": batch_id,
            "experiment_id": experiment_id,
            "goal_id": str(goal["id"]) if goal else None,
            "n_cells": len(cell_records),
            "batch_yaml": str((batch_dir / "batch.yaml").relative_to(_repo_root())),
            "cells": cell_records,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        },
    )


def _write_cell_yaml(path: Path, batch_id: str, run_id: str, cell: dict) -> None:
    lines = [
        f"exploration_batch_id: {batch_id}",
        f"run_id: {run_id}",
        "axes:",
    ]
    for k, v in cell.items():
        lines.append(f"  {k}: {_yaml_scalar(v)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_batch_yaml(
    path: Path,
    *,
    slug: str,
    batch_id: str,
    experiment_id: str,
    goal_id: str | None,
    spec: dict,
    cells: list[dict],
) -> None:
    lines = [
        f"competition: {slug}",
        f"exploration_batch_id: {batch_id}",
        f"experiment_id: {experiment_id}",
        f"goal_id: {goal_id if goal_id else 'null'}",
        f"sample: {_yaml_scalar(spec.get('sample', 'full'))}",
        "axes:",
    ]
    for k, v in (spec.get("axes") or {}).items():
        vals = v if isinstance(v, (list, tuple)) else [v]
        rendered = ", ".join(_yaml_scalar(x) for x in vals)
        lines.append(f"  {k}: [{rendered}]")
    lines.append(f"n_cells: {len(cells)}")
    lines.append("cells:")
    for c in cells:
        lines.append(f"  - run_id: {c['run_id']}")
        lines.append(f"    run_dir: {c['run_dir']}")
        lines.append(f"    cell: {json.dumps(c['cell'], sort_keys=True)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return str(value)


def cmd_run(args: argparse.Namespace) -> int:
    batch_id = args.batch
    dry_run = bool(getattr(args, "dry_run", False))
    try:
        _db = _load_db()
        runs = _batch_runs(_db, batch_id)
    except Exception as exc:
        return _emit(
            False,
            {"error": str(exc), "side_effect": SideEffect.LOCAL_WRITE.value},
            EXIT_RUNTIME,
        )

    planned = [r for r in runs if r.get("stage") == STAGE_PLANNED]
    if not runs:
        return _emit(
            False,
            {
                "error": "BATCH_NOT_FOUND",
                "batch": batch_id,
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )
    if not planned:
        return _emit(
            True,
            {
                "batch": batch_id,
                "screened": 0,
                "message": "no planned runs to screen",
                "dry_run": dry_run,
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
        )

    if not dry_run:
        # Real training is documented but NOT executed in M14-T003. Refuse so
        # the no-GPU acceptance path is the only one this task exercises.
        return _emit(
            False,
            {
                "error": "REAL_TRAINING_NOT_ENABLED_IN_T003",
                "message": (
                    "kca explore run requires --dry-run in M14-T003; the real "
                    "local-screening path (templated baseline.py against the "
                    "local data slice via a GPU-memory-capped process pool) is "
                    "documented in explore.py but intentionally not executed here"
                ),
                "side_effect": SideEffect.LOCAL_WRITE.value,
            },
            EXIT_RUNTIME,
        )

    n_cells = len(planned)
    max_conc, conc_reason = resolve_max_concurrent(getattr(args, "max_concurrent", None), n_cells)

    seed = int(getattr(args, "seed", 0) or 0)
    payloads = [
        {
            "run_id": r["run_dir"].rsplit("/", 1)[-1] if r.get("run_dir") else r["id"],
            "run_db_id": r["id"],
            "cell": (r.get("analysis_jsonb") or {}).get("cell", {}),
            "dry_run": True,
            "seed": seed,
        }
        for r in planned
    ]

    results: list[dict] = []
    if max_conc <= 1:
        for p in payloads:
            results.append(_screen_cell_worker(p))
    else:
        with ProcessPoolExecutor(max_workers=max_conc) as ex:
            futures = [ex.submit(_screen_cell_worker, p) for p in payloads]
            for fut in as_completed(futures):
                results.append(fut.result())

    screened = 0
    out_cells = []
    for res in results:
        run_db_id = res["run_db_id"]
        metrics = res["metrics"]
        for key in ("holdout_accuracy", "macro_f1", "train_seconds"):
            _db.record_metric(run_db_id, key, float(metrics[key]))
        _set_run_stage(_db, run_db_id, STAGE_SCREENED)
        screened += 1
        out_cells.append({"run_id": res["run_id"], "run_db_id": run_db_id, "metrics": metrics})

    out_cells.sort(key=lambda c: c["run_id"])
    return _emit(
        True,
        {
            "batch": batch_id,
            "screened": screened,
            "dry_run": True,
            "max_concurrent": max_conc,
            "concurrency_reason": conc_reason,
            "cells": out_cells,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        },
    )


def _metric_value(metrics: Any, key: str) -> float | None:
    """Read a metric value from experiment_runs.metrics (jsonb)."""
    if not isinstance(metrics, dict):
        return None
    v = metrics.get(key)
    if v is None:
        return None
    # M4 record_metric writes a bare float; M2 path writes {"value": ...}.
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _resolve_screen_threshold(_db, batch_id: str, runs: list[dict], override):
    """Return (threshold, source). override wins; else 0.90 x goal target."""
    if override is not None:
        return float(override), "explicit --threshold"
    # Find the goal via the batch's competition.
    target = None
    try:
        conn = _db.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT g.target_lb_score
                      FROM experiment_runs er
                      JOIN experiments e ON e.id = er.experiment_id
                      JOIN goals g ON g.competition_id = e.competition_id
                                  AND g.status = 'active'
                     WHERE er.analysis_jsonb ->> 'exploration_batch_id' = %s
                     LIMIT 1
                    """,
                    (batch_id,),
                )
                row = cur.fetchone()
                if row and row["target_lb_score"] is not None:
                    target = float(row["target_lb_score"])
        finally:
            conn.close()
    except Exception:
        target = None
    if target is None:
        return None, "no active goal target — qualifies left null"
    return round(_DEFAULT_SCREEN_FRACTION * target, 6), (f"{_DEFAULT_SCREEN_FRACTION} x goal target_lb_score={target}")


def cmd_rank(args: argparse.Namespace) -> int:
    batch_id = args.batch
    try:
        _db = _load_db()
        runs = _batch_runs(_db, batch_id)
    except Exception as exc:
        return _emit(
            False,
            {"error": str(exc), "side_effect": SideEffect.READ_ONLY.value},
            EXIT_RUNTIME,
        )
    if not runs:
        return _emit(
            False,
            {
                "error": "BATCH_NOT_FOUND",
                "batch": batch_id,
                "side_effect": SideEffect.READ_ONLY.value,
            },
            EXIT_RUNTIME,
        )

    screened = [r for r in runs if r.get("stage") == STAGE_SCREENED]
    threshold, thr_source = _resolve_screen_threshold(_db, batch_id, runs, getattr(args, "threshold", None))

    cohort = []
    for r in screened:
        holdout = _metric_value(r.get("metrics"), "holdout_accuracy")
        macro_f1 = _metric_value(r.get("metrics"), "macro_f1")
        train_seconds = _metric_value(r.get("metrics"), "train_seconds")
        qualifies = None
        if threshold is not None and holdout is not None:
            qualifies = bool(holdout >= threshold)
        cohort.append(
            {
                "run_db_id": r["id"],
                "run_dir": r.get("run_dir"),
                "cell": (r.get("analysis_jsonb") or {}).get("cell", {}),
                "holdout_accuracy": holdout,
                "macro_f1": macro_f1,
                "train_seconds": train_seconds,
                "qualifies": qualifies,
            }
        )

    cohort.sort(
        key=lambda c: c["holdout_accuracy"] if c["holdout_accuracy"] is not None else -1.0,
        reverse=True,
    )
    return _emit(
        True,
        {
            "batch": batch_id,
            "n_screened": len(cohort),
            "screen_threshold": threshold,
            "threshold_source": thr_source,
            "ranked": cohort,
            "side_effect": SideEffect.READ_ONLY.value,
        },
    )


def cmd_prune(args: argparse.Namespace) -> int:
    batch_id = args.batch
    try:
        _db = _load_db()
        runs = _batch_runs(_db, batch_id)
        if not runs:
            return _emit(
                False,
                {
                    "error": "BATCH_NOT_FOUND",
                    "batch": batch_id,
                    "side_effect": SideEffect.LOCAL_WRITE.value,
                },
                EXIT_RUNTIME,
            )
        n_deleted = _delete_planned_runs(_db, batch_id)
    except Exception as exc:
        return _emit(
            False,
            {"error": str(exc), "side_effect": SideEffect.LOCAL_WRITE.value},
            EXIT_RUNTIME,
        )

    # Best-effort: remove the now-orphaned planned run dirs from the filesystem.
    removed_dirs = []
    for r in runs:
        if r.get("stage") == STAGE_PLANNED and r.get("run_dir"):
            d = _repo_root() / r["run_dir"]
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                removed_dirs.append(r["run_dir"])

    return _emit(
        True,
        {
            "batch": batch_id,
            "pruned_runs": n_deleted,
            "removed_dirs": removed_dirs,
            "side_effect": SideEffect.LOCAL_WRITE.value,
        },
    )


# ---------------------------------------------------------------------------
# propose-next (M14-T006) — idea-sourcing reader -> next_candidates.yaml.
#
# Reads top public kernels / forum threads / arxiv papers via the injectable,
# untrusted-data-filtered readers in research.py, then proposes 3-5 NEW
# search-space cells (not already tried for this competition). Default
# --dry-run writes the YAML but schedules NO batch.
# ---------------------------------------------------------------------------

# The axis vocabulary propose-next draws from. Source text only *selects* among
# these known-safe values via keyword hits — a source string can never inject a
# value: an unrecognised token simply does not match and is ignored.
_PROPOSE_BACKBONES = [
    "efficientnet_b0",
    "efficientnetv2_s",
    "resnet50",
    "resnet101",
    "densenet121",
    "convnext_tiny",
    "xception",
]
_PROPOSE_IMAGE_SIZES = [192, 224, 256, 331]
_PROPOSE_EPOCHS = [3, 6, 9]

# Map a source keyword hit (from research._kernel_keywords) to a safe backbone.
_KEYWORD_TO_BACKBONE = {
    "efficientnet": "efficientnet_b0",
    "efficientnetv2": "efficientnetv2_s",
    "resnet": "resnet50",
    "resnet101": "resnet101",
    "densenet": "densenet121",
    "convnext": "convnext_tiny",
    "xception": "xception",
}


def _cell_key(cell: dict) -> str:
    return json.dumps(cell, sort_keys=True)


def propose_candidates(
    sources: list[dict],
    tried: list[dict],
    *,
    want_min: int = 3,
    want_max: int = 5,
) -> list[dict]:
    """Propose NEW search-space cells from sanitized sources, de-duped vs tried.

    Each proposed cell carries ``source_url`` + ``trust_label`` + ``rationale``.
    Sources only *select* among the known-safe axis vocabulary via keyword hits;
    an injection-flagged source can still seed a cell but the proposal inherits
    its low ``trust_label`` so the operator sees it was adversarial. The cross
    product of candidate axes is de-duped against ``tried`` (prior-batch cells).
    """
    tried_keys = {_cell_key(c) for c in tried}

    # Derive candidate backbones from source keyword hits; fall back to the
    # default vocabulary order so we always have enough material to propose.
    backbones: list[str] = []
    for s in sources:
        for kw in s.get("keyword_hits", []) or []:
            bb = _KEYWORD_TO_BACKBONE.get(kw)
            if bb and bb not in backbones:
                backbones.append(bb)
    for bb in _PROPOSE_BACKBONES:
        if bb not in backbones:
            backbones.append(bb)

    # Attach a representative source to each backbone for citation. Prefer a
    # source whose keyword maps to that backbone; else the first source.
    def _source_for(bb: str) -> dict | None:
        for s in sources:
            for kw in s.get("keyword_hits", []) or []:
                if _KEYWORD_TO_BACKBONE.get(kw) == bb:
                    return s
        return sources[0] if sources else None

    # Build the (size, epoch) combos once, in deterministic order.
    settings = [(size, ep) for size in _PROPOSE_IMAGE_SIZES for ep in _PROPOSE_EPOCHS]

    proposals: list[dict] = []
    seen: set[str] = set()
    # Round-robin over backbones (outer loop = setting index) so the proposed
    # cells span DISTINCT backbones / sources rather than exhausting one
    # backbone first — keeps the batch diverse and cites multiple sources.
    for setting_idx in range(len(settings)):
        size, ep = settings[setting_idx]
        for bb in backbones:
            cell = {"backbone": bb, "image_size": size, "epochs": ep}
            key = _cell_key(cell)
            if key in tried_keys or key in seen:
                continue
            src = _source_for(bb)
            trust = src.get("trust_label", "unknown") if src else "unknown"
            url = src.get("source_url") if src else None
            quote = src.get("quote", "") if src else ""
            markers = src.get("injection_markers", []) if src else []
            rationale = (
                f"{bb} @ {size}px/{ep}ep — surfaced from "
                f"{src.get('source_kind', 'unknown') if src else 'unknown'} source"
            )
            if quote:
                rationale += f'; source quote: "{quote}"'
            proposals.append(
                {
                    "cell": cell,
                    "source_url": url,
                    "trust_label": trust,
                    "rationale": rationale,
                    "injection_markers": markers,
                }
            )
            seen.add(key)
            if len(proposals) >= want_max:
                return proposals
    return proposals


def _write_next_candidates_yaml(
    path: Path,
    *,
    slug: str,
    proposals: list[dict],
    n_tried: int,
) -> None:
    """Write next_candidates.yaml. Every value is a quoted/escaped data scalar."""
    lines = [
        "# kca explore propose-next (M14-T006) — GENERATED, human-approved before scheduling.",
        "# Each candidate is sourced from UNTRUSTED public kernels / forum / arxiv text;",
        "# source text is captured as quoted data, never executed. Schedule with:",
        f"#   kca explore init --competition {slug} --search-space next_candidates.yaml",
        f"competition: {slug}",
        f"n_tried_cells: {n_tried}",
        f"n_candidates: {len(proposals)}",
        "candidates:",
    ]
    for p in proposals:
        cell = p["cell"]
        lines.append(f"  - backbone: {_yaml_scalar(cell['backbone'])}")
        lines.append(f"    image_size: {_yaml_scalar(cell['image_size'])}")
        lines.append(f"    epochs: {_yaml_scalar(cell['epochs'])}")
        lines.append(f"    source_url: {_yaml_quote(p.get('source_url'))}")
        lines.append(f"    trust_label: {_yaml_scalar(p.get('trust_label', 'unknown'))}")
        lines.append(f"    rationale: {_yaml_quote(p.get('rationale', ''))}")
        markers = p.get("injection_markers") or []
        if markers:
            rendered = ", ".join(_yaml_quote(m) for m in markers)
            lines.append(f"    injection_markers_flagged: [{rendered}]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _yaml_quote(value) -> str:
    """Emit a safely double-quoted YAML scalar for untrusted strings."""
    if value is None:
        return "null"
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", " ").replace("\r", " ")
    return f'"{s}"'


def cmd_propose_next(args: argparse.Namespace) -> int:
    import research

    slug = args.competition
    dry_run = not bool(getattr(args, "schedule", False))  # default dry-run
    budget = int(getattr(args, "budget_search_queries", 8) or 8)

    se = SideEffect.LOCAL_WRITE
    try:
        _db = _load_db()
        comp = _db.get_competition_by_slug(slug)
    except KeyError:
        return _emit(
            False,
            {
                "error": f"competition '{slug}' not registered; run `kca competition register` first",
                "side_effect": se.value,
            },
            EXIT_RUNTIME,
        )
    except Exception as exc:
        return _emit(False, {"error": str(exc), "side_effect": se.value}, EXIT_RUNTIME)

    # Injectable readers: tests set explore._propose_readers; default = no network.
    readers = getattr(cmd_propose_next, "_readers", None) or {}
    sources = research.gather_sources(
        slug,
        budget=budget,
        kernels_reader=readers.get("kernels"),
        forum_reader=readers.get("forum"),
        arxiv_reader=readers.get("arxiv"),
        keywords=readers.get("keywords"),
    )

    try:
        tried = tried_cells_for_competition(_db, comp["id"])
    except Exception as exc:
        return _emit(False, {"error": str(exc), "side_effect": se.value}, EXIT_RUNTIME)

    proposals = propose_candidates(sources, tried)
    if len(proposals) < 3:
        return _emit(
            False,
            {
                "error": "INSUFFICIENT_NEW_CANDIDATES",
                "competition": slug,
                "n_candidates": len(proposals),
                "n_tried": len(tried),
                "message": (
                    "fewer than 3 new (untried) cells could be proposed; the "
                    "idea well may be dry — surface to a human (T007)"
                ),
                "side_effect": se.value,
            },
            EXIT_RUNTIME,
        )

    out_path = _comp_dir(slug) / "next_candidates.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_next_candidates_yaml(out_path, slug=slug, proposals=proposals, n_tried=len(tried))

    payload = {
        "competition": slug,
        "dry_run": dry_run,
        "scheduled_batch": None,  # propose-next NEVER schedules (T006 non-goal)
        "next_candidates_yaml": str(out_path.relative_to(_repo_root())),
        "n_candidates": len(proposals),
        "n_tried": len(tried),
        "n_sources": len(sources),
        "candidates": [
            {
                "cell": p["cell"],
                "source_url": p["source_url"],
                "trust_label": p["trust_label"],
                "rationale": p["rationale"],
                "injection_markers_flagged": p.get("injection_markers") or [],
            }
            for p in proposals
        ],
        "side_effect": se.value,
    }
    return _emit(True, payload)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    explore = sub.add_parser(
        "explore",
        help="Exploration-batch lifecycle: init / run / rank / prune (M14-T003)",
    )
    explore_sub = explore.add_subparsers(dest="explore_cmd", required=True)

    p_init = explore_sub.add_parser(
        "init",
        help="Expand a search-space YAML into per-cell dirs + planned runs (LOCAL_WRITE)",
    )
    p_init.add_argument("--competition", required=True, help="competition slug")
    p_init.add_argument(
        "--search-space",
        dest="search_space",
        required=True,
        help="path to the axes YAML (ADR-0020 §4)",
    )
    p_init.add_argument("--json", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_run = explore_sub.add_parser(
        "run",
        help="Fan out local screenings for a batch (LOCAL_WRITE; use --dry-run)",
    )
    p_run.add_argument("--batch", required=True, help="exploration_batch_id")
    p_run.add_argument(
        "--max-concurrent",
        dest="max_concurrent",
        type=int,
        default=None,
        help="process-pool size; default is GPU-memory-aware (1 on CPU-only)",
    )
    p_run.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="synthetic screening: NO training, NO Kaggle (required in M14-T003)",
    )
    p_run.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seed for the deterministic dry-run metrics",
    )
    p_run.add_argument("--json", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_rank = explore_sub.add_parser(
        "rank",
        help="List screened cells sorted by holdout, flag which qualify (READ_ONLY)",
    )
    p_rank.add_argument("--batch", required=True, help="exploration_batch_id")
    p_rank.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="override the qualify threshold (default 0.90 x goal target_lb_score)",
    )
    p_rank.add_argument("--json", action="store_true")
    p_rank.set_defaults(func=cmd_rank)

    p_prune = explore_sub.add_parser(
        "prune",
        help="GC planned-but-never-screened runs for a batch (LOCAL_WRITE)",
    )
    p_prune.add_argument("--batch", required=True, help="exploration_batch_id")
    p_prune.add_argument("--json", action="store_true")
    p_prune.set_defaults(func=cmd_prune)

    p_propose = explore_sub.add_parser(
        "propose-next",
        help=(
            "Read public kernels / forum / arxiv (untrusted-data filtered) and "
            "write next_candidates.yaml with 3-5 new cells (LOCAL_WRITE; default "
            "--dry-run writes YAML but schedules NO batch) (M14-T006)"
        ),
    )
    p_propose.add_argument("--competition", required=True, help="competition slug")
    p_propose.add_argument(
        "--budget-search-queries",
        dest="budget_search_queries",
        type=int,
        default=8,
        help="max source records to read per channel (default 8)",
    )
    p_propose.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="(default) write next_candidates.yaml WITHOUT scheduling a batch",
    )
    p_propose.add_argument(
        "--schedule",
        dest="schedule",
        action="store_true",
        help=(
            "reserved: propose-next never schedules in T006 (human runs "
            "`kca explore init --search-space next_candidates.yaml`)"
        ),
    )
    p_propose.add_argument("--json", action="store_true")
    p_propose.set_defaults(func=cmd_propose_next)
