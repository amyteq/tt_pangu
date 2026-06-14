根据 2026-05-23 的附件，我建议把这次任务改成 **“M8.5 / pre-M9 hardening”**，不要直接叫 M9。原因是当前 CI 不是绿的，且你还要引入 GitHub Issues/PR/labels 作为 human ↔ Claude Code 协作接口；这些都是 **M9 前置治理和稳定性工作**。M9 的 live Kaggle regression 应该等 CI 绿、GitHub issue/label 基础规则落地后再规划。

## 我从附件里看到的关键问题

当前 CI 主要不是业务逻辑错误，而是 **依赖、CLI 注册、pnpm workspace/lockfile 配置**问题。

Python no-db 失败点包括：`nbformat` 缺失导致 `nb to-ipynb`/roundtrip 测试失败，`requests` 缺失导致 research fetch 本地服务测试失败，`yaml` 缺失导致 skill loader 相关测试失败，此外 `kca skill` 没有注册到 CLI/command registry，导致 `kca: error: argument group: invalid choice: 'skill'`；no-db 总结里是 `18 failed, 61 passed, 10 skipped`。 

live-db 失败基本是同一类问题：`nbformat` 缺失、`requests` 缺失、`yaml` 缺失、`skill` command 未注册；live-db 总结里是 `18 failed, 71 passed`。 

UI job 失败点是 `pnpm -C ui install --frozen-lockfile` 报 `ERROR packages field missing or empty`，这通常意味着 repo 根目录存在 `pnpm-workspace.yaml` 但 `packages` 为空/缺失，或 pnpm workspace 配置与 `ui/` 子项目不一致；M8 prompt 原本要求 CI 执行 `pnpm -C ui install --frozen-lockfile → lint → typecheck → build → test`。 

工程实践文档的方向很适合本项目：GitHub 应作为 canonical source of truth，代码、docs、决策、PR、review、issues、evidence 都应该回到 repo 或 GitHub 记录里；AI 只能实现 `ai:ready` 且决策已确认的 issue，未决问题应保持 `decision:needed` / `ai:blocked`。

---

## 关于 `~/.ssh` 从 `.claude/settings.json` 移除

我建议**不要简单地完全放开 Claude 读取 SSH 私钥**。更好的做法是：

1. 从 `.claude/settings.json` 的 sandbox filesystem deny list 中移除 `~/.ssh`，这样 `git push` / `gh pr create` 这类底层命令可以通过 SSH agent 或 OpenSSH 使用 key。
2. 仍然保留 hook 级别的防护：禁止 `cat ~/.ssh/*`、`grep ~/.ssh/*`、读取 `id_rsa` / `id_ed25519` 这类显式 secret exfiltration 行为。当前 `guard_tool.py` 已经会拦截 shell 读取 `.env`、`kaggle.json`、`id_rsa`、`id_ed25519`、`.aws`、`.ssh` 等模式，并且对 `git push`、`gh pr create/merge` 返回 ask。
3. `git push`、`gh pr create`、`gh pr merge` 仍然建议 ask，而不是 silent allow。

