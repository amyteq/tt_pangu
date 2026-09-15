"""Render the committed loader-probe excerpt from a `codex debug prompt-input` dump.

Usage: render_probe.py <dump.json> <AGENTS.md> <out.txt> <probe-commit>

The probe commit is passed in, never inferred from HEAD: the dump was captured at
one commit and this script may run later, from a dirty tree, which is how the SHA
went wrong the first time (review round 2, N1). It is also *verified* rather than
attested — the AGENTS.md at that commit must be byte-identical to the file whose
load is being recorded, or nothing is written.
"""

import json
import pathlib
import subprocess
import sys

dump = json.load(open(sys.argv[1]))
agents_md = pathlib.Path(sys.argv[2])
out = pathlib.Path(sys.argv[3])
commit = sys.argv[4]

committed = subprocess.run(["git", "show", f"{commit}:AGENTS.md"], capture_output=True).stdout
on_disk = agents_md.read_bytes()
if committed != on_disk:
    sys.exit(
        f"refusing to write: AGENTS.md at {commit} ({len(committed)} bytes) is not the file "
        f"measured here ({len(on_disk)} bytes). Re-run the probe against a clean checkout."
    )

text = dump[0]["content"][0]["text"]
roots = [ln for ln in text.splitlines() if ln.startswith("- `r")]
skills = [ln for ln in text.splitlines() if ln.startswith("- ") and "(file: r1/" in ln]
doc = [m["content"][0]["text"] for m in dump if "AGENTS.md instructions" in m["content"][0]["text"]][0]

head = doc.split("\n")[:8]
tail = doc.split("\n")[-8:]
version = subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()
characters = len(on_disk.decode("utf-8"))

lines = [
    "Loader probe — what Codex actually loads from this repo.",
    "",
    "Command:  CODEX_HOME=<isolated> codex debug prompt-input 'Start work on competitions/arc-agi2'",
    f"Binary:   {version}",
    f"Repo:     {commit} — verified: `git show {commit}:AGENTS.md` is byte-identical to the",
    "          file measured below, so these numbers reproduce from that commit.",
    f"Measured: AGENTS.md on disk: {len(on_disk)} bytes, {characters} characters",
    f"          project-doc message in the prompt: {len(doc)} characters",
    "          = the file plus Codex's own wrapper (a '# AGENTS.md instructions for <abs path>'",
    "            header and <INSTRUCTIONS> tags), so this total varies with the checkout path.",
    "            The sentinels below, not the total, are what show the file loaded whole.",
    f"          opening sentinel present: {'GENERATED FILE' in doc}",
    f"          closing sentinel present: {'not interchangeable ones' in doc}",
    f"          truncation marker: {'truncat' in doc.lower()}",
    f"          project skills listed under r1: {len(skills)}",
    "",
    "`codex debug prompt-input` renders the model-visible prompt without a network call.",
    "An isolated CODEX_HOME keeps the human's own config and user-level skills out of it.",
    "",
    "== developer message: skills catalogue (excerpt) ==",
    "### Skill roots",
    *roots,
    "### Available skills",
    "",
    "-- project skills listed from r1 --",
    *skills,
    "",
    "== user message: project doc ==",
    *head,
    f"   [... {len(doc)} chars total ...]",
    *tail,
]
out.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
print(f"wrote {out} ({len(lines)} lines), verified against {commit}")
