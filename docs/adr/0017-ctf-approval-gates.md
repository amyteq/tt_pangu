# ADR-0017: CTF approval gates — `challenge_run`, `flag_submit`, `network_egress`

## Status

Accepted (M11-T002, 2026-06-09). Lands with `.kca/permissions/*.yaml`, `src/worker/reviewer.py`, `src/worker/worker.py`, `.claude/settings.json`, and `.claude/hooks/guard_tool.py`.

Cross-links:
- [`docs/evidence/m11/discovery/design-red-team.md`](../evidence/m11/discovery/design-red-team.md) — the open question about WHICH LAYER enforces `network_egress` is resolved here (`§ Enforcement layer pinning` below).
- [`docs/adr/0006-configurable-approval-gates.md`](0006-configurable-approval-gates.md) — operation data shape this ADR extends.
- [`docs/adr/0016-ctf-data-model.md`](0016-ctf-data-model.md) — the `ctf_scopes` / `ctf_attempts` rows the gate writes against.

## Context

M11 introduces the first non-Kaggle competition platform on the agent stack: authorized CTF / lab workflows. Two new high-blast-radius operations need a reviewer gate:

1. **`challenge_run`** — executing a solver against an authorized CTF target (local in-scope service OR a URL in `ctf_scopes.target_urls`).
2. **`flag_submit`** — submitting a flag string to the event's API.

A third operation, **`network_egress`**, exists to catch worker-issued HTTP calls whose host falls outside the union of `ctf_scopes.target_urls` rows for the current project. Unlike `challenge_run` and `flag_submit`, `network_egress` is a *deny-by-default silent backstop*, not a gate that fires for an intentional action.

Without these three operations, the platform has only `kaggle_submit` / `kernel_push` style gates, which are leaderboard-shaped and assume the target URL is implicit (`kaggle.com`). CTF events have per-event target URLs (the picoCTF case, the bbbctf case), and the wrong target + the wrong flag would be a critical incident with no leaderboard infrastructure to limit blast radius.

## Decision

Add three operations to `.kca/permissions/*.yaml`, extend the reviewer trigger set, and wire a tool-name → target-op mapping in the worker so synthetic CTF tools surface as the correct operation string on the `agent_reviews` row.

### 1. Operations + defaults

| Operation | `default.yaml` | `permissive-dev.yaml` | `competition-runner.yaml` | `audit_required` |
|---|---|---|---|---|
| `challenge_run` | `ask` | `ask` (no dev auto-allow) | `ask`, `conditional_allow.when_in_scope: allow` | `true` |
| `flag_submit` | `ask` | `ask` | `ask` (no conditional allow) | `true` |
| `network_egress` | `deny`, `conditional_allow.when_in_scope: ask` | same | same | `true` |

Rationale for the asymmetry:
- `challenge_run` may move to `allow` under `competition-runner` when the target URL is in `ctf_scopes.target_urls` — the human has already authorized the scope row, and gating every solver attempt would destroy the workflow.
- `flag_submit` stays on `ask` regardless of profile. Flag submission is the highest-blast-radius op (wrong flag from wrong account = team ban; correct flag with wrong credential file = audit gap matching the kkr.py replay failure mode). No auto-allow path.
- `network_egress` defaults to `deny`. The only relaxation path is `conditional_allow.when_in_scope: ask` — if the request host matches a `ctf_scopes.target_urls` row, the gate fires for human approval instead of silently denying. To widen access, the human edits the scope row, not the policy.

### 2. `conditional_allow.when_in_scope` semantics

`when_in_scope` is consulted by the worker before raising `ApprovalRequired`. The check shape (M11-T003 / T005 implement the worker side; T002 records only the policy YAML):

1. The worker resolves the project's `ctf_scopes` rows that are not expired (`expires_at` IS NULL OR `expires_at` > now()).
2. The union of `target_urls` (textarray on each row) is computed.
3. For `challenge_run` / `network_egress`, the call's destination URL host is compared to that union (exact-host match for M11; subdomain match is filed as a follow-up).
4. If matched, `conditional_allow.when_in_scope` is honored: `allow` → run without a gate; `ask` → raise `ApprovalRequired` and fire the reviewer.
5. If unmatched: fall back to `default_decision`.

### 3. Enforcement layer pinning

The design-red-team report (`docs/evidence/m11/discovery/design-red-team.md` § `open_disagreements` 4th bullet) raised the open question: which layer enforces `network_egress`? Three candidates exist:

- **Reviewer-gate** (`src/worker/reviewer.py`): fires when the worker raises `ApprovalRequired(operation="network_egress")`.
- **Hook layer** (`.claude/hooks/guard_tool.py`): denies known-bad hosts at Claude Code's PreToolUse step.
- **HTTP-client interceptor** (httpx middleware): wraps every outbound request from the worker.

**Decision (binding for M11):**

1. **Primary authority: the reviewer-gate.** When the worker is about to issue a request whose host is outside the in-scope union, it raises `ApprovalRequired("network_egress", ...)`. The reviewer-gate is the deny-default authority. This is what `.kca/permissions/*.yaml` pins.
2. **Secondary defense: the hook layer.** `.claude/hooks/guard_tool.py` denies known-bad hosts (metadata services, CTF credential paths) even before the reviewer fires. This catches shell-level egress attempts (`curl`, `wget`, `scp`, `rsync`) and direct Read/Edit of `~/.ctf/*.json`.
3. **Out of scope for M11: the httpx interceptor.** A per-request httpx middleware that consults `ctf_scopes.target_urls` on every outbound HTTP call is *the right long-term answer* (it survives subprocess and direct-Python paths the worker doesn't know about), but it requires touching `tools/kca/research_fetch.py` and every other httpx-using surface. Filed as a follow-up: `M12 / M13 network-egress-interceptor`.

The known consequence of the layer choice: a subprocess `curl` issued from inside a `bash` tool call bypasses both the reviewer-gate and the hook layer's regex (for hosts not in `deny_patterns`). M11 mitigates by hard-asking on every `bash` call under `default.yaml` and by the M11-T005 solver flow running `docker-compose up` against a *local* network only — the live event egress is gated to T007's single approved call.

### 3a. CTFtime platform credential tier (`~/.env`)

_Added 2026-05-27 in response to PR #45 reviewer feedback._

Background: the user pointed out that the M11-T002/T003 credential model only covered **per-event** signups (`~/.ctf/<slug>.json`). It did not have a place for the **CTFtime.org platform account** (single account per user; used for the CTFtime calendar / event-registration flow and for events that accept CTFtime SSO).

**Decision:** treat CTFtime as a separate, single-account credential tier with its own canonical location, loader, and hook carve-out — parallel to the per-event tier.

| Aspect | CTFtime platform tier | Per-event tier |
|---|---|---|
| When to use | CTFtime calendar / SSO-enabled events | Events requiring separate signup |
| Storage | `~/.env` (one file per user) | `~/.ctf/<slug>.json` (one file per event) |
| Keys | `CTFTIME_USERNAME`, `CTFTIME_PASSWORD` (or `CTFTIME_TOKEN`) | `username`, `token`, optional `team_id` |
| Loader | `tools/kca/ctf.py::_load_ctftime_credentials()` | `tools/kca/ctf.py::_load_event_credentials(slug)` |
| Hook carve-out | `~/.env` denied at hook; loader is sole allow-listed caller | `~/.ctf/*` denied at hook; loader is sole allow-listed caller |
| CI fallback | process env `CTFTIME_USERNAME` + `CTFTIME_PASSWORD`/`_TOKEN` | process env `CTF_<EVENT>_USERNAME` + `CTF_<EVENT>_TOKEN` |

`~/.env` is **distinct** from the project root `.env`. The project root `.env` (e.g., `./.env`, `./.env.local`, `./.env.development`) remains readable per the dev-phase carve-out documented in `.claude/hooks/guard_tool.py::path_is_protected` — it holds `SUPABASE_DB_URL` and similar local DSNs. Only `~/.env` (HOME-dir scope) is the protected CTFtime tier.

The hook's path-protection check distinguishes them by absolute path equality (`p == "{HOME}/.env"`) so `./env` style relative paths still fall through to the dev-phase carve-out.

The shell-read deny patterns additionally cover `cat ~/.env`, `grep ... ~/.env`, `curl -d "$(cat ~/.env)" ...`, and `/home/<user>/.env` absolute variants — using a tightened look-ahead `(?![.A-Za-z0-9_-])` so that `~/.env.local` does NOT match (we don't claim that path).

### 4. Audit row shape

For each gated operation, the worker writes:

- `agent_reviews` row with `target_op` ∈ {`challenge_run`, `flag_submit`, `network_egress`} and the reviewer's `verdict` / `rationale`. For `flag_submit`, **the flag value never appears** in `rationale`, `evidence`, or the rendered prompt — the reviewer module's `_redact_tool_input` replaces the flag with `{"_redacted": true, "length": N}` before prompt rendering.
- `human_decisions` row with `status='pending'` then `approved` / `denied`. The decision_api surfaces it; the UI Approval Inbox renders it; T006 exercises the round-trip.
- `agent_job_events` rows for `reviewer_decision`, `approval_resume`, and `reviewer_reject` / `reviewer_abstain` as appropriate (same shape as M9 / M10).
- `agent_tool_audit` row via `tools/kca/agent/audit.log_policy_decision` recording the resolved policy decision. For `network_egress` denies, this is the audit row that captures the attempt — no agent_reviews row is written if the resolution short-circuits at `default_decision: deny` (the human must widen `ctf_scopes.target_urls` to even attempt the call).

No new `agent_tool_audit` columns are added in M11-T002; the existing shape captures `tool`, `operation`, `decision`, `policy_profile`, `mode`, `audit_required`, `args` (with the same flag-redaction posture applied via `args.flag = {"_redacted": True, ...}` when `tool == "flag_submit"`).

### 5. Alternatives + dropped capabilities

Cross-link [`docs/evidence/m11/discovery/design-red-team.md`](../evidence/m11/discovery/design-red-team.md) for the full design-red-team analysis. Summary of what M11 explicitly *did not* adopt:

- **Single `ctf_op` operation with sub-action discriminator** — considered; rejected because the policy YAMLs already key on per-operation rows and a discriminator would push the ask/deny/conditional-allow logic into worker code.
- **Per-request httpx interceptor instead of reviewer-gate** — deferred to M12/M13 as noted above.
- **Auto-widen `ctf_scopes.target_urls` on a reviewer-approved `network_egress`** — rejected. The reviewer can approve a one-shot egress without widening the persistent scope row; the human edits the scope row to widen access for future calls.
- **A `flag_submit_dry_run` operation distinct from `flag_submit`** — rejected. The `--dry-run=False` flag on the kca CLI is the gate; dry-runs do not raise the operation.
- **Per-challenge rate-limit as a policy field** — out of scope. The red-team report flagged this as a dropped capability; it is filed as a follow-up against `ctf_scopes` schema extensions.

## Consequences

- **Positive:** The CTF workflow has a clean three-op surface that maps 1:1 to the reviewer-gate / audit chain that already exists for `kaggle_submit` / `kernel_push`.
- **Positive:** The flag value never reaches the reviewer prompt or any audit row — eliminates a leakage path that would otherwise appear in `agent_reviews.rationale` (LLM-generated text) and in the OTEL span for the reviewer call.
- **Positive:** `network_egress` deny-by-default makes the wrong host a hard error rather than a silent leak. The kkr.py replay failure mode (ambient credential + wrong endpoint) is structurally prevented for new CTF events.
- **Negative:** A subprocess `curl` from inside `bash` can bypass the reviewer-gate. Mitigation: `bash` is `ask` under `default.yaml` and every bash invocation is audited. M12/M13 will harden via httpx interceptor.
- **Negative:** The `conditional_allow.when_in_scope` field is a new YAML shape; tools that read the policy file (the worker, the UI's policy preview) need to handle it. M11-T002 lands the YAML; the worker-side check is wired in M11-T005.

## Implementation notes (for M11-T003+ wiring)

- The worker resolves `tool_name → target_op` via the `_TOOL_TO_TARGET_OP` map in `src/worker/worker.py`. Adding a new CTF tool means adding a row there; the reviewer trigger set in `src/worker/reviewer.py::DEFAULT_TRIGGER_OPS` already covers the three operation strings.
- The reviewer-rendered prompt is built by `src/worker/reviewer.py::_render_prompt`, which calls `_redact_tool_input` before serializing `tool_input` to JSON. For `flag_submit`, fields named `flag` / `flag_value` / `submission` are replaced with `{"_redacted": True, "length": N}`. The reviewer receives event_slug + challenge_slug + flag_length; this is sufficient context for the abstain/approve/reject decision.
- `~/.ctf/<slug>.json` files are denied at the hook layer for `Read` / `Edit` / `Write` tools and for shell `cat|less|...|curl|wget` reads. The Python `tools/kca/ctf.py::_load_event_credentials` call-site (T003) reads via Python `open()` from inside the kca process, which the hook layer does not intercept (this is the designed seam).