你当前 `.claude/settings.json` 同时在 permissions deny 里有 `Read(~/.ssh/**)`，并且在 sandbox filesystem 里 `denyRead`/`denyWrite` 都包含 `~/.ssh`。这会妨碍 GitHub SSH 操作。 建议让 Claude Code 修改为：

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.local)",
      "Read(./.env.development)",
      "Read(./.env.production)",
      "Read(./.env.test)",
      "Read(./kaggle.json)",
      "Read(./.kaggle/kaggle.json)",
      "Read(~/.kaggle/kaggle.json)",
      "Read(./secrets/**)",
      "Read(./**/kaggle.json)",
      "Read(~/.aws/**)",
      "Read(~/.config/gcloud/**)",
      "Edit(./.env*)",
      "Edit(./secrets/**)",
      "Bash(git push --force*)",
      "Bash(rm -rf / *)",
      "Bash(rm -rf ~*)",
      "Bash(sudo*)"
    ],
    "ask": [
      "Bash(git push*)",
      "Bash(gh pr create*)",
      "Bash(gh pr merge*)"
    ]
  },
  "sandbox": {
    "filesystem": {
      "denyRead": ["~/.aws", "~/.config/gcloud"],
      "denyWrite": ["/", "/etc", "/usr", "/var", "~/.aws", "~/.config/gcloud"],
      "allowWrite": [".", "/tmp"]
    }
  }
}
```

重点是：**允许 Git/SSH 工作，但不允许 Claude 直接读取或打印 SSH key 内容。**

---

## 现在 Claude Code 用你的 GitHub 用户，会有什么影响？

有影响，但在当前单人/早期项目阶段可以接受。影响主要是 **审计身份和权限边界**：

* 本地 Claude Code 通过你的 `gh` / git 凭据操作时，issue comment、label change、branch push、PR 都会显示为你的 GitHub 用户。短期方便，长期会混淆“human 决策”和“agent 操作”。
* 如果 Claude Code 能修改 labels、issues、PR comments，那它就是在用你的权限进行远程写操作。工程实践里建议 Claude Code 作为 managed repo execution lane 时必须有 source-of-truth、bounded scope、allowed files、forbidden paths、required tests/evidence、sync-back。
* 你现在的 `claude.yml` 触发条件已经覆盖 issue comment、PR review comment、issues opened/assigned、PR review submitted，并通过 `@claude` 触发；但 workflow 权限目前是 `contents: read`、`pull-requests: read`、`issues: read`、`actions: read`，所以它更像 read/review lane，不适合直接更新 labels/comments，除非你增加权限或用单独 workflow。

我的建议：

* 现在本地继续用你的 GitHub 用户，但要求 Claude Code 在所有远程写入前说明操作，例如 “I will run `gh issue edit #12 --add-label ai:ready`”。
* 新建一个 dedicated machine/bot identity，例如 `kca-claude-bot`，后面专门用于 GitHub Actions、issue triage、label sync、PR closeout check。
* 在 commit message、PR title、issue comment 里统一加前缀，例如 `[ai-agent]`、`[claude-code]`。
* `ai:ready` label 不允许 agent 自行推断；只能在 human 明确评论 “confirmed / approved / ready for AI” 后由 triage agent 添加。这个规则和 details 文件里的 AI pickup rule 一致：issue 必须 open、有 `ai:ready`、决策涉及项必须 `decision:confirmed`、有 acceptance criteria、owner/reviewer，且没有 `ai:blocked`。

---

## 推荐把原任务拆成 3 个 Claude Code work orders

不要给 Claude Code 一个大 prompt 一次做完。推荐顺序：

```text
M8.5-T001: CI repair + dependency / CLI registration fix
M8.5-T002: Engineering practice + GitHub labels/issues/PR interface
M8.5-T003: M9 planning only, after CI green
```

这样符合工程实践里的 loop：Decision/issue → plan → bounded worktree → tests → PR → review → docs/inventory sync-back。

---

# Prompt 1 — M8.5-T001 CI repair

建议先跑这个，**只修 CI，不做 labels/agents/M9**。

