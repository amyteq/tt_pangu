"""Audit-grep harness — scan captured pytest output for secret + flag leakage.

Used by tests/test_m11_e2e.py to enforce the M11 hygiene invariant:

  - No `.env`-style `KCA_TOKEN=...` / `CTF_*_TOKEN=...` line escapes from
    any in-process test into stdout / stderr.
  - No `~/.ctf/<event>.json` contents (raw `username`/`token` values)
    surface in any captured envelope.
  - No CTF flag value matching the canonical formats — `picoCTF{...}`,
    `flag{...}`, `kca{...}`, `FLAG{...}`, `CTF{...}` — appears in any
    captured output.

The regexes are intentionally narrow on purpose: pattern-match must hit
on a real leak, not on the literal substring `flag\\{` that lives
inside a `expected_flag_format` regex column in the fixture YAMLs.

This is the M11 analogue of the M10 dotenv-leak regression (issue #11)
extended for the CTF surface — see docs/tasks/M11-T008-e2e-dryrun-test.md.

Both `scan_text(text)` and `scan_lines(lines)` return a list of (regex,
match) tuples. Callers in test_m11_e2e.py assert the list is empty.
"""

from __future__ import annotations

import re
from typing import Iterable

# ---------------------------------------------------------------------------
# Regex catalog
# ---------------------------------------------------------------------------

# 1. Env-var leak — token / secret lines that would appear in a `.env`
#    dump or in a process's exported env. We do NOT match
#    `KCA_ALLOW_REMOTE=1` (a known-safe gate) or any `=` paired with
#    empty / `_redacted` / `${...}` placeholders.
_SECRET_KV_RE = re.compile(
    r"(?:^|[\s\"'])"
    r"(?:KCA_TOKEN|KCA_API_KEY|"
    r"ANTHROPIC_API_KEY|OPENAI_API_KEY|"
    r"KAGGLE_KEY|KAGGLE_USERNAME|"
    r"SUPABASE_DB_URL|SUPABASE_ANON_KEY|SUPABASE_SERVICE_ROLE_KEY|"
    r"CTF_[A-Z0-9_]{2,}_TOKEN|CTF_[A-Z0-9_]{2,}_USERNAME|"
    r"CTF_[A-Z0-9_]{2,}_TEAM_ID|"
    r"GITHUB_TOKEN|GH_TOKEN)"
    r"\s*=\s*"
    r"(?!\s*$)"  # value must be non-empty
    r"(?!\$\{)"  # placeholder ${VAR}
    r"(?!_redacted)"
    r"(?!REDACTED)"
    r"(?:'[^']{4,}|\"[^\"]{4,}|[^\s'\"]{4,})"
)

# 2. ~/.ctf/<slug>.json line — only matches when the line contains a
#    PATH-LIKE reference (~/.ctf/<slug>.json or /home/.../.ctf/<slug>.json)
#    plus a `username` / `token` JSON key on the SAME line. The path
#    alone is fine (it appears in error messages legitimately).
_CTF_JSON_LEAK_RE = re.compile(
    r"\.ctf/[A-Za-z0-9_\-]+\.json.*?\"(?:username|token|team_id)\"\s*:\s*\"[^\"]+\"|"
    r"\"(?:username|token|team_id)\"\s*:\s*\"[^\"]+\".*?\.ctf/[A-Za-z0-9_\-]+\.json"
)

