#!/usr/bin/env python3
"""Render the committed loader-probe excerpt from a `codex debug prompt-input` dump.

    python scripts/render_codex_probe.py probe.json AGENTS.md \
        docs/evidence/issue-189-codex-parity/loader-probe.txt <commit>

The excerpt's header claims the numbers reproduce from `<commit>`. Three things
have to hold for that to be true, and all three are checked here rather than
trusted — a header that says "verified" while nothing was verified is worse than
one that says nothing:

1. `AGENTS.md` at `<commit>` is byte-identical to the file being measured;
2. that file is what the dump actually carries — otherwise a stale `probe.json`
   from before an edit renders against today's `AGENTS.md` and looks current;
3. `<commit>` is HEAD, so the dump was taken from this state.

The binary version in the header comes from `codex --version` at render time; if
the dump was captured with a different binary, that line is wrong and nothing
here can tell. Render right after probing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    sys.exit(f"render_codex_probe: {message}")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"`git {' '.join(args)}` failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main() -> None:
    if len(sys.argv) != 5:
        fail("usage: render_codex_probe.py <dump.json> <AGENTS.md> <out.txt> <commit>")
    dump_path, agents_path, out_path, commit = (
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        sys.argv[4],
    )

    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    on_disk = agents_path.read_bytes()
    short = git("rev-parse", "--short", commit)

    # 1. the named commit holds the file we measured
    committed = subprocess.run(["git", "show", f"{commit}:AGENTS.md"], cwd=REPO_ROOT, capture_output=True).stdout
    if committed != on_disk:
        fail(
            f"refusing to write: AGENTS.md at {short} ({len(committed)} bytes) is not the file "
            f"measured here ({len(on_disk)} bytes). Re-run the probe against a clean checkout."
        )

    # 3. and that commit is the state the probe was taken from
    if git("rev-parse", "HEAD") != git("rev-parse", f"{commit}^{{commit}}"):
        fail(f"refusing to write: {short} is not HEAD, so the dump was taken from another state.")

    messages = [m["content"][0]["text"] for m in dump]
    docs = [m for m in messages if "AGENTS.md instructions" in m]
    if len(docs) != 1:
        fail(f"expected exactly one project-doc message in the dump, found {len(docs)}")
    doc = docs[0]

    # 2. the dump carries *this* AGENTS.md, not an older one. The message wraps the
    #    file in a path header and <INSTRUCTIONS> tags, so containment is the check.
    text_on_disk = on_disk.decode("utf-8")
    if text_on_disk.strip() not in doc:
        fail(
            "refusing to write: the dump's project-doc message does not contain the AGENTS.md "
            "being measured. The dump is stale — re-run `codex debug prompt-input`."
        )

    catalogue = messages[0]
    roots = [ln for ln in catalogue.splitlines() if ln.startswith("- `r")]
    skills = [ln for ln in catalogue.splitlines() if ln.startswith("- ") and "(file: r1/" in ln]
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()

    lines = [
        "Loader probe — what Codex actually loads from this repo.",
        "",
        "Command:  CODEX_HOME=<isolated> codex debug prompt-input 'Start work on competitions/arc-agi2'",
        f"Binary:   {version} (as reported at render time)",
        f"Repo:     {short} — verified: it is HEAD, its AGENTS.md is byte-identical to the file",
        "          measured below, and the dump's project-doc message contains that same file.",
        f"Measured: AGENTS.md on disk: {len(on_disk)} bytes, {len(text_on_disk)} characters",
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
        *doc.split("\n")[:8],
        f"   [... {len(doc)} chars total ...]",
        *doc.split("\n")[-8:],
    ]
    out_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    print(f"wrote {out_path}, verified against {short}")


if __name__ == "__main__":
    main()
