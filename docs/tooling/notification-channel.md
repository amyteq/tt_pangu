# Notification / HITL channel — Telegram push + GitHub record

Decision: [#197](https://github.com/amyteq/tt_pangu/issues/197) (owner [comment](https://github.com/amyteq/tt_pangu/issues/197#issuecomment-5679417228)) — **the Telegram bot is the primary channel, GitHub is the secondary channel and the system of record.** Telegram carries the push; the GitHub issue comment carries the attributable, timestamped decision record, and is where the answer is given. If Telegram is down the record still exists; if the record cannot be written we do not pretend a decision was made.

Bot-per-agent-entry follows [discussion #187](https://github.com/amyteq/tt_pangu/discussions/187) §3, which owns the *interactive* half of this story (the official Claude Code Telegram channel plugin). See [Two channels, one bot fleet](#two-channels-one-bot-fleet) for how the two fit together.

## Pieces (all source-controlled)

| File | Role |
|---|---|
| `.kca/notify.yml` | bots, recipients, per-level routing, quiet hours, daily budget. **Names env vars; holds no secret.** |
| `tools/kca/notify.py` | `kca notify doctor / send / decision` + the reply contract (`parse_decision_reply`, `resolve_reply`) |
| `scripts/agent_notify.py` | adapter so a Claude Code hook or a Codex `notify` turn can push through the same channel |
| `tests/test_notify.py`, `tests/test_agent_notify.py` | format, reply determinism, expiry, suppression, redaction, both harness payload shapes |
| `env.example` | the `TELEGRAM_*` variable names, documented and empty |

Secret **values** live only in the env file named by `secrets_file` in `.kca/notify.yml` (default: the home-directory `.env`, outside the repo). The notify process loads `TELEGRAM_*` keys from it and nothing else; no `kca` command ever prints a token or a chat id.

## The bots

Two bots are configured, one per agent entry, because **a bot token has exactly one active receiving process** (#187 §3) — two Claude Code entries cannot share one. *Sending* is unaffected, so `kca notify` can push through a bot whose update stream a Channels plugin is holding.

| key in `.kca/notify.yml` | env var | bot | intended entry |
|---|---|---|---|
| `bot1` (`default_bot`) | `TELEGRAM_BOT1_TOKEN` | `@ayla_claude1_bot` | Claude Code account 1; also every `kca notify` / KCA push |
| `bot2` | `TELEGRAM_BOT2_TOKEN` | `@ayla_harry_bot` | Claude Code account 2 / Codex |

Recipient `harry` → `TELEGRAM_CHAT_ID_ME`, deciding for accounts `harrysun2006` and `firefly2006`. Pick a non-default bot per call with `--bot bot2`, or pin one to a recipient with `bot:` in the config.

## Setup

Steps 1–3 can only be done by a human in the Telegram app — a bot cannot create itself, and Telegram forbids a bot from opening a conversation with a user who has never messaged it. **They are already done for the two bots above**; repeat them only when adding an entry.

1. **Create the bot**: chat with **@BotFather** → `/newbot` → display name (e.g. `Ayla 1 · Kaggle`) → username ending in `bot`. BotFather replies with a token shaped `8123456789:AA…`. **That token is the bot — never paste it into an issue, PR, log, or a chat with an agent.** Optional: `/setprivacy` → Enable.
2. **Press Start** in the new bot's chat. Nothing can be delivered before this.
3. **Find the chat id**: message **@userinfobot**, or use `getUpdates` below.
4. **Store the values** in the env file named by `secrets_file`:
   ```
   TELEGRAM_BOT1_TOKEN=8123456789:AA...
   TELEGRAM_BOT2_TOKEN=8987654321:AA...
   TELEGRAM_CHAT_ID_ME=123456789
   ```
   > The Claude Code guard hook (`.claude/hooks/guard_tool.py:56`) denies the agent reading that file directly, by design — it also holds unrelated credentials. `kca notify` reads it inside its own process and loads only `TELEGRAM_*` keys, so the agent can *use* the channel without ever seeing the file. Do not work around that by printing the file.
5. **Verify**: `kca notify doctor` — every check must be `ok: true`. It prints each bot's `@username` (from `getMe`) and whether each token/chat id is set, never a value. Run it outside the agent's command sandbox; inside it, `gh` cannot read its own credential file and reports "not logged in".

## Verifying with `curl`

Everything `doctor` does is plain Bot API, so you can check by hand. Keep the token out of your shell history — read it from the env file instead of typing it:

```bash
set +o history                         # bash; zsh: setopt HIST_IGNORE_SPACE
export TG=$(grep -m1 '^TELEGRAM_BOT1_TOKEN=' ~/.env | cut -d= -f2-)

# 1. Is the token valid, and which bot is it?  -> {"ok":true,"result":{"username":"ayla_claude1_bot",...}}
curl -s "https://api.telegram.org/bot$TG/getMe" | jq '.result.username'

# 2. What is my chat id?  (send the bot a message first; empty result = you never pressed Start)
curl -s "https://api.telegram.org/bot$TG/getUpdates" | jq '.result[].message.chat.id'

# 3. Can it reach me?
curl -s -X POST "https://api.telegram.org/bot$TG/sendMessage" \
  -d chat_id="$TELEGRAM_CHAT_ID_ME" -d text="curl check" | jq '.ok'

# 4. Is something else already consuming this bot's updates?  (a Channels plugin, a poller)
curl -s "https://api.telegram.org/bot$TG/getWebhookInfo" | jq '{url, pending_update_count}'

unset TG; set -o history
```

Failure modes worth recognising: `401 Unauthorized` = wrong/revoked token; `400 chat not found` = wrong chat id or Start never pressed; `409 Conflict` on `getUpdates` = **another process is already long-polling this token** (see #187 §3 — that is the one-receiver rule biting).

## Turning it on inside Claude Code and Codex

`scripts/agent_notify.py` adapts each harness's event to a `kca notify` push. It exits 0 no matter what, so a notification failure can never break the turn it is reporting on — including on a payload that is valid JSON of an unexpected shape.

### Claude Code (verified against 2.1.273)

The harness pipes a hook JSON object on stdin. Add to `.claude/settings.json` (or `~/.claude/settings.json` for every project):

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/agent_notify.py --source claude --bot bot1 --label 'ayla1 · tt_pangu'"
          }
        ]
      }
    ],
    "StopFailure": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/agent_notify.py --source claude --bot bot1 --label 'ayla1 · tt_pangu'"
          }
        ]
      }
    ]
  }
}
```

`Notification` (the session is waiting on you — a permission prompt or an idle prompt) and `StopFailure` (the turn ended in an API error) map to level `attention`: they bypass quiet hours and are never rate-limited, because you are the thing that is blocking.

`Stop` is deliberately **not** wired above. It fires at the end of *every* turn, and #187 §4 warns against reporting each `Stop` as "task complete". Add it only with a level you are happy to have deduped and capped: `… --source claude --level info`.

Use the second account's entry by pointing its settings at `--bot bot2`.

### Codex (verified against codex-cli 0.154.0)

Codex execs a program with one argv holding the event JSON. In `~/.codex/config.toml`:

```toml
notify = [
  "/home/harry/test/tt_pangu/scripts/agent_notify.py",
  "--source", "codex",
  "--bot", "bot2",
  "--label", "codex · tt_pangu",
]
```

Codex fires `agent-turn-complete` (payload: `type`, `thread-id`, `turn-id`, `cwd`, `input-messages`, `last-assistant-message`), which maps to level `info` — routine traffic, so it is deduped for 3 h, deferred out of quiet hours, and counted against the daily budget. Override with `--level attention` if you want every Codex turn to break through, but expect the volume.

**Session text is opt-in.** By default a push carries metadata only: the event, the label (the cwd basename when you pass no `--label`), the session/thread id, and — on the Claude side — the harness's own status line, the one it writes itself ("Claude needs your permission to use Bash"). Your prompt and the assistant's reply are forwarded only when you add `--content` (or export `KCA_NOTIFY_CONTENT=1`); `--no-content` is still accepted as a no-op so an older hook line keeps running.

That default is not timidity about a private chat: `tools/kca/notify.py` states as a binding invariant that no private competition payload leaves in a notification, and redaction masks credential *shapes*, not "text that might be private" — arbitrary competition data has no shape to match on. Everything the adapters do build is redacted and length-bounded before it leaves the process. See [What can never reach a notification](#what-can-never-reach-a-notification).

Check either wiring without touching Telegram:

```bash
echo '{"hook_event_name":"Notification","message":"test","session_id":"abc","cwd":"'$PWD'"}' \
  | scripts/agent_notify.py --source claude --dry-run
