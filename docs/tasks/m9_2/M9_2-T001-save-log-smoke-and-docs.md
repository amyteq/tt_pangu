# M9.2-T001: `/save-log` smoke + negative paths + doc note

## Milestone
M9.2: `/save-log` skill — Claude Code session transcript export.

## Goal
Exercise the newly-implemented `/save-log` skill end-to-end against a
real stopped or completed Claude Code background session, then verify
the three negative paths (running session, ambiguous selector, secret
match). Add a brief `/save-log` mention to `README.md`. Confirm
`docs/logs/` stays un-gitignored.

## Read first

1. `docs/tasks/m9_2/M9_2-T000-save-log-scaffold-and-impl.md` and its
   closeout.
2. `docs/meeting-notes/2026-05-26-r1.md` §5 (validation flow).
3. `scripts/save_claude_session_log.py` (the just-landed script).
4. `.claude/skills/save-log/SKILL.md`.
5. `README.md` — current-milestone block + tooling section.
6. `.gitignore` — confirm `docs/logs/` is not listed.

## Scope

1. List Claude Code background sessions and pick one that is `completed`
   or `stopped` and belongs to this repo:

   ```bash
   claude agents --json | jq -r '.[] | [.name, .sessionId, .status, .cwd] | @tsv'
   ```

   Record the chosen `name`, `sessionId`, and `status` in the closeout.
   Prefer the M9 / M10 closeout sessions if they are listed. Do NOT
   pick a running session for the positive smoke.

2. Run the script against the chosen session:

   ```bash
   python scripts/save_claude_session_log.py "<name-or-id>"
   ```

   Confirm:
   - Exit code 0.
   - JSON output prints `ok: true`, the matched selector, and the
     resolved transcript path.
   - `docs/logs/<safe-name>.md` exists.
   - The output file's first 30 lines contain the header block (lines
     starting with `- Exported at:`, `- Session name:`, `- Job id:`,
     `- Session id:`, `- Status:`, `- Source transcript:`, `- Output:`)
     and a `---` separator before the body.
   - The body is Markdown — no ANSI escape sequences
     (`\x1b[`/`\033[`), no terminal control codes.
   - File ends with a single trailing newline.

3. **Negative path A — running session.** Pick a session whose status
   is `running` / `working` (or `start` a fresh one if none exists).
   Run:

   ```bash
   python scripts/save_claude_session_log.py "<running-name-or-id>"
   ```

   Confirm:
   - Exit code 1.
   - Stderr contains "not stopped/completed" or equivalent, plus the
     hint to use `--allow-any-state`.
   - No `docs/logs/<name>.md` is written.

4. **Negative path B — ambiguous fuzzy selector.** Choose a substring
   that matches multiple agent names (e.g. `m` if two sessions start
   with `m`). Run:

   ```bash
   python scripts/save_claude_session_log.py "<ambiguous-substring>"
   ```

   Confirm:
   - Exit code 1.
   - Stderr contains "Ambiguous session selector" and lists the
     candidates (name / job_id / session_id / status / source).
   - No `docs/logs/<name>.md` is written.

   If no natural ambiguity exists in the current `claude agents`
   output, document that fact in the closeout and synthesize a
   minimal test by temporarily renaming two sessions to share a
   prefix; restore the names afterwards.

5. **Negative path C — secret-pattern hit.** Take the export from step
   2, copy it to a temp file, and append a line containing
   `sk-ant-abc123def456ghi789jkl012mno345pqr` (a clearly-fake but
   pattern-matching string). Reset the transcript locator by
   placing the temp file at a path the locator can find — easiest:
   write a synthetic `.jsonl` with one message containing the
   secret-like substring under `$TMPDIR/save-log-secret-test/` and
   point `CLAUDE_CONFIG_DIR` at a fake config dir containing a
   matching state.json. Then run:

   ```bash
   python scripts/save_claude_session_log.py "secret-test"
   ```

   Confirm:
   - Exit code 1.
   - Stderr contains "secret-like patterns detected" and lists at
     least one of the nine pattern labels (e.g. "Anthropic API key"
     or "generic sk-* API key").
   - No `docs/logs/secret-test.md` is written.

   Then re-run with `--allow-secret-like` and confirm the file IS
   written. Delete the synthetic `docs/logs/secret-test.md` after the
   check — do not commit it.

   If wiring a synthetic `CLAUDE_CONFIG_DIR` is too invasive, the
   acceptable fallback is to monkey-patch the `SECRET_PATTERNS` test
   inline in a one-off Python REPL run that scans a known-secret
   string and assert at least one pattern matches; document the
   fallback in the closeout.