```text
/goal Execute M8.5-T001 CI repair for kaggle-code-agent until all CI-equivalent local checks pass or stop after 80 turns and summarize blockers.

Mission:
Repair the current CI failures before any M9 planning. Do not add new product features except what is necessary to restore the M8/M8.5 baseline.

Source of truth:
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones/README.md
- docs/milestones/m8/final-review.md
- .github/workflows/test.yml
- temp/ui-build-lint.log
- temp/no-db-pytest.log
- temp/live-db-pytest.log
- pyproject.toml
- tools/kca/
- tools/legacy/
- tests/
- ui/

Current known failures from CI logs:
1. no-db pytest fails because:
   - ModuleNotFoundError: No module named 'nbformat'
   - ModuleNotFoundError: No module named 'yaml'
   - requests is not installed
   - kca CLI does not recognize the 'skill' command
2. live-db pytest fails with the same root causes.
3. UI job fails at:
   - pnpm -C ui install --frozen-lockfile
   - ERROR packages field missing or empty

Scope:
- Fix Python package/dependency metadata so CI installs all test/runtime dependencies needed by current tests.
- Register or restore the `kca skill` command in the CLI and command registry.
- Fix pnpm workspace / ui install config so `pnpm -C ui install --frozen-lockfile` works in GitHub Actions.
- Keep changes minimal and consistent with the existing project structure.
- Update docs only if needed to reflect changed test/install commands.

Non-goals:
- Do not plan or implement M9 yet.
- Do not run real Kaggle submit/kernel push/dataset upload/model upload.
- Do not change Supabase production or remote DB.
- Do not rewrite the CLI architecture.
- Do not add broad new dependencies unless tests prove they are required.
- Do not remove safety gates for Kaggle submissions.

Allowed files:
- pyproject.toml
- requirements/dev dependency files if present
- tools/kca/**
- tests/**
- ui/package.json
- ui/pnpm-lock.yaml
- pnpm-workspace.yaml
- .github/workflows/test.yml
- docs/testing*.md or README.md only if command docs need updating

Forbidden paths:
- .env*
- secrets/**
- **/kaggle.json
- ~/.kaggle/kaggle.json
- real Kaggle API calls
- production Supabase resources
- M9 planning docs unless CI is green

Implementation guidance:
- Prefer adding missing declared dependencies over skipping tests:
  - PyYAML or equivalent for `import yaml`
  - nbformat for legacy py2nb/nb2py wrappers
  - requests for research_fetch tests, unless the code already intends to use urllib/httpx
- Ensure `kca skill` is registered in both:
  - CLI argparse/subcommand layer
  - command registry expected by tests
- For pnpm:
  - inspect root `pnpm-workspace.yaml`
  - ensure it has a valid packages list such as:
    packages:
      - "ui"
  - do not delete the lockfile unless necessary; regenerate only if required and explain why.

Validation required:
Run these locally and fix until green:
- python -m pytest tests/ services/decision_api/tests -v
- ruff check .
- ruff format --check .
- pnpm -C ui install --frozen-lockfile
- pnpm -C ui lint
- pnpm -C ui typecheck
- pnpm -C ui build
- pnpm -C ui test --run

If live DB is available, also run:
- for f in supabase/migrations/000*.sql; do psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$f"; done
- python -m pytest tests/ services/decision_api/tests -v

Permissions:
- Local file edits and local tests are allowed.
- git status/diff/log/add are allowed.
- Do not run git commit without human approval.
- Do not run git push without human approval.
- Do not create or merge PRs without human approval.
- Do not read or print secrets.

Closeout format:
- Root causes found
- Files changed
- Dependency changes
- kca skill registration changes
- UI/pnpm workspace changes
- Tests run with PASS/FAIL
- Remaining blockers
- Whether it is safe to proceed to M8.5-T002
```

---

# Prompt 2 — M8.5-T002 engineering practice + GitHub interface

这个在 CI 修好后跑。它的重点是 **GitHub Issues/PR/comments/labels 成为 human ↔ Claude Code 的协作接口**，但不做 M9。

