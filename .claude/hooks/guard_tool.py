#!/usr/bin/env python3
"""Claude Code PreToolUse guardrail hook for permissive KCA development.

Policy:
- Allow normal development work without prompts.
- Deny secret access and host-destructive operations.
- Ask only for irreversible or decision-level operations.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def emit(decision: str, reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def normalize_path(value: str) -> str:
    if not value:
        return ""
    return os.path.expanduser(value).replace("\\", "/")


def path_is_protected(path: str) -> bool:
    """Dev-phase carve-out: project .env, .env.local, .env.development and
    ~/.kaggle/kaggle.json are readable so kca / Claude Code can pick up the
    local DSN and Kaggle test credentials without manual handoffs.
    .env.production and .env.test remain protected — these may contain
    production/staging credentials. SSH / AWS / gcloud / gh OAuth token /
    generic secrets/ dir stay protected.

    M11 (ADR-0017): per-event CTF credentials live in ~/.ctf/<slug>.json and
    are intended to be read ONLY from the allow-listed call-site
    `tools/kca/ctf.py::_load_event_credentials`. Direct Read/Edit of paths
    under ~/.ctf/ (and ctf-credentials.json anywhere) is denied at the hook
    layer — the kca CTF flow opens the file via Python `open()` from inside
    the kca process, never via the Claude Code Read/Edit/Write tools.

    M11 follow-up (two-tier credential model — ADR-0017 §"CTFtime platform
    tier"): the CTFtime.org platform account (single account per user;
    e.g., `CTFTIME_USERNAME=flyingfox`) lives in ~/.env and is loaded only
    by `tools/kca/ctf.py::_load_ctftime_credentials`. Direct Read/Edit of
    ~/.env via the Claude Code tools is denied at this hook layer. This is
    distinct from the **project-root** `.env` (./env) which stays readable
    per the dev-phase carve-out for SUPABASE_DB_URL / Kaggle test creds.
    """
    p = normalize_path(path)
    home = normalize_path(os.environ.get("HOME", str(Path.home())))
    home_env = f"{home}/.env" if home else ""
    if home_env and p == home_env:
        # M11 follow-up: ~/.env holds CTFtime platform credentials; deny
        # direct Read/Edit/Write. Allow-listed loader is
        # tools/kca/ctf.py::_load_ctftime_credentials.
        return True
    protected_fragments = [
        "/secrets/",
        "/.ssh/",
        "/.aws/",
        "/.config/gcloud/",
        "/.config/gh/hosts.yml",
        "/.netrc",
        "/id_rsa",
        "/id_ed25519",
        # M11: deny Read/Edit/Write of any path under ~/.ctf/. This catches
        # both ~/.ctf/<slug>.json and arbitrary CTF credential dumps the
        # human may have staged there.
        "/.ctf/",
    ]
    protected_names = {
        ".env.production",
        ".env.test",
        ".netrc",
        "id_rsa",
        "id_ed25519",
        "hosts.yml",
        # M11: explicit per-name guard so a relative path like
        # "ctf-credentials.json" is denied even outside ~/.ctf/.
        "ctf-credentials.json",
    }
    name = Path(p).name
    return name in protected_names or any(fragment in p for fragment in protected_fragments)


def compact(command: str) -> str:
    return " ".join(command.strip().split())


# --- command normalisation (issue #204) --------------------------------------
#
# The deny/ask patterns below match words in the command string, so they only
# recognise the spellings they were written for. Two consequences, both real:
#
# - `gh` accepts a flag between the binary and the subcommand, and runs it the
#   same way: `gh --repo OWNER/REPO issue delete 1` == `gh issue delete 1`. The
#   pattern assumed the two words were adjacent, so the flagged spelling reached
#   no rule at all.
# - Matching the *whole* command string means a heredoc or a quoted message that
#   merely writes *about* a gated verb is refused, although it executes nothing.
#
# Both are handled by normalising the command before matching. Every step here is
# a deletion, never a reordering or a re-quoting, so normalisation can only make
# the matcher see less — it can never fabricate a word sequence that the operator
# did not type.

# gh flags that may legally precede the subcommand. `--repo` / `-R` are the ones
# gh 2.100.0 actually accepts there (verified against repo-scoped commands);
# `--hostname` is included because gh accepts it on `auth` / `api` and a future
# version may widen it. Boolean forms take no value.
GH_LEADING_FLAGS = re.compile(
    r"\bgh(?:\s+(?:--repo|-R|--hostname)(?:=\S+|\s+\S+)|\s+(?:--help|-h|--version))+",
    flags=re.IGNORECASE,
)

# A heredoc opener: `<<TAG`, `<<'TAG'`, `<<"TAG"`, `<<-TAG`.
HEREDOC_START = re.compile(r"<<-?\s*(?P<quote>['\"]?)(?P<tag>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)")

# Programs that execute what they are handed. If any of them appears at a command
# position, heredoc bodies stay in scope: `bash <<EOF ... EOF` and
# `cat <<EOF | bash` really do run their payload.
INTERPRETERS = {
    "ash",
    "bash",
    "csh",
    "dash",
    "env",
    "eval",
    "fish",
    "ksh",
    "node",
    "perl",
    "php",
    "python",
    "python3",
    "ruby",
    "sh",
    "source",
    "xargs",
    "zsh",
}

# A word in command position: start of string, or after a pipe/separator/substitution,
# optionally preceded by VAR=value assignments.
COMMAND_POSITION = re.compile(r"(?:^|[|;&\n]|\$\(|`)\s*(?:\w+=\S+\s+)*(?P<program>[\w./-]+)")

# The literal value of a message-carrying flag. Single quotes never expand; double
# quotes are only accepted when they contain no `$`, backtick or backslash, so a
# payload that could execute something — `--body "$(cat ~/.ssh/id_rsa)"` — is left
# in place and still matched.
LITERAL_MESSAGE_PAYLOAD = re.compile(
    r"(?<![\w-])(?:-m|--message|-b|--body|-t|--title|--notes)(?:\s+|=)(?:'[^']*'|\"[^\"$`\\]*\")"
)


def mentions_interpreter(command: str) -> bool:
    return any(Path(match.group("program")).name in INTERPRETERS for match in COMMAND_POSITION.finditer(command))


def strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc payloads, unless something in the command line would execute them.

    A heredoc written to a file (`cat > note.md <<'EOF' … EOF`) is data. A heredoc
    fed to a shell (`bash <<'EOF' … EOF`, `cat <<'EOF' | bash`) is code, so it is
    left untouched and keeps facing every rule below.
    """
    if "<<" not in command or mentions_interpreter(command):
        return command

    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        opener = HEREDOC_START.search(line)
        if not opener:
            continue
        tag = opener.group("tag")
        while index < len(lines) and lines[index].strip() != tag:
            index += 1
        if index < len(lines):
            kept.append(lines[index])
            index += 1
    return "\n".join(kept)


