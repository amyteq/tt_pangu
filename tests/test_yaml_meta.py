"""Tests for tools/kca/yaml_meta.py — per-competition YAML → kernel-metadata.json."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "kca"))

import yaml_meta  # noqa: E402

YAML = """
_base:
  competition: demo-comp
  submit_file: submission.zip
  language: python
  kernel_type: notebook
  is_private: true
  enable_gpu: true
  enable_tpu: false
  enable_internet: false
  keywords: [gpu]
  competition_sources: [demo-comp]
  dataset_sources: [a/x, b/y]
  kernel_sources: []
  model_sources: [m/model/Transformers/default/1]
  docker_image: gcr.io/demo
  machine_shape: NvidiaRtxPro6000

train:
  id: harrysun2006/demo-train
  title: Demo Train
  code_file: demo-train.ipynb
  lb: 0.85          # annotation key — must be stripped
  schedule: overnight

merge:
  id: firefly2006/demo-merge
  title: Demo Merge
  code_file: demo-merge.ipynb
  enable_gpu: false
  machine_shape: null   # None must drop the key (CPU kernel)
  model_sources: []
"""


@pytest.fixture
def yaml_path(tmp_path):
    p = tmp_path / "kca-demo.yaml"
    p.write_text(YAML)
    return str(p)


def test_resolve_merges_base_and_section(yaml_path):
    m = yaml_meta.resolve(yaml_path, "train")
    assert m["id"] == "harrysun2006/demo-train"
    assert m["title"] == "Demo Train"
    assert m["dataset_sources"] == ["a/x", "b/y"]  # inherited from _base
    assert m["machine_shape"] == "NvidiaRtxPro6000"
    assert m["enable_gpu"] is True


def test_resolve_strips_non_kaggle_keys(yaml_path):
    m = yaml_meta.resolve(yaml_path, "train")
    for k in ("lb", "schedule", "competition", "submit_file"):
        assert k not in m
    assert set(m).issubset(set(yaml_meta.KAGGLE_KEYS))


def test_resolve_none_override_drops_key(yaml_path):
    m = yaml_meta.resolve(yaml_path, "merge")
    assert m["enable_gpu"] is False
    assert "machine_shape" not in m  # null override removes the GPU default
    assert "model_sources" in m and m["model_sources"] == []


def test_resolve_unknown_section_raises(yaml_path):
    with pytest.raises(KeyError):
        yaml_meta.resolve(yaml_path, "nope")


def test_write_emits_json(yaml_path, tmp_path):
    out = tmp_path / "build"
    path = yaml_meta._write_metadata(yaml_meta.resolve(yaml_path, "train"), str(out))
    import json

    data = json.loads(Path(path).read_text())
    assert data["id"] == "harrysun2006/demo-train"
    assert data["code_file"] == "demo-train.ipynb"
