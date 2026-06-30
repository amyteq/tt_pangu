"""Unit tests for the model-agnostic TTT solver core (augment / serialize / ttt_data / select).

Run:  PYTHONPATH=<pytest-target> python -m pytest competitions/arc-agi2/tests/test_solver.py -q
"""

import sys
from pathlib import Path

import pytest

# make the competition dir importable so `import solver.*` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from solver.augment import (  # noqa: E402
    Augmentation,
    apply_color_map,
    build_augmentations,
    d8_augmentations,
    flip_lr,
    invert_perm,
    rot_ccw,
    rot_cw,
)
from solver.model import parse_generated_grid  # noqa: E402
from solver.selection import Candidate, select_top2, to_submission_entry  # noqa: E402
from solver.serialize import format_task_prompt, grid_to_str, str_to_grid  # noqa: E402
from solver.ttt_data import build_inference_prompts, build_ttt_examples  # noqa: E402

G = [[1, 2, 3], [4, 5, 6]]  # 2x3, non-symmetric so transforms are distinguishable


# --- geometry primitives -----------------------------------------------------
def test_rot_cw_then_ccw_identity():
    assert rot_ccw(rot_cw(G)) == G
    assert rot_cw(rot_ccw(G)) == G


def test_rot_cw_shape_and_values():
    # clockwise rotation of a 2x3 -> 3x2; first column bottom-to-top becomes first row
    assert rot_cw(G) == [[4, 1], [5, 2], [6, 3]]


def test_flip_lr_involution():
    assert flip_lr(flip_lr(G)) == G


def test_four_rotations_return_to_start():
    g = G
    for _ in range(4):
        g = rot_cw(g)
    assert g == G


# --- color permutations ------------------------------------------------------
def test_color_map_and_inverse():
    perm = [0, 3, 1, 2, 4, 5, 6, 7, 8, 9]  # 1->3, 2->1, 3->2, rest fixed
    recolored = apply_color_map(G, perm)
    assert apply_color_map(recolored, invert_perm(perm)) == G


# --- the Augmentation object (the AIRV invariant) ----------------------------
def test_d8_has_eight_distinct_transforms():
    augs = d8_augmentations()
    assert len(augs) == 8
    images = {grid_to_str(a.apply(G)) for a in augs}
    # a 2x3 non-symmetric grid yields 8 distinct images under D8 (4 of shape 2x3, 4 of 3x2)
    assert len(images) == 8


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_apply_invert_roundtrip_all_augs(seed):
    augs = build_augmentations(n=16, seed=seed)
    assert len(augs) == 16
    for a in augs:
        assert a.invert(a.apply(G)) == G, f"round-trip failed for {a}"


def test_build_augmentations_first_eight_are_pure_geometry():
    augs = build_augmentations(n=16, seed=3)
    assert all(a.color_perm == tuple(range(10)) for a in augs[:8])
    # at least one of the later ones recolors
    assert any(a.color_perm != tuple(range(10)) for a in augs[8:])


def test_background_preserved_when_keep_background():
    augs = build_augmentations(n=16, seed=5, keep_background=True)
    assert all(a.color_perm[0] == 0 for a in augs)


# --- serialization -----------------------------------------------------------
def test_grid_str_roundtrip():
    assert str_to_grid(grid_to_str(G)) == G


def test_grid_to_str_format():
    assert grid_to_str([[0, 1], [2, 3]]) == "01\n23"


def test_grid_to_str_rejects_out_of_range():
    with pytest.raises(ValueError):
        grid_to_str([[0, 10]])


def test_prompt_ends_ready_for_generation():
    pairs = [{"input": [[1]], "output": [[2]]}]
    prompt = format_task_prompt(pairs, [[3]])
    assert prompt.rstrip("\n").endswith("O") or prompt.endswith("O\n")
    assert grid_to_str([[2]]) in prompt  # demo output present
    # the test output (unknown) must NOT be in the prompt
    assert prompt.count("O\n") >= 2  # one per demo + one trailing


# --- TTT data ----------------------------------------------------------------
def test_leave_one_out_example_count():
    pairs = [{"input": [[i]], "output": [[i + 1]]} for i in range(3)]  # 3 demos
    augs = build_augmentations(n=4, seed=0)
    ex = build_ttt_examples(pairs, augs, seed=0)
    assert len(ex) == 3 * 4  # n demos * A augmentations


def test_ttt_needs_two_demos():
    one = [{"input": [[1]], "output": [[2]]}]
    assert build_ttt_examples(one, build_augmentations(4)) == []


def test_inference_prompt_count():
    pairs = [{"input": [[1]], "output": [[2]]}, {"input": [[3]], "output": [[4]]}]
    augs = build_augmentations(n=16, seed=0)
    prompts = build_inference_prompts(pairs, [[5]], augs)
    assert len(prompts) == 16
    assert all(isinstance(a, Augmentation) and isinstance(p, str) for a, p in prompts)


# --- selection (PoE / vote) — the end-to-end AIRV property -------------------
def test_perfect_augmented_predictions_deaugment_to_one_grid():
    """If every augmentation predicts the *correct* augmented output, de-augmenting must make
    them all agree on the original grid -> it wins with full vote count."""
    truth = [[7, 0, 3], [0, 5, 0]]
    augs = build_augmentations(n=16, seed=2)
    cands = [Candidate(aug=a, grid=a.apply(truth)) for a in augs]
    top2 = select_top2(cands)
    assert top2[0] == truth


def test_poe_prefers_higher_logprob():
    a = build_augmentations(n=2, seed=0)[0]  # single aug, identity geometry
    truth = [[1, 2]]
    other = [[2, 1]]
    cands = [
        Candidate(aug=a, grid=a.apply(truth), logprob=-0.1),
        Candidate(aug=a, grid=a.apply(other), logprob=-5.0),
    ]
    assert select_top2(cands)[0] == truth


def test_vote_fallback_without_logprobs():
    a = build_augmentations(n=2, seed=0)[0]
    truth = [[1, 2]]
    other = [[2, 1]]
    cands = [
        Candidate(aug=a, grid=a.apply(truth)),
        Candidate(aug=a, grid=a.apply(truth)),
        Candidate(aug=a, grid=a.apply(other)),
    ]
    assert select_top2(cands)[0] == truth


def test_parse_clean_grid():
    assert parse_generated_grid("01\n23") == [[0, 1], [2, 3]]


def test_parse_stops_at_non_digit():
    assert parse_generated_grid("01\n23\nthe answer is above") == [[0, 1], [2, 3]]


def test_parse_empty_on_no_digits():
    assert parse_generated_grid("here is a grid:") == []


def test_parse_normalises_ragged_to_modal_width():
    # rows of width 3,3,2 -> modal width 3; the short row is padded with 0
    assert parse_generated_grid("123\n456\n78") == [[1, 2, 3], [4, 5, 6], [7, 8, 0]]
    # rows of width 2,3,3 -> modal 3; the long-short mix truncates/pads to 3
    assert parse_generated_grid("12\n345\n678") == [[1, 2, 0], [3, 4, 5], [6, 7, 8]]


def test_submission_entry_always_two_attempts():
    e = to_submission_entry([[[1]]])
    assert e["attempt_1"] == [[1]] and e["attempt_2"] == [[1]]
    e2 = to_submission_entry([[[1]], [[2]]])
    assert e2["attempt_1"] == [[1]] and e2["attempt_2"] == [[2]]
    e3 = to_submission_entry([])
    assert "attempt_1" in e3 and "attempt_2" in e3