def normalize_command(command: str) -> str:
    """Canonicalise a command for matching: inert payloads out, gh flag noise out."""
    text = strip_heredoc_bodies(command)
    text = LITERAL_MESSAGE_PAYLOAD.sub(" ", text)
    text = GH_LEADING_FLAGS.sub("gh", text)
    return compact(text)


def bash_decision(command: str) -> tuple[str | None, str | None]:
    c = normalize_command(command)
    lc = c.lower()

    # Hard deny: host-destructive, privilege escalation, secret
    # exfiltration, and permanent-deletion remote writes. Project .env
    # and ~/.kaggle/kaggle.json are intentionally not in the secret list
    # (dev-phase carve-out — see path_is_protected docstring).
    deny_patterns = [
        (r"\bsudo\b", "Refusing sudo from the agent."),
        (r"\bsu\s+", "Refusing su from the agent."),
        (r"\bdoas\b", "Refusing doas from the agent."),
        (
            r"\brm\s+-rf\s+(/|~|\$HOME)(\s|$)",
            "Refusing recursive deletion of root/home.",
        ),
        (
            r"\brm\s+-rf\s+/\S+",
            "Refusing recursive deletion of absolute filesystem paths.",
        ),
        (r"\bchmod\s+777\b", "Refusing chmod 777."),
        (r"\bchown\s+.*\s+(/|~|\$HOME)\b", "Refusing ownership change on broad paths."),
        (r"\bdd\s+.*\bof=/dev/", "Refusing raw disk write."),
        (r"\bmkfs(\.|\s|$)", "Refusing filesystem formatting command."),
        (r"\bshutdown\b|\breboot\b|\bhalt\b", "Refusing host power command."),
        (
            # The flag is legal anywhere in the push, not only straight after it:
            # `git push origin main --force` and `git push --quiet --force origin main`
            # are the same action as `git push --force origin main`.
            r"\bgit\s+push\b[^|;&]*?\s(-f|--force|--force-with-lease)\b",
            "Refusing force push.",
        ),
        (
            r"\bgit\s+push\b[^|;&]*?(--delete\b|\s:\S)",
            "Refusing remote branch deletion (preserve GitHub branch history).",
        ),
        (
            r"\bgh\s+(issue|label|release|repo|secret|webhook|ssh-key|gpg-key|cache|run)\s+delete\b",
            "Refusing permanent GitHub deletion (issues / labels / releases / repo / secrets / webhooks / keys / caches / runs).",
        ),
        (
            r"\bgh\s+extension\s+remove\b",
            "Refusing gh extension removal.",
        ),
        (
            # CLAUDE.md:103 lists this with the permanent-deletion remote writes.
            # The script's own --i-mean-it token is a second line of defence, not
            # this one: a bare --apply must not reach GitHub from the agent.
            r"\bsync_labels\.py\b[^|;&]*?\s--apply\b",
            "Refusing scripts/sync_labels.py --apply (remote label write requires human approval).",
        ),
        (
            r"\bdocker\s+run\b.*\s--privileged\b",
            "Refusing privileged Docker container.",
        ),
        (
            r"\b(cat|less|more|head|tail|grep|rg|awk|sed|xxd|od|strings)\b.*(id_rsa|id_ed25519|\.aws|\.ssh|\.config/gcloud|secrets/|hosts\.yml|\.netrc|\.ctf/|ctf-credentials\.json|(?:~|\$home|/home/[^/\s]+)/\.env(?![.A-Za-z0-9_-]))",
            "Refusing shell read of protected secrets.",
        ),
        (
            r"\b(curl|wget|scp|rsync)\b.*(id_rsa|id_ed25519|\.aws|\.ssh|secrets/|metadata\.google|169\.254\.169\.254|\.ctf/|ctf-credentials\.json|(?:~|\$home|/home/[^/\s]+)/\.env(?![.A-Za-z0-9_-]))",
            "Refusing shell exfiltration/metadata access pattern.",
        ),
        (
            r"\b(psql|sqlite3)\b.*\b(drop\s+database|drop\s+schema)\b",
            "Refusing database/schema drop from the agent.",
        ),
    ]
    for pattern, reason in deny_patterns:
        if re.search(pattern, lc, flags=re.IGNORECASE):
            return "deny", reason

    # Ask: irreversible or product/competition decision gates.
    ask_patterns = [
        (
            r"\brm\b",
            "File deletion requires approval unless implemented through an approved cleanup command.",
        ),
        (r"\brmdir\b", "Directory deletion requires approval."),
        (r"\bfind\b.*\s-delete\b", "find -delete requires approval."),
        (r"\bgit\s+clean\b", "git clean requires approval."),
        (r"\bkaggle\s+kernels\s+push\b", "Kaggle kernel push requires human approval."),
        (
            r"\bkaggle\s+datasets\s+(create|version)\b",
            "Kaggle dataset publication requires human approval.",
        ),
        (
            r"\bpython\s+tools/kca/kca\.py\s+kaggle\s+(push|upload)\b",
            "KCA Kaggle publication requires human approval.",
        ),
        (
            r"\bsupabase\s+db\s+(push|reset)\b",
            "Remote/destructive Supabase database operation requires approval.",
        ),
        (
            r"\b(psql|sqlite3)\b.*\b(truncate|delete\s+from)\b",
            "Destructive SQL requires approval.",
        ),
        (
            r"\bdocker\s+compose\s+down\b.*\s-v\b",
            "Docker volume deletion requires approval.",
        ),
    ]
    for pattern, reason in ask_patterns:
        if re.search(pattern, lc, flags=re.IGNORECASE):
            return "ask", reason

    return None, None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        emit("deny", f"Guard hook could not parse input: {exc}")
        return 0

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool in {"Read", "Edit", "Write"}:
        file_path = tool_input.get("file_path") or tool_input.get("path") or ""
        if path_is_protected(file_path):
            emit("deny", f"Protected path blocked: {file_path}")
            return 0

    if tool == "Bash":
        command = tool_input.get("command") or ""
        decision, reason = bash_decision(command)
        if decision and reason:
            emit(decision, reason)
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
