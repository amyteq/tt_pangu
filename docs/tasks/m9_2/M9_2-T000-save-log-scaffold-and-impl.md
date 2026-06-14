# M9.2-T000: `/save-log` skill scaffold + script implementation

## Milestone
M9.2: `/save-log` skill — Claude Code session transcript export.

## Goal
Create the project skill at `.claude/skills/save-log/SKILL.md`, the
backing Python script at `scripts/save_claude_session_log.py`, and the
empty `docs/logs/.gitkeep` placeholder. Implement the script verbatim
from `docs/meeting-notes/2026-05-26-r1.md` §3, with the read-list
restrictions documented below. Confirm the script parses, `ruff` is
clean, and `uvx` + `claude-code-log` are reachable. No real session is
exported in this task — that is T001's job.

## Read first

1. `docs/meeting-notes/2026-05-26-r1.md` — canonical spec, §2 (SKILL.md)
   and §3 (Python script).
2. `docs/milestones/README.md` §M9.2.
3. `docs/milestones/m9_2/loop-prompts.md` — milestone shape.
4. `docs/milestone-loop-protocol.md` — sequencing + secret denylist.
5. `CLAUDE.md` — note that the dev-phase secret carve-out does **not**
   apply here (this script has no need to read credentials).
6. `.claude/skills/worktree-milestone-pr/SKILL.md` — skill frontmatter
   precedent (`name:` + `description:` only).
7. `.claude/skills/kg-nb/SKILL.md` — another skill precedent.
8. `scripts/README.md` — script-directory conventions.

## Scope

1. Create `.claude/skills/save-log/` and write `SKILL.md` with the
   frontmatter and body from meeting-notes §2:

   ```yaml
   ---
   name: save-log
   description: Export a stopped or completed Claude Code background session transcript to docs/logs/<session-name>.md using claude-code-log.
   argument-hint: "<name|id>"
   arguments:
     - session
   allowed-tools:
     - Bash(python scripts/save_claude_session_log.py*)
   disable-model-invocation: true
   tags:
     - logging
     - handoff
     - claude-code
   ---

   !`python scripts/save_claude_session_log.py "$session"`
   ```

   If the active Claude Code loader silently drops any of
   `argument-hint`, `arguments`, `allowed-tools`,
   `disable-model-invocation`, or `tags`, that is acceptable — keep
   them in the file so future loader versions pick them up. If the
   loader **rejects** the file outright (refuses to register
   `/save-log`), trim to `name:` + `description:` only and document the
   trim in the closeout.

2. Create `scripts/save_claude_session_log.py` verbatim from
   meeting-notes §3 (lines 176–666). Honour these read-list
   restrictions when copying:
   - The script reads only `~/.claude/projects/**/*.jsonl`,
     `~/.claude/jobs/*/state.json`, and the stdout of
     `claude agents --json`.
   - The script does **not** read `.env*`, `~/.kaggle/kaggle.json`,
     `~/.ssh/**`, `~/.aws/**`, `~/.config/gcloud/**`,
     `~/.config/gh/**`, `.netrc`, or anything under `./secrets/`.
   - If a future locator path is added, it MUST stay inside
     `~/.claude/projects/` or `~/.claude/jobs/`.

3. `chmod +x scripts/save_claude_session_log.py`.

4. Create `docs/logs/.gitkeep` (empty file) so the directory is tracked
   even before the first export.

5. Verify `python scripts/save_claude_session_log.py --help` exits 0
   and prints all four flags: `--allow-any-state`,
   `--allow-secret-like`, `--detail`, `--output-dir`.

6. Verify the script's nine `SECRET_PATTERNS` exactly match the
   meeting-notes §3 list (GitHub fine-grained PAT, GitHub token,
   Anthropic API key, generic `sk-*`, private key block, Anthropic env
   key, OpenAI env key, Kaggle key, Supabase key, generic secret
   assignment). Patterns may be reformatted but the regex bodies
   stay verbatim.

7. Run `ruff check scripts/save_claude_session_log.py` and
   `ruff format --check scripts/save_claude_session_log.py`. Both
   clean.

