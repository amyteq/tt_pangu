#!/usr/bin/env python3
"""Check tracked source for credentials/transcripts; never print matched values.

A passing scan is not approval to publish Git history or hosted discussions,
attachments, logs, artifacts, datasets or third-party material. Use --privacy
for advisory personal-path, email and private-network findings as well.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from urllib.parse import urlsplit
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = "scripts/public-source-allowlist.json"

# No directory-wide exclusions: a credential in a test or example still fails.
RULES = {
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{50,})"),
    "model-api-key": re.compile(r"\bsk-(?:ant-(?:api\d+-)?|proj-)?[A-Za-z0-9_-]{24,}"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "supabase-secret-key": re.compile(r"\bsb_secret_[A-Za-z0-9_-]{16,}"),
    "telegram-token": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    "credential-url": re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb|redis|https?)://[^\s/:@]+:([^\s@]+)@[^\s/]+"),
    "credential-assignment": re.compile(
        r"(?i)\b(?:PGPASSWORD|[A-Z0-9_]*(?:API_KEY|SECRET_KEY|ACCESS_TOKEN|AUTH_TOKEN|BOT_TOKEN|PASSWORD)|KAGGLE_KEY)"
        r"\s*[=:]\s*[\"']?([A-Za-z0-9_./+%=-]{16,})"
    ),
    "private-key-block": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[ \t]*(?:\r?\n|\\r\\n|\\n)"
        r"(?:[A-Za-z0-9+/=]+(?:\r?\n|\\r\\n|\\n))+"
        r"-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "service-role-jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{15,}"),
}
PRIVACY_RULES = {
    "personal-path": re.compile(r"(?:/Users/[^\s/]+|/home/[^\s/]+|[A-Z]:\\Users\\[^\\\s]+)"),
    "private-network": re.compile(r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    rule: str
    severity: str = "error"


def forbidden_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        any(p in {"logs", "worklogs", ".agent", ".claude-session", "secrets"} for p in parts)
        or PurePosixPath(path).name in {".env", "kaggle.json", "id_rsa", "id_ed25519"}
        or bool(re.search(r"(?:^|/)\.env\.(?!example$|sample$|template$)", path))
    )


def placeholder(value: str) -> bool:
    # Explicit, recognisable documentation placeholders only. Actual token-shaped
    # test fixtures need a reviewed, exact-line allowlist entry instead.
    return bool(
        re.fullmatch(
            r"(?i)(?:postgres|password|s3cr3t|changeme|REDACTED|MASKED|your[-_][A-Z0-9_-]+|example[-_][A-Z0-9_-]+)",
            value,
        )
    )


def scan_text(path: str, text: str, *, privacy: bool = False) -> list[Finding]:
    import base64

    hits: set[Finding] = set()
    if forbidden_path(path):
        hits.add(Finding(path, 1, "forbidden-private-path"))
    if text.startswith("# Claude session log:") or "Source transcript: `" in text[:1000]:
        hits.add(Finding(path, 1, "session-transcript"))
    for rule, regex in RULES.items():
        for match in regex.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            if placeholder(value):
                if rule != "credential-url":
                    continue
                try:
                    host = urlsplit(match.group(0)).hostname
                except ValueError:
                    host = None
                if host in {"localhost", "127.0.0.1", "::1"}:
                    continue
            if rule == "service-role-jwt":
                try:
                    claims = json.loads(base64.urlsafe_b64decode(value.split(".")[1] + "==="))
                except (ValueError, UnicodeError):
                    continue
                if claims.get("role") != "service_role":
                    continue
            hits.add(Finding(path, text.count("\n", 0, match.start()) + 1, rule))
    if privacy:
        for rule, regex in PRIVACY_RULES.items():
            for match in regex.finditer(text):
                hits.add(Finding(path, text.count("\n", 0, match.start()) + 1, rule, "review"))
    return sorted(hits)


def line_digest(text: str, line: int) -> str:
    return hashlib.sha256(text.splitlines()[line - 1].encode()).hexdigest()


def allowed(finding: Finding, text: str, entries: list[dict]) -> bool:
    # Only credentials can have synthetic-test exceptions. Transcripts, private
    # paths, binary files and privacy-review findings cannot be waived here.
    if finding.rule not in RULES or finding.rule == "private-key-block":
        return False
    digest = line_digest(text, finding.line)
    return any(
        row.get("path") == finding.path
        and row.get("rule") == finding.rule
        and row.get("line_sha256") == digest
        and bool(row.get("reason"))
        for row in entries
    )


def tracked_files(root: Path) -> list[str]:
    raw = subprocess.check_output(["git", "-C", str(root), "ls-files", "--cached", "-z"])
    return sorted(set(p.decode() for p in raw.split(b"\0") if p))


def read_source(root: Path, path: str, staged: bool) -> bytes | None:
    if staged:
        return subprocess.check_output(["git", "-C", str(root), "show", f":{path}"])
    source = root / path
    if source.is_symlink():
        return str(source.readlink()).encode()  # inspect the target string, never follow it
    if not source.exists():
        return None  # deletion proposed in the working tree
    return source.read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Scan the exact Git index instead of working-tree bytes.")
    parser.add_argument(
        "--privacy", action="store_true", help="Also report personal paths, emails and private IPs for review."
    )
    parser.add_argument("--strict-privacy", action="store_true", help="Make privacy-review findings fail the check.")
    args = parser.parse_args(argv)
    allow_bytes = read_source(ROOT, ALLOWLIST, args.staged)
    entries = json.loads(allow_bytes or b"[]")
    findings: list[Finding] = []
    checked = binary = 0
    for path in tracked_files(ROOT):
        data = read_source(ROOT, path, args.staged)
        if data is None:
            continue
        checked += 1
        if b"\0" in data:
            binary += 1
            if forbidden_path(path):
                findings.append(Finding(path, 1, "forbidden-private-path"))
            continue
        text = data.decode("utf8", errors="replace")
        findings.extend(
            hit
            for hit in scan_text(path, text, privacy=args.privacy or args.strict_privacy)
            if not allowed(hit, text, entries)
        )
    for hit in sorted(findings):
        print(f"{hit.path}:{hit.line}: {hit.severity}: {hit.rule} (matched value withheld)")
    errors = sum(hit.severity == "error" for hit in findings)
    reviews = len(findings) - errors
    print(
        f"Checked {checked} tracked files: {errors} credential/transcript errors; {reviews} privacy review findings; {binary} binary files not text-scanned."
    )
    print("Scope: current source only. Git history and hosted content require separate review.")
    return int(bool(errors or (args.strict_privacy and reviews)))


if __name__ == "__main__":
    raise SystemExit(main())
