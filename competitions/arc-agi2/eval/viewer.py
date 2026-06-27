"""Terminal viewer for ARC tasks — render grids as colored blocks (ANSI) or digits.

Usage:
    python -m eval.viewer <task_id> [--split evaluation] [--no-color]
    python -m eval.viewer --task-file path/to/task.json
"""

from __future__ import annotations

import argparse
import sys

from arc_io import DEFAULT_GITHUB_ROOT, Task, _load_json, load_github_split

# ARC's canonical 10-color palette mapped to 256-color ANSI backgrounds.
_ANSI = {
    0: 16,  # black
    1: 21,  # blue
    2: 196,  # red
    3: 46,  # green
    4: 226,  # yellow
    5: 244,  # grey
    6: 201,  # magenta
    7: 208,  # orange
    8: 51,  # cyan
    9: 88,  # maroon
}


def render_grid(grid, color: bool = True) -> str:
    lines = []
    for row in grid:
        if color:
            cells = [f"\033[48;5;{_ANSI.get(v, 15)}m  \033[0m" for v in row]
            lines.append("".join(cells))
        else:
            lines.append("".join(str(v) for v in row))
    return "\n".join(lines)


def show_task(task: Task, color: bool = True) -> str:
    out = [f"=== task {task.task_id}  ({len(task.train)} train pairs, {task.n_test} test) ==="]
    for i, pair in enumerate(task.train):
        out.append(f"\n-- train[{i}] input --")
        out.append(render_grid(pair["input"], color))
        out.append(f"-- train[{i}] output --")
        out.append(render_grid(pair["output"], color))
    for i, inp in enumerate(task.test_inputs):
        out.append(f"\n-- test[{i}] input --")
        out.append(render_grid(inp, color))
        if task.test_outputs is not None:
            out.append(f"-- test[{i}] output (solution) --")
            out.append(render_grid(task.test_outputs[i], color))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render an ARC task in the terminal.")
    ap.add_argument("task_id", nargs="?", help="task id (filename stem)")
    ap.add_argument("--split", default="evaluation", choices=["training", "evaluation"])
    ap.add_argument("--task-file", help="path to a single task JSON (overrides task_id/split)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)
    color = not args.no_color

    if args.task_file:
        d = _load_json(args.task_file)
        tid = args.task_file.rsplit("/", 1)[-1].replace(".json", "")
        task = Task(
            task_id=tid,
            train=d["train"],
            test_inputs=[t["input"] for t in d["test"]],
            test_outputs=([t.get("output") for t in d["test"]] if all("output" in t for t in d["test"]) else None),
        )
    else:
        if not args.task_id:
            ap.error("provide a task_id or --task-file")
        tasks = load_github_split(args.split, DEFAULT_GITHUB_ROOT)
        if args.task_id not in tasks:
            ap.error(f"task {args.task_id} not in split '{args.split}'")
        task = tasks[args.task_id]

    print(show_task(task, color))
    return 0


if __name__ == "__main__":
    sys.exit(main())
