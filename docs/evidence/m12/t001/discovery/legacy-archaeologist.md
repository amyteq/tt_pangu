legacy-archaeologist report for M12-T001 competition-policy generalization
(read targets: supabase/migrations/0004_m4_competition_repo.sql,
tools/kca/competition.py, tools/kca/kg.py, tools/legacy/kkr.py,
tools/legacy/kkr.yaml, .kca/permissions/{default,competition-runner,permissive-dev}.yaml,
.claude/skills/kaggle-experiment-loop/SKILL.md, docs/adr/0006, docs/adr/0009)

_Methodology note (parent-session disclosure)._ The Agent / Task tool was not
exposed to this Loop Prompt's environment; the parent session therefore
produced the three Discovery / Debate Gate reports inline against the
`.claude/agents/{legacy-archaeologist,requirements-skeptic,design-red-team}.md`
specs (same read-only surfaces, same mandatory section list, same canonical
acceptance line). The "agent path / skill path emit compatible output
shapes" clause in `docs/milestone-loop-protocol.md` §7 and
`docs/architecture/discovery-debate-gate.md` "Relationship to M9.3's
design-archaeology skill" governs this fallback. No interpretive judgement
about the design was made before the requirements-skeptic and
design-red-team reports were written; each role was authored in isolation
and then the parent synthesised ADR-0018.

1. workflows:
   - competition register (Kaggle slug → DB row + repo metadata) — entry: tools/kca/competition.py:48 (`cmd_register`); exit: tools/kca/competition.py:81 (`return EXIT_OK`)
   - competition clone (git clone competition repo to local_clone_path) — entry: tools/kca/competition.py:84 (`cmd_clone`); exit: tools/kca/competition.py:135
   - competition list (READ_ONLY enumeration of registered competitions) — entry: tools/kca/competition.py:138; exit: tools/kca/competition.py:165
   - competition info (READ_ONLY single-row inspection by slug) — entry: tools/kca/competition.py:168; exit: tools/kca/competition.py:184
   - Kaggle CSV submit (SUBMISSION side-effect, gated) — entry: tools/kca/kg.py:42 (`_check_approval_gate`); env-override: tools/kca/kg.py:17 (`_GATE_ENV = "KCA_ALLOW_REMOTE"`)
   - Kaggle kernel push (multi-account-capable in legacy) — entry: tools/legacy/kkr.py:528 (`_load_env_for_owner`); per-owner config: tools/legacy/kkr.yaml:57–86 (a09h / a09m / b09h / b09m pairs)
   - Kaggle dataset / model source attachment (kernel-time, not submission-time) — config: tools/legacy/kkr.yaml:22–35 (`competition_sources`, `dataset_sources`, `kernel_sources`, `model_sources`)
   - kaggle-experiment-loop skill workflow (research → baseline → hypothesis → run → analyze → submission-gate) — entry: .claude/skills/kaggle-experiment-loop/SKILL.md:13–42
   - permission-resolver evaluation (skill profile + mode → allow/ask/deny) — entry: tools/kca/agent/permission_policy.py:41 (`PermissionPolicy.resolve`)

2. hidden_assumptions:
   - "Every competition is a Kaggle competition" — schema-level: supabase/migrations/0004_m4_competition_repo.sql:14–18 names the table `competitions` and attaches `repo_url`, `default_branch`, `local_clone_path`, `competition_policy` but no `platform` / `competition_type` column; the Kaggle-shape is hard-coded by absence.
   - Default clone path templated to Kaggle slug — tools/kca/competition.py:38–39 (`_default_clone_path` → `~/competitions/kaggle-<slug>`); a non-Kaggle event would silently inherit `kaggle-` prefix.
   - The `competition_policy` jsonb on `competitions` is free-form and read by ADR-0006 lookup, but the resolver does not type-check the keys (`approval_gates.kaggle_submit`, `approval_gates.kernel_push`); a Devpost row would carry meaningless Kaggle keys unless code is added — evidence: docs/adr/0006-configurable-approval-gates.md:30–43 vs supabase/migrations/0004_m4_competition_repo.sql:18 (`DEFAULT '{}'`).
   - Approval-gate env-override is shared across operations — tools/kca/kg.py:17 (`_GATE_ENV = "KCA_ALLOW_REMOTE"`) is a single boolean for *all* Kaggle remote ops; there is no per-operation env-override and no per-competition env-override.
   - Permission profile per skill (`hackathon-runner.yaml`) does not exist yet — `.kca/permissions/` ships exactly three files (default, competition-runner, permissive-dev); the resolver expects a profile-file-per-skill-binding (tools/kca/agent/permission_policy.py:79–88 `load_policy`), so adding `competition_type='devpost'` without a matching profile file falls back to `default.yaml` and emits no Devpost-specific behaviour.
   - The `kaggle-experiment-loop` skill embeds Kaggle vocabulary in its prompt (.claude/skills/kaggle-experiment-loop/SKILL.md:13–17 "competition slug, metric, objective, data constraints, submission format, submission limits") — sibling skills for Devpost / CTF / generic must restate those slots in their own vocabulary.
   - Repo-per-competition convention is Kaggle-named — docs/adr/0009-competition-repo-strategy.md:40–42 (`<github-user>/kaggle-<slug>[-YYYY]`); a Devpost slug would inherit the `kaggle-` prefix unless the convention is loosened.