6. Add a one-line `/save-log` mention to `README.md` under whichever
   section lists project skills / operator tooling. Wording suggestion:

   ```markdown
   - `/save-log <name|id>` — export a stopped or completed Claude Code
     background session transcript to `docs/logs/<name>.md` via
     `claude-code-log`. See `.claude/skills/save-log/SKILL.md`.
   ```

7. Confirm `docs/logs/` is **not** in `.gitignore`. If it is, halt and
   ask — this is a milestone decision (see `docs/milestones/m9_2/loop-prompts.md`
   §"Human decisions").

8. Do **not** commit `docs/logs/<name>.md` from step 2. The export is
   evidence for the closeout; the human reviewer decides per-export
   whether to commit. Keep it locally during the milestone; the
   milestone PR opened by T002 may or may not include it (T002's
   call).

9. Run `python -m pytest tests/ -q`. Must be green (no regression).

## Non-goals

- Do not add new pytest cases under `tests/`.
- Do not change `scripts/save_claude_session_log.py` other than to fix
  bugs surfaced by the smoke tests. If a behavioural change is needed,
  open a follow-up issue and patch in a separate PR.
- Do not delete or rename existing `claude agents` sessions for the
  ambiguity test without restoring them afterwards.
- Do not commit `docs/logs/*.md` other than `.gitkeep`. T002 decides
  whether the smoke-test export goes in the M9.2 PR.

## Acceptance criteria

- Positive smoke: a real `docs/logs/<name>.md` exists with the header
  block and a Markdown body free of ANSI escapes.
- Negative A (running session): exit 1 with the expected message; no
  file written.
- Negative B (ambiguous selector): exit 1 with the candidate list; no
  file written.
- Negative C (secret pattern): exit 1 with the pattern label; re-run
  with `--allow-secret-like` succeeds.
- `README.md` mentions `/save-log` in at least one place.
- `.gitignore` does **not** contain `docs/logs/`.
- `python -m pytest tests/ -q` still passes.

## Permissions

- Local file reads and writes inside the worktree are allowed.
- `~/.claude/projects/`, `~/.claude/jobs/`, and `claude agents --json`
  may be read.
- `~/.kaggle/kaggle.json`, `.env*`, `~/.ssh/**`, `~/.aws/**`,
  `~/.config/gcloud/**`, `~/.config/gh/**`, and `secrets/**` are not
  read.
- `git commit` and `git push` are **not** allowed in this task.
- No DB calls; no `dangerouslyDisableSandbox`.

## Closeout format

```
M9.2-T001 closeout
  Smoke session: name=<name> session_id=<id> status=<completed|stopped>
  Output: docs/logs/<name>.md (size=<bytes>, ANSI-free=YES)
  Header block: PASS (Exported at / Session name / Job id / Session id / Status / Source transcript / Output)
  Negative A (running session): PASS — exit 1, no file written
  Negative B (ambiguous selector): PASS — exit 1, candidates listed
  Negative C (secret pattern): PASS — exit 1, label=<which pattern>; --allow-secret-like override: PASS
  README.md /save-log mention: PASS
  .gitignore check: docs/logs/ NOT ignored
  pytest tests/ -q: PASS
  Acceptance: PASS | FAIL — link to issue
  Risks / blockers: ...
  Next: M9.2-T002 ready to start
```

## Related issues

- N/A — file an M9.2-T001 issue when picking up the task.
- If the smoke surfaces a `claude-code-log` flag-compatibility issue,
  file as a follow-up `type:bug` issue and document the workaround in
  the closeout; do not block T002 on closing it unless the workaround
  produces an unusable export.

## Stop condition

Stop after 60 turns. Halt and ask if:

- No stopped/completed session is available (the dev box has never
  produced one, or all known ones have been pruned). Decision: rerun
  T001 later, or stub the smoke with a frozen `.jsonl` fixture
  committed under `tests/fixtures/save_log_smoke/` (then update T000's
  read-list with the fixture path).
- The script writes to a path outside `docs/logs/`. Halt and rewrite
  before opening any PR.
- The secret-pattern test trips false-positively on the real
  transcript from step 2 (i.e. the real transcript is refused without
  `--allow-secret-like`). Halt — do not soften the patterns; inspect
  the transcript for a real secret first, then decide whether to
  flag a follow-up.
