<!-- GENERATED FILE — DO NOT EDIT BY HAND.
     Sources: .claude/skills/ + the excludes in scripts/gen_agents.py.
     Regenerate: python scripts/gen_agents.py
     Verify:     python scripts/gen_agents.py --check   (also asserted by tests/test_instruction_parity.py)
-->

# `.agents/` — the Codex-side mirror of `.claude/`

Phase 1 launches the same competition workflow from Claude Code and from Codex against the same repo state (discussion #185, issue #189). Claude Code reads `CLAUDE.md` + `.claude/`; Codex reads `AGENTS.md` + this directory.

Nothing here is hand-maintained. `python scripts/gen_agents.py` writes it, and `python scripts/gen_agents.py --check` — asserted by `tests/test_instruction_parity.py` in CI — fails if it drifts from `.claude/`.

## Mirrored — symlinks, never copies

`.agents/skills/<name>` is a relative symlink to `.claude/skills/<name>`, so a skill has exactly one body on disk and both harnesses load the same bytes. Codex follows the symlink and lists the skill under its front-matter `name`.

| Skill | Symlink target | What it is for |
|---|---|---|
| `agent-iteration-review` | `../../.claude/skills/agent-iteration-review` | Use after tests, validation, benchmark, submission, or CTF solver results are available |
| `at-review-pr` | `../../.claude/skills/at-review-pr` | Run bounded PR review and fix rounds with independent Codex or Claude Code sessions, evidence-linked dispositions, and a final full review before approval |
| `ctf-sandbox` | `../../.claude/skills/ctf-sandbox` | Use for authorized CTF challenge solving only: local challenge analysis, sandboxed exploitation, solver scripts, flags, and writeups within explicitly provided scope |
| `design-archaeology` | `../../.claude/skills/design-archaeology` | Use before implementing any migration, rewrite, take-over, or port of legacy scripts / configs |
| `github-issue-triage` | `../../.claude/skills/github-issue-triage` | Triage one or more GitHub issues — propose label adds/removes and a triage comment, gated by deterministic rules |
| `inventory-drift-audit` | `../../.claude/skills/inventory-drift-audit` | Scan docs / code / tests / config / schema / inventory for drift; produce evidence-backed drift findings and propose drift.yml issues |
| `kaggle-evaluation-harness` | `../../.claude/skills/kaggle-evaluation-harness` | Use when creating, running, or improving validation/evaluation loops for Kaggle competitions and competition-like benchmarks |
| `kaggle-experiment-loop` | `../../.claude/skills/kaggle-experiment-loop` | Use for Kaggle or ML competition work: understand metric/rules, plan validation, implement one experiment, run it, compare metrics, and decide whether to iterate or prepare a submission |
| `kaggle-tooling-integration` | `../../.claude/skills/kaggle-tooling-integration` | Use when integrating or invoking Kaggle helper scripts such as notebook conversion, kernel push, competition submission, result retrieval, and experiment artifact recording |
| `kg-nb` | `../../.claude/skills/kg-nb` | Convert between Jupyter notebooks and percent-format Python scripts via the kca CLI |
| `kg-run` | `../../.claude/skills/kg-run` | Initialize a run artifact directory under runs/<competition>/<run_id>/ and record metrics, via the kca CLI |
| `labels-sync` | `../../.claude/skills/labels-sync` | Diff repo labels against .github/labels.yml and prepare a sync plan |
| `memory-promotion` | `../../.claude/skills/memory-promotion` | Use to distill GitHub issue/PR/review/meeting-notes content into proposed patches against canonical memory (PROJECT_STATE.md, docs/milestones/README.md, docs/milestones/*/handoff.md, docs/adr/) |
| `milestone-final-review` | `../../.claude/skills/milestone-final-review` | Generate docs/milestones/m{N}/final-review.md from a milestone's validation matrix |
| `milestone-review` | `../../.claude/skills/milestone-review` | Review a milestone against acceptance criteria, produce a structured review report |
| `pr-closeout-review` | `../../.claude/skills/pr-closeout-review` | Check that a PR's body matches the closeout template (tests run, docs/inventory, evidence, schema/secrets, remote side effects), and report which boxes are unchecked or unsupported |
| `research-brief` | `../../.claude/skills/research-brief` | Use when researching webpages, docs, papers, forums, competition pages, writeups, or browser-rendered content |
| `worktree-milestone-pr` | `../../.claude/skills/worktree-milestone-pr` | Execute the milestone-end git+gh sequence per docs/milestone-loop-protocol.md §5 — one commit per Loop Prompt, push the worktree branch, open a PR against main |

Claude-Code-only front-matter keys (`allowed-tools`, `argument-hint`) are tolerated by Codex — a skill carrying them is still listed.

### Not mirrored

| Skill | Why |
|---|---|
| `save-log` | Claude-Code-only — exports a Claude Code session transcript via `claude-code-log`. |

## No Codex counterpart

| `.claude/` | Status in `.agents/` | Consequence |
|---|---|---|
| `agents/*.md` (sub-agent definitions) | **absent** — Codex 0.154.0 has no repo-level sub-agent format | Run the review in-session against the same checklist, and say it was not an independent agent. |
| `hooks/*.py` (`guard_tool`, `format_gate`, `audit_event`) | **absent** — Codex hooks are per-user config (`~/.codex/config.toml` / a managed dir), never repo-shipped | Real safety asymmetry: in Codex the deletion / force-push / secret rules are enforced only by reading them, and no `.agent/audit/tool-events.jsonl` trail is written. See *The safety asymmetry* in `AGENTS.md`. |
| `settings.json` (`permissions.allow` / `deny`) | **absent** — Codex approval policy and sandbox come from per-user config and CLI flags | The human sets Codex's approval mode; the repo cannot pre-approve commands for it. |

## Regenerating

```sh
python scripts/gen_agents.py          # rewrite AGENTS.md + .agents/
python scripts/gen_agents.py --check  # verify (what CI runs)
```

The Codex-side evidence and the two-harness smoke check are in `docs/tooling/codex-parity.md`.
