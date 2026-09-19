---
name: kaggle-tooling-integration
description: Use when integrating or invoking Kaggle helper scripts such as notebook conversion, kernel push, competition submission, result retrieval, and experiment artifact recording.
---

> **Archived (issue #192) — not loaded by any harness.** Split, then retired: the submission gate and the required-facts list moved to `kg-submit`; the kernel/version model, flat structure, per-account concurrency and the in-kernel mount-path resolver moved to `docs/tooling/kaggle-kernel-ops.md`. Its "do not submit until explicit approval is given" wording is *unscoped* — it predates ADR-0022 §5 and is superseded by `kg-submit`, which says which agent each rule binds. Kept as history: read it as a record of what the project once instructed, not as instruction. See `.claude/archive/skills/README.md`.

# Kaggle Tooling Integration Skill

## Purpose
Use project-approved wrappers for Kaggle operations. Do not call ad hoc scripts directly unless the user explicitly asks and the command has been reviewed.

## Workflow
1. Identify the tool category: read-only, local-write, remote-write, or submission.
2. Prefer `kca ...` wrapper commands when available.
3. For remote-write or submission actions, follow *Who approves what* below — this skill's default is a human approval request, not direct execution.
4. Record outputs into `runs/<competition_slug>/<run_id>/`.
5. Summarize result, metric, artifact paths, and next action.

## Who approves what

This skill is used by a **development harness** (Claude Code / Codex) driving Kaggle tooling on the human's own machine and account. It is not KCA's submission policy — keep the two apart (`CLAUDE.md` → *Two agents*, issue #65):

- **Harness (you, here).** A remote write or submission spends the human's Kaggle credentials and daily quota, so ask first. That is the same rule as "the Claude Code harness still asks for paid-API/credential use", and it binds a Codex session identically.
- **KCA product agent.** Governed by its competition's `autonomy` block — the file `competition.yaml:autonomy_config` names, conventionally `kca-<slug>.yaml` — and that block is configuration, not permission. ADR-0022 §5 opens the approval-free path only for a competition meeting activation conditions **A1-A7**; no competition meets them, ADR-0021 §2's earlier screened grant is unimplemented, and no code reads the block, so KCA's pushes and submissions are asked for too. Where the grant is open, the record is the submission intent persisted under `competitions/<slug>/submissions/` before dispatch — never an audit log (`CLAUDE.md` principle 6).

Either way the same facts are required before a Kaggle submission — in the approval request if you are the harness, in the persisted submission record if you are KCA:

- competition slug.
- file path.
- submission message.
- validation score and metric direction.
- daily submission count if known.
- expected risk or uncertainty.

Running as the harness: do not submit until explicit approval is given.

## Kernel/version model, structure & concurrency
For code-competition (notebook/kernel) work, follow `docs/tooling/kaggle-kernel-ops.md`. Key rules:
- **Versions are latest-only via API** — `kaggle kernels output/status` expose only the latest run, and stale `-v` is unreliable. Submit the just-pushed (latest) version (omit `--version` in `kca kaggle submit --kernel …`).
- **Flat structure**: one kernel per candidate/direction (variant in the slug, e.g. `nemotron-cot-r32-s400`) so every candidate stays retrievable and can run in parallel. Single-kernel-many-versions is for throwaway iteration only.
- **Concurrency is per *account*, global**: ~1 concurrent GPU session + floating ~30 h/week quota (resets Sat 00:00 UTC). Submission limits are per competition team, per day. Maximise throughput with flat parallel kernels, bounded runs, keeping non-GPU work off the quota, and overflow compute (local 4090/3090 for models that fit; external GPU under evaluation).
- **Pre-push hygiene**: static lint (`kca kaggle push` gate / `validate_kernel.py`), a fail-fast eval preflight, and isolating non-essential steps — never waste a multi-hour GPU run on a typo.

## Kaggle in-kernel data mount paths
Inside a Kaggle kernel, **do not hardcode** the input mount. Since ~Feb 2026 Kaggle adds a slug chunk to the path, so the same competition data may appear under either form depending on the kernel's attached sources:

- Competition data: `/kaggle/input/competitions/<competition-slug>/` (newer) or `/kaggle/input/<competition-slug>/` (older).
- Datasets / models: `/kaggle/input/<owner>/<dataset-slug>/` (and utility-script / model mounts under `/kaggle/usr/lib/...` with the slug **slugified to underscores**, e.g. `nvidia-utility-script` → `nvidia_utility_script`).

Resolve robustly with a glob rather than a literal path, e.g.:

```python
import glob
cands = (glob.glob("/kaggle/input/competitions/*/train.csv")
         + glob.glob("/kaggle/input/*/train.csv")
         + glob.glob("/kaggle/input/**/train.csv", recursive=True))
train_csv = cands[0]  # raise if empty; print cands for diagnostics
```

A battle-tested resolver lives in `experiments/tpu-getting-started/baseline-tl/baseline.py` (`_resolve_kaggle_input_path`): try `/kaggle/input/<slug>` then `/kaggle/input/competitions/<slug>`, and on miss, list `/kaggle/input` contents so the failure shows the real layout instead of an opaque "not found".

## Safety
Kaggle credentials are **read-for-use, not read-to-share** (see the dev-phase secret policy in `CLAUDE.md` / `AGENTS.md`): read `~/.kaggle/kaggle.json` or the per-account credential files that policy names (`.vscode/.env.harry`, `.vscode/.env.may` — that list, not a wildcard) to authenticate a call, but never echo a credential into the session, a log, a web fetch, a PR, or a comment. Never commit API tokens. Never bypass daily submission limits or competition rules.
