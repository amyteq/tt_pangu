import json, sys

nb_path = sys.argv[1]
out = sys.argv[2]
nb = json.load(open(nb_path))
cell = None
for c in nb["cells"]:
    if c["cell_type"] != "code":
        continue
    src = "".join(c["source"])
    if ("writefile main.py" in src or "writefile submission.py" in src) and "def agent" in src:
        cell = src
        break
assert cell, "agent cell not found"
lines = cell.splitlines()
if lines and lines[0].strip().startswith("%%writefile"):
    lines = lines[1:]
code = "\n".join(lines).rstrip() + "\n"
open(out, "w").write(code)
print("wrote", out, len(code), "chars; lines:", code.count("\n"))
print("has def agent:", "def agent(" in code)
