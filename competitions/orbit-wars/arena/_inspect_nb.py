import json, glob, sys

root = sys.argv[1]
for nb_path in sorted(glob.glob(root + "/*/*.ipynb")):
    nb = json.load(open(nb_path))
    print("\n###", nb_path.split("/")[-2])
    for i, c in enumerate(nb["cells"]):
        if c["cell_type"] == "code":
            src = "".join(c["source"])
            first = src.strip().splitlines()[0][:70] if src.strip() else "(empty)"
            flags = []
            if "writefile" in src:
                flags.append("WRITEFILE")
            if "def agent" in src:
                flags.append("DEF_AGENT")
            if "env.run" in src or "make(" in src:
                flags.append("RUNS_ENV")
            if "pip install" in src:
                flags.append("PIP")
            print(f"  cell {i}: len={len(src):5d} [{','.join(flags)}] | {first}")
