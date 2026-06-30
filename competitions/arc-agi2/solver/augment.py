"""Augmentation for AIRV (Augment -> Infer -> Reverse-augment -> Vote).

An `Augmentation` = a D8 geometric transform (the dihedral group of the square: 4 rotations x
2 reflections) composed with a color permutation. It is applied to every grid in a task
(demo inputs/outputs + the test input); the model predicts in the augmented frame, and the
prediction is mapped back with `.invert()` before voting. Example-order shuffling is a
prompt-only augmentation (it does not transform grids) and lives in ttt_data/serialize.

Pure-Python, no third-party deps — grids are `list[list[int]]`, values 0-9.

D8 parameterisation: forward = R_cw^k ( F(grid) ), with F = horizontal flip if `flip` else id,
k in {0,1,2,3}. The inverse is therefore  F( R_ccw^k(grid) )  (since (AB)^-1 = B^-1 A^-1, F is
self-inverse, and R_cw^-1 = R_ccw). This is verified by the round-trip tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

Grid = list  # list[list[int]]


# --- primitive geometric ops -------------------------------------------------
def rot_cw(g: Grid) -> Grid:
    """Rotate 90 degrees clockwise."""
    return [list(row) for row in zip(*g[::-1])]


def rot_ccw(g: Grid) -> Grid:
    """Rotate 90 degrees counter-clockwise."""
    return [list(row) for row in zip(*g)][::-1]


def flip_lr(g: Grid) -> Grid:
    """Mirror left-right (reverse each row)."""
    return [row[::-1] for row in g]


def _rotate(g: Grid, k: int, cw: bool) -> Grid:
    fn = rot_cw if cw else rot_ccw
    for _ in range(k % 4):
        g = fn(g)
    return g


# --- color permutation -------------------------------------------------------
def apply_color_map(g: Grid, cmap) -> Grid:
    """Recolor every cell via cmap (an indexable of length >= 10: new = cmap[old])."""
    return [[cmap[c] for c in row] for row in g]


def invert_perm(perm) -> list:
    """Inverse of a permutation given as perm[old] = new -> inv[new] = old."""
    inv = [0] * len(perm)
    for old, new in enumerate(perm):
        inv[new] = old
    return inv


def random_color_perm(rng: random.Random, keep_background: bool = True) -> list:
    """A permutation of colors 0-9. If keep_background, color 0 is fixed (common practice)."""
    if keep_background:
        rest = list(range(1, 10))
        rng.shuffle(rest)
        return [0] + rest
    perm = list(range(10))
    rng.shuffle(perm)
    return perm


# --- the Augmentation object -------------------------------------------------
@dataclass(frozen=True)
class Augmentation:
    k: int  # number of clockwise 90-deg rotations (0..3)
    flip: bool  # apply a horizontal flip before rotation
    color_perm: tuple  # color_perm[old] = new (length 10); identity = tuple(range(10))

    def apply(self, g: Grid) -> Grid:
        g = apply_color_map(g, self.color_perm)
        if self.flip:
            g = flip_lr(g)
        return _rotate(g, self.k, cw=True)

    def invert(self, g: Grid) -> Grid:
        # undo geometry first (reverse order), then undo color
        g = _rotate(g, self.k, cw=False)
        if self.flip:
            g = flip_lr(g)
        return apply_color_map(g, invert_perm(self.color_perm))


IDENTITY_PERM = tuple(range(10))


def d8_augmentations() -> list[Augmentation]:
    """The 8 pure geometric (no-recolor) augmentations."""
    return [Augmentation(k=k, flip=f, color_perm=IDENTITY_PERM) for f in (False, True) for k in range(4)]


def build_augmentations(n: int = 16, seed: int = 0, keep_background: bool = True) -> list[Augmentation]:
    """Build `n` augmentations: cycle the 8 D8 transforms, each with a random color permutation.

    n=16 reproduces the ARChitects set (8 D8 x 2 random color perms). The first 8 use the
    identity color map so the pure-geometric view is always represented; the rest get random
    perms. Deterministic given `seed`.
    """
    rng = random.Random(seed)
    geoms = [(k, f) for f in (False, True) for k in range(4)]
    augs: list[Augmentation] = []
    for i in range(n):
        k, f = geoms[i % 8]
        perm = IDENTITY_PERM if i < 8 else tuple(random_color_perm(rng, keep_background))
        augs.append(Augmentation(k=k, flip=f, color_perm=perm))
    return augs