```text
/goal Execute M8.5-T002 engineering practice and GitHub interface baseline until acceptance criteria pass or stop after 80 turns and summarize blockers.

Mission:
Integrate the reusable and project-appropriate parts of engineering_practice_summary.md and engineering_practice_details.md into this repository, and add a GitHub Issues/PR/labels interface for human + Claude Code collaboration.

Source of truth:
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones/README.md
- temp/engineering_practice_summary.md
- temp/engineering_practice_details.md
- .github/workflows/claude.yml
- .github/workflows/claude-code-review.yml
- .github/workflows/test.yml
- .claude/settings.json
- .claude/hooks/guard_tool.py
- existing .claude/agents and .claude/skills directories

Current baseline:
- GitHub repo is the canonical source of truth.
- M0-M8 are complete; M9 must not start until CI is green.
- Claude Code is the primary platform-development coding agent.
- Runtime competition code agents are product-internal and separate.
- GitHub issues/PR reviews/comments/labels should become a shared interface between human users and Claude Code.

Scope:
1. Update `.claude/settings.json` so Claude Code can use SSH/GitHub for branch push and PR creation:
   - remove `~/.ssh` from sandbox filesystem denyRead/denyWrite;
   - do not allow direct reading/printing of SSH private keys;
   - keep git push, gh pr create, gh pr merge as ask/approval operations.
2. Keep or strengthen `.claude/hooks/guard_tool.py` so explicit secret reads remain blocked:
   - `.env*`
   - kaggle.json
   - id_rsa/id_ed25519
   - AWS/GCP credentials
   - shell commands like cat/grep/head/tail over secret paths
3. Add project engineering practice docs, but avoid over-documentation:
   - prefer `docs/engineering-practice.md` as a concise project-specific summary;
   - optionally add `docs/github-collaboration.md` if needed;
   - link to details rather than copying huge handbooks.
4. Add recommended labels from engineering_practice_details.md:
   - create `.github/labels.yml` as source of truth;
   - include label name, color, description.
5. Add a safe labels sync mechanism:
   - either `.github/workflows/labels-sync.yml`, or `scripts/sync_labels.py`, or documented `gh label create/edit` commands;
   - label sync is a remote write and must require human approval before running.
6. Add GitHub issue forms:
   - bug.yml
   - drift.yml
   - decision.yml
   - test-gap.yml
   - feature-work.yml
7. Add or update PR template / closeout checklist:
   - tests run
   - docs/inventory impact
   - evidence links
   - schema/RLS/secrets impact
   - remote side effects yes/no
8. Add Claude Code agents/skills for GitHub collaboration:
   - Issue Triage Agent
   - PR Review Follow-up Agent
   - Inventory Drift Auditor
   - Milestone Reviewer
   - Test Coverage Reviewer
   - Release Readiness Agent
   - matching skills where useful, especially GitHub issue triage and PR closeout review.
9. Update AGENTS.md / CLAUDE.md only with concise routing rules:
   - AI implementation may only pick up issues with `ai:ready`;
   - decisions require `decision:confirmed`;
   - unresolved work gets `decision:needed` and `ai:blocked`;
   - issue/label/PR comment writes should cite evidence and acceptance criteria.

Non-goals:
- Do not implement M9.
- Do not run live Kaggle submissions.
- Do not change production Supabase.
- Do not add a complex project management system.
- Do not create huge duplicate docs; keep summaries short and link to source docs.
- Do not silently apply labels to many issues unless explicitly approved.

Required labels:
type:bug
type:drift
type:test-gap
type:decision
type:docs
type:cleanup
type:feature

decision:needed
decision:confirmed

ai:triage
ai:ready
ai:implementing
ai:blocked

priority:P0
priority:P1
priority:P2

area:frontend
area:supabase
area:auth
area:docs
area:testing
area:config
area:inventory
area:release

Suggested additional project-specific labels:
area:kaggle
area:worker
area:agent-sdk
area:github-ops
area:ui
area:ci
area:security
area:ctf
policy:approval-required

GitHub agent rules:
- Issue Triage Agent may read issues/comments and update labels/comments only when the rule is deterministic.
- Issue Triage Agent must not infer decisions from ambiguous comments.
- Implementation Agent may work only when issue has `ai:ready`, required decisions are `decision:confirmed`, and acceptance criteria are clear.
- Milestone Reviewer may create follow-up issues but must not claim readiness without tests/evidence.
- Release Readiness Agent may summarize blockers but must not grant READY.
- Test Coverage Reviewer may create test-gap issues or propose test PRs; implementation requires approval.

Validation required:
- python -m pytest tests/ services/decision_api/tests -v
- ruff check .
- ruff format --check .
- pnpm -C ui install --frozen-lockfile
- pnpm -C ui lint
- pnpm -C ui typecheck
- pnpm -C ui build
- pnpm -C ui test --run
- Validate YAML for:
  - .github/labels.yml
  - .github/ISSUE_TEMPLATE/*.yml
  - .github/workflows/*.yml
- If a labels sync script is added, run it in dry-run mode only.

Permissions:
- Local edits and local tests are allowed.
- GitHub read operations are allowed:
  - gh issue list/view
  - gh pr view
  - gh label list
- GitHub write operations require explicit human approval:
  - gh issue edit/comment
  - gh pr comment/edit
  - gh label create/edit/delete
  - gh pr create/merge
- git commit and git push require explicit human approval.

Closeout format:
- Engineering practice docs updated
- Labels added/defined
- Issue forms added
- PR template/checklist updated
- Agents/skills added or updated
- Settings/hook changes
- Tests run
- Remote writes performed or skipped
- Risks and follow-ups
- Whether it is safe to proceed to M8.5-T003 / M9 planning
```

---

# Prompt 3 — M8.5-T003 M9 planning only

只有 Prompt 1/2 都完成、CI 绿之后再跑。

