"""Reconstruct a package-based agent from a notebook's %%writefile cells.

Usage: python _reconstruct_pkg.py <notebook.ipynb> <out_dir>
Writes every `%%writefile <path>` cell to <out_dir>/<path>.
"""

import json, os, sys

nb_path, out_dir = sys.argv[1], sys.argv[2]
nb = json.load(open(nb_path))
os.makedirs(out_dir, exist_ok=True)
written = []
for c in nb["cells"]:
    if c["cell_type"] != "code":
        continue
    src = "".join(c["source"])
    lines = src.splitlines()
    if lines and lines[0].strip().startswith("%%writefile"):
        target = lines[0].split("writefile", 1)[1].strip()
        body = "\n".join(lines[1:]).rstrip() + "\n"
        path = os.path.join(out_dir, target)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(body)
        written.append((target, len(body)))
for t, n in written:
    print(f"  wrote {t} ({n} chars)")
print("total files:", len(written))
