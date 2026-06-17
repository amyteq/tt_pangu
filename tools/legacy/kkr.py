#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import sys
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import nbformat
import yaml

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_INPUT = 2
EXIT_DEP = 3

TS_FORMAT = "%Y%m%d_%H%M%S"
DEFAULT_RUN_ROOT = Path(".kkr")
DEFAULT_REGISTRY_DIRNAME = "registry"
DEFAULT_VERSION_INDEX_FILENAME = "version_index.json"
DEFAULT_INTERVAL = 60
DEFAULT_TIMEOUT = 0
DEFAULT_SUBMIT_RETRY_TIMEOUT = 30
DEFAULT_SUBMIT_RETRY_INTERVAL = 5
DEFAULT_SUBMIT_RETRY_INITIAL_DELAY = 10
DEFAULT_SOURCE_DIRNAME = "source"
DEFAULT_OUTPUT_DIRNAME = "output"
DEFAULT_ZIP_DIRNAME = "extracted"
DEFAULT_STATE_FILENAME = "state.json"
DEFAULT_MANIFEST_FILENAME = "manifest.json"
DEFAULT_PUSH_FILENAME = "kkr_push.json"
DEFAULT_WATCH_FILENAME = "kkr_watch.json"
DEFAULT_FETCH_FILENAME = "kkr_fetch.json"
DEFAULT_SUBMIT_FILENAME = "kkr_submit.json"
DEFAULT_POSTPROCESS_FILENAME = "kkr_postprocess.json"
DEFAULT_METADATA_FILENAME = "kernel-metadata.json"

ACTION_PUSH = "push"
ACTION_SUBMIT = "submit"
ACTION_WATCH = "watch"
ACTION_FETCH = "fetch"
ACTION_STATUS = "status"
ACTION_LIST = "list"
SUCCESS_STATUSES = {"complete", "completed"}
TERMINAL_STATUSES = {"complete", "completed", "error", "failed", "cancel", "cancelled"}
QUEUED_STATUSES = {"queued", "pending"}
REQUIRED_CFG_KEYS = ("id", "title", "code_file", "language", "kernel_type")
LIST_CFG_KEYS = (
    "competition_sources",
    "kernel_sources",
    "dataset_sources",
    "model_sources",
    "keywords",
    "_exts",
    "_refs",
    "_drop_tags",
)
SCORE_KEYS = (
    "publicScore",
    "public_score",
    "score",
    "Score",
    "privateScore",
    "private_score",
)
STATUS_KEYS = ("status", "currentStatus")
PUSH_RESULT_FIELDS = (
    "ref",
    "url",
    "error",
    "kernelId",
    "kernel_id",
    "versionNumber",
    "version_number",
    "invalidTags",
    "invalidDatasetSources",
    "invalidCompetitionSources",
    "invalidKernelSources",
    "invalidModelSources",
)
DEBUG_TAG_RE = re.compile(r"^debug.*", re.IGNORECASE)
VERSION_LABEL_RE = re.compile(r"^v(\d+)$", re.IGNORECASE)

_LOG_QUIET = False
_LOG_VERBOSE = 0

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from kkr_ctx import KKRCtx, run_exts
except Exception:

    @dataclass
    class KKRCtx:
        action: str
        name: str
        cfg: dict[str, Any]
        run_dir: Path
        kernel_id: str
        output_files: list[str] = field(default_factory=list)
        status: str = ""

    def run_exts(ctx: KKRCtx, exts: list[str] | None = None) -> None:
        return None


@dataclass
class KernelMetadata:
    id: str
    title: str
    code_file: str
    language: str
    kernel_type: str
    is_private: bool
    enable_gpu: bool
    enable_tpu: bool
    enable_internet: bool
    competition_sources: list[Any] = field(default_factory=list)
    kernel_sources: list[Any] = field(default_factory=list)
    dataset_sources: list[Any] = field(default_factory=list)
    model_sources: list[Any] = field(default_factory=list)
    keywords: list[Any] = field(default_factory=list)
    docker_image: str | None = None
    machine_shape: str | None = None
    persistence: Any = None


@dataclass
class PushResult:
    ref: str | None = None
    url: str | None = None
    error: Any = None
    kernel_id: int | None = None
    version_number: int | None = None
    invalid_tags: list[Any] = field(default_factory=list)
    invalid_dataset_sources: list[Any] = field(default_factory=list)
    invalid_competition_sources: list[Any] = field(default_factory=list)
    invalid_kernel_sources: list[Any] = field(default_factory=list)
    invalid_model_sources: list[Any] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompetitionSubmitResult:
    ok: bool = False
    state: str = "failed"
    message: str | None = None
    ref: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class FetchResult:
    source_dir: str
    source_ok: bool
    output_dir: str
    output_files: list[str] = field(default_factory=list)
    output_status: str = ""
    extracted_dirs: list[str] = field(default_factory=list)


@dataclass
class RunState:
    run_id: str
    status: str
    updated_at: str
    action: str
    raw_status: str | None = None
    message: str | None = None
    url: str | None = None
    version_number: int | None = None
    kernel_id: int | None = None
    competition_submitted: bool | None = None
    latest_submission_score: float | str | None = None
    best_public_score: float | str | None = None
    pb_score: float | str | None = None
    score_source: str | None = None
    submit_state: str | None = None


@dataclass
class RunManifest:
    run_id: str
    name: str
    action: str
    created_at: str
    run_dir: str
    base_kernel_ref: str
    kernel_ref: str
    owner: str
    slug: str
    base_title: str | None = None
    version_label: str | None = None
    competition: str | None = None
    submit_type: str | None = None
    submit_file: str | None = None
    env_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    cfg: dict[str, Any] = field(default_factory=dict)
    notebook: dict[str, Any] = field(default_factory=dict)
    kernel_metadata: dict[str, Any] = field(default_factory=dict)
    push_result: dict[str, Any] = field(default_factory=dict)
    submit_result: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegistryEntry:
    run_id: str
    name: str
    action: str
    created_at: str
    updated_at: str
    run_dir: str
    base_kernel_ref: str
    kernel_ref: str
    owner: str
    slug: str
    base_title: str | None = None
    version_label: str | None = None
    competition: str | None = None
    submit_type: str | None = None
    submit_file: str | None = None
    kernel_id: int | None = None
    version_number: int | None = None
    url: str | None = None
    status: str = "created"
    raw_status: str | None = None
    env_path: str | None = None
    pb_score: float | str | None = None
    score_source: str | None = None
    submit_state: str = "not_applicable"


@dataclass
class ScoreInfo:
    latest_submission_score: float | str | None = None
    best_public_score: float | str | None = None
    pb_score: float | str | None = None
    score_source: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedRun:
    entry: RegistryEntry
    manifest: RunManifest
    cfg: dict[str, Any]
    run_dir: Path


def _set_log_mode(quiet: bool, verbose: int) -> None:
    global _LOG_QUIET, _LOG_VERBOSE
    _LOG_QUIET = bool(quiet)
    _LOG_VERBOSE = max(0, int(verbose or 0))


def _log(message: str, level: str = "INFO") -> None:
    if level == "DEBUG" and _LOG_VERBOSE < 1:
        return
    if _LOG_QUIET and level not in {"WARN", "ERROR"}:
        return
    print(f"{level}: {message}", file=sys.stderr)


def _to_data(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_data(x) for x in value]
    return value


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_data(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _print_table(rows: list[dict[str, Any]]) -> None:
    headers = [
        ("run_id", "run_id"),
        ("name", "name"),
        ("action", "action"),
        ("version_label", "slug_ver"),
        ("version", "kernel_ver"),
        ("status", "status"),
        ("submit_state", "submit"),
        ("url", "url"),
    ]
    if not rows:
        print("(no runs)")
        return
    widths = {k: len(title) for k, title in headers}
    for row in rows:
        for k, _ in headers:
            widths[k] = max(widths[k], len(str(row.get(k, "") or "")))
    print("  ".join(title.ljust(widths[k]) for k, title in headers))
    print("  ".join("-" * widths[k] for k, _ in headers))
    for row in rows:
        print("  ".join(str(row.get(k, "") or "").ljust(widths[k]) for k, _ in headers))


def _emit_ok(args: argparse.Namespace, **payload: Any) -> int:
    data = {"ok": True, **_to_data(payload)}
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False))
    elif data.get("action") == ACTION_LIST and "runs" in data:
        _print_table(list(data.get("runs") or []))
    else:
        for key in (
            "action",
            "name",
            "run_id",
            "status",
            "submit_state",
            "run_dir",
            "base_kernel_ref",
            "kernel_ref",
            "url",
        ):
            value = data.get(key)
            if value is not None:
                print(f"{key}: {value}")
    return EXIT_OK