```text
/goal Execute M8.5-T003 M9 planning only until docs/milestones/m9/loop-prompts.md and related planning docs are ready for human review, or stop after 60 turns and summarize blockers.

Mission:
Plan M9 after CI is green and GitHub collaboration rules are in place. Do not implement M9 code yet.

Read first:
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones/README.md
- docs/milestones/m8/final-review.md
- docs/milestones/m8/handoff.md
- docs/engineering-practice.md
- docs/github-collaboration.md if present
- .github/labels.yml
- .github/ISSUE_TEMPLATE/
- latest docs/adr/
- tools/kca/
- src/worker/
- ui/

M9 baseline:
- M8 follow-up says first M9 task is live Kaggle regression test for Spaceship Titanic under approval.
- Current platform supports UI shell, worker, approval gates, research/browser workflow, model routing, and local Kaggle tooling.
- External side effects must require human approval.

Scope:
- Draft docs/milestones/m9/loop-prompts.md.
- Draft docs/tasks/m9/M9-T000-*.md through M9-T00N if useful.
- Update PROJECT_STATE.md to point to the first M9 task only if not already updated.
- Add or update an ADR only if M9 requires a new architectural decision.

M9 planning should cover:
1. Spaceship Titanic live regression workflow.
2. Kaggle credentials handling without exposing secrets.
3. Competition registration and local clone/workspace setup.
4. Data download policy and checksum/evidence.
5. Baseline run and local validation.
6. Submission file validation.
7. Approval gate before any real Kaggle submission.
8. GitHub issue/PR/label interface for human decisions.
9. CI/evidence requirements before and after submission.
10. Rollback/stop criteria.

Non-goals:
- Do not run real Kaggle submit.
- Do not push kernels.
- Do not upload datasets/models.
- Do not start autonomous competition loops.
- Do not change production Supabase.
- Do not implement M9 code yet.

Validation:
- python -m pytest tests/ services/decision_api/tests -v
- ruff check .
- ruff format --check .
- pnpm -C ui lint
- pnpm -C ui typecheck
- pnpm -C ui build
- pnpm -C ui test --run
- markdown/yaml syntax checks for new docs/workflows if applicable.

Closeout format:
- M9 scope
- M9 non-goals
- M9 task sequence
- Approval gates
- GitHub issue/label workflow
- Required tests/evidence
- Risks
- First implementation prompt
- Human decisions needed before starting M9 implementation
```

---

## 推荐新增/更新的 agents 和 skills

我建议让 Claude Code 在 Prompt 2 里添加这些轻量文件：

```text
.claude/agents/
  github-issue-triage.md
  pr-review-followup.md
  inventory-drift-auditor.md
  milestone-reviewer.md
  test-coverage-reviewer.md
  release-readiness.md

.claude/skills/
  github-issue-triage/SKILL.md
  pr-closeout-review/SKILL.md
  labels-sync/SKILL.md
  milestone-review/SKILL.md
  inventory-drift-audit/SKILL.md
```

每个 agent/skill 都要写清楚 “Must not”。比如：

```text
Issue Triage Agent must not:
- implement code;
- infer decisions from ambiguous comments;
- add ai:ready without clear acceptance criteria and confirmed decisions;
- touch secrets or production infra;
- merge PRs.
```

这正好对应 engineering details 里的 agent split：Inventory Drift Auditor 只扫描并创建/更新 issues，不静默改代码；Issue Triage Agent 只在规则满足时标 ready/blocked；Implementation Planner 先产出 scope/risks/test plan；Implementation Agent 只实现已批准 issue；Milestone Reviewer/Test Coverage Reviewer/Release Readiness Agent 都不能替代 human readiness 决策。

---

## 建议给 Claude Code 的最终合并版启动 prompt

如果你想先让 Claude Code plan，而不是马上执行，可以发这个：

```text
Plan M8.5 pre-M9 hardening. Do not edit files yet.

Read:
- PROJECT_STATE.md
- AGENTS.md
- CLAUDE.md
- docs/milestones/README.md
- docs/milestones/m8/final-review.md
- .github/workflows/test.yml
- .github/workflows/claude.yml
- .github/workflows/claude-code-review.yml
- temp/ui-build-lint.log
- temp/no-db-pytest.log
- temp/live-db-pytest.log
- temp/engineering_practice_summary.md
- temp/engineering_practice_details.md
- .claude/settings.json
- .claude/hooks/guard_tool.py
- pyproject.toml
- tools/kca/
- tests/
- ui/

Mission:
Prepare a plan to fix CI, then integrate engineering practice / GitHub issue-label-PR collaboration, then draft M9 planning only after CI is green.

Return:
1. Root-cause analysis of current CI failures.
2. Proposed sequence: M8.5-T001, M8.5-T002, M8.5-T003.
3. Files likely to change in each task.
4. Risks and approval needs.
5. Exact tests to run.
6. Whether ~/.ssh should be removed from sandbox deny lists while keeping direct secret reads blocked.
7. Proposed agents/skills for GitHub issue/PR/label collaboration.
8. Stop conditions.
9. Ask for approval before editing.

Do not:
- implement M9;
- run real Kaggle submit/kernel push/upload;
- read secrets;
- commit or push;
- modify production Supabase.
```

然后批准它执行 Prompt 1。CI 绿以后再跑 Prompt 2；Prompt 2 合并后再跑 Prompt 3。
