#!/usr/bin/env python3
"""Generate Kaggle kernel-metadata.json on the fly from a per-competition YAML.

Modelled on the legacy `tools/legacy/kkr.yaml` pattern: a `_base` section holds
the fields shared by every kernel variant, and each named section overrides only
what differs (id / title / code_file / sources / machine). One YAML is the single
source of truth for all variations of one competition across multiple accounts
(e.g. harrysun2006 / firefly2006), so per-kernel `kernel-metadata.json` files no
longer need to be source-controlled — they are materialised at push/submit time.

Usage:
  # write kernel-metadata.json (merged _base + <section>) into a build dir
  python tools/kca/yaml_meta.py write competitions/nvidia-nemotron/kca-nemo.yaml v14 <build_dir>

  # assemble a complete push dir (metadata.json + built .ipynb) from a flat source
  python tools/kca/yaml_meta.py build competitions/nvidia-nemotron/kca-nemo.yaml c1 \
      --src-dir competitions/nvidia-nemotron/kernels --out <build_dir>
  # then:  python tools/kca/kca.py kaggle push --kernel-dir <build_dir> --no-watch

Only the keys Kaggle's kernel-metadata.json understands are emitted; any extra
annotation keys in the YAML (lb, schedule, note, account, competition, submit_*,
and any `_`-prefixed key) are ignored in the output.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import yaml

# The exact set of keys Kaggle's kernel-metadata.json accepts.
KAGGLE_KEYS = (
    "id",
    "title",
    "code_file",
    "language",
    "kernel_type",
    "is_private",
    "enable_gpu",
    "enable_tpu",
    "enable_internet",
    "keywords",
    "dataset_sources",
    "kernel_sources",
    "model_sources",
    "competition_sources",
    "docker_image",
    "machine_shape",
)


def load(yaml_path: str) -> dict:
    with open(yaml_path) as f:
        return yaml.safe_load(f) or {}


def resolve(yaml_path: str, section: str) -> dict:
    """Merge `_base` with `section` and return only Kaggle-recognised metadata keys.

    A `None` value (e.g. `machine_shape: null` to override a GPU default with CPU)
    removes the key from the output rather than emitting null.
    """
    cfg = load(yaml_path)
    base = dict(cfg.get("_base", {}))
    if section not in cfg:
        raise KeyError(
            f"section '{section}' not in {yaml_path}; available: {sorted(k for k in cfg if not k.startswith('_'))}"
        )
    merged = {**base, **cfg[section]}
    meta = {}
    for k in KAGGLE_KEYS:
        if k in merged and merged[k] is not None:
            meta[k] = merged[k]
    if "id" not in meta or "code_file" not in meta:
        raise ValueError(f"section '{section}' missing required id/code_file")
    return meta


def _write_metadata(meta: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "kernel-metadata.json")
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    return path


def cmd_write(args: argparse.Namespace) -> int:
    meta = resolve(args.yaml, args.section)
    path = _write_metadata(meta, args.out)
    print(json.dumps({"ok": True, "section": args.section, "metadata": path, "id": meta["id"]}))
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Assemble a push dir: kernel-metadata.json + built .ipynb from a flat .py.

    The source notebook is `<src-dir>/<code_file-stem>.py` (percent format); it is
    converted to `<out>/<code_file>` via `kca nb to-ipynb`.
    """
    meta = resolve(args.yaml, args.section)
    out = args.out or os.path.join(os.environ.get("TMPDIR", "/tmp"), "kca-build", args.section)
    os.makedirs(out, exist_ok=True)
    stem = os.path.splitext(meta["code_file"])[0]
    src_py = os.path.join(args.src_dir, f"{stem}.py")
    if not os.path.isfile(src_py):
        print(json.dumps({"ok": False, "error": f"source not found: {src_py}"}))
        return 1
    # copy the source .py into the build dir and build the .ipynb beside it
    dst_py = os.path.join(out, f"{stem}.py")
    with open(src_py) as fsrc, open(dst_py, "w") as fdst:
        fdst.write(fsrc.read())
    kca = os.path.join(os.path.dirname(__file__), "kca.py")
    proc = subprocess.run(
        [sys.executable, kca, "nb", "to-ipynb", dst_py],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "nb to-ipynb failed",
                    "stderr": proc.stderr[-500:],
                }
            )
        )
        return 1
    _write_metadata(meta, out)
    print(json.dumps({"ok": True, "section": args.section, "build_dir": out, "id": meta["id"]}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pw = sub.add_parser("write", help="write kernel-metadata.json for a section")
    pw.add_argument("yaml")
    pw.add_argument("section")
    pw.add_argument("out", help="output dir for kernel-metadata.json")
    pw.set_defaults(func=cmd_write)
    pb = sub.add_parser("build", help="assemble a push dir (metadata + .ipynb)")
    pb.add_argument("yaml")
    pb.add_argument("section")
    pb.add_argument("--src-dir", required=True, help="dir holding the flat <stem>.py sources")
    pb.add_argument("--out", default=None, help="build dir (default $TMPDIR/kca-build/<section>)")
    pb.set_defaults(func=cmd_build)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
