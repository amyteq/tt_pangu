# Notification / HITL channel — Telegram push + GitHub record

Decision: [#197](https://github.com/amyteq/tt_pangu/issues/197) (owner
[comment](https://github.com/amyteq/tt_pangu/issues/197#issuecomment-5679417228)) —
**the Telegram bot is the primary channel, GitHub is the secondary channel and
the system of record.** Telegram carries the push and the buttons; the GitHub
issue comment carries the attributable, timestamped decision record. If Telegram
is down the record still exists; if the record cannot be written we do not
pretend a decision was made.

## Pieces (all source-controlled)

| File | Role |
|---|---|
| `.kca/notify.yml` | channels, recipients, per-level routing, quiet hours, daily budget. **Names env vars; holds no secret.** |
| `tools/kca/notify.py` | `kca notify doctor / send / decision` + the reply contract (`parse_decision_reply`, `resolve_reply`) |
| `tests/test_notify.py` | format, reply determinism, expiry, suppression, redaction |
| `env.example` | the two `TELEGRAM_*` variable names, documented and empty |

Secret **values** live only in the env file named by `secrets_file` in
`.kca/notify.yml` (default: the home-directory `.env`, outside the repo). The
notify process loads `TELEGRAM_*` keys from it and nothing else; no `kca`
command ever prints a token or a chat id.

## Prerequisites

Two of the steps can only be done by a human inside the Telegram app — a bot
cannot create itself, and a bot cannot open a conversation with you.

### Step 1 (human, ~2 min) — create the bot

1. In Telegram, open a chat with **@BotFather** and send `/newbot`.
2. Display name: anything, e.g. `KCA Ops`.
3. Username: must end in `bot` and be globally unique, e.g. `kca_ttpangu_bot`.
4. BotFather replies with a token shaped `8123456789:AA...`. **That token is the
   bot.** Do not paste it into an issue, a PR, a log or a chat with an agent.

Optional hardening, same chat:

* `/setprivacy` → **Enable** (in groups the bot only sees `/`-commands).
* `/setdescription`, `/setuserpic` — cosmetic.

### Step 2 (human, ~10 s) — open the conversation

Open your new bot's chat and press **Start** (sends `/start`). Telegram bots
cannot message a user who has never messaged them, so nothing works until this
is done.

### Step 3 — find the chat id

Either message **@userinfobot** (it replies with your numeric id), or, with the
token in hand:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[].message.chat.id'
```

The id is a number like `123456789` (negative for groups). It is not secret in
the way the token is, but it is not published either.

### Step 4 — store both values

Add to the env file named by `secrets_file` in `.kca/notify.yml` (default: the
home-directory `.env`, **not** the repo):

```
TELEGRAM_BOT_TOKEN=8123456789:AA...
TELEGRAM_CHAT_ID_HARRY=123456789
```

> The Claude Code guard hook (`.claude/hooks/guard_tool.py:56`) denies the agent
> reading that home env file directly, by design — it also holds unrelated
> credentials. `kca notify` reads it inside its own process and loads only
> `TELEGRAM_*` keys, so the agent can *use* the channel without ever seeing the
> file. That is deliberate; do not work around it by printing the file.

### Step 5 — verify

```bash
kca notify doctor            # presence + live getMe; prints no secret value
kca notify doctor --offline  # skip the network round-trip
```

Every check must be `ok: true`. `gh auth` is checked too, because the record leg
shells out to `gh issue comment`. (Run this outside the agent's command sandbox —
inside it, `gh` cannot read its own credential file and reports "not logged in".)

### Step 6 — smoke-test the two legs

```bash
# 1. Render without sending (works even before the token exists).
kca notify send --level info --title "hello" --body "channel smoke test" --dry-run

# 2. Real push to Telegram.
kca notify send --level info --title "hello" --body "channel smoke test"

# 3. A full decision request: GitHub record + Telegram card with buttons.
kca notify decision \
  --decision-id d-$(date +%Y-%m-%d)-001 \
  --competition nemo-equation \
  --summary "Promote rules24.py (LB 0.951) as tomorrow's submission." \
  --option "promote=Promote rules24" \
  --option "hold=Hold, keep v17" \
  --expires-at "$(date -d '+18 hours' -Iseconds)" \
  --issue 197 --account harrysun2006 --dry-run   # drop --dry-run to send
```

No system packages are needed: `requests` and `PyYAML` are already project
dependencies, and the daemon in phase 1b runs as a **systemd user unit** (same
pattern as [`worklogs-systemd-timer.md`](./worklogs-systemd-timer.md)) — no
root, no `pacman`.

## How a decision flows

1. The agent calls `kca notify decision …`.
2. The **GitHub comment** is written first — `decision_id`, competition, plan
   summary, `plan_hash`, options, expiry, plus a machine-readable YAML block.
3. The **Telegram card** goes out with one button per option
   (`callback_data = kca:<decision_id>:<option_id>`) and a link to the record.
4. The human taps a button, **or** comments on the issue:

   ```
   /decide <decision_id> <option_id>
   ```

   Anything after the option id is recorded as context but is never parsed as
   the answer. Prose alone — "yes", "go ahead", "A" — deliberately does **not**
   parse: the answer is an option id or it is not an answer.
5. `resolve_reply()` returns `ANSWERED` / `INVALID_OPTION` /
   `MISMATCHED_DECISION` / `EXPIRED` / `WAIT_HUMAN`. **Only `ANSWERED` sets
   `approved: true`.** Past `expires_at` a request lapses to `EXPIRED` — silence
   is never consent, and a late tap does not revive it.

## Traffic rules (enforced in code, not by convention)

| Level | Channels | Quiet hours | Suppression |
|---|---|---|---|
| `gate` | GitHub + Telegram | **bypass** — work is blocked | never deduped, never rate-limited |
| `digest` | Telegram | deferred to the next window | deduped 12 h; counts against the daily budget |
| `info` | Telegram | deferred | deduped 3 h; counts against the daily budget |

* Quiet hours: 22:00–08:00 `Australia/Melbourne` (`.kca/notify.yml`).
* Routine budget: **2 pushes/day** — the #185 §18 intervention-cost criterion.
  A suppressed send is a *success* (`status: deduped | deferred |
  rate_limited`), not an error; `--force` overrides all three.
* Every transmitted title/body/summary passes through `redact()` (the shared
  `stuck.redact_escalation_payload` filter plus a bot-token pattern), so a DSN,
  API key, flag or bot token cannot reach a notification body (#185 §9).

## Not built yet (phase 1b)

`kca notify` only **sends**. Nothing yet consumes `getUpdates` / button taps, so
today an answer arrives by commenting `/decide …` on the issue. The poller —
a systemd user unit that reads updates, ignores chat ids outside
`.kca/notify.yml`, and writes the answer back into the issue as the record — is
the follow-up. The reply contract above is already fixed and tested, so the
poller is transport work only, and the multi-account requirement (#197 req 4)
is already modelled: one bot, `chat_id → recipient → accounts`.
