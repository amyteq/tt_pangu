# Milestone Loop Protocol

_Shared rules that apply to every milestone Loop Prompt (M0+) unless a
milestone explicitly overrides one._

Each `docs/m*-loop-prompts.md` should reference this file once at the top
rather than duplicating the rules per prompt.

---

## 1. Sequencing

- Loop Prompts within a milestone MUST execute in order.
- Each prompt's **acceptance checks MUST pass** before moving to the next.
- On failure: fix the specific issue and **retry that prompt only**; do
  not skip ahead and do not redo prompts that already passed.

## 2. External systems and side effects

- Do NOT call the **real Anthropic API or Kaggle API** outside of paths
  the milestone explicitly designates as live; default to `--dry-run`.
- Do NOT run real **Kaggle submit / kernel push / dataset upload /
  model upload** unless the milestone explicitly requests it AND a
  human-approval record exists.
- Do NOT change **production Supabase**.

## 3. Database validation

- Use `SUPABASE_DB_URL=postgresql://postgres:s3cr3t@172.21.0.4:5432/postgres`
  — the `supabase-db` container on the local Docker network.
- Container IPs change on `docker compose down/up`; refresh with:
  ```bash
  docker inspect supabase-db \
    --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
  ```
- DB calls and LAN-host calls require `dangerouslyDisableSandbox=true`.
  Cloud LLM calls stay **inside** the sandbox.

## 4. Reporting

- Report **PASS / FAIL / SKIP** inline for each prompt's verification
  step.
- At milestone end, write the milestone's defined **Closeout format**
  (see each milestone's last Loop Prompt for the exact fields).

## 5. Git / GitHub — worktree mode

This project executes each milestone inside a dedicated **git worktree**
branched off `main`.

- **Mid-milestone, mid-prompt:** do not `git commit` or `git push`
  unless the individual task spec explicitly says so. Stage with
  `git add` and surface diffs in the inline report.
- **At milestone end** — once every Loop Prompt has PASSed and the
  milestone's Closeout has been written — Claude Code SHOULD:
  1. `git add` only the files listed in the Closeout's "files changed"
     section (or its equivalent).
  2. `git commit` using either:
     - one squash commit per milestone, OR
     - one commit per Loop Prompt,
     depending on the milestone's preference. The default is **one
     commit per Loop Prompt**, with the milestone's final review as the
     last commit.
  3. `git push` the worktree's branch to the remote.
  4. `gh pr create` against `main` using the milestone's
     `docs/m{N}-final-review.md` as the PR body.

- The following **still require explicit human approval** at any time:
  - `git push --force` (any branch)
  - `gh pr merge` (any PR)
  - any push to `main` directly
  - any `gh label create/edit/delete`, `gh issue edit/comment`,
    `gh pr edit/comment` against issues or PRs **not** owned by this
    milestone

- If the milestone's task spec or scope says
  "do not commit / push / open PRs", that override **wins** — typically
  used for planning-only or evidence-only milestones.

## 6. Secrets and forbidden reads

These are always denied, regardless of milestone:

- `.env*`
- `**/kaggle.json`, `~/.kaggle/kaggle.json`
- `~/.ssh/id_rsa`, `~/.ssh/id_ed25519`, any private key contents
- `~/.aws/**`, `~/.config/gcloud/**`
- `secrets/**`

Shell commands that would surface the above (`cat`, `grep`, `head`,
`tail`, `less`, `more`, file uploads) over these paths are blocked at
the hook layer.

---

## How a milestone references this file

In each Loop Prompt block, instead of repeating the rules above, include
one line near the top:

```
Follow: docs/milestone-loop-protocol.md
```

A milestone's `docs/m{N}-loop-prompts.md` should still spell out:

- the milestone's own scope, non-goals, and task list;
- per-Loop-Prompt read lists, scope, acceptance criteria;
- any **override** of a default in this file (e.g. a planning-only
  milestone overriding the worktree commit/push behavior).