def _emit_fail(
    args: argparse.Namespace,
    message: str,
    *,
    error: str = "runtime_error",
    exit_code: int = EXIT_RUNTIME,
    **payload: Any,
) -> int:
    _log(message, "ERROR")
    if getattr(args, "json", False):
        print(
            json.dumps(
                {"ok": False, "error": error, "message": message, **_to_data(payload)},
                ensure_ascii=False,
            )
        )
    return exit_code


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _resolve_stored_path(path_value: str | Path, *, base: Path | None = None) -> Path:
    path = Path(str(path_value)).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def _as_relpath(path_value: str | Path, *, start: Path | None = None) -> str:
    base = (start or Path.cwd()).resolve()
    path = _resolve_stored_path(path_value, base=base)
    try:
        rel = os.path.relpath(str(path), str(base))
    except Exception:
        return str(path)
    if rel == ".":
        return "./"
    return rel if rel.startswith(".") else f"./{rel}"


def _run_dir(run_root: Path, run_id: str) -> Path:
    return run_root / run_id


def _stored_run_dir(run_root: Path, run_id: str) -> str:
    return _as_relpath(_run_dir(run_root, run_id))


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    def union_list(left: list[Any], right: list[Any]) -> list[Any]:
        out: list[Any] = []
        seen: set[str] = set()
        for item in left + right:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else repr(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    merged = dict(base)
    for key, value in override.items():
        if key not in merged:
            merged[key] = value
            continue
        base_value = merged[key]
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(base_value, value)
        elif isinstance(base_value, list) and isinstance(value, list):
            merged[key] = union_list(base_value, value)
        else:
            merged[key] = value
    return merged


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _slug_parts(kernel_ref: str) -> tuple[str, str]:
    parts = str(kernel_ref).strip().split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("config 'id' must be in the form 'owner/slug'")
    return parts[0], parts[1]


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _dataclass_from_dict(cls: Any, data: dict[str, Any]) -> Any:
    allowed = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in dict(data or {}).items() if k in allowed}
    return cls(**filtered)


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("yaml root must be a mapping")
    return data


def _merged_config(path: Path, name: str) -> tuple[dict[str, Any], dict[str, str]]:
    data = _load_yaml_config(path)
    if "_base" not in data:
        raise ValueError("yaml must contain a '_base' block")
    if name not in data:
        raise ValueError(f"configuration block not found: {name}")
    env_map_raw = data.get("_envs") or {}
    if not isinstance(env_map_raw, dict):
        raise ValueError("_envs must be a mapping")
    env_map = {str(k): str(v) for k, v in env_map_raw.items() if not _is_blank(k) and not _is_blank(v)}
    cfg = _deep_merge(dict(data.get("_base") or {}), dict(data.get(name) or {}))
    for key in REQUIRED_CFG_KEYS:
        if _is_blank(cfg.get(key)):
            raise ValueError(f"missing required config key after merge: {key}")
    for list_key in LIST_CFG_KEYS:
        cfg[list_key] = _normalize_list(cfg.get(list_key))
    cfg["id"] = str(cfg["id"]).strip()
    cfg["title"] = str(cfg["title"]).strip()
    cfg["code_file"] = str(cfg["code_file"]).strip()
    cfg["language"] = str(cfg.get("language") or "python").strip()
    cfg["kernel_type"] = str(cfg.get("kernel_type") or "notebook").strip()
    cfg.setdefault("submit_type", "notebook")
    cfg.setdefault("submit_file", "submission.csv")
    cfg.setdefault("_msg", "kkr_auto_submit@{ts}")
    cfg.setdefault("_stub", None)
    cfg.setdefault("_versioned_slug", False)
    cfg.setdefault("_version_width", 4)
    cfg["owner"], cfg["slug"] = _slug_parts(cfg["id"])
    return cfg, env_map


def _config_warnings(cfg: dict[str, Any]) -> list[str]:
    return []


def _load_env_for_owner(
    owner: str,
    *,
    env_override: str | None = None,
    env_map: dict[str, str] | None = None,
) -> str | None:
    if env_override:
        path = Path(env_override).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"dotenv file not found: {path}")
    elif env_map and owner in env_map:
        path = Path(env_map[owner]).expanduser()
    else:
        path = Path(".") / f".env.{owner}"
    if path.exists() and callable(load_dotenv):
        load_dotenv(path, override=True)
        _log(f"loaded dotenv: {path}", "DEBUG")
        return _as_relpath(path)
    if env_override:
        raise FileNotFoundError(f"dotenv file not found: {path}")
    return None


def _format_submit_message(template: Any) -> str:
    text = str(template or "kkr@{ts}")
    try:
        text = text.format(ts=datetime.now().strftime(TS_FORMAT))
    except Exception:
        pass
    text = text.strip()
    if len(text) > 500:
        raise ValueError(f"submit message exceeds 500 characters: {len(text)}")
    return text


def _apply_runtime_overrides(cfg: dict[str, Any], args: argparse.Namespace, *, action: str) -> dict[str, Any]:
    out = dict(cfg)

    stub_override = getattr(args, "stub", None)
    if stub_override is not None:
        out["_stub"] = stub_override

    if action == ACTION_SUBMIT:
        msg_override = getattr(args, "msg", None)
        if msg_override is not None:
            msg_override = str(msg_override)
            base = str(out.get("_msg") or "kkr@{ts}")
            if msg_override.startswith("+"):
                extra = msg_override[1:].strip()
                out["_msg"] = f"{base} {extra}".strip() if extra else base
            else:
                out["_msg"] = msg_override
        _format_submit_message(out.get("_msg"))

    return out


def _get_kaggle_api() -> Any:
    spec = importlib.util.find_spec("kaggle.api.kaggle_api_extended")
    if spec is None:
        raise RuntimeError("missing dependency: kaggle")
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    return api