scripts/agent_notify.py --source codex --dry-run \
  '{"type":"agent-turn-complete","last-assistant-message":"done","cwd":"'$PWD'"}'
```

## Two channels, one bot fleet

| | `kca notify` (#197, this doc) | Claude Code Telegram channel (#187) |
|---|---|---|
| Direction | outbound push only | two-way chat into a live session |
| Needs a session running | no — cron, KCA, CI, a hook | yes, and it must stay online |
| Writes the GitHub decision record | **yes** | no |
| Buttons | one link to the record — nothing tappable to answer with (option B is deferred) | tool-approval relay only |
| Uses a bot's update stream | no (send-only) | **yes — exclusively** |

They coexist because only the plugin consumes updates. Both can send through the same bot. The consequence for **phase 1b** (the reply poller) is concrete: a poller calling `getUpdates` on a token a Channels plugin already holds will get `409 Conflict`, so it must either use a third, dedicated bot or read replies from the GitHub record instead.

## How a decision flows

1. The agent calls `kca notify decision …`.
2. The **GitHub comment** is written first — `decision_id`, competition, plan summary, `plan_hash`, options, expiry, plus a machine-readable YAML block. Both legs have to succeed: if the record cannot be written the command reports `partial` and exits non-zero, even when the Telegram push landed.
3. The **Telegram card** goes out: a compact mirror with the `/decide` line for every option and a link button to the record. It is deliberately **read-only** — see [No buttons in phase 1a](#no-buttons-in-phase-1a).
4. The human comments on the issue:

   ```
   /decide <decision_id> <option_id>
   ```

   Anything after the option id is recorded as context but is never parsed as the answer. Prose alone — "yes", "go ahead", "A" — deliberately does **not** parse: the answer is an option id or it is not an answer. A `decision_id` or option id the parser could not read is rejected when the decision is *created*, so a published gate is always answerable.
5. `resolve_reply()` returns `ANSWERED` / `INVALID_OPTION` / `MISMATCHED_DECISION` / `EXPIRED` / `WAIT_HUMAN`. **Only `ANSWERED` sets `approved: true`.** Past `expires_at` a request lapses to `EXPIRED` — silence is never consent, and a late answer does not revive it.

### No buttons in phase 1a

The decision card carries one button, and it is a link to the GitHub record. There is deliberately no tappable button per option: nothing consumes `getUpdates` or callback queries yet, so a tap would resolve nothing while looking exactly like an answer — the human would believe the gate was handled and the decision would block until it expired. `callback_data` (`kca:<decision_id>:<option_id>`) is still fixed, and every id is validated against its 64-byte limit at creation, so a decision opened today stays answerable by a tap once the phase-1b poller exists.

## Traffic rules (enforced in code, not by convention)

| Level | Channels | Quiet hours | Suppression |
|---|---|---|---|
| `gate` | GitHub + Telegram | **bypass** — a decision blocks work | never deduped, never capped |
| `attention` | Telegram | **bypass** — a session is stuck on you | deduped 5 min, never capped |
| `digest` | Telegram | deferred to the next window | deduped 12 h, **and held while unchanged**; counts against the daily budget |
| `info` | Telegram | deferred | deduped 3 h; counts against the daily budget |

* Quiet hours: 22:00–08:00 `Australia/Melbourne` (`.kca/notify.yml`).
* Routine budget: **2 pushes/day** — the #185 §18 intervention-cost criterion. It applies to `digest`/`info` only. A suppressed send is a *success* (`status: deduped | deferred | rate_limited`), not an error; `--force` overrides all three.
* `suppress_unchanged` (set on `digest`) is time-independent, unlike `dedupe_minutes`: a digest saying exactly what the last digest said is held back however long ago that was, which is what "daily digest suppressed when nothing changed" needs — a 24 h repeat always falls outside a 12 h window.
* Statuses: `sent` means **every** configured channel took the message. One failed leg is `partial`, which is a failure: a `gate` whose GitHub record failed is not a decision that was filed. A channel that is disabled in `.kca/notify.yml` is a successful skip for a push-only level, but **not** for `gate`, whose contract is *both* legs: a disabled GitHub channel fails the gate rather than reporting `sent` with nothing filed, and a disabled Telegram channel fails it rather than reporting `sent` for a block nobody was told about. `kca notify doctor` / config loading reject either configuration up front. Leaving a leg *off* `levels.gate.channels` altogether — no record channel, or no push channel — is the same non-delivery and fails the same way: the guarantee holds however the config omits a leg, not only when a listed channel is disabled.
* Exit codes: `0` sent, `2` suppressed by policy, `1` the send failed or only partly landed.

### The send ledger

Dedupe and the daily cap are backed by a JSONL ledger under `state_dir` (`.agent/notify/sent.jsonl`, gitignored).

* It is **one ledger per repository, not per worktree**: a relative `state_dir` resolves against the primary checkout, because the budget protects a human's phone rather than a directory.
* The read → decide → send → append sequence runs under a lock on `.agent/notify/ledger.lock`, so two agents cannot both spend the last of the budget. It is a `flock` where `fcntl` exists and an exclusive-create (`O_CREAT|O_EXCL`) where it does not, so the fail-closed rule below is never skipped on the platform that needs it most; `kca notify doctor` reports which mechanism is in use. A lock file left untouched for longer than a legitimate hold can take is reclaimed once, but in the fallback reclaiming is never acquiring: the abandoned file is claimed by an atomic rename and deleted only if it still carries the token that was observed stale, so a contender cannot delete the fresh lock another contender just created, and the lock is only ever established by winning the exclusive create. The lock is held across the transports, so the wait for it is derived from their timeouts (`telegram.timeout_s` + the 90 s `gh` timeout + a margin, overridable with `limits.lock_wait_s`) — a shorter ceiling would time out on an ordinary slow send rather than on a wedged holder.
* If the lock cannot be taken in that time the level decides what happens: a `gate` or an `attention` is sent unserialised (`serialized: false` in the result) rather than dropped, while a routine `digest`/`info` **fails closed** with `deferred` and a `retry_after` — spending the daily budget against a count it could not read is how two processes both take the last slot.
* `--dry-run` takes no lock and creates nothing — not the ledger, not `ledger.lock`, not the state directory: it appends nothing, so it has nothing to serialise, and it reports `serialized: false`.
* A suppressed outcome is recorded once per hour per message, not once per hook invocation, and the file is compacted to its newest entries once it crosses ~500 KB. What compaction keeps has to answer both questions the policy asks of the ledger, so two classes of entry are pinned in place however old they are: the last `sent` entry per level (the state `suppress_unchanged` compares against) and the live day's routine `sent` entries up to the daily cap (the budget counts every one of them, not just the newest per level). Only a writer holding the lock compacts — an unserialised `gate` appends its line and leaves the trim to the next serialised send, because a read/rewrite/`os.replace` from a stale snapshot would discard whatever landed in between. A line that is not a JSON object is skipped, so a corrupted ledger cannot take the channel — or `doctor` — down.

### What can never reach a notification

Every transmitted title, body, summary, option label and link goes through `redact()` and is clipped (200 chars for a title, 2000 for a body, 120 per option label, 10 option lines on a card). A rendered decision card is additionally held under Telegram's 4096-character limit without ever slicing the assembled HTML: each field is bounded *after* escaping (`&` becomes `&amp;`, so escaping expands), then the card re-renders with fewer options, then whole rendered lines are dropped. A cut inside `<code>…</code>` would make Telegram reject the message and lose the gate entirely, so a long label degrades the card instead of failing the push. `redact()` masks, in order:

* credential shapes — Telegram bot tokens, `sk-…` / `sk-proj-…` / `sk-ant-…` keys, GitHub PATs, Google, Slack, Hugging Face and GitLab tokens, JWTs, `Bearer` / `Basic` / `Digest` credentials, PEM private-key blocks;
* an `Authorization:` / `Proxy-Authorization:` line — masked to the end of the line, because the whole value is the credential, scheme included;
* `NAME=value` / `NAME: value` where the name itself says secret (`*TOKEN*`, `*SECRET*`, `*API_KEY*`, `*PASSWORD*`, `*CHAT_ID*`, …) — the name is kept, only the value is masked;
* the literal values *this* config resolves to, so a body quoting our own chat id or bot token cannot echo it back;
* everything the shared `stuck.redact_escalation_payload` filter knows: DSNs, `user:pass@host`, AWS key ids, CTF flags.

It deliberately does **not** mask "anything that looks like a number": a named budget field whose value *is* a count is exempt (`tokens: 1500 remaining`, `max_tokens: 4096`), as are hyphenated names like `sk-learn-baseline`. The exemption needs both halves — an exact field name from a short list and a numeric value — so `TOKENS_SECRET=…`, `API_TOKENS=…` and `max_tokens=sk-live-…` all still mask. The reason for any exemption at all: a redaction that silences a gate or eats the operator's own sentence is a worse outcome than the leak it prevents. `decision_id` and option ids are the one field rendered verbatim (they must round-trip through `/decide`), so a secret-shaped id is rejected at creation instead.

What it therefore does **not** guarantee: private competition data, which has no credential shape. A sentence an agent wrote about the private split would be transmitted as written — which is why the harness adapters do not forward session text at all unless you pass `--content` / `KCA_NOTIFY_CONTENT=1`, and why the only recipient is your own `TELEGRAM_CHAT_ID_ME` chat. `kca notify send --body …` is a deliberate send: what you put in the body is what is transmitted, redaction aside.

## Running it

`kca` is not installed as a console script on HARRY-ARCH, so invoke the module from a checkout:

```bash
python -m tools.kca.kca notify doctor
```

`pip install -e .` would put `kca` on `PATH` (`pyproject.toml` already declares the entry point) — that is independent of this feature.

## Closing the loop: `kca notify poll` (phase 1b)

`kca notify` sends; `kca notify poll` is what finally **receives**. It reads the tracking issue's comments, finds `/decide …` answers, and writes each resolution back into the same issue.

```bash
python -m tools.kca.kca notify poll --issue 197            # resolve what is answered
python -m tools.kca.kca notify poll --issue 197 --dry-run  # report only; writes nothing
```

**Why it reads GitHub and not Telegram.** A bot token has exactly one active receiving process ([#187](https://github.com/amyteq/tt_pangu/discussions/187) §3), and `bot1` / `bot2` are both agent entries, so a poller calling `getUpdates` on either would get `409 Conflict`. Reading the answer off the record needs no third bot, no `@BotFather` step, and no long-running process — the decision recorded in [#219](https://github.com/amyteq/tt_pangu/issues/219) is *A now, B later*. One-tap answering (a receive-only `bot3` consuming `callback_query`) stays a deliberate follow-up, and `callback_data()` is already shipped and validated as its reserved contract.

**It is transport only.** Every judgement about what a reply *means* is still `resolve_reply()`'s, unchanged from phase 1a. The record comment's trailing `yaml` block already **is** the mapping `resolve_reply()` accepts, so the poller keeps no second copy of the decision schema — it reads back exactly what the sender wrote.

### What it does, in order

1. Reads every comment on the issue, oldest first.
2. Finds decision records (first line `<!-- kca-decision:v1 -->`) and parses each one's trailing `yaml` block into `decision_id` / `expires_at` / `options`. A record whose block did not survive the round trip is **ignored**, not guessed at: an unanswerable record is a sending bug, and inventing options here would resolve a decision nobody published.
3. Finds resolutions it wrote earlier (first line `<!-- kca-decision-resolved:v1 -->`). This is the idempotency key, and it deliberately lives **in the issue** rather than in `state_dir` — a gitignored local file would let a second checkout resolve the same decision twice.
4. For every other comment, parses a reply with `parse_decision_reply()`.
5. Checks the answering author's **effective** repository permission and requires `admin` or `write`.
6. Calls `resolve_reply()`. Only `ANSWERED` writes anything.

### Who may answer

The commenter's effective permission is read from the collaborator endpoint:

```bash
gh api repos/amyteq/tt_pangu/collaborators/<login>/permission --jq .permission
```

`authorAssociation` is **not** used and must not be: it reports how GitHub labels a commenter's relationship to the repository, not whether they can write to it — on a user-owned repository a collaborator with full write access still reports `NONE` ([#196](https://github.com/amyteq/tt_pangu/issues/196#issuecomment-5672917107)). A failed lookup returns no permission and therefore does not authorise, because a check that opens up when the network is down is not a check.

### What never resolves a decision

| Input | Outcome |
|---|---|
| The record's own `/decide <decision_id> <option_id>` help line | Nothing. Angle brackets are not legal ids so it cannot parse, and record comments are skipped outright rather than resting on the grammar alone |
| A blockquoted `> /decide …` | Nothing — quoting someone else's answer must not re-trigger it |
| A fenced ` ``` /decide … ``` ` | **Resolves.** Pasting the line from the card inside a fence is a real answer |
| Prose — "yes", "go ahead", a bare "A" | Nothing (`WAIT_HUMAN`) |
| An option that is not on the decision | Nothing (`INVALID_OPTION`) |
| A `decision_id` with no record on the issue, or an answer predating its record | Nothing (`MISMATCHED_DECISION`) |
| An answer after `expires_at` | Nothing (`EXPIRED`) — silence is never consent, and neither is a late reply |
| A second answer to an already-resolved decision | Nothing (`ALREADY_RESOLVED`), within one run and across runs alike |
| An author without `admin` / `write` | Nothing (`UNAUTHORIZED_AUTHOR`) |

### Running it on a timer

The units are source-controlled and mirror the worklogs dump ([`worklogs-systemd-timer.md`](./worklogs-systemd-timer.md)):

| File | Role |
|---|---|
| `scripts/systemd/kca-notify-poll.service` | `Type=oneshot` — reads the thread, writes any resolution, exits. Nothing to supervise, nothing holding a bot's update stream |
| `scripts/systemd/kca-notify-poll.timer` | fires every five minutes (`OnCalendar=*:0/5`), `Persistent=true` so a suspend does not swallow an answer |

Installing them is a human step — the agent ships the units, it does not enable anything:

```bash
cd ~/test/tt_pangu
systemctl --user link "$PWD/scripts/systemd/kca-notify-poll.service"
systemctl --user link "$PWD/scripts/systemd/kca-notify-poll.timer"
systemctl --user daemon-reload
systemctl --user enable --now kca-notify-poll.timer

# Which issue it polls (default 197). Override rather than editing the unit:
systemctl --user edit kca-notify-poll.service   # [Service] Environment=KCA_NOTIFY_POLL_ISSUE=219

systemctl --user list-timers kca-notify-poll.timer   # verify
journalctl --user -u kca-notify-poll.service -n 50   # what it did
```

Linger is already enabled for the worklogs timer, so the poller runs without an active login too.

## Still deferred to option B ([#230](https://github.com/amyteq/tt_pangu/issues/230))

One-tap answering from the Telegram card. It needs a third, receive-only bot (`bot3`) so that nothing contends for `bot1` / `bot2`'s update stream, which in turn needs a human prerequisite only the owner can do: create the bot with @BotFather, press Start, and add `TELEGRAM_BOT3_TOKEN` to `~/.env`. That work must report a `409 Conflict` as a configuration error rather than retrying forever. Until then the card stays a read-only mirror with a link to the record, and the answer is a `/decide` comment.