3. personas_and_accounts:
   - Kaggle account "owner" — selector: tools/legacy/kkr.yaml:6 (`id: harrysun2006/test`, owner = `harrysun2006`) and tools/legacy/kkr.yaml:58 (`id: harrysun2006/gpt-oss-120b-a09h`) vs tools/legacy/kkr.yaml:66 (`id: firefly2006/gpt-oss-120b-a09m`); storage: per-owner dotenv via tools/legacy/kkr.py:541 (`path = Path(".") / f".env.{owner}"`); env-map override: tools/legacy/kkr.py:495 (`env_map_raw = data.get("_envs") or {}`).
   - The current `tools/kca/competition.py` / `tools/kca/kg.py` paths carry NO equivalent multi-account selector — there is one set of Kaggle creds in process env (`KAGGLE_USERNAME` / `KAGGLE_KEY`) and no per-row override. This is the M9-T000 deviation working around the kaggle-CLI auth shape (the canonical failure mode named in `.claude/agents/legacy-archaeologist.md:11–16` and `docs/architecture/discovery-debate-gate.md:18–22`).
   - GitHub user (competition-repo owner) — selector: docs/adr/0009-competition-repo-strategy.md:40 (`<github-user>/kaggle-<slug>`); storage: implicit from local git config, not from a DB column.
   - Devpost identity (M12 net-new) — no selector exists; the Devpost cookie / API-token shape will land in M12-T003 / M12-T007 with a `.env` slot (auth shape TBD per docs/milestones/m12/loop-prompts.md:386–391 closing-issue record).
   - Team identity (M12 net-new) — no selector exists; minimal `teams` + `team_memberships` schema lands in M12-T002 per docs/milestones/m12/loop-prompts.md:132 and docs/tasks/m12/M12-T001-discovery-debate-gate.md:91–92 ("M12 ships read-only team membership only").
   - Service / reviewer account — selector: human's `kca decisions approve --id <id>` invocation (docs/adr/0006-configurable-approval-gates.md:110–118); storage: `human_decisions` rows; no separation between "team-member reviewer" and "project-owner reviewer" in M12 scope.

4. side_effects:
   - Local DB write on `competition register` — tools/kca/competition.py:56–62 (`_db.update_competition`).
   - Local filesystem write on `competition clone` — tools/kca/competition.py:117 (`subprocess.run(["git", "clone", repo_url, clone_path], …)`).
   - Remote Kaggle SUBMISSION (CSV) — tools/kca/kg.py `cmd_submit` path; gated by `_check_approval_gate` (tools/kca/kg.py:42) and `_GATE_ENV` (tools/kca/kg.py:17).
   - Remote Kaggle kernel push (multi-owner-capable in legacy) — tools/legacy/kkr.py ACTION_PUSH = "push" (tools/legacy/kkr.py:50); produces public side-effect under the *configured owner*, not the env-default owner.
   - Public dataset / kernel publication side-effect — tools/legacy/kkr.yaml:13 (`is_private: true`) toggles whether the published artefact is public or owner-private; a misconfigured row leaks code.
   - `human_decisions` row insertion on every gated op — tools/kca/kg.py:62–78 (`_record_approval`).
   - Logged event in `agent_job_events` — every gate decision is auditable per docs/adr/0006-configurable-approval-gates.md:125–132 ("All operations are still logged in agent_job_events").
   - Net-new for M12: Devpost form-POST (T007) and Devpost READ_ONLY page-fetch (T003); the Devpost fetch reuses the research-fetch HTTP path per docs/milestones/m12/loop-prompts.md:259.