def _load_notebook(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return nbformat.read(handle, as_version=4)


def _save_notebook(path: Path, notebook: Any) -> None:
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        nbformat.write(notebook, handle)


def _ensure_papermill_metadata(notebook: Any) -> None:
    metadata = getattr(notebook, "metadata", None)
    if metadata is None:
        notebook.metadata = {}
        metadata = notebook.metadata
    kernelspec = metadata.get("kernelspec") or {}
    kernelspec.setdefault("name", "python3")
    kernelspec.setdefault("display_name", "Python 3")
    metadata["kernelspec"] = kernelspec
    language_info = metadata.get("language_info") or {}
    language_info.setdefault("name", "python")
    metadata["language_info"] = language_info


def _normalize_tags(cell: Any) -> list[str]:
    return [str(tag) for tag in cell.metadata.get("tags", []) if str(tag).strip()]


def _should_drop_for_action(cell: Any, action: str, cfg: dict[str, Any]) -> tuple[bool, str | None]:
    tags = [tag.lower() for tag in _normalize_tags(cell)]
    drop_tags = {str(tag).lower() for tag in _normalize_list(cfg.get("_drop_tags"))}
    if cell.cell_type == "markdown":
        return True, "markdown"
    if action == ACTION_SUBMIT and any(tag in drop_tags for tag in tags):
        return True, "drop_tag"
    if action == ACTION_SUBMIT and any(DEBUG_TAG_RE.match(tag) for tag in tags):
        return True, "debug"
    return False, None


def build_notebook(
    src_path: Path,
    dst_path: Path,
    action: str,
    cfg: dict[str, Any],
    stub_code: str | None = None,
) -> dict[str, Any]:
    notebook = _load_notebook(src_path)
    new_cells = []
    dropped_markdown = dropped_debug = dropped_tagged = stubbed = 0
    for cell in notebook.cells:
        drop, reason = _should_drop_for_action(cell, action, cfg)
        if drop:
            if reason == "markdown":
                dropped_markdown += 1
            elif reason == "debug":
                dropped_debug += 1
            else:
                dropped_tagged += 1
            continue
        new_cell = copy.deepcopy(cell)
        if getattr(new_cell, "cell_type", None) == "code":
            new_cell.outputs = []
            new_cell.execution_count = None
            if stub_code is not None and any(tag.lower() == "stub" for tag in _normalize_tags(new_cell)):
                new_cell.source = bytes(stub_code, "utf-8").decode("unicode_escape")
                stubbed += 1
        new_cells.append(new_cell)
    notebook.cells = new_cells
    _ensure_papermill_metadata(notebook)
    _save_notebook(dst_path, notebook)
    return {
        "src": _as_relpath(src_path),
        "dst": _as_relpath(dst_path),
        "action": action,
        "kept_cells": len(new_cells),
        "dropped_markdown_cells": dropped_markdown,
        "dropped_debug_cells": dropped_debug,
        "dropped_tagged_cells": dropped_tagged,
        "stubbed_cells": stubbed,
    }


def build_kernel_metadata(cfg: dict[str, Any], run_dir: Path, staged_name: str) -> tuple[Path, KernelMetadata]:
    meta = KernelMetadata(
        id=cfg["id"],
        title=cfg["title"],
        code_file=staged_name,
        language=cfg.get("language", "python"),
        kernel_type=cfg.get("kernel_type", "notebook"),
        is_private=bool(cfg.get("is_private", True)),
        enable_gpu=bool(cfg.get("enable_gpu", False)),
        enable_tpu=bool(cfg.get("enable_tpu", False)),
        enable_internet=bool(cfg.get("enable_internet", False)),
        competition_sources=_normalize_list(cfg.get("competition_sources")),
        kernel_sources=_normalize_list(cfg.get("kernel_sources")),
        dataset_sources=_normalize_list(cfg.get("dataset_sources")),
        model_sources=_normalize_list(cfg.get("model_sources")),
        keywords=_normalize_list(cfg.get("keywords")),
        docker_image=cfg.get("docker_image"),
        machine_shape=cfg.get("machine_shape"),
        persistence=cfg.get("persistence"),
    )
    path = run_dir / DEFAULT_METADATA_FILENAME
    _write_json(path, meta)
    return path, meta


def _coerce_push_result(resp: Any) -> PushResult:
    if resp is None:
        return PushResult()
    if hasattr(resp, "to_dict"):
        try:
            raw = resp.to_dict()
        except Exception:
            raw = {"result": str(resp)}
    elif isinstance(resp, dict):
        raw = dict(resp)
    else:
        raw = {f: _attr(resp, f, default=None) for f in PUSH_RESULT_FIELDS if _attr(resp, f, default=None) is not None}
        if not raw:
            raw = {"result": str(resp)}
    kernel_id = _attr(raw, "kernel_id", "kernelId", default=None)
    version_number = _attr(raw, "version_number", "versionNumber", default=None)
    try:
        kernel_id = int(kernel_id) if kernel_id not in (None, "") else None
    except Exception:
        kernel_id = None
    try:
        version_number = int(version_number) if version_number not in (None, "") else None
    except Exception:
        version_number = None
    return PushResult(
        ref=_attr(raw, "ref", default=None),
        url=_attr(raw, "url", default=None),
        error=_attr(raw, "error", default=None),
        kernel_id=kernel_id,
        version_number=version_number,
        invalid_tags=_normalize_list(_attr(raw, "invalidTags", default=[])),
        invalid_dataset_sources=_normalize_list(_attr(raw, "invalidDatasetSources", default=[])),
        invalid_competition_sources=_normalize_list(_attr(raw, "invalidCompetitionSources", default=[])),
        invalid_kernel_sources=_normalize_list(_attr(raw, "invalidKernelSources", default=[])),
        invalid_model_sources=_normalize_list(_attr(raw, "invalidModelSources", default=[])),
        raw=raw,
    )


def _push_success(push_result: PushResult) -> bool:
    return not push_result.error and push_result.version_number not in (None, 0)


def _status_text(status_resp: Any) -> str:
    return str(_attr(status_resp, *STATUS_KEYS, default=status_resp) or "").strip()


def parse_kernel_status(status_resp: Any) -> str:
    text = _status_text(status_resp).lower()
    if not text:
        return "unknown"
    if any(x in text for x in ("cancelled", "canceled", "cancel")):
        return "cancelled"
    if any(x in text for x in ("complete", "completed", "success")):
        return "complete"
    if "running" in text:
        return "running"
    if any(x in text for x in ("queued", "pending")):
        return "queued"
    if any(x in text for x in ("error", "failed")):
        return "error"
    return text


def _extract_output_listing(resp: Any) -> tuple[list[str], str]:
    if isinstance(resp, tuple) and len(resp) == 2:
        files, status = resp
        return [str(x) for x in list(files or [])], str(status or "")
    if isinstance(resp, dict):
        return [str(x) for x in _normalize_list(_attr(resp, "files", default=[]))], str(
            _attr(resp, "status", default="")
        )
    return [], ""


def _scan_relative_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    return [_as_relpath(p) for p in sorted(root.rglob("*")) if p.is_file()]


def _make_run_id(name: str) -> str:
    return f"{name}_{datetime.now().strftime(TS_FORMAT)}_{uuid.uuid4().hex[:6]}"


def _registry_root(run_root: Path) -> Path:
    return run_root / DEFAULT_REGISTRY_DIRNAME


def _registry_path(run_root: Path, run_id: str) -> Path:
    return _registry_root(run_root) / f"{run_id}.json"


def _version_index_path(run_root: Path) -> Path:
    return run_root / DEFAULT_VERSION_INDEX_FILENAME


def _save_manifest(run_dir: Path, manifest: RunManifest) -> None:
    _write_json(run_dir / DEFAULT_MANIFEST_FILENAME, manifest)


def _load_manifest(run_dir: Path) -> RunManifest:
    return _dataclass_from_dict(RunManifest, _read_json(run_dir / DEFAULT_MANIFEST_FILENAME))


def _save_state(run_dir: Path, state: RunState) -> None:
    _write_json(run_dir / DEFAULT_STATE_FILENAME, state)


def _save_registry(run_root: Path, entry: RegistryEntry) -> None:
    _write_json(_registry_path(run_root, entry.run_id), entry)


def _load_registry(run_root: Path, run_id: str) -> RegistryEntry:
    return _dataclass_from_dict(RegistryEntry, _read_json(_registry_path(run_root, run_id)))


def _list_registry_entries(run_root: Path) -> list[RegistryEntry]:
    root = _registry_root(run_root)
    if not root.exists():
        return []
    out = []
    for path in sorted(root.glob("*.json")):
        try:
            out.append(_dataclass_from_dict(RegistryEntry, _read_json(path)))
        except Exception as exc:
            _log(f"skipping invalid registry entry {path.name}: {exc}", "WARN")
    out.sort(key=lambda x: (x.created_at, x.run_id), reverse=True)
    return out


def _load_version_index(run_root: Path) -> dict[str, int]:
    path = _version_index_path(run_root)
    if not path.exists():
        return {}
    raw = _read_json(path)
    return {str(k): int(v) for k, v in raw.items() if str(v).isdigit()}


def _save_version_index(run_root: Path, data: dict[str, int]) -> None:
    _write_json(_version_index_path(run_root), data)


def _scan_highest_version(run_root: Path, base_kernel_ref: str) -> int:
    highest = 0
    for entry in _list_registry_entries(run_root):
        if (entry.base_kernel_ref or entry.kernel_ref) != base_kernel_ref:
            continue
        if entry.version_label:
            m = VERSION_LABEL_RE.match(entry.version_label)
            if m:
                highest = max(highest, int(m.group(1)))
    return highest


def _preview_or_allocate_version(run_root: Path, base_kernel_ref: str, *, width: int, allocate: bool) -> str:
    index = _load_version_index(run_root)
    current = max(
        int(index.get(base_kernel_ref, 0) or 0),
        _scan_highest_version(run_root, base_kernel_ref),
    )
    nxt = current + 1
    if allocate:
        index[base_kernel_ref] = nxt
        _save_version_index(run_root, index)
    return f"v{nxt:0{max(1, width)}d}"


def _apply_versioned_slug(
    run_root: Path, cfg: dict[str, Any], *, allocate: bool
) -> tuple[dict[str, Any], str, str, str | None]:
    base_kernel_ref = cfg["id"]
    base_title = cfg["title"]
    cfg2 = dict(cfg)
    if not bool(cfg.get("_versioned_slug")):
        return cfg2, base_kernel_ref, base_title, None
    owner, base_slug = _slug_parts(base_kernel_ref)
    version_label = _preview_or_allocate_version(
        run_root,
        base_kernel_ref,
        width=int(cfg.get("_version_width") or 4),
        allocate=allocate,
    )
    cfg2["id"] = f"{owner}/{base_slug}-{version_label}"
    cfg2["title"] = f"{base_title}-{version_label}"
    cfg2["owner"], cfg2["slug"] = _slug_parts(cfg2["id"])
    return cfg2, base_kernel_ref, base_title, version_label


def _score_to_number(value: Any) -> float | str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        text = str(value).strip()
        return text or None


def _extract_score_from_item(item: Any) -> float | str | None:
    for key in SCORE_KEYS:
        score = _score_to_number(_attr(item, key, default=None))
        if score is not None:
            return score
    return None


def _best_effort_score_info(api: Any, competition: str | None) -> ScoreInfo:
    if not competition:
        return ScoreInfo()
    for source_name, method_name in (
        ("competition_submissions", "competition_submissions"),
        ("competition_submissions_cli", "competition_submissions_cli"),
    ):
        method = getattr(api, method_name, None)
        if not callable(method):
            continue
        try:
            raw = method(competition)
        except TypeError:
            try:
                raw = method(competition=competition)
            except Exception:
                continue
        except Exception:
            continue
        items = raw if isinstance(raw, list) else _normalize_list(_attr(raw, "submissions", default=[]))
        scores = [s for s in (_extract_score_from_item(item) for item in items) if s is not None]
        numeric = [s for s in scores if isinstance(s, float)]
        latest = scores[0] if scores else None
        best_public = max(numeric) if numeric else None
        return ScoreInfo(
            latest_submission_score=latest,
            best_public_score=best_public,
            pb_score=best_public if best_public is not None else latest,
            score_source=source_name,
            raw={"count": len(items)},
        )
    return ScoreInfo()


def _output_file_candidates(run_dir: Path, submit_file: str) -> list[Path]:
    path = Path(submit_file)
    candidates = []
    for name in (
        submit_file,
        path.name,
        f"{DEFAULT_OUTPUT_DIRNAME}/{path.name}",
        f"{DEFAULT_SOURCE_DIRNAME}/{path.name}",
    ):
        candidate = run_dir / name
        if candidate.exists() and candidate.is_file():
            candidates.append(candidate)
    out_root = run_dir / DEFAULT_OUTPUT_DIRNAME
    if out_root.exists():
        candidates.extend([p for p in sorted(out_root.rglob(path.name)) if p.is_file()])
    uniq = []
    seen = set()
    for p in candidates:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def _build_ctx(
    action: str,
    name: str,
    cfg: dict[str, Any],
    run_dir: Path,
    output_files: list[str],
    status: str,
) -> KKRCtx:
    return KKRCtx(
        action=action,
        name=name,
        cfg=cfg,
        run_dir=run_dir,
        kernel_id=cfg["id"],
        output_files=output_files,
        status=status,
    )


def _unpack_zip_files(run_dir: Path) -> list[str]:
    extracted = []
    root = run_dir / DEFAULT_OUTPUT_DIRNAME
    if not root.exists():
        return extracted
    for zip_path in sorted(root.rglob("*.zip")):
        target = run_dir / DEFAULT_ZIP_DIRNAME / zip_path.stem
        _ensure_dir(target)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(target)
        extracted.append(_as_relpath(target))
    return extracted


def _write_pending_submit_marker(run_dir: Path, state: str, message: str) -> None:
    _write_json(
        run_dir / DEFAULT_SUBMIT_FILENAME,
        CompetitionSubmitResult(ok=False, state=state, message=message, raw={"pending": True}),
    )


def _stage_run_notebook(
    run_dir: Path, cfg: dict[str, Any], name: str, action: str
) -> tuple[Path, dict[str, Any], KernelMetadata]:
    src_nb = Path(cfg["code_file"]).expanduser().resolve()
    staged_nb = run_dir / f"{name}.ipynb"
    notebook_info = build_notebook(src_nb, staged_nb, action, cfg, cfg.get("_stub"))
    _, meta = build_kernel_metadata(cfg, run_dir, staged_nb.name)
    return staged_nb, notebook_info, meta


def _prepare_submit_artifacts(
    run_dir: Path, entry: RegistryEntry, manifest: RunManifest, cfg: dict[str, Any]
) -> RunManifest:
    submit_cfg = dict(cfg)
    submit_cfg["id"] = entry.kernel_ref
    if entry.base_title and entry.version_label:
        submit_cfg["title"] = f"{entry.base_title}-{entry.version_label}"
    submit_cfg["owner"], submit_cfg["slug"] = _slug_parts(submit_cfg["id"])
    _, notebook_info, meta = _stage_run_notebook(run_dir, submit_cfg, entry.name, ACTION_SUBMIT)
    manifest.cfg = submit_cfg
    manifest.notebook = notebook_info
    manifest.kernel_metadata = _to_data(meta)
    _save_manifest(run_dir, manifest)
    return manifest


def _post_process(
    run_dir: Path,
    action: str,
    name: str,
    cfg: dict[str, Any],
    output_files: list[str],
    status: str,
) -> dict[str, Any]:
    extracted_dirs = _unpack_zip_files(run_dir)
    ctx = _build_ctx(action, name, cfg, run_dir, output_files, status)
    run_exts(ctx, cfg.get("_exts") or [])
    result = {"extracted_dirs": extracted_dirs}
    _write_json(run_dir / DEFAULT_POSTPROCESS_FILENAME, result)
    return result


def _determine_submit_state(entry: RegistryEntry, manifest: RunManifest, current_status: str | None = None) -> str:
    sr = dict(manifest.submit_result or {})
    if sr:
        state = str(sr.get("state") or "").strip()
        if state:
            return state
        return "submitted" if sr.get("ok") else "failed"
    if entry.action == ACTION_SUBMIT:
        return (
            "pending_competition_submit"
            if (current_status or entry.status) in SUCCESS_STATUSES
            else "pending_kernel_success"
        )
    return entry.submit_state or "not_applicable"


def _row_from_entry(entry: RegistryEntry) -> dict[str, Any]:
    return {
        "run_id": entry.run_id,
        "name": entry.name,
        "action": entry.action,
        "version_label": entry.version_label,
        "version": entry.version_number,
        "status": entry.status,
        "submit_state": entry.submit_state,
        "url": entry.url,
        "kernel_ref": entry.kernel_ref,
        "base_kernel_ref": entry.base_kernel_ref,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def _resolve_selector(run_root: Path, args: argparse.Namespace, *, allow_missing_name: bool = False) -> RegistryEntry:
    if getattr(args, "run", None):
        return _load_registry(run_root, args.run)
    entries = _list_registry_entries(run_root)
    if getattr(args, "kernel", None):
        entries = [x for x in entries if x.kernel_ref == args.kernel]
    if getattr(args, "name", None):
        entries = [x for x in entries if x.name == args.name]
    if getattr(args, "version", None) is not None:
        entries = [x for x in entries if x.version_number == args.version]
    if not entries:
        if (
            allow_missing_name
            and not getattr(args, "name", None)
            and not getattr(args, "kernel", None)
            and getattr(args, "version", None) is None
        ):
            raise ValueError("please provide NAME, --run, or --kernel/--version")
        raise FileNotFoundError("no matching run found")
    return entries[0]


def _resolved_run(run_root: Path, args: argparse.Namespace) -> ResolvedRun:
    entry = _resolve_selector(run_root, args, allow_missing_name=True)
    run_dir = _resolve_stored_path(entry.run_dir)
    manifest = _load_manifest(run_dir)
    return ResolvedRun(entry=entry, manifest=manifest, cfg=dict(manifest.cfg or {}), run_dir=run_dir)


def _competition_submit(
    api: Any,
    cfg: dict[str, Any],
    run_dir: Path,
    entry: RegistryEntry,
    manifest: RunManifest,
) -> CompetitionSubmitResult:
    manifest = _prepare_submit_artifacts(run_dir, entry, manifest, cfg)
    competition = cfg.get("competition")
    submit_type = str(cfg.get("submit_type") or "notebook").lower()
    message = _format_submit_message(cfg.get("_msg"))
    if not competition:
        result = CompetitionSubmitResult(ok=False, state="unsupported", message="competition is not configured")
    elif submit_type == "notebook":
        if entry.version_number in (None, 0):
            result = CompetitionSubmitResult(
                ok=False,
                state="failed",
                message="kernel version is missing; cannot call competition_submit_code",
            )
        else:
            try:
                resp = api.competition_submit_code(
                    competition=competition,
                    file_name=cfg.get("submit_file") or "submission.csv",
                    kernel=entry.kernel_ref,
                    kernel_version=entry.version_number,
                    message=message,
                    quiet=False,
                )
                raw = (
                    resp.to_dict()
                    if hasattr(resp, "to_dict")
                    else (dict(resp) if isinstance(resp, dict) else {"result": str(resp)})
                )
                result = CompetitionSubmitResult(
                    ok=True,
                    state="submitted",
                    message=_attr(raw, "message", default=None),
                    ref=_attr(raw, "ref", default=None),
                    raw=raw,
                )
            except Exception as exc:
                result = CompetitionSubmitResult(ok=False, state="failed", message=str(exc), raw={"error": str(exc)})
    elif submit_type == "local":
        candidates = _output_file_candidates(run_dir, str(cfg.get("submit_file") or "submission.csv"))
        if not candidates:
            result = CompetitionSubmitResult(
                ok=False,
                state="failed",
                message=f"submit file not found under {run_dir}: {cfg.get('submit_file')}",
            )
        else:
            try:
                resp = api.competition_submit(
                    file_name=str(candidates[0]),
                    competition=competition,
                    message=message,
                )
                raw = (
                    resp.to_dict()
                    if hasattr(resp, "to_dict")
                    else (dict(resp) if isinstance(resp, dict) else {"result": str(resp)})
                )
                result = CompetitionSubmitResult(
                    ok=True,
                    state="submitted",
                    message=_attr(raw, "message", default=None),
                    ref=_attr(raw, "ref", default=None),
                    raw=raw,
                )
            except Exception as exc:
                result = CompetitionSubmitResult(ok=False, state="failed", message=str(exc), raw={"error": str(exc)})
    else:
        result = CompetitionSubmitResult(
            ok=False,
            state="unsupported",
            message=f"unsupported submit_type: {submit_type}",
        )
    manifest.submit_result = _to_data(result)
    _write_json(run_dir / DEFAULT_SUBMIT_FILENAME, result)
    _save_manifest(run_dir, manifest)
    entry.submit_state = result.state
    return result


def _competition_submit_with_retry(
    api: Any,
    cfg: dict[str, Any],
    run_dir: Path,
    entry: RegistryEntry,
    manifest: RunManifest,
    *,
    timeout_seconds: int = DEFAULT_SUBMIT_RETRY_TIMEOUT,
    interval_seconds: int = DEFAULT_SUBMIT_RETRY_INTERVAL,
    initial_delay_seconds: int = DEFAULT_SUBMIT_RETRY_INITIAL_DELAY,
) -> CompetitionSubmitResult:
    attempts: list[dict[str, Any]] = []
    deadline = time.time() + max(0, int(timeout_seconds or 0))
    last_result: CompetitionSubmitResult | None = None
    if initial_delay_seconds > 0:
        time.sleep(initial_delay_seconds)
    while True:
        try:
            raw_status_obj = api.kernels_status(entry.kernel_ref)
            kernel_status = parse_kernel_status(raw_status_obj)
            raw_status = _status_text(raw_status_obj)
        except Exception as exc:
            kernel_status = "unknown"
            raw_status = str(exc)
        result = _competition_submit(api, cfg, run_dir, entry, manifest)
        last_result = result
        attempts.append(
            {
                "at": _now_iso(),
                "kernel_status": kernel_status,
                "raw_status": raw_status,
                "submit_ok": result.ok,
                "submit_state": result.state,
                "submit_message": result.message,
            }
        )
        if result.ok:
            result.raw = dict(result.raw or {})
            result.raw["submit_retry"] = {
                "timeout_seconds": int(timeout_seconds or 0),
                "interval_seconds": int(interval_seconds or 0),
                "initial_delay_seconds": int(initial_delay_seconds or 0),
                "attempts": attempts,
            }
            _write_json(run_dir / DEFAULT_SUBMIT_FILENAME, result)
            manifest.submit_result = _to_data(result)
            _save_manifest(run_dir, manifest)
            entry.submit_state = result.state
            return result
        if time.time() >= deadline:
            break
        time.sleep(max(1, int(interval_seconds or 1)))
    if last_result is None:
        last_result = CompetitionSubmitResult(ok=False, state="failed", message="competition submit retry exhausted")
    last_result.raw = dict(last_result.raw or {})
    last_result.raw["submit_retry"] = {
        "timeout_seconds": int(timeout_seconds or 0),
        "interval_seconds": int(interval_seconds or 0),
        "initial_delay_seconds": int(initial_delay_seconds or 0),
        "attempts": attempts,
    }
    _write_json(run_dir / DEFAULT_SUBMIT_FILENAME, last_result)
    manifest.submit_result = _to_data(last_result)
    _save_manifest(run_dir, manifest)
    entry.submit_state = last_result.state
    return last_result


def _refresh_entry_from_remote(
    run_root: Path,
    yaml_path: Path,
    entry: RegistryEntry,
    *,
    env_override: str | None = None,
) -> tuple[RegistryEntry, ScoreInfo, str, dict[str, Any]]:
    cfg, env_map = _merged_config(yaml_path, entry.name)
    _load_env_for_owner(cfg["owner"], env_override=env_override, env_map=env_map)
    api = _get_kaggle_api()
    raw = api.kernels_status(entry.kernel_ref)
    status = parse_kernel_status(raw)
    raw_status = _status_text(raw)
    score = _best_effort_score_info(api, cfg.get("competition")) if entry.action == ACTION_SUBMIT else ScoreInfo()
    entry.updated_at = _now_iso()
    entry.status = status
    entry.raw_status = raw_status
    if score.pb_score is not None:
        entry.pb_score = score.pb_score
        entry.score_source = score.score_source
    run_dir = _resolve_stored_path(entry.run_dir)
    manifest = _load_manifest(run_dir)
    entry.submit_state = _determine_submit_state(entry, manifest, status)
    _save_registry(run_root, entry)
    state = RunState(
        run_id=entry.run_id,
        status=status,
        updated_at=entry.updated_at,
        action=ACTION_STATUS,
        raw_status=raw_status,
        url=entry.url,
        version_number=entry.version_number,
        kernel_id=entry.kernel_id,
        competition_submitted=bool(manifest.submit_result),
        latest_submission_score=score.latest_submission_score,
        best_public_score=score.best_public_score,
        pb_score=score.pb_score,
        score_source=score.score_source,
        submit_state=entry.submit_state,
    )
    _save_state(run_dir, state)
    return entry, score, raw_status, _read_json(run_dir / DEFAULT_STATE_FILENAME)


def _watch_run(
    args: argparse.Namespace, *, resolved: ResolvedRun, auto_submit: bool
) -> tuple[RunState, list[dict[str, Any]], CompetitionSubmitResult | None, ScoreInfo | None]:
    api = _get_kaggle_api()
    history = []
    deadline = None if int(getattr(args, "timeout", 0) or 0) <= 0 else time.time() + int(args.timeout)
    final_status = "unknown"
    final_raw = ""
    while True:
        raw = api.kernels_status(resolved.entry.kernel_ref)
        status = parse_kernel_status(raw)
        raw_status = _status_text(raw)
        at = _now_iso()

        row = {"at": at, "status": status, "raw_status": raw_status}
        history.append(row)
        final_status, final_raw = status, raw_status
        resolved.entry.status = status
        resolved.entry.raw_status = raw_status
        resolved.entry.updated_at = at
        resolved.entry.submit_state = _determine_submit_state(resolved.entry, resolved.manifest, status)
        _save_registry(Path(args.run_root).expanduser().resolve(), resolved.entry)
        _save_state(
            resolved.run_dir,
            RunState(
                run_id=resolved.entry.run_id,
                status=status,
                updated_at=at,
                action=ACTION_WATCH,
                raw_status=raw_status,
                url=resolved.entry.url,
                version_number=resolved.entry.version_number,
                kernel_id=resolved.entry.kernel_id,
                submit_state=resolved.entry.submit_state,
            ),
        )
        _log(f"watch {resolved.entry.run_id}: status={status} raw={raw_status}")

        if status in TERMINAL_STATUSES:
            break
        if not getattr(args, "wait", True):
            break
        if deadline is not None and time.time() >= deadline:
            raise TimeoutError(f"watch timed out for {resolved.entry.run_id}")
        time.sleep(max(5, int(getattr(args, "interval", DEFAULT_INTERVAL) or DEFAULT_INTERVAL)))
    _write_json(resolved.run_dir / DEFAULT_WATCH_FILENAME, {"history": history})
    submit_result = None
    score = None
    if final_status in SUCCESS_STATUSES and auto_submit and not resolved.manifest.submit_result:
        submit_result = _competition_submit_with_retry(
            api, resolved.cfg, resolved.run_dir, resolved.entry, resolved.manifest
        )
        if submit_result.ok:
            score = _best_effort_score_info(api, resolved.cfg.get("competition"))
            resolved.entry.pb_score = score.pb_score
            resolved.entry.score_source = score.score_source
        resolved.entry.submit_state = submit_result.state
        _save_registry(Path(args.run_root).expanduser().resolve(), resolved.entry)
    elif resolved.manifest.submit_result:
        submit_result = _dataclass_from_dict(CompetitionSubmitResult, resolved.manifest.submit_result)
        resolved.entry.submit_state = submit_result.state or resolved.entry.submit_state
    state = RunState(
        run_id=resolved.entry.run_id,
        status=final_status,
        updated_at=_now_iso(),
        action=ACTION_WATCH,
        raw_status=final_raw,
        url=resolved.entry.url,
        version_number=resolved.entry.version_number,
        kernel_id=resolved.entry.kernel_id,
        competition_submitted=bool(submit_result and submit_result.ok),
        latest_submission_score=score.latest_submission_score if score else None,
        best_public_score=score.best_public_score if score else None,
        pb_score=score.pb_score if score else resolved.entry.pb_score,
        score_source=score.score_source if score else resolved.entry.score_source,
        submit_state=resolved.entry.submit_state,
    )
    _save_state(resolved.run_dir, state)
    return state, history, submit_result, score


def _fetch_runtime(cfg: dict[str, Any], run_dir: Path) -> FetchResult:
    source_dir = run_dir / DEFAULT_SOURCE_DIRNAME
    output_dir = run_dir / DEFAULT_OUTPUT_DIRNAME
    _ensure_dir(source_dir)
    _ensure_dir(output_dir)
    api = _get_kaggle_api()
    source_ok = False
    try:
        api.kernels_pull(kernel=cfg["id"], path=str(source_dir), metadata=True)
        source_ok = True
    except Exception as exc:
        _log(f"kernels_pull warning: {exc}", "WARN")
    output_resp = api.kernels_output(kernel=cfg["id"], path=str(output_dir))
    _, output_status = _extract_output_listing(output_resp)
    output_files = _scan_relative_files(output_dir)
    result = FetchResult(
        source_dir=_as_relpath(source_dir),
        source_ok=source_ok,
        output_dir=_as_relpath(output_dir),
        output_files=output_files,
        output_status=output_status,
        extracted_dirs=_unpack_zip_files(run_dir),
    )
    _write_json(run_dir / DEFAULT_FETCH_FILENAME, result)
    return result


def _selector_mode_submit(args: argparse.Namespace) -> bool:
    return bool(
        getattr(args, "run", None) or getattr(args, "kernel", None) or getattr(args, "version", None) is not None
    )


def _create_new_run(args: argparse.Namespace, *, action: str) -> int:
    run_root = Path(args.run_root).expanduser().resolve()
    cfg_base, env_map = _merged_config(Path(args.yaml).expanduser().resolve(), args.name)
    cfg_base = _apply_runtime_overrides(cfg_base, args, action=action)

    env_path = _load_env_for_owner(cfg_base["owner"], env_override=getattr(args, "env", None), env_map=env_map)
    warnings = _config_warnings(cfg_base)
    cfg, base_kernel_ref, base_title, version_label = _apply_versioned_slug(
        run_root, cfg_base, allocate=not args.dry_run
    )

    run_id = _make_run_id(args.name)
    run_dir = _run_dir(run_root, run_id)
    run_dir_value = _stored_run_dir(run_root, run_id)
    if args.dry_run:
        return _emit_ok(
            args,
            action=action,
            name=args.name,
            run_id=run_id,
            run_dir=run_dir_value,
            base_kernel_ref=base_kernel_ref,
            kernel_ref=cfg["id"],
            version_label=version_label,
            warnings=warnings,
            wait=bool(getattr(args, "wait", False)),
            submit_state="pending_kernel_success" if action == ACTION_SUBMIT else "not_applicable",
            dry_run=True,
        )
    _ensure_dir(run_dir)
    _ensure_dir(_registry_root(run_root))
    _, notebook_info, meta = _stage_run_notebook(run_dir, cfg, args.name, action)
    created_at = _now_iso()
    manifest = RunManifest(
        run_id=run_id,
        name=args.name,
        action=action,
        created_at=created_at,
        run_dir=run_dir_value,
        base_kernel_ref=base_kernel_ref,
        kernel_ref=cfg["id"],
        owner=cfg["owner"],
        slug=cfg["slug"],
        base_title=base_title,
        version_label=version_label,
        competition=cfg.get("competition"),
        submit_type=cfg.get("submit_type"),
        submit_file=cfg.get("submit_file"),
        env_path=env_path,
        warnings=warnings,
        cfg=cfg,
        notebook=notebook_info,
        kernel_metadata=_to_data(meta),
    )
    _save_manifest(run_dir, manifest)
    entry = RegistryEntry(
        run_id=run_id,
        name=args.name,
        action=action,
        created_at=created_at,
        updated_at=created_at,
        run_dir=run_dir_value,
        base_kernel_ref=base_kernel_ref,
        kernel_ref=cfg["id"],
        owner=cfg["owner"],
        slug=cfg["slug"],
        base_title=base_title,
        version_label=version_label,
        competition=cfg.get("competition"),
        submit_type=cfg.get("submit_type"),
        submit_file=cfg.get("submit_file"),
        env_path=env_path,
        status="staged",
        submit_state="pending_kernel_success" if action == ACTION_SUBMIT else "not_applicable",
    )
    _save_registry(run_root, entry)
    _save_state(
        run_dir,
        RunState(
            run_id=run_id,
            status="staged",
            updated_at=created_at,
            action=action,
            submit_state=entry.submit_state,
        ),
    )
    if action == ACTION_SUBMIT:
        _write_pending_submit_marker(
            run_dir,
            entry.submit_state,
            "waiting for kernel success before competition submit",
        )
    api = _get_kaggle_api()
    resp = api.kernels_push(str(run_dir), timeout=int(args.timeout) if int(args.timeout or 0) > 0 else None)
    push_result = _coerce_push_result(resp)
    manifest.push_result = _to_data(push_result)
    _save_manifest(run_dir, manifest)
    _write_json(run_dir / DEFAULT_PUSH_FILENAME, push_result)
    entry.kernel_id, entry.version_number, entry.url = (
        push_result.kernel_id,
        push_result.version_number,
        push_result.url,
    )
    entry.status = "pushed" if _push_success(push_result) else "push_error"
    entry.updated_at = _now_iso()
    _save_registry(run_root, entry)
    _save_state(
        run_dir,
        RunState(
            run_id=run_id,
            status=entry.status,
            updated_at=entry.updated_at,
            action=action,
            url=entry.url,
            version_number=entry.version_number,
            kernel_id=entry.kernel_id,
            submit_state=entry.submit_state,
        ),
    )
    if not _push_success(push_result):
        return _emit_fail(
            args,
            f"kaggle kernels push failed: {push_result.raw}",
            error="remote_failed",
            exit_code=EXIT_RUNTIME,
            action=action,
            name=args.name,
            run_id=run_id,
            run_dir=run_dir_value,
            base_kernel_ref=base_kernel_ref,
            kernel_ref=cfg["id"],
            version_label=version_label,
            push_result=push_result,
            warnings=warnings,
            submit_state=entry.submit_state,
        )
    if getattr(args, "wait", False):
        resolved = ResolvedRun(entry=entry, manifest=manifest, cfg=cfg, run_dir=run_dir)
        state, history, submit_result, score = _watch_run(
            args, resolved=resolved, auto_submit=(action == ACTION_SUBMIT)
        )
        if state.status not in SUCCESS_STATUSES:
            return _emit_fail(
                args,
                f"kernel finished with status={state.status}",
                error="remote_failed",
                exit_code=EXIT_RUNTIME,
                action=action,
                name=args.name,
                run_id=run_id,
                run_dir=run_dir_value,
                base_kernel_ref=base_kernel_ref,
                kernel_ref=cfg["id"],
                version_label=version_label,
                status=state.status,
                submit_state=state.submit_state,
                history=history,
            )
        if action == ACTION_SUBMIT and submit_result and not submit_result.ok:
            return _emit_fail(
                args,
                submit_result.message or "competition submit failed",
                error="remote_failed",
                exit_code=EXIT_RUNTIME,
                action=action,
                name=args.name,
                run_id=run_id,
                run_dir=run_dir_value,
                base_kernel_ref=base_kernel_ref,
                kernel_ref=cfg["id"],
                version_label=version_label,
                status=state.status,
                submit_state=submit_result.state,
                submit_result=submit_result,
            )
        return _emit_ok(
            args,
            action=action,
            name=args.name,
            run_id=run_id,
            run_dir=run_dir_value,
            base_kernel_ref=base_kernel_ref,
            kernel_ref=cfg["id"],
            version_label=version_label,
            kernel_id=entry.kernel_id,
            version_number=entry.version_number,
            url=entry.url,
            status=state.status,
            submit_state=state.submit_state,
            submit_result=submit_result,
            pb_score=score.pb_score if score else None,
            score_source=score.score_source if score else None,
            warnings=warnings,
        )
    return _emit_ok(
        args,
        action=action,
        name=args.name,
        run_id=run_id,
        run_dir=run_dir_value,
        base_kernel_ref=base_kernel_ref,
        kernel_ref=cfg["id"],
        version_label=version_label,
        kernel_id=entry.kernel_id,
        version_number=entry.version_number,
        url=entry.url,
        status=entry.status,
        submit_state=entry.submit_state,
        warnings=warnings,
    )


def _submit_existing(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).expanduser().resolve()
    resolved = _resolved_run(run_root, args)
    cfg_yaml, env_map = _merged_config(Path(args.yaml).expanduser().resolve(), resolved.entry.name)
    _load_env_for_owner(cfg_yaml["owner"], env_override=getattr(args, "env", None), env_map=env_map)
    resolved.cfg = _apply_runtime_overrides(
        _deep_merge(cfg_yaml, dict(resolved.manifest.cfg or {})),
        args,
        action=ACTION_SUBMIT,
    )
    resolved.manifest.cfg = dict(resolved.cfg)
    _save_manifest(resolved.run_dir, resolved.manifest)
    if args.dry_run:
        return _emit_ok(
            args,
            action=ACTION_SUBMIT,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            version_number=resolved.entry.version_number,
            dry_run=True,
        )
    _write_pending_submit_marker(
        resolved.run_dir,
        resolved.entry.submit_state or "pending_kernel_success",
        "waiting for kernel success before competition submit",
    )
    if resolved.manifest.submit_result:
        existing = _dataclass_from_dict(CompetitionSubmitResult, resolved.manifest.submit_result)
        resolved.entry.submit_state = existing.state or resolved.entry.submit_state
        _save_registry(run_root, resolved.entry)
        if existing.ok:
            return _emit_ok(
                args,
                action=ACTION_SUBMIT,
                name=resolved.entry.name,
                run_id=resolved.entry.run_id,
                run_dir=resolved.entry.run_dir,
                base_kernel_ref=resolved.entry.base_kernel_ref,
                kernel_ref=resolved.entry.kernel_ref,
                version_label=resolved.entry.version_label,
                version_number=resolved.entry.version_number,
                url=resolved.entry.url,
                status=resolved.entry.status,
                submit_state=resolved.entry.submit_state,
                submit_result=existing,
                already_submitted=True,
            )
    api = _get_kaggle_api()
    raw = api.kernels_status(resolved.entry.kernel_ref)
    status = parse_kernel_status(raw)
    resolved.entry.status = status
    resolved.entry.raw_status = _status_text(raw)
    resolved.entry.updated_at = _now_iso()
    _save_registry(run_root, resolved.entry)
    if status not in SUCCESS_STATUSES:
        if getattr(args, "wait", False):
            state, history, submit_result, score = _watch_run(args, resolved=resolved, auto_submit=True)
            if state.status not in SUCCESS_STATUSES:
                return _emit_fail(
                    args,
                    f"kernel finished with status={state.status}",
                    error="remote_failed",
                    exit_code=EXIT_RUNTIME,
                    action=ACTION_SUBMIT,
                    name=resolved.entry.name,
                    run_id=resolved.entry.run_id,
                    run_dir=resolved.entry.run_dir,
                    base_kernel_ref=resolved.entry.base_kernel_ref,
                    kernel_ref=resolved.entry.kernel_ref,
                    version_label=resolved.entry.version_label,
                    status=state.status,
                    submit_state=state.submit_state,
                    history=history,
                )
            if submit_result and not submit_result.ok:
                return _emit_fail(
                    args,
                    submit_result.message or "competition submit failed",
                    error="remote_failed",
                    exit_code=EXIT_RUNTIME,
                    action=ACTION_SUBMIT,
                    name=resolved.entry.name,
                    run_id=resolved.entry.run_id,
                    run_dir=resolved.entry.run_dir,
                    base_kernel_ref=resolved.entry.base_kernel_ref,
                    kernel_ref=resolved.entry.kernel_ref,
                    version_label=resolved.entry.version_label,
                    status=state.status,
                    submit_state=submit_result.state,
                    submit_result=submit_result,
                )
            return _emit_ok(
                args,
                action=ACTION_SUBMIT,
                name=resolved.entry.name,
                run_id=resolved.entry.run_id,
                run_dir=resolved.entry.run_dir,
                base_kernel_ref=resolved.entry.base_kernel_ref,
                kernel_ref=resolved.entry.kernel_ref,
                version_label=resolved.entry.version_label,
                version_number=resolved.entry.version_number,
                url=resolved.entry.url,
                status=state.status,
                submit_state=state.submit_state,
                submit_result=submit_result,
                pb_score=score.pb_score if score else None,
                score_source=score.score_source if score else None,
            )
        resolved.entry.submit_state = "pending_kernel_success"
        _save_registry(run_root, resolved.entry)
        _write_pending_submit_marker(
            resolved.run_dir,
            resolved.entry.submit_state,
            "waiting for kernel success before competition submit",
        )
        return _emit_ok(
            args,
            action=ACTION_SUBMIT,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            version_number=resolved.entry.version_number,
            url=resolved.entry.url,
            status=status,
            submit_state=resolved.entry.submit_state,
        )
    submit_result = _competition_submit_with_retry(
        api, resolved.cfg, resolved.run_dir, resolved.entry, resolved.manifest
    )
    score = _best_effort_score_info(api, resolved.cfg.get("competition")) if submit_result.ok else ScoreInfo()
    resolved.entry.updated_at = _now_iso()
    resolved.entry.submit_state = submit_result.state
    if score.pb_score is not None:
        resolved.entry.pb_score = score.pb_score
        resolved.entry.score_source = score.score_source
    _save_registry(run_root, resolved.entry)
    _save_state(
        resolved.run_dir,
        RunState(
            run_id=resolved.entry.run_id,
            status=status,
            updated_at=resolved.entry.updated_at,
            action=ACTION_SUBMIT,
            raw_status=resolved.entry.raw_status,
            url=resolved.entry.url,
            version_number=resolved.entry.version_number,
            kernel_id=resolved.entry.kernel_id,
            competition_submitted=submit_result.ok,
            latest_submission_score=score.latest_submission_score,
            best_public_score=score.best_public_score,
            pb_score=score.pb_score,
            score_source=score.score_source,
            submit_state=resolved.entry.submit_state,
        ),
    )
    if not submit_result.ok:
        return _emit_fail(
            args,
            submit_result.message or "competition submit failed",
            error="remote_failed",
            exit_code=EXIT_RUNTIME,
            action=ACTION_SUBMIT,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            status=status,
            submit_state=submit_result.state,
            submit_result=submit_result,
        )
    return _emit_ok(
        args,
        action=ACTION_SUBMIT,
        name=resolved.entry.name,
        run_id=resolved.entry.run_id,
        run_dir=resolved.entry.run_dir,
        base_kernel_ref=resolved.entry.base_kernel_ref,
        kernel_ref=resolved.entry.kernel_ref,
        version_label=resolved.entry.version_label,
        version_number=resolved.entry.version_number,
        url=resolved.entry.url,
        status=status,
        submit_state=submit_result.state,
        submit_result=submit_result,
        pb_score=score.pb_score,
        score_source=score.score_source,
    )


def _watch_impl(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).expanduser().resolve()
    resolved = _resolved_run(run_root, args)
    cfg, env_map = _merged_config(Path(args.yaml).expanduser().resolve(), resolved.entry.name)
    resolved.cfg = _deep_merge(cfg, dict(resolved.manifest.cfg or {}))
    if args.dry_run:
        return _emit_ok(
            args,
            action=ACTION_WATCH,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            dry_run=True,
        )
    _load_env_for_owner(cfg["owner"], env_override=getattr(args, "env", None), env_map=env_map)
    state, history, submit_result, score = _watch_run(args, resolved=resolved, auto_submit=False)
    if state.status not in SUCCESS_STATUSES:
        return _emit_fail(
            args,
            f"kernel finished with status={state.status}",
            error="remote_failed",
            exit_code=EXIT_RUNTIME,
            action=ACTION_WATCH,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            status=state.status,
            submit_state=state.submit_state,
            history=history,
        )
    return _emit_ok(
        args,
        action=ACTION_WATCH,
        name=resolved.entry.name,
        run_id=resolved.entry.run_id,
        run_dir=resolved.entry.run_dir,
        base_kernel_ref=resolved.entry.base_kernel_ref,
        kernel_ref=resolved.entry.kernel_ref,
        version_label=resolved.entry.version_label,
        kernel_id=resolved.entry.kernel_id,
        version_number=resolved.entry.version_number,
        url=resolved.entry.url,
        status=state.status,
        submit_state=state.submit_state,
        submit_result=submit_result,
        pb_score=score.pb_score if score else resolved.entry.pb_score,
        score_source=score.score_source if score else resolved.entry.score_source,
        history=history,
    )


def _fetch_impl(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).expanduser().resolve()
    resolved = _resolved_run(run_root, args)
    cfg, env_map = _merged_config(Path(args.yaml).expanduser().resolve(), resolved.entry.name)
    cfg = _deep_merge(cfg, dict(resolved.manifest.cfg or {}))
    cfg["id"] = resolved.entry.kernel_ref
    if args.dry_run:
        return _emit_ok(
            args,
            action=ACTION_FETCH,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            dry_run=True,
        )
    _load_env_for_owner(cfg["owner"], env_override=getattr(args, "env", None), env_map=env_map)
    fetch = _fetch_runtime(cfg, resolved.run_dir)
    post = _post_process(
        resolved.run_dir,
        ACTION_FETCH,
        resolved.entry.name,
        cfg,
        fetch.output_files,
        fetch.output_status,
    )
    resolved.entry.updated_at = _now_iso()
    if fetch.output_status:
        resolved.entry.status = fetch.output_status
    _save_registry(run_root, resolved.entry)
    _save_state(
        resolved.run_dir,
        RunState(
            run_id=resolved.entry.run_id,
            status=fetch.output_status or resolved.entry.status,
            updated_at=_now_iso(),
            action=ACTION_FETCH,
            url=resolved.entry.url,
            version_number=resolved.entry.version_number,
            kernel_id=resolved.entry.kernel_id,
            submit_state=resolved.entry.submit_state,
        ),
    )
    return _emit_ok(
        args,
        action=ACTION_FETCH,
        name=resolved.entry.name,
        run_id=resolved.entry.run_id,
        run_dir=resolved.entry.run_dir,
        base_kernel_ref=resolved.entry.base_kernel_ref,
        kernel_ref=resolved.entry.kernel_ref,
        version_label=resolved.entry.version_label,
        kernel_id=resolved.entry.kernel_id,
        version_number=resolved.entry.version_number,
        url=resolved.entry.url,
        status=fetch.output_status or resolved.entry.status,
        submit_state=resolved.entry.submit_state,
        fetch_result=fetch,
        postprocess=post,
    )


def _status_impl(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).expanduser().resolve()
    resolved = _resolved_run(run_root, args)
    if args.dry_run:
        return _emit_ok(
            args,
            action=ACTION_STATUS,
            name=resolved.entry.name,
            run_id=resolved.entry.run_id,
            run_dir=resolved.entry.run_dir,
            base_kernel_ref=resolved.entry.base_kernel_ref,
            kernel_ref=resolved.entry.kernel_ref,
            version_label=resolved.entry.version_label,
            dry_run=True,
        )
    entry, score, raw_status, local_state = _refresh_entry_from_remote(
        run_root,
        Path(args.yaml).expanduser().resolve(),
        resolved.entry,
        env_override=getattr(args, "env", None),
    )
    return _emit_ok(
        args,
        action=ACTION_STATUS,
        name=entry.name,
        run_id=entry.run_id,
        run_dir=entry.run_dir,
        base_kernel_ref=entry.base_kernel_ref,
        kernel_ref=entry.kernel_ref,
        version_label=entry.version_label,
        kernel_id=entry.kernel_id,
        version_number=entry.version_number,
        url=entry.url,
        status=entry.status,
        raw_status=raw_status,
        submit_state=entry.submit_state,
        local_state=local_state,
        pb_score=score.pb_score,
        score_source=score.score_source,
        latest_submission_score=score.latest_submission_score,
        best_public_score=score.best_public_score,
    )


def _list_impl(args: argparse.Namespace) -> int:
    run_root = Path(args.run_root).expanduser().resolve()
    entries = _list_registry_entries(run_root)
    if getattr(args, "run", None):
        entries = [e for e in entries if e.run_id == args.run]
    if getattr(args, "name", None):
        entries = [e for e in entries if e.name == args.name]
    if getattr(args, "kernel", None):
        entries = [e for e in entries if e.kernel_ref == args.kernel]
    if getattr(args, "version", None) is not None:
        entries = [e for e in entries if e.version_number == args.version]
    if getattr(args, "limit", None):
        entries = entries[: max(1, int(args.limit))]
    refreshed = 0
    if getattr(args, "refresh", False):
        yaml_path = Path(args.yaml).expanduser().resolve()
        new_entries = []
        for entry in entries:
            try:
                entry, _, _, _ = _refresh_entry_from_remote(
                    run_root, yaml_path, entry, env_override=getattr(args, "env", None)
                )
                refreshed += 1
            except Exception as exc:
                _log(f"list refresh warning for {entry.run_id}: {exc}", "WARN")
            new_entries.append(entry)
        entries = new_entries
    rows = [_row_from_entry(e) for e in entries]
    return _emit_ok(
        args,
        action=ACTION_LIST,
        count=len(rows),
        refreshed=refreshed,
        queued_count=sum(1 for e in entries if e.status in QUEUED_STATUSES),
        running_count=sum(1 for e in entries if e.status == "running"),
        runs=rows,
    )


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--yaml", default="kkr.yaml", help="Path to kkr.yaml")
    common.add_argument(
        "--run-root",
        default=str(DEFAULT_RUN_ROOT),
        help="Root directory for run folders and registry",
    )
    common.add_argument("--env", help="Override dotenv path for the selected owner")
    common.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    common.add_argument("--dry-run", action="store_true", help="Plan only; do not call Kaggle")
    common.add_argument("--quiet", action="store_true", help="Suppress non-error logs")
    common.add_argument("-v", "--verbose", action="count", default=0, help="Increase log verbosity")
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument(
        "name",
        nargs="?",
        help="Config name, e.g. b09m. For read actions this selects the latest matching run.",
    )
    selector.add_argument("--run", help="Exact RUN_ID under .kkr/")
    selector.add_argument(
        "--kernel",
        help="Exact Kaggle kernel ref, e.g. firefly2006/gpt-oss-120b-b09m-v0006",
    )
    selector.add_argument("--version", type=int, help="Filter a registry lookup by version number")
    parser = argparse.ArgumentParser(
        prog="kkr.py",
        description="Kaggle notebook runner with stable JSON outputs, local registry, and .kkr run tracking.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="action", required=True)
    push = sub.add_parser(ACTION_PUSH, parents=[common], help="Build and push a Kaggle notebook run")
    push.add_argument("name", help="Config name in kkr.yaml, e.g. b09m")
    push.add_argument("--stub", help="Override _stub for this run only")
    push.add_argument(
        "--wait",
        action="store_true",
        help="Wait until the remote kernel reaches a terminal status",
    )
    push.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds when --wait is set",
    )
    push.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Push/watch timeout in seconds; 0 means no timeout",
    )
    submit = sub.add_parser(
        ACTION_SUBMIT,
        parents=[common, selector],
        help="Create and submit a new version, or submit an existing selected version",
    )
    submit.add_argument("--stub", help="Override _stub for this submit only")
    submit.add_argument(
        "--msg",
        help="Override submit message; use '+TEXT' to append to YAML _msg (max 500 chars after formatting)",
    )
    submit.add_argument(
        "--wait",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Wait for kernel success before competition submit when needed",
    )
    submit.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds when waiting",
    )
    submit.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Push/watch timeout in seconds; 0 means no timeout",
    )
    watch = sub.add_parser(
        ACTION_WATCH,
        parents=[common, selector],
        help="Watch a run selected by NAME, --run, or --kernel/--version",
    )
    watch.add_argument(
        "--wait",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Poll until terminal status; use --no-wait for a single check",
    )
    watch.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Polling interval in seconds",
    )
    watch.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Watch timeout in seconds; 0 means no timeout",
    )
    sub.add_parser(
        ACTION_FETCH,
        parents=[common, selector],
        help="Download source/output artifacts for a selected run",
    )
    sub.add_parser(
        ACTION_STATUS,
        parents=[common, selector],
        help="Query remote status for a selected run",
    )
    lst = sub.add_parser(
        ACTION_LIST,
        parents=[common, selector],
        help="List tracked runs from the local registry",
    )
    lst.add_argument("--limit", type=int, default=50, help="Maximum number of rows to return")
    lst.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh remote kernel status before printing rows",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    # if getattr(args, "stub", None) is not None:
    #     args.stub = bytes(str(args.stub), "utf-8").decode("unicode_escape")
    _set_log_mode(getattr(args, "quiet", False), getattr(args, "verbose", 0))
    try:
        if (
            getattr(args, "version", None) is not None
            and not getattr(args, "run", None)
            and not getattr(args, "kernel", None)
            and not getattr(args, "name", None)
        ):
            return _emit_fail(
                args,
                "--version requires NAME, --run, or --kernel",
                error="invalid_input",
                exit_code=EXIT_INPUT,
            )
        if args.action == ACTION_PUSH:
            return _create_new_run(args, action=ACTION_PUSH)
        if args.action == ACTION_SUBMIT:
            if _selector_mode_submit(args):
                return _submit_existing(args)
            if not getattr(args, "name", None):
                return _emit_fail(
                    args,
                    "submit requires NAME for a new version, or --run / --kernel[/--version] for an existing version",
                    error="invalid_input",
                    exit_code=EXIT_INPUT,
                )
            return _create_new_run(args, action=ACTION_SUBMIT)
        if args.action == ACTION_WATCH:
            return _watch_impl(args)
        if args.action == ACTION_FETCH:
            return _fetch_impl(args)
        if args.action == ACTION_STATUS:
            return _status_impl(args)
        if args.action == ACTION_LIST:
            return _list_impl(args)
        return _emit_fail(
            args,
            f"unsupported action: {args.action}",
            error="invalid_input",
            exit_code=EXIT_INPUT,
        )
    except FileNotFoundError as exc:
        return _emit_fail(args, str(exc), error="invalid_input", exit_code=EXIT_INPUT)
    except ValueError as exc:
        return _emit_fail(args, str(exc), error="invalid_input", exit_code=EXIT_INPUT)
    except RuntimeError as exc:
        return _emit_fail(args, str(exc), error="missing_dependency", exit_code=EXIT_DEP)
    except TimeoutError as exc:
        return _emit_fail(args, str(exc), error="timeout", exit_code=EXIT_RUNTIME)
    except KeyboardInterrupt:
        return _emit_fail(args, "interrupted", error="interrupted", exit_code=EXIT_RUNTIME)
    except Exception as exc:
        return _emit_fail(args, str(exc), error="runtime_error", exit_code=EXIT_RUNTIME)


if __name__ == "__main__":
    raise SystemExit(main())
