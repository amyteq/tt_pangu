"""Credential-safe Kaggle account auth for the Orbit Wars live loop (KCT-OW-LIVE-002).

Hard secret rules (task credential_policy):
  * read ONLY .vscode/.env.harry / .vscode/.env.may;
  * NEVER print/log/return secret values (KAGGLE_KEY / KAGGLE_API_TOKEN);
  * NEVER mutate the parent process env with secrets — creds go only into a
    COPIED env handed to a subprocess;
  * usernames + account aliases MAY be displayed;
  * refuse unknown accounts.

The worktree has no .vscode/ (gitignored); resolve against the main checkout too.
"""

from __future__ import annotations

import os
import subprocess

# account alias -> credential dotenv basename
_ACCOUNTS = {
    "harry": ".env.harry",
    "may": ".env.may",
}

# search roots for .vscode/<dotenv> (worktree first, then the main checkout)
_HERE = os.path.dirname(os.path.abspath(__file__))
_COMP = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_COMP, "..", ".."))
_SEARCH_ROOTS = [_REPO, os.path.expanduser("~/test/tt_pangu")]

# secret keys that must never surface in any output
_SECRET_KEYS = ("KAGGLE_KEY", "KAGGLE_API_TOKEN", "KAGGLE_API_KEY")


class AuthError(RuntimeError):
    pass


def known_accounts() -> list[str]:
    return list(_ACCOUNTS)


def cred_path(account: str) -> str:
    """Resolve the dotenv path for an account, or raise. No file contents read."""
    if account not in _ACCOUNTS:
        raise AuthError(f"unknown account {account!r}; allowed: {sorted(_ACCOUNTS)}")
    base = _ACCOUNTS[account]
    for root in _SEARCH_ROOTS:
        p = os.path.join(root, ".vscode", base)
        if os.path.isfile(p):
            return p
    raise AuthError(f"credential file for {account!r} not found (.vscode/{base})")


def _parse_dotenv(path: str) -> dict[str, str]:
    creds: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip().strip("'\"")
    return creds


def load(account: str) -> tuple[dict[str, str], str, list[str]]:
    """Return (subprocess_env, username, secret_values) for an account.

    subprocess_env = a COPY of os.environ overlaid with this account's Kaggle
    vars (so the parent process env is never polluted with secrets).
    secret_values = the literal secret strings, for the redactor ONLY — callers
    must never print this list; it exists so output can be scrubbed.
    """
    path = cred_path(account)
    creds = _parse_dotenv(path)
    user = creds.get("KAGGLE_USERNAME", "?")
    env = dict(os.environ)
    for k in ("KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_API_TOKEN", "KAGGLE_CONFIG_DIR"):
        if k in creds:
            env[k] = creds[k]
    # isolate kaggle config dir per account so the CLI never reads ~/.kaggle
    env.setdefault("KAGGLE_CONFIG_DIR", "/tmp/claude/.kaggle_noconfig")
    secret_values = [creds[k] for k in _SECRET_KEYS if creds.get(k)]
    return env, user, secret_values


def redactor(secret_values: list[str]):
    """Build a function that scrubs any secret substring from text before it is
    printed, written to a doc, or returned."""
    secrets = [s for s in secret_values if s and len(s) >= 6]

    def _scrub(text: str) -> str:
        if not text:
            return text
        for s in secrets:
            text = text.replace(s, "***REDACTED***")
        return text

    return _scrub


def username(account: str) -> str:
    """Display-only Kaggle username for an account (no secret access)."""
    return _parse_dotenv(cred_path(account)).get("KAGGLE_USERNAME", "?")


def run_kaggle(args: list[str], account: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run `kaggle <args>` authenticated as `account`. Returns a CompletedProcess
    whose stdout/stderr have been REDACTED of any secret substring. The account
    creds live only in the child's env, never in this process's os.environ."""
    env, _user, secrets = load(account)
    scrub = redactor(secrets)
    proc = subprocess.run(
        ["kaggle", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    proc.stdout = scrub(proc.stdout or "")
    proc.stderr = scrub(proc.stderr or "")
    return proc


if __name__ == "__main__":
    # self-test: prove we can resolve + load both accounts WITHOUT leaking secrets
    for acct in known_accounts():
        try:
            _env, user, secrets = load(acct)
            print(f"{acct:6s} -> username={user}  creds_loaded={'yes' if secrets else 'no-key'}")
        except AuthError as e:
            print(f"{acct:6s} -> AuthError: {e}")