5. state_files_and_registries:
   - `competitions` table (Supabase) — supabase/migrations/0004_m4_competition_repo.sql:14–18 (`repo_url`, `default_branch`, `local_clone_path`, `competition_policy jsonb DEFAULT '{}'`).
   - `experiments`, `experiment_runs`, `submissions` tables — supabase/migrations/0004_m4_competition_repo.sql:23–109; `submissions.public_lb_score numeric(10,6)` is Kaggle-specific (no Devpost analog).
   - `.kca/permissions/<profile>.yaml` files — loaded by tools/kca/agent/permission_policy.py:83–88 (`path = root / f"{profile}.yaml"`); profile name comes from the bound skill (tools/kca/agent/permission_policy.py:91–100 `resolve_for_skill`).
   - `.env.<owner>` per-Kaggle-owner dotenv — tools/legacy/kkr.py:541; carries the legacy multi-account secret partitioning that the current tools/kca/kg.py does NOT preserve.
   - `.kkr/` run root (legacy only) — tools/legacy/kkr.py:30 (`DEFAULT_RUN_ROOT = Path(".kkr")`); the kca-side equivalent is `runs/<slug>/<run_id>/` (docs/milestones/m12/loop-prompts.md:344, M12-T006 scope).
   - `manifest.json` / `state.json` / `kkr_*.json` per-run files — tools/legacy/kkr.py:41–47; the kca-side equivalent is `experiment_runs.artifact_paths` jsonb (supabase/migrations/0004_m4_competition_repo.sql:60–61).

6. config_dimensions:
   - `competitions.competition_policy` jsonb = `{}` default — supabase/migrations/0004_m4_competition_repo.sql:18; per-competition override of ADR-0006 default gates.
   - Per-job `JobPolicy.approval_gates` dict — src/worker/_types.py:18–29; tightens but cannot loosen competition_policy per docs/adr/0006-configurable-approval-gates.md:65–73.
   - `JobPolicy.policy_profile` (default: `"default"`) and `JobPolicy.mode` (default: `"default"`) — src/worker/_types.py:35–36; the resolver routes on (operation, mode) → allow/ask/deny.
   - `_GATE_ENV = "KCA_ALLOW_REMOTE"` emergency override — tools/kca/kg.py:17, 56 (`os.environ.get(_GATE_ENV) == "1"`); single boolean for all Kaggle remote ops.
   - Skill front-matter `approval_policy` — drives `load_policy(profile, …)` in tools/kca/agent/permission_policy.py:97–99.
   - `.kca/permissions/<profile>.yaml` `default_decision` ∈ {allow, ask, deny} — tools/kca/agent/permission_policy.py:13 (`DECISIONS = {"allow", "ask", "deny"}`); `allowed_in_modes` whitelist per record.
   - Legacy: `_envs:` mapping in `kkr.yaml` → per-Kaggle-owner `.env.<owner>` path — tools/legacy/kkr.py:495–520, tools/legacy/kkr.yaml omits an `_envs` block today so the default-per-owner `.env.harrysun2006` / `.env.firefly2006` would be used implicitly.
   - Default clone path template — tools/kca/competition.py:38–39 (`_default_clone_path`); Kaggle-prefixed.

7. features_to_preserve:
   - ADR-0006 four-level policy hierarchy (per-job → competition → project → platform defaults) — why: existing test coverage and live regression (M9 / M10); evidence: docs/adr/0006-configurable-approval-gates.md:100–108.
   - `default_decision` semantics ∈ {allow, ask, deny} — why: `DECISIONS` set is referenced by every existing profile; evidence: tools/kca/agent/permission_policy.py:13.
   - `KCA_ALLOW_REMOTE` env-override path — why: CI/emergency override is documented in ADR-0006:90–94; removing it would break headless flows.
   - Per-competition `competition_policy` jsonb override surface — why: ADR-0006 §"Per-competition override" + supabase/migrations/0004_m4_competition_repo.sql:18; existing Kaggle rows carry this.
   - Repo-per-competition convention (ADR-0009) — why: M9 and M10 worker lifecycle depends on `local_clone_path` + git-worktree; evidence: docs/adr/0009-competition-repo-strategy.md:113–141.
   - `experiment_runs.metrics` jsonb + `experiment_runs.artifact_paths` jsonb — why: M9 / M10 record metric_name='cv_accuracy' or similar through this surface, M12 will record `metric_name='checklist_completion'`; evidence: supabase/migrations/0004_m4_competition_repo.sql:60–61, docs/milestones/m12/loop-prompts.md:367–369.
   - `submissions.public_lb_score numeric(10,6)` nullable column — why: M9-T004 wrote a real value here; Devpost submissions will leave it NULL; evidence: supabase/migrations/0004_m4_competition_repo.sql:91 (already NULL-able).
   - audit_required flag on the permission profile — why: enforces `agent_tool_audit` writes; evidence: .kca/permissions/default.yaml:8, 19; tools/kca/agent/permission_policy.py:74.

