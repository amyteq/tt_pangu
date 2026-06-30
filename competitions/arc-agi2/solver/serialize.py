"""Grid <-> compact string encoding + task-prompt formatting.

Encoding follows the ARChitects "one token per cell" convention: each cell is a single digit
0-9 (a color), rows are joined with newlines. Because colors are single chars there is no
intra-row separator. A task prompt packs all demo pairs then the test input, each grid
wrapped by input/output markers; the model is expected to emit only the final output grid.

This is the *text* layer. A model-specific tokenizer (e.g. NVARC's 16-token vocab) can map
these characters/markers to dedicated token ids later; the structure here is what matters.
"""

from __future__ import annotations

Grid = list  # list[list[int]]

ROW_SEP = "\n"
IN_MARK = "I"
OUT_MARK = "O"
PAIR_SEP = "\n"


def grid_to_str(g: Grid) -> str:
    """[[0,1],[2,3]] -> '01\\n23'. Raises on values outside 0-9."""
    rows = []
    for row in g:
        if any(not (0 <= c <= 9) for c in row):
            raise ValueError(f"cell value out of range 0-9 in row {row}")
        rows.append("".join(str(c) for c in row))
    return ROW_SEP.join(rows)


def str_to_grid(s: str) -> Grid:
    """Inverse of grid_to_str. Ignores leading/trailing blank lines; rows must be rectangular."""
    lines = [ln for ln in s.strip().splitlines() if ln != ""]
    grid = [[int(ch) for ch in line] for line in lines]
    if grid:
        w = len(grid[0])
        if any(len(r) != w for r in grid):
            raise ValueError("non-rectangular grid while parsing")
    return grid


def format_pair(inp: Grid, out: Grid | None = None) -> str:
    """'I\\n<input>\\nO\\n<output>' (output omitted -> ends at 'O\\n' for generation)."""
    s = f"{IN_MARK}{ROW_SEP}{grid_to_str(inp)}{ROW_SEP}{OUT_MARK}{ROW_SEP}"
    if out is not None:
        s += grid_to_str(out)
    return s


def format_task_prompt(train_pairs: list[dict], test_input: Grid) -> str:
    """Pack demo pairs + the test input into a single prompt that ends ready for the model to
    generate the test output (after the trailing 'O\\n').

    train_pairs: [{"input": Grid, "output": Grid}, ...] (already in the desired/augmented order).
    """
    blocks = [format_pair(p["input"], p["output"]) for p in train_pairs]
    blocks.append(format_pair(test_input, None))
    return PAIR_SEP.join(blocks)
