#!/usr/bin/env python
"""Build the 4 ARC-AGI-3 submission notebooks + kernel-metadata from agent sources.

Each notebook is the official 4-cell skeleton (install wheels / write my_agent.py /
competition runner / dummy submission) with cell 1 swapped for one of our agents.
The skeleton (cells 0,2,3) is taken verbatim from the official sample submission so
the Kaggle competition-rerun contract is matched exactly.

Usage: build_notebooks.py <sample_notebook.ipynb> <out_dir>
"""

import json
import os
import sys

# kernel name -> (kaggle account, agent source file, enable_gpu, title)
# Title MUST slugify to exactly the kernel name (id), else Kaggle creates the
# kernel under a different slug than the metadata id (the title-slug mismatch).
KERNELS = {
    "arc3-goose": ("harrysun2006", "agent_goose.py", True, "arc3 goose"),
    "arc3-goosenov": ("harrysun2006", "agent_goosenov.py", True, "arc3 goosenov"),
    "arc3-explore": ("firefly2006", "agent_explore.py", False, "arc3 explore"),
    "arc3-reactive": ("firefly2006", "agent_reactive.py", False, "arc3 reactive"),
}
WRITEFILE = "%%writefile /kaggle/working/my_agent.py\n"


def main() -> None:
    sample_path, out_root = sys.argv[1], sys.argv[2]
    sample = json.load(open(sample_path))
    cells = sample["cells"]
    c1 = cells[1]["source"]
    c1 = "".join(c1) if isinstance(c1, list) else c1
    assert c1.startswith("%%writefile"), "cell 1 is not the agent cell"
    base_meta = json.load(open(os.path.join(os.path.dirname(sample_path), "kernel-metadata.json")))
    agents_dir = os.path.dirname(os.path.abspath(__file__)) + "/agents"

    for name, (account, agent_file, gpu, title) in KERNELS.items():
        agent_src = open(os.path.join(agents_dir, agent_file)).read()
        nb = json.loads(json.dumps(sample))  # deep copy
        # swap cell 1 to our agent (keep the writefile magic)
        nb["cells"][1]["source"] = WRITEFILE + agent_src
        for c in nb["cells"]:
            c["outputs"] = c.get("outputs", []) if c["cell_type"] == "markdown" else []
            if c["cell_type"] == "code":
                c["execution_count"] = None

        out_dir = os.path.join(out_root, name)
        os.makedirs(out_dir, exist_ok=True)
        nb_file = f"{name}.ipynb"
        json.dump(nb, open(os.path.join(out_dir, nb_file), "w"), indent=1)

        meta = dict(base_meta)
        meta["id"] = f"{account}/{name}"
        meta.pop("id_no", None)
        meta["title"] = title
        meta["code_file"] = nb_file
        meta["is_private"] = True
        meta["enable_gpu"] = gpu
        meta["enable_internet"] = False
        meta["competition_sources"] = ["arc-prize-2026-arc-agi-3"]
        if not gpu:
            meta.pop("machine_shape", None)
        json.dump(meta, open(os.path.join(out_dir, "kernel-metadata.json"), "w"), indent=2)
        print(f"built {out_dir}/{nb_file}  (account={account} gpu={gpu})")


if __name__ == "__main__":
    main()
