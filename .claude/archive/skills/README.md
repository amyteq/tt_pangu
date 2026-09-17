# `.claude/archive/skills/` — retired skills, kept for history

A skill here is **retired**. It is **not loaded** by any harness: Claude Code reads `.claude/skills/`, Codex reads `.agents/skills/`, and `scripts/gen_agents.py` mirrors only the former — nothing scans this directory. Moving a skill here is therefore a removal from both harnesses, not a demotion.

It is kept rather than deleted because the body is evidence: it records what the project once told an agent to do, which is what makes a later "why did it behave that way?" answerable. Each file arrived by `git mv`, so `git log --follow` on it reaches back to the original.

**Read an archived body as history, never as instruction.** Some of these contradict rules that are current today — that is usually *why* they were retired. Each file carries a banner naming the skill that replaced it; follow the banner, not the body. If you want the behaviour an archived skill described, get it from the replacement.

## What is here

| Retired skill | Retired in | Replaced by | Why |
|---|---|---|---|
| `kaggle-evaluation-harness` | issue #192 | `kg-audit` | A pure checklist — no tool calls, no repo-specific knowledge. Every line is subsumed by `kg-audit`'s leakage / split / metric / reproducibility / rules review. |
| `kaggle-tooling-integration` | issue #192 | `kg-submit` + `docs/tooling/kaggle-kernel-ops.md` | Split, then the shell archived. The submission gate and the required-facts list moved into `kg-submit`; the kernel/version model, flat-kernel structure, per-account concurrency and the in-kernel mount-path resolver moved into `docs/tooling/kaggle-kernel-ops.md`. Its approval text also contradicted ADR-0021 / ADR-0022 §5. |

## Retiring a skill

1. `git mv .claude/skills/<name> .claude/archive/skills/<name>` — never `rm` and re-add, or `--follow` stops at the new file.
2. Add the banner under the front matter: what replaced it, and the issue that retired it.
3. Add a row above.
4. Run `python scripts/gen_agents.py` so `.agents/` drops the mirror symlink, and check `SKILL_EXCLUDES` in `scripts/gen_agents.py` no longer names it — a stale exclude leaves a phantom row in `.agents/README.md` and fails `--check`.
5. Move anything still true into its replacement in the same change. An archived skill is not a place to look things up.
