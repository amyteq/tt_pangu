# M5-T003: `kca research` CLI + agent integration

## Milestone
M5: research and browser workflow.

## Goal
Wrap `research_fetch.fetch_page` (T002) and the DB helpers (T001) behind a
CLI surface that both humans and the agent loop can call. Add the
`external_fetch` approval gate so non-allowlisted domains can be policy-gated
per ADR-0006.

## Read first
1. `tools/kca/competition.py` — pattern for a new subcommand module
2. `tools/kca/kg.py` — approval-gate integration (T006 / T007 from M4)
3. `tools/kca/research_fetch.py` (T002)
4. `tools/kca/db.py` (T001)
5. `docs/adr/0006-configurable-approval-gates.md`

## New file: `tools/kca/research.py`

### Commands
```
kca research fetch --url <url> [--competition <slug>] [--fetcher http|playwright]
                   [--trust official|trusted_public|community|untrusted|unknown]
                   [--summary <text>] [--json]
   → on success: writes artifacts under artifacts/research/<hash[:12]>/raw.html
                 + main.txt; inserts artifacts rows; inserts research_items row
                 with html_artifact_id / text_artifact_id / content_hash; emits
                 {"ok": true, "research_item_id": "...", "url": "...",
                  "trust": "...", "side_effect": "REMOTE_WRITE"}

kca research add --url <url> [--title <t>] [--summary <s>] [--trust <l>]
                 [--competition <slug>] [--json]
   → manual entry (no fetch). LOCAL_WRITE.

kca research list [--competition <slug>] [--limit 50] [--json]
kca research show --id <item_id> [--json]
kca research cite --id <item_id> [--run-id <run>] [--experiment-id <exp>]
                  [--quote <text>] [--json]
```

### Approval gate
Before any `fetch` to a host NOT on `KCA_RESEARCH_ALLOW_DOMAINS`, call
`_check_approval_gate("external_fetch", policy)`. Default gate value should
be **False** (allow) — the gate is for paranoid policies that want every
external fetch reviewed.

Add `"external_fetch": False` to `OPERATION_DEFAULTS` in `tools/kca/kg.py`
and to `JobPolicy.approval_gates` in `src/worker/_types.py`.

### research-brief skill alignment
Update `.claude/agents/research-brief.md` (or equivalent) to explicitly
require `kca research fetch` as the only sanctioned external-page reader,
so future agents do not invent ad-hoc `curl`/`wget` paths.

## Wiring
- Register parsers in `tools/kca/kca.py`: `import research as research_mod; research_mod.add_parsers(sub)`.
- Add `kca research*` to `.claude/settings.json` allow list (no leading-write
  prompts in autonomous mode).

## Acceptance criteria
- `kca research --help` lists `fetch | add | list | show | cite`.
- `kca research fetch --url http://localhost/ --json` returns
  `{"ok": false, "error": "private-net"}` (T002 enforcement).
- With a small fixture HTTP server (or `httpbin.org` mocked):
  - `fetch` writes `artifacts/research/<hash>/raw.html` + `main.txt`.
  - DB row exists in `research_items` with matching `content_hash`.
- `external_fetch` gate raises `ApprovalRequired` when set to True in policy
  and host is not allowlisted.
- `python -m pytest tests/ -v` — 0 failures.

## Stop condition
Stop after 40 turns.