8. features_to_deprecate:
   - The legacy `.env.<owner>` partitioning convention (tools/legacy/kkr.py:541) is NOT inherited by tools/kca/kg.py and SHOULD NOT be re-introduced in M12 unless a deliberate ADR follow-up adopts it — reason: today's single-Kaggle-account `KAGGLE_USERNAME` / `KAGGLE_KEY` env is sufficient for M9 / M10; multi-Kaggle-account work is out of M12 scope (docs/tasks/m12/M12-T001-discovery-debate-gate.md:81–82 "M12 ships read-only team membership only").
   - The `_GATE_ENV = "KCA_ALLOW_REMOTE"` single-boolean override (tools/kca/kg.py:17) is *not* deprecated by M12 but should be flagged: a `competition_type='devpost'` row would set the same boolean to allow a Devpost submit, which conflates two surfaces. Recommend the M12-T002 refactor keep `_GATE_ENV` Kaggle-only and add a sibling `KCA_ALLOW_DEVPOST_SUBMIT` (or scope the env to (operation, type) pairs).
   - `competitions.competition_policy` jsonb's untyped key surface (supabase/migrations/0004_m4_competition_repo.sql:18) is a foot-gun once non-Kaggle types exist — reason: a Devpost row carrying `approval_gates.kaggle_submit: true` is meaningless but valid JSON; recommend the policy-resolver in M12-T002 type-check keys against the competition_type.

9. questions_for_skeptic:
   - Does M12 commit to a single `competition_type` enum value for Devpost (`'devpost'`) or two values that distinguish hackathon-format Devpost from generic Devpost (`'devpost'` + `'hackathon_devpost'`)? — triggered by: docs/milestones/m12/loop-prompts.md:204 (both literals appear) and docs/tasks/m12/M12-T001-discovery-debate-gate.md:81 (the enum ships both).
   - Should the per-competition `competition_policy` jsonb be migrated to a typed `competition_type_policy` jsonb shape, or left free-form? — triggered by: supabase/migrations/0004_m4_competition_repo.sql:18 (`DEFAULT '{}'`) vs the M12 need for `devpost_submit` / `demo_upload` / `team_invite` keys.
   - Does the team-scoped operation rule (which gates a non-owner team member can trigger) need to land in M12 or is "all gates owner-only for now" acceptable? — triggered by: docs/tasks/m12/M12-T001-discovery-debate-gate.md:88–92 (the task spec already offers the owner-only default).
   - Does the policy resolver fall back to the `default` profile when no type-specific profile exists, or does it refuse to start the run? — triggered by: tools/kca/agent/permission_policy.py:83–85 (`if not path.is_file(): raise FileNotFoundError`).
   - Is `ctf` exclusively for M11 (no M12-T002 code paths) or does M12 also seed a `default_decision: deny` for unknown CTF ops? — triggered by: docs/milestones/m12/loop-prompts.md:80–82 (the enum value ships but no CTF code) vs docs/tasks/m12/M12-T001-discovery-debate-gate.md:82–83 (CTF non-negotiable for schema reuse).
   - Should `kaggle_submit` / `kernel_push` profile entries be moved to a `kaggle-runner.yaml` profile and the existing `competition-runner.yaml` be renamed, OR should the existing names stay (additive)? — triggered by: docs/milestones/m12/loop-prompts.md:116 ("Renaming any of the existing Kaggle-specific surfaces" is out of scope) vs the cleanliness of per-type profiles.

10. parity_tests:
    - test_m9_e2e.py-parity for `competition_type='kaggle'` — covers: an existing Spaceship-Titanic row still resolves `kaggle_submit: ask` under the M12 resolver (regression); fixture: tests/test_m9_e2e.py + a new `tests/test_m12_competition_type_kaggle_parity.py` reading the same fixture.
    - test_m10 kernel_push parity for `competition_type='kaggle'` — covers: the resolver routes `kernel_push` identically pre- and post-migration; fixture: tests/test_m10_smoke.py if present, else the M10 closeout-recorded row.
    - permission_policy.resolve parity — covers: `PermissionPolicy.resolve("kaggle_submit", mode="default")` returns `"ask"` whether or not a `competition_type` is bound (regression); fixture: tools/kca/agent/tests (existing).
    - competition_policy jsonb backwards-compat — covers: existing Kaggle rows with `competition_policy={}` continue to resolve via ADR-0006 defaults; fixture: a DB-gated test that inserts a `competition_type='kaggle'` row with empty jsonb and asserts gate decisions match pre-migration.
    - new `competition_type='devpost'` smoke — covers: a Devpost row resolves `devpost_submit: ask`, falls back to default profile if hackathon-runner.yaml not yet shipped, and writes `agent_tool_audit`; fixture: tests/test_m12_smoke.py (planned in M12-T008).
    - audit_required propagation — covers: a `devpost_submit` decision with `audit_required: true` writes an `agent_tool_audit` row (M8 contract); fixture: services/decision_api/tests pattern.

> Output MUST cover all 10 sections; ≥5 distinct legacy behavior
> dimensions must be named explicitly, including any multi-account /
> owner / env mapping the legacy artefact encodes.
