"""Tests for the lb1-v1 Nemotron post-LB1 pipeline.

Covers the deterministic, falsifiable validations (no GPU, no network):
  * 24-rule inventory shape + signature catalog == 4205 (exact, reproduces writeup);
  * HEX compression matches the writeup worked example;
  * Hamming repair recovers a corrupted catalog transform;
  * synthetic traces are internally consistent (answer extractable + correct);
  * submission packaging produces a root-structured zip and the preflight gate
    rejects rank>32 and nested zips.
The equation re-probe assertion runs only when the (gitignored) competition
train.csv is present locally; otherwise it is skipped (keeps CI green).
"""

import os
import sys
import zipfile

import pytest

_VDIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "competitions",
    "nvidia-nemotron",
    "versions",
    "lb1-v1",
)
sys.path.insert(0, _VDIR)
sys.path.insert(0, os.path.join(os.path.dirname(_VDIR), "..", "eval"))

import rules24  # noqa: E402
import signature_catalog  # noqa: E402
import rule_sequence_catalog as rseq  # noqa: E402
import hex_compress  # noqa: E402
import solvers  # noqa: E402
import synth_gen  # noqa: E402
import package_submission as pkg  # noqa: E402
import validate as vdl  # noqa: E402
from official_metric import extract_final_answer, verify  # noqa: E402

TRAIN = os.path.expanduser("~/competitions/kaggle-nvidia-nemotron-model-reasoning-challenge/data/train.csv")


def test_rule_inventory_shape():
    assert len(rules24.RULES) == 24
    assert len(rules24.NON_JOIN_RULES) == 22


def test_signature_catalog_exact_4205():
    cat = signature_catalog.build_catalog()
    assert len(cat) == 4205, f"expected 4205 signatures, got {len(cat)}"
    # published ABCCCDD row: add 1, flip_add 8, flip_add+1 6 -> 15 candidates
    assert signature_catalog.candidate_count(cat, "ABCCCDD") == 15
    by = signature_catalog.rows_by_rule(cat, "ABCCCDD")
    assert len(set(by["add"])) == 1
    assert len(set(by["flip_add"])) == 8
    assert len(set(by["flip_add+1"])) == 6
    assert "8911100" in by["add"]
    assert "0299911" in by["flip_add"]


def test_hex_compression_writeup_example():
    assert hex_compress.bits_to_hex("1101000001") == "341"
    assert hex_compress.bits_to_hex("01101001") == "69"
    assert hex_compress.hex_to_bits("341", 10) == "1101000001"


def test_repair_recovers_corrupted_transform():
    prims = (
        ["x", "not_x"]
        + [f"shl{k}" for k in range(1, 4)]
        + [f"shr{k}" for k in range(1, 4)]
        + [f"rol{k}" for k in range(1, 8)]
    )
    cat = rseq.build_core_catalog(prims)
    op, args = ("sel_nand_xnor", ("rol1", "shr3", "shl2"))
    true_seq = rseq.per_bit_sequence(op, args)
    assert true_seq in cat
    fn = rseq.transform_function(op, args)
    ins = [3, 17, 42, 200, 255, 128, 73, 99, 1, 250]
    examples = [(x, fn(x)) for x in ins]
    corrupt = list(true_seq)
    for i in (3, 4, 5):
        corrupt[i] = ("id", (rseq.CONST1,))
    res = rseq.repair(tuple(corrupt), cat, examples, k=32)
    assert res is not None and res[1] == (op, args)


def test_synth_traces_are_consistent():
    recs, _ = synth_gen.build_corpus(10, seed=99)
    assert len(recs) > 0
    for r in recs:
        assert verify(r["answer"], extract_final_answer(r["trace"])), r
        assert r["trace"].rstrip().endswith("}")  # finality line
        assert hex_compress.char_tokens(r["trace"]) < 7680


def test_packaging_and_preflight_gate(tmp_path):
    adir = tmp_path / "adapter"
    pkg.make_dummy_adapter(str(adir), rank=32)
    zpath = tmp_path / "submission.zip"
    pkg.build_submission_zip(str(adir), str(zpath))
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
    assert set(names) == set(pkg.REQUIRED_FILES)  # root-level, no nesting
    chk = vdl.Check()
    vdl.check_zip(chk, str(zpath))
    assert chk.ok(), chk.results


def test_preflight_rejects_rank_over_32(tmp_path):

    adir = tmp_path / "bad"
    pkg.make_dummy_adapter(str(adir), rank=64)
    zpath = tmp_path / "bad.zip"
    pkg.build_submission_zip(str(adir), str(zpath))
    chk = vdl.Check()
    vdl.check_zip(chk, str(zpath))
    assert not chk.ok()


def test_preflight_rejects_nested_zip(tmp_path):
    zpath = tmp_path / "nested.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("adapter/adapter_config.json", '{"r": 32}')
        z.writestr("adapter/adapter_model.safetensors", "x")
    chk = vdl.Check()
    vdl.check_zip(chk, str(zpath))
    assert not chk.ok()


def test_bit_solver_produces_verifying_trace():
    # rol3 is a pure rotation: out bit i = in bit (i+3)%8, uniquely determined when
    # the example input bit-columns are distinct. Powers of two give an identity
    # matrix of columns, so per-bit selection cannot "match by chance".
    op, args = ("id", ("rol3",))
    fn = rseq.transform_function(op, args)
    ins = [1, 2, 4, 8, 16, 32, 64, 128, 255, 0]
    ex_lines = "\n".join(f"{i:08b} -> {fn(i):08b}" for i in ins)
    q = 0b10110010
    prompt = (
        "In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary numbers.\n"
        f"Here are some examples of input -> output:\n{ex_lines}\n"
        f"Now, determine the output for: {q:08b}"
    )
    out = solvers.solve_bit(prompt, repair_catalog=None, use_hex=True)
    assert out is not None
    assert out[0] == f"{fn(q):08b}"


@pytest.mark.skipif(not os.path.exists(TRAIN), reason="competition train.csv not present (gitignored)")
def test_equation_reprobe_deduce_high():
    import eq_reprobe

    _, tally, _ = eq_reprobe.run(TRAIN)
    t, s = tally["deduce"]["total"], tally["deduce"]["solved"]
    assert t == 596, f"expected 596 deduce prompts, got {t}"
    assert s / t >= 0.90, f"deduce coverage {s}/{t} below 0.90 (refutes global-cipher premise)"
