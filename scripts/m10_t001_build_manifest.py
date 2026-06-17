#!/usr/bin/env python
"""Build the M10-T001 Petals to the Metal data manifest.

Per docs/tasks/M10-T001-data-discovery-manifest.md the raw TFRecord
data (~5+ GB across image-size variants) is NOT downloaded by default;
the kernel runner reads it from Kaggle's GCS-hosted dataset at runtime.

This script:
  1. Runs `kaggle competitions files -c tpu-getting-started --csv`
     (paginating until Kaggle stops returning a Next Page Token).
  2. Records every entry with name, size, creationDate, and a
     ``sha256: None`` placeholder ("remote-only; read by kernel at
     runtime").
  3. Writes `data/tpu-getting-started/manifest.json`.

The shape mirrors the M9-T001 CSV manifest (`competition`, `files`)
but omits sha256 checksums and adds an `image_size_variants` summary
plus a `notes` field documenting the remote-only contract.

Run from the repo root:

    python scripts/m10_t001_build_manifest.py

The script is READ_ONLY against Kaggle (no submit / push / upload)
and LOCAL_WRITE for the manifest file.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import subprocess
import sys
from io import StringIO
from pathlib import Path


COMPETITION = "tpu-getting-started"
DEFAULT_PATH = Path("data") / COMPETITION


def _run_kaggle_files(competition: str, page_token: str | None) -> tuple[str, str | None]:
    """Run ``kaggle competitions files`` once and return (csv_body, next_token).

    csv_body is the CSV-only portion (Next Page Token line stripped, warnings
    stripped). next_token is None when Kaggle did not return one.
    """
    cmd = ["kaggle", "competitions", "files", "-c", competition, "--csv"]
    if page_token:
        cmd.extend(["--page-token", page_token])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"kaggle competitions files failed (rc={proc.returncode}): {proc.stderr!r}")
    out = proc.stdout or ""
    next_token: str | None = None
    body_lines: list[str] = []
    for line in out.splitlines():
        if line.startswith("Next Page Token = "):
            tok = line[len("Next Page Token = ") :].strip()
            next_token = tok or None
            continue
        if line.startswith("Warning:"):
            continue
        body_lines.append(line)
    return "\n".join(body_lines), next_token


def discover_files(competition: str, max_pages: int = 50) -> list[dict]:
    """Return the full list of file records via paginated kaggle CLI calls."""
    files: list[dict] = []
    seen_header = False
    token: str | None = None
    pages = 0
    while True:
        pages += 1
        if pages > max_pages:
            raise RuntimeError(f"exceeded max_pages={max_pages}; pagination did not terminate")
        body, next_token = _run_kaggle_files(competition, token)
        reader = csv.DictReader(StringIO(body))
        for row in reader:
            if not row.get("name"):
                continue
            files.append(
                {
                    "name": row["name"],
                    "size": int(row["size"]),
                    "creationDate": row.get("creationDate") or None,
                }
            )
        seen_header = True
        if not next_token:
            break
        token = next_token
    if not seen_header:
        raise RuntimeError("kaggle returned no rows; data shape may have changed")
    return files


_VARIANT_RE = re.compile(r"tfrecords-jpeg-(\d+x\d+)/")


def extract_variants(files: list[dict]) -> list[str]:
    variants: set[str] = set()
    for f in files:
        m = _VARIANT_RE.match(f["name"])
        if m:
            variants.add(m.group(1))
    return sorted(variants)


def build_manifest(files: list[dict], variants: list[str]) -> dict:
    entries = [
        {
            "name": f["name"],
            "size": f["size"],
            "creationDate": f["creationDate"],
            "sha256": None,
            "comment": "remote-only; read by kernel at runtime",
        }
        for f in files
    ]
    return {
        "competition": COMPETITION,
        "format": "kernel-input",
        "discovered_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "discovery_method": "kaggle competitions files -c tpu-getting-started --csv",
        "files": entries,
        "image_size_variants": variants,
        "notes": (
            "Raw TFRecords are NOT downloaded; the kernel runner consumes them "
            "from Kaggle's GCS-hosted dataset at runtime. sha256 is null for "
            "every entry because nothing was fetched locally."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default=str(DEFAULT_PATH),
        help="output directory for manifest.json (default: data/tpu-getting-started)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="discover files but do not write the manifest",
    )
    args = parser.parse_args(argv)

    files = discover_files(COMPETITION)
    variants = extract_variants(files)
    manifest = build_manifest(files, variants)

    out_dir = Path(args.path)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    summary = {
        "competition": COMPETITION,
        "files": len(files),
        "image_size_variants": variants,
        "manifest": str(manifest_path),
        "dry_run": args.dry_run,
    }
    if not args.dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