8. Verify `uvx --version` exits 0 and `uvx claude-code-log@latest --help`
   prints usage. Record the resolved `claude-code-log` version in the
   closeout (do not pin it in the script).

9. Do **not** run a real export. T001 owns smoke verification.

10. Do **not** commit. Per protocol §5 mid-milestone, stage with
    `git add` and surface diffs in the inline report; the closeout
    commit is owned by T002 / `worktree-milestone-pr`.

## Non-goals

- Do not run `python scripts/save_claude_session_log.py <selector>`
  against a real session in this task.
- Do not add tests under `tests/test_save_log_*.py`. M9.2 is operator
  tooling; smoke verification lives in T001.
- Do not modify `.claude/settings.json`, `.claude/hooks/`, or the
  global `permission` blocks. The skill's `allowed-tools` block is the
  load-bearing gate.
- Do not add `docs/logs/*.md` to `.gitignore`.
- Do not create `.claude/commands/save-log.md`. Skills override
  commands of the same name; a duplicate is forbidden by the meeting
  notes §2.
- Do not add a network call beyond what `uvx` itself does on first
  use.

## Acceptance criteria

- `.claude/skills/save-log/SKILL.md` exists, with the meeting-notes §2
  frontmatter and body (modulo any frontmatter trim recorded in the
  closeout per scope step 1).
- `scripts/save_claude_session_log.py` exists, is executable, and
  matches the meeting-notes §3 reference. The nine `SECRET_PATTERNS`
  are present.
- `docs/logs/.gitkeep` exists (zero bytes).
- `docs/logs/` is **not** added to `.gitignore`.
- `python scripts/save_claude_session_log.py --help` exits 0 and prints
  the four flags.
- `ruff check scripts/save_claude_session_log.py` clean.
- `ruff format --check scripts/save_claude_session_log.py` clean.
- `uvx claude-code-log@latest --help` runs successfully; the resolved
  version is recorded in the closeout.
- `git status` shows exactly the three new files (`SKILL.md`,
  `save_claude_session_log.py`, `docs/logs/.gitkeep`) and nothing
  else.

## Permissions

- Local file writes are allowed inside the worktree.
- `~/.claude/projects/` and `~/.claude/jobs/` may be read by the
  script at runtime (not by T000's verification, which only runs
  `--help`).
- `~/.kaggle/kaggle.json`, `.env*`, `~/.ssh/**`, `~/.aws/**`,
  `~/.config/gcloud/**`, `~/.config/gh/**`, and `secrets/**` are
  **not** read at any time. This is stricter than the CLAUDE.md
  dev-phase carve-out, on purpose: this script has no need for them.
- `git commit` and `git push` are **not** allowed in this task.
- No DB calls; no `dangerouslyDisableSandbox`.

## Closeout format

```
M9.2-T000 closeout
  Files created: .claude/skills/save-log/SKILL.md, scripts/save_claude_session_log.py, docs/logs/.gitkeep
  SKILL.md frontmatter: full meeting-notes §2 set | trimmed to name+description (record reason)
  Script --help: PASS — prints --allow-any-state, --allow-secret-like, --detail, --output-dir
  ruff check: PASS | FAIL
  ruff format --check: PASS | FAIL
  uvx --version: <version>
  claude-code-log version resolved by uvx: <version>
  Read-list restriction: confirmed — script reads only ~/.claude/projects/ and ~/.claude/jobs/
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M9.2-T001 ready to start
```

## Related issues

- N/A — M9.2 has its own M9.2-T000 issue once filed. Link it from the
  closeout.

## Stop condition

Stop after 60 turns. Halt and ask if:

- `uvx` is missing on the dev box and cannot be installed without
  approval.
- `claude-code-log` rejects the `--format md / --detail low / --compact`
  flag combination — do not silently pin a different version.
- The Claude Code skill loader refuses the meeting-notes §2 frontmatter
  outright. Document which keys failed before trimming.
- The script reads any file outside `~/.claude/projects/` or
  `~/.claude/jobs/` (e.g. an accidental glob). Halt and rewrite.