# 3. CTF flag patterns. The fixtures' `expected_flag_format` columns
#    contain *regexes* like `^kca\{[A-Za-z0-9_]+\}$` — these regex
#    tokens are NOT flag values and we deliberately do not match them.
#    The match must contain at least one alnum/underscore between
#    `{` and `}`, AND must not be the literal regex character class
#    `[A-Za-z0-9_]+`.
#    A second guard: the matched body must not contain `+`, `[`, `]`,
#    `\\`, or `*` (any of which signals a regex literal).
_FLAG_PATTERNS = [
    re.compile(r"(?:^|\W)(picoCTF\{[^{}\s\\\[\]*+]{1,200}\})", re.IGNORECASE),
    re.compile(r"(?:^|\W)(flag\{[^{}\s\\\[\]*+]{1,200}\})", re.IGNORECASE),
    re.compile(r"(?:^|\W)(kca\{[^{}\s\\\[\]*+]{1,200}\})"),
    re.compile(r"(?:^|\W)(CTF\{[^{}\s\\\[\]*+]{1,200}\})"),
    re.compile(r"(?:^|\W)(FLAG\{[^{}\s\\\[\]*+]{1,200}\})"),
]


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("secret_kv", _SECRET_KV_RE),
    ("ctf_json", _CTF_JSON_LEAK_RE),
] + [("flag", p) for p in _FLAG_PATTERNS]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_text(text: str) -> list[tuple[str, str]]:
    """Return a list of (pattern_name, matched_substring) hits.

    Empty list ⇒ clean.
    """
    if not text:
        return []
    hits: list[tuple[str, str]] = []
    for name, pat in _PATTERNS:
        for m in pat.finditer(text):
            # Use the first capture group if present, otherwise the whole match.
            try:
                snippet = m.group(1)
            except IndexError:
                snippet = m.group(0)
            hits.append((name, snippet))
    return hits


def scan_lines(lines: Iterable[str]) -> list[tuple[str, str]]:
    """Convenience for streaming line-iterables (e.g. capsys output)."""
    return scan_text("\n".join(lines))


def fingerprint() -> dict[str, int]:
    """Return a small dict describing the catalog — used by self-tests."""
    return {
        "secret_kv_patterns": 1,
        "ctf_json_patterns": 1,
        "flag_patterns": len(_FLAG_PATTERNS),
        "total_patterns": len(_PATTERNS),
    }


# ---------------------------------------------------------------------------
# Self-test — `python tests/_audit_grep.py` runs the contract.
# ---------------------------------------------------------------------------


def _self_test() -> None:
    # 1. Positive matches.
    leaks = scan_text(
        "KCA_TOKEN=tok_abcdef1234567\n"
        "CTF_PICOCTF_2025_TOKEN=hunter2hunter2\n"
        '~/.ctf/picoctf-2025.json {"username":"alice","token":"xyz"}\n'
        "the flag was kca{m11_t008_audit_grep_test_value}\n"
        "picoCTF{never_share_this_one_please}\n"
        "FLAG{ctf_competition_flag_here_2026}\n"
        "ANTHROPIC_API_KEY=sk-ant-redacted_but_long_enough\n"
    )
    names = [n for n, _ in leaks]
    for required in ("secret_kv", "ctf_json", "flag"):
        assert required in names, f"missing {required!r} in {names!r}"
    assert sum(1 for n in names if n == "flag") >= 3, names
    # 2. Negative cases — regex columns and benign env should NOT match.
    benign = scan_text(
        # `expected_flag_format` regex with character class — NOT a flag value
        r"expected_flag_format: '^kca\{[A-Za-z0-9_]+\}$'" + "\n"
        # KCA_ALLOW_REMOTE is the gate var and is benign
        "KCA_ALLOW_REMOTE=1\n"
        # `_redacted` placeholder is the M11 reviewer-prompt redaction
        "CTF_PICOCTF_2025_TOKEN=_redacted" + "\n"
        # bare path mention in an error message — no JSON key, no value
        "no credentials for event 'picoctf-2025': expected ~/.ctf/picoctf-2025.json\n"
        # placeholder in env example
        "KCA_TOKEN=${KCA_TOKEN}\n"
        # short value (<4 chars) — not a real secret
        "KCA_TOKEN=x\n"
    )
    assert benign == [], f"expected 0 hits on benign input, got {benign!r}"
    print(f"audit_grep self-test PASS — patterns={fingerprint()}, positive_hits={len(leaks)}")


if __name__ == "__main__":
    _self_test()
