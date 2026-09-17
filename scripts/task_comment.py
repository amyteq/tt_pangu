#!/usr/bin/env python3
"""Resolve a task delivered as a GitHub issue / discussion comment (issue #196).

Phase 1 delivers tasks as comment URLs rather than committed `task.md` files. A
comment is mutable, deletable, and writable by anyone who can comment, so it is
not safe to fetch-and-run. This module is the reference implementation of the
contract in `docs/tooling/task-comment-contract.md`; both harnesses (Claude Code
and Codex) shell out to it, so the rules live in one place.

Four properties, in the order they are enforced:

  1. Explicit dispatch — there is no discovery mode. Every entry point takes a
     target the human supplied; nothing here searches for work to do.
  2. Authorization — the author must hold **effective repository permission**
     `admin` or `write` (`repos/{repo}/collaborators/{login}/permission`).
     NOT `authorAssociation`: this repo is owned by an Organization, so `MEMBER`
     only means org membership (possibly read-only) and `COLLABORATOR` only means
     an accepted invitation. (GPT-6 review of discussion #185, finding 3.)
  3. Pinning — `url`, `comment_id`, `author`, `updated_at`, `sha256(body)` and a
     verbatim body snapshot are written to the run dir at fetch time.
  4. The edit rule — before every gated action, re-check. Append (earlier bytes
     unchanged) is adopted and logged; rewrite or truncation stops at WAIT_HUMAN.

Usage:
  python scripts/task_comment.py fetch <url|#n> --out runs/<slug>/<run_id>/task
  python scripts/task_comment.py recheck runs/<slug>/<run_id>/task
  python scripts/task_comment.py provenance runs/<slug>/<run_id>/task

Exit codes:
  0  — ok / body unchanged
  2  — usage or unsupported target
  3  — refused: author lacks write access
  10 — body APPENDED since the snapshot (adopt, log the new hash, continue)
  20 — body REWRITTEN or truncated since the snapshot (stop at WAIT_HUMAN)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "amyteq/tt_pangu"

WRITE_PERMISSIONS = frozenset({"admin", "write"})

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_APPENDED = 10
EXIT_REWRITTEN = 20

ISSUE_COMMENT_RE = re.compile(r"/issues/(?P<number>\d+)#issuecomment-(?P<cid>\d+)")
DISCUSSION_COMMENT_RE = re.compile(r"/discussions/(?P<number>\d+)#discussioncomment-(?P<cid>\d+)")
ISSUE_RE = re.compile(r"/issues/(?P<number>\d+)/?$")
DISCUSSION_RE = re.compile(r"/discussions/(?P<number>\d+)/?$")
BARE_NUMBER_RE = re.compile(r"^#?(?P<number>\d+)$")

DISCUSSION_QUERY = """
query($owner:String!, $name:String!, $number:Int!) {
  repository(owner:$owner, name:$name) {
    discussion(number:$number) {
      url
      body
      updatedAt
      author { login }
      comments(first:100) {
        nodes {
          url databaseId updatedAt body author { login }
          replies(first:100) {
            nodes { url databaseId updatedAt body author { login } }
          }
        }
      }
    }
  }
}
"""


class TaskCommentError(RuntimeError):
    """Raised for an unusable target, a failed lookup, or a refused author."""


def run_gh(args: list[str]) -> str:
    """Invoke `gh` and return stdout. The single seam every GitHub read goes through.

    Tests monkeypatch this; nothing else in the module touches the network.
    """
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise TaskCommentError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _gh_json(args: list[str]):
    return json.loads(run_gh(args))


def parse_target(target: str) -> dict:
    """Classify a dispatched target into the lookup it needs.

    Supported shapes, per the contract:
      - `.../issues/<n>#issuecomment-<id>`            -> REST
      - `.../discussions/<n>#discussioncomment-<id>`  -> GraphQL (comments + replies)
      - `.../issues/<n>` / `.../discussions/<n>`      -> the body of that item
      - `<n>` or `#<n>`                               -> issue, falling back to discussion
    """
    target = target.strip()

    match = ISSUE_COMMENT_RE.search(target)
    if match:
        return {"kind": "issue_comment", "number": int(match["number"]), "comment_id": match["cid"]}

    match = DISCUSSION_COMMENT_RE.search(target)
    if match:
        return {"kind": "discussion_comment", "number": int(match["number"]), "comment_id": match["cid"]}

    match = ISSUE_RE.search(target)
    if match:
        return {"kind": "issue_body", "number": int(match["number"])}

    match = DISCUSSION_RE.search(target)
    if match:
        return {"kind": "discussion_body", "number": int(match["number"])}

    match = BARE_NUMBER_RE.match(target)
    if match:
        return {"kind": "bare_number", "number": int(match["number"])}

    raise TaskCommentError(
        f"unsupported target: {target!r} — expected an issue/discussion comment URL, "
        "an issue/discussion URL, or a number"
    )


def _fetch_issue_comment(repo: str, comment_id: str) -> dict:
    row = _gh_json(["api", f"repos/{repo}/issues/comments/{comment_id}"])
    return {
        "url": row["html_url"],
        "comment_id": str(row["id"]),
        "author": row["user"]["login"],
        "updated_at": row["updated_at"],
        "kind": "issue_comment",
        "body": row["body"] or "",
    }


def _fetch_issue_body(repo: str, number: int) -> dict:
    row = _gh_json(["api", f"repos/{repo}/issues/{number}"])
    return {
        "url": row["html_url"],
        "comment_id": f"issue-{number}",
        "author": row["user"]["login"],
        "updated_at": row["updated_at"],
        "kind": "issue_body",
        "body": row["body"] or "",
    }


def _discussion_payload(repo: str, number: int) -> dict:
    owner, name = repo.split("/", 1)
    raw = _gh_json(
        [
            "api",
            "graphql",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={number}",
            "-f",
            f"query={DISCUSSION_QUERY}",
        ]
    )
    discussion = raw["data"]["repository"]["discussion"]
    if discussion is None:
        raise TaskCommentError(f"discussion #{number} not found in {repo}")
    return discussion


def _fetch_discussion_comment(repo: str, number: int, comment_id: str) -> dict:
    discussion = _discussion_payload(repo, number)
    nodes = list(discussion["comments"]["nodes"])
    # Replies are comments too — a task can be dispatched from one, so search both levels.
    for node in discussion["comments"]["nodes"]:
        nodes.extend(node.get("replies", {}).get("nodes", []))

    for node in nodes:
        if str(node["databaseId"]) == str(comment_id):
            return {
                "url": node["url"],
                "comment_id": str(node["databaseId"]),
                "author": (node["author"] or {}).get("login", ""),
                "updated_at": node["updatedAt"],
                "kind": "discussion_comment",
                "body": node["body"] or "",
            }
    raise TaskCommentError(f"discussion comment {comment_id} not found on discussion #{number}")


def _fetch_discussion_body(repo: str, number: int) -> dict:
    discussion = _discussion_payload(repo, number)
    return {
        "url": discussion["url"],
        "comment_id": f"discussion-{number}",
        "author": (discussion["author"] or {}).get("login", ""),
        "updated_at": discussion["updatedAt"],
        "kind": "discussion_body",
        "body": discussion["body"] or "",
    }


def fetch_target(target: str, repo: str = DEFAULT_REPO) -> dict:
    """Resolve a dispatched target to its body + provenance, without authorizing it."""
    parsed = parse_target(target)
    kind = parsed["kind"]

    if kind == "issue_comment":
        return _fetch_issue_comment(repo, parsed["comment_id"])
    if kind == "discussion_comment":
        return _fetch_discussion_comment(repo, parsed["number"], parsed["comment_id"])
    if kind == "issue_body":
        return _fetch_issue_body(repo, parsed["number"])
    if kind == "discussion_body":
        return _fetch_discussion_body(repo, parsed["number"])

    # Bare number: an issue and a discussion can share a number, so try the issue
    # first and fall back, rather than guessing from the digits.
    try:
        return _fetch_issue_body(repo, parsed["number"])
    except TaskCommentError:
        return _fetch_discussion_body(repo, parsed["number"])


def effective_permission(login: str, repo: str = DEFAULT_REPO) -> str:
    """Return the author's effective repository permission, or `none`.

    This is the check that matters. `authorAssociation` (OWNER / MEMBER /
    COLLABORATOR) describes affiliation, not access: on an Organization-owned
    repo a MEMBER can hold a read-only role and a COLLABORATOR can have been
    invited at `triage`. Both would pass an affiliation check and neither can
    write here.
    """
    if not login:
        return "none"
    try:
        row = _gh_json(["api", f"repos/{repo}/collaborators/{login}/permission"])
    except TaskCommentError:
        # 404 is the documented answer for "not a collaborator".
        return "none"
    return row.get("permission", "none")


def authorize(author: str, repo: str = DEFAULT_REPO) -> str:
    """Return the permission if the author may dispatch tasks; raise otherwise."""
    permission = effective_permission(author, repo)
    if permission not in WRITE_PERMISSIONS:
        raise TaskCommentError(
            f"refused: author {author or '<unknown>'} has permission={permission}; "
            f"need one of {sorted(WRITE_PERMISSIONS)}"
        )
    return permission


def body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def classify_change(old_body: str, new_body: str) -> str:
    """UNCHANGED / APPENDED / REWRITTEN — the Decision 3 prefix test.

    Append is safe to adopt because everything the run already acted on is still
    there, byte for byte. Any edit to earlier bytes (including truncation) can
    change what was already done, so it stops at WAIT_HUMAN.
    """
    if old_body == new_body:
        return "UNCHANGED"
    if new_body.startswith(old_body):
        return "APPENDED"
    return "REWRITTEN"


def write_snapshot(out_dir: Path, fetched: dict, permission: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = fetched["body"]
    # Bytes, not `write_text`/`read_text`: those apply universal-newline translation,
    # which would silently rewrite the `\r\n` GitHub returns into `\n`. The snapshot
    # would then never match the live body and every re-check would report REWRITTEN.
    (out_dir / "comment.md").write_bytes(body.encode("utf-8"))
    provenance = {
        "url": fetched["url"],
        "comment_id": fetched["comment_id"],
        "author": fetched["author"],
        "permission": permission,
        "updated_at": fetched["updated_at"],
        "kind": fetched["kind"],
        "sha256": body_sha256(body),
    }
    (out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return provenance


def read_snapshot(task_dir: Path) -> tuple[dict, str]:
    provenance = json.loads((task_dir / "provenance.json").read_text(encoding="utf-8"))
    body = (task_dir / "comment.md").read_bytes().decode("utf-8")
    return provenance, body


def provenance_block(provenance: dict, run_dir: str | None = None) -> str:
    """The block posted back to the tracking issue.

    `runs/` is gitignored (`.gitignore:58`), so the run-dir snapshot is a working
    copy only. This block is the durable record of which task text was executed.
    """
    lines = [
        f"task: {provenance['url']}",
        f"sha256: {provenance['sha256']}",
        f"author: {provenance['author']} ({provenance['permission']}) · updated: {provenance['updated_at']}",
    ]
    if run_dir:
        lines.append(f"run: {run_dir}")
    return "\n".join(lines)


def cmd_fetch(args: argparse.Namespace) -> int:
    fetched = fetch_target(args.target, args.repo)
    permission = authorize(fetched["author"], args.repo)
    provenance = write_snapshot(Path(args.out), fetched, permission)
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return EXIT_OK


def cmd_recheck(args: argparse.Namespace) -> int:
    task_dir = Path(args.task_dir)
    provenance, old_body = read_snapshot(task_dir)

    fetched = fetch_target(provenance["url"], args.repo)
    # Authorization is re-evaluated, not trusted from the snapshot: access can be
    # revoked between dispatch and a gated action.
    permission = authorize(fetched["author"], args.repo)

    status = classify_change(old_body, fetched["body"])
    result = {
        "status": status,
        "url": provenance["url"],
        "old_sha256": provenance["sha256"],
        "new_sha256": body_sha256(fetched["body"]),
        "permission": permission,
    }

    if status == "APPENDED" and args.adopt:
        write_snapshot(task_dir, fetched, permission)
        result["adopted"] = True

    print(json.dumps(result, indent=2, sort_keys=True))
    return {"UNCHANGED": EXIT_OK, "APPENDED": EXIT_APPENDED, "REWRITTEN": EXIT_REWRITTEN}[status]


def cmd_provenance(args: argparse.Namespace) -> int:
    provenance, _ = read_snapshot(Path(args.task_dir))
    print(provenance_block(provenance, args.run_dir))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="task_comment.py",
        description="Resolve a dispatched GitHub comment task with provenance, authorization and pinning.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default: {DEFAULT_REPO})")
    sub = parser.add_subparsers(dest="command", required=True)

    # Every subcommand takes an explicit target or an existing snapshot. There is
    # deliberately no `scan` / `poll` / `latest` mode: a privileged author's
    # comment is never auto-executable.
    p_fetch = sub.add_parser("fetch", help="Resolve a dispatched target and write the snapshot")
    p_fetch.add_argument("target", help="comment URL, issue/discussion URL, or number")
    p_fetch.add_argument("--out", required=True, help="run dir, e.g. runs/<slug>/<run_id>/task")
    p_fetch.set_defaults(func=cmd_fetch)

    p_recheck = sub.add_parser("recheck", help="Re-check a snapshot before a gated action")
    p_recheck.add_argument("task_dir")
    p_recheck.add_argument("--adopt", action="store_true", help="rewrite the snapshot when the change is an append")
    p_recheck.set_defaults(func=cmd_recheck)

    p_prov = sub.add_parser("provenance", help="Print the provenance block to post back to the tracking issue")
    p_prov.add_argument("task_dir")
    p_prov.add_argument("--run-dir", default=None)
    p_prov.set_defaults(func=cmd_provenance)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except TaskCommentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED if str(exc).startswith("refused:") else EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
