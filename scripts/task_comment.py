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
     `admin` or `write` (`repos/{repo}/collaborators/{login}/permission`) on a
     repository in `TRUSTED_REPOS`. NOT `authorAssociation`: this repo is owned
     by an Organization, so `MEMBER` only means org membership (possibly
     read-only) and `COLLABORATOR` only means an accepted invitation. (GPT-6
     review of discussion #185, finding 3.)
  3. Pinning — `url`, `comment_id`, `author`, `updated_at`, `sha256(body)`, any
     attachment URLs, and a verbatim body snapshot are written to the run dir at
     fetch time, and the snapshot is verified against its own pin on every read.
  4. The edit rule — before every gated action, re-check. Append (earlier bytes
     unchanged) is adopted and logged; rewrite, truncation or deletion of the
     source stops at WAIT_HUMAN.

Targets are bound to one repository on `github.com`: the URL's own host and
`owner/name` must be the repository being resolved, and that repository must be
trusted. The carve-out in `CLAUDE.md` principle 1 covers *this* repository, so a
comment living anywhere else stays data no matter who wrote it.

Usage:
  python scripts/task_comment.py fetch <url|#n> --out runs/<slug>/<run_id>/task
  python scripts/task_comment.py recheck runs/<slug>/<run_id>/task
  python scripts/task_comment.py provenance runs/<slug>/<run_id>/task

Exit codes:
  0  — ok / body unchanged
  2  — usage, unsupported or out-of-scope target, target not found, unusable API
       response, or no snapshot at the given path
  3  — refused: author lacks write access, or the repository is not trusted
  10 — body APPENDED since the snapshot (adopt, log the new hash, continue)
  20 — stop at WAIT_HUMAN: body REWRITTEN or truncated, the source comment was
       DELETED, the pinned object changed identity, or the local snapshot no
       longer matches the `sha256` recorded beside it
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "amyteq/tt_pangu"

# The trust carve-out is scoped to "this repository" (`CLAUDE.md` principle 1),
# so trust is not transferable: `--repo` exists to name the repository being read,
# not to extend instruction status to a comment somewhere else. Widening this set
# is a policy decision, not a flag.
TRUSTED_REPOS = frozenset({DEFAULT_REPO})

WRITE_PERMISSIONS = frozenset({"admin", "write"})

# The complete instruction surface: the only things this resolver will promote
# from data to instruction. `CLAUDE.md` principle 1 enumerates the same four, and
# `tests/test_task_comment_contract.py` fails if the two lists drift apart. Every
# other GitHub surface — pull-request bodies and review comments, commit
# comments, wikis, gists, releases — stays data.
SUPPORTED_KINDS = ("issue_comment", "discussion_comment", "issue_body", "discussion_body")

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3
EXIT_APPENDED = 10
EXIT_REWRITTEN = 20

# GraphQL pages 100 nodes at a time. The cap is a loop guard, not a limit anyone
# should reach: it stops loudly rather than silently returning a partial thread.
GRAPHQL_PAGE_SIZE = 100
MAX_GRAPHQL_PAGES = 50

BARE_NUMBER_RE = re.compile(r"#?(?P<number>\d+)")

# A GitHub issue/discussion URL for *some* repository. Only used to tell "wrong
# repository" apart from "not a task URL at all" in the error message.
ANY_GITHUB_ITEM_RE = re.compile(
    r"https?://(?P<host>[^/\s]+)/(?P<owner>[^/\s]+)/(?P<name>[^/\s]+)/(?:issues|discussions)/\d+",
    re.IGNORECASE,
)

# Attachment URLs GitHub itself hosts. Matched inside the body so the pin records
# which images a task referred to; see `extract_attachments`.
GITHUB_ASSET_HOSTS = (
    r"github\.com/user-attachments/",
    r"(?:[a-z0-9-]+\.)?githubusercontent\.com/",
)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?(?P<url>[^)\s>]+)")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"'](?P<url>[^\"']+)[\"']", re.IGNORECASE)
ASSET_URL_RE = re.compile(r"https://(?:" + "|".join(GITHUB_ASSET_HOSTS) + r")[^\s)>\]\"']+", re.IGNORECASE)

DISCUSSION_QUERY = """
query($owner:String!, $name:String!, $number:Int!, $after:String) {
  repository(owner:$owner, name:$name) {
    discussion(number:$number) {
      url
      body
      updatedAt
      author { login }
      comments(first:%(page)d, after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id url databaseId updatedAt body author { login }
          replies(first:%(page)d) {
            pageInfo { hasNextPage endCursor }
            nodes { url databaseId updatedAt body author { login } }
          }
        }
      }
    }
  }
}
""" % {"page": GRAPHQL_PAGE_SIZE}

REPLIES_QUERY = """
query($commentId:ID!, $after:String) {
  node(id:$commentId) {
    ... on DiscussionComment {
      replies(first:%(page)d, after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes { url databaseId updatedAt body author { login } }
      }
    }
  }
}
""" % {"page": GRAPHQL_PAGE_SIZE}


class TaskCommentError(RuntimeError):
    """Base error. Anything not handled more specifically exits `2`."""


class UnsupportedTargetError(TaskCommentError):
    """The target is not an in-scope issue/discussion address on the trusted repo."""


class GhError(TaskCommentError):
    """`gh` failed, or GitHub answered with an error that is not a 404."""


class NotFoundError(GhError):
    """GitHub answered 404 / null for the object. The only error a fallback may swallow."""


class MalformedResponseError(TaskCommentError):
    """A response arrived but does not have the shape the contract reads."""


class RefusedError(TaskCommentError):
    """Trust refusal: unwritable author, or a repository outside `TRUSTED_REPOS`. Exits `3`."""


class SnapshotMissingError(TaskCommentError):
    """No snapshot at the given path — nothing to re-check. Exits `2`."""


class SnapshotIntegrityError(TaskCommentError):
    """The local snapshot does not match its own pin. Exits `20` (WAIT_HUMAN)."""


def run_gh(args: list[str]) -> str:
    """Invoke `gh` and return stdout. The single seam every GitHub read goes through.

    A 404 is raised as `NotFoundError` and everything else as `GhError`, because
    the bare-number fallback may only swallow "this object does not exist" — a
    transient 5xx or an authorization failure must not be read as "not an issue,
    try the discussion".

    Tests monkeypatch this; nothing else in the module touches the network.
    """
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        message = f"gh {' '.join(args)} failed: {stderr}"
        if "HTTP 404" in stderr:
            raise NotFoundError(message)
        raise GhError(message)
    return proc.stdout


def _gh_json(args: list[str]):
    raw = run_gh(args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedResponseError(f"gh {' '.join(args[:2])} returned non-JSON output") from exc


def _dig(payload, *keys: str, what: str):
    """Read a nested field, turning a shape surprise into a documented exit code."""
    node = payload
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            raise MalformedResponseError(f"{what}: response has no {'.'.join(keys)}")
        node = node[key]
    return node


def _require_trusted_repo(repo: str) -> None:
    if repo not in TRUSTED_REPOS:
        raise RefusedError(
            f"refused: repository {repo} is not in the trusted set {sorted(TRUSTED_REPOS)}; "
            "the CLAUDE.md principle 1 carve-out covers this repository only, so a comment "
            "elsewhere is data, not an instruction"
        )


@functools.lru_cache(maxsize=8)
def _target_pattern(repo: str) -> re.Pattern[str]:
    """A full-match pattern for one repository's issue/discussion addresses.

    Host and `owner/name` are baked in, and the whole target must match: an
    unanchored search would accept `https://evil.example/...`, another
    repository, or a URL buried in surrounding prose.
    """
    owner, _, name = repo.partition("/")
    return re.compile(
        r"https?://(?:www\.)?github\.com/"
        rf"{re.escape(owner)}/{re.escape(name)}/"
        r"(?P<noun>issues|discussions)/(?P<number>\d+)/?"
        r"(?:#(?P<fragment>issuecomment|discussioncomment)-(?P<cid>\d+))?",
        re.IGNORECASE,
    )


def parse_target(target: str, repo: str = DEFAULT_REPO) -> dict:
    """Classify a dispatched target into the lookup it needs.

    Supported shapes, per the contract — all of them on `github.com/{repo}`:
      - `.../issues/<n>#issuecomment-<id>`            -> REST
      - `.../discussions/<n>#discussioncomment-<id>`  -> GraphQL (comments + replies)
      - `.../issues/<n>` / `.../discussions/<n>`      -> the body of that item
      - `<n>` or `#<n>`                               -> issue, falling back to discussion
    """
    target = target.strip()

    match = BARE_NUMBER_RE.fullmatch(target)
    if match:
        return {"kind": "bare_number", "number": int(match["number"])}

    match = _target_pattern(repo).fullmatch(target)
    if match:
        noun, fragment = match["noun"], match["fragment"]
        number = int(match["number"])
        if fragment is None:
            return {"kind": "issue_body" if noun == "issues" else "discussion_body", "number": number}
        if noun == "issues" and fragment == "issuecomment":
            return {"kind": "issue_comment", "number": number, "comment_id": match["cid"]}
        if noun == "discussions" and fragment == "discussioncomment":
            return {"kind": "discussion_comment", "number": number, "comment_id": match["cid"]}
        raise UnsupportedTargetError(
            f"unsupported target: {target!r} — a /{noun}/ URL cannot carry a #{fragment}- anchor"
        )

    elsewhere = ANY_GITHUB_ITEM_RE.search(target)
    if elsewhere:
        found = f"{elsewhere['host']}/{elsewhere['owner']}/{elsewhere['name']}"
        if found.lower() == f"github.com/{repo}".lower():
            raise UnsupportedTargetError(
                f"unsupported target: {target!r} — the URL must be the entire target, "
                "with no surrounding text, so that what is resolved is what was dispatched"
            )
        raise UnsupportedTargetError(
            f"out-of-scope target: {target!r} addresses {found}, not github.com/{repo} — "
            "the task-comment contract resolves targets on one repository only"
        )

    raise UnsupportedTargetError(
        f"unsupported target: {target!r} — expected an issue/discussion comment URL, "
        f"an issue/discussion URL on github.com/{repo}, or a number"
    )


def _fetch_issue_comment(repo: str, number: int, comment_id: str) -> dict:
    row = _gh_json(["api", f"repos/{repo}/issues/comments/{comment_id}"])
    what = f"issue comment {comment_id}"
    html_url = _dig(row, "html_url", what=what)
    # The comment id is global: `issues/comments/{id}` happily returns a comment
    # that lives on another issue or on a pull request. Confirm the object the
    # URL claimed is the object GitHub returned, or the pin describes something
    # the human never dispatched.
    try:
        parsed = parse_target(html_url, repo)
    except UnsupportedTargetError as exc:
        raise UnsupportedTargetError(f"{what} resolves to {html_url}, which is not an in-scope issue comment") from exc
    if parsed["kind"] != "issue_comment" or parsed["number"] != number:
        raise UnsupportedTargetError(f"{what} belongs to {html_url}, not issue #{number} of {repo}")
    return {
        "url": html_url,
        "comment_id": str(_dig(row, "id", what=what)),
        "author": _dig(row, "user", "login", what=what),
        "updated_at": _dig(row, "updated_at", what=what),
        "kind": "issue_comment",
        "body": row.get("body") or "",
    }


def _fetch_issue_body(repo: str, number: int) -> dict:
    row = _gh_json(["api", f"repos/{repo}/issues/{number}"])
    what = f"issue #{number}"
    # `repos/{repo}/issues/{n}` also serves pull requests, which share the issue
    # number space. The contract covers issues and discussions, so a PR body is
    # rejected rather than silently promoted into a task.
    if isinstance(row, dict) and row.get("pull_request"):
        raise UnsupportedTargetError(
            f"out-of-scope target: #{number} in {repo} is a pull request, not an issue; "
            "the contract covers issue and discussion comments and bodies"
        )
    return {
        "url": _dig(row, "html_url", what=what),
        "comment_id": f"issue-{number}",
        "author": _dig(row, "user", "login", what=what),
        "updated_at": _dig(row, "updated_at", what=what),
        "kind": "issue_body",
        "body": row.get("body") or "",
    }


def _graphql(query: str, **variables) -> dict:
    args = ["api", "graphql"]
    for key, value in variables.items():
        if value is None:
            continue
        # `-F` types the value (so `number` arrives as Int!); `-f` keeps it a
        # string, which is what an opaque cursor has to stay.
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    args += ["-f", f"query={query}"]
    return _gh_json(args)


def _graphql_errors(raw) -> str:
    if isinstance(raw, dict) and raw.get("errors"):
        return "; ".join(str(err.get("message", err)) for err in raw["errors"])
    return ""


def _fetch_reply_page(comment_node_id: str, cursor: str | None) -> dict:
    raw = _graphql(REPLIES_QUERY, commentId=comment_node_id, after=cursor)
    errors = _graphql_errors(raw)
    node = _dig(raw, "data", "node", what="discussion comment replies") if not errors else None
    if node is None:
        raise GhError(f"replies for comment {comment_node_id} could not be read: {errors or 'null node'}")
    return _dig(node, "replies", what="discussion comment replies")


def _expand_replies(node: dict, number: int) -> None:
    """Page a comment's replies in place, so a reply past the first page resolves."""
    replies = node.get("replies") or {}
    collected = list(replies.get("nodes") or [])
    page_info = replies.get("pageInfo") or {}
    pages = 1
    while page_info.get("hasNextPage"):
        if pages >= MAX_GRAPHQL_PAGES:
            raise GhError(
                f"comment {node.get('databaseId')} on discussion #{number} has more than "
                f"{MAX_GRAPHQL_PAGES * GRAPHQL_PAGE_SIZE} replies; refusing to page further"
            )
        page = _fetch_reply_page(_dig(node, "id", what="discussion comment"), page_info.get("endCursor"))
        collected.extend(page.get("nodes") or [])
        page_info = page.get("pageInfo") or {}
        pages += 1
    node["replies"] = {"nodes": collected}


def _discussion_payload(repo: str, number: int) -> dict:
    """The discussion with *every* comment and reply — paged, never truncated.

    `first:100` alone silently drops the 101st comment, and a dropped comment is
    reported as "not found": the resolver would tell a human their task URL does
    not exist because the thread grew.
    """
    owner, _, name = repo.partition("/")
    discussion: dict | None = None
    comments: list[dict] = []
    cursor: str | None = None

    for _page in range(MAX_GRAPHQL_PAGES):
        raw = _graphql(DISCUSSION_QUERY, owner=owner, name=name, number=number, after=cursor)
        errors = _graphql_errors(raw)
        page = None if errors else _dig(raw, "data", "repository", "discussion", what=f"discussion #{number}")
        if page is None:
            if errors:
                raise GhError(f"discussion #{number} in {repo} could not be read: {errors}")
            raise NotFoundError(f"discussion #{number} not found in {repo}")
        if discussion is None:
            discussion = page
        page_comments = _dig(page, "comments", what=f"discussion #{number}")
        comments.extend(page_comments.get("nodes") or [])
        page_info = page_comments.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    else:
        raise GhError(
            f"discussion #{number} in {repo} has more than {MAX_GRAPHQL_PAGES * GRAPHQL_PAGE_SIZE} "
            "comments; refusing to page further"
        )

    for node in comments:
        _expand_replies(node, number)
    discussion["comments"] = {"nodes": comments}
    return discussion


def _fetch_discussion_comment(repo: str, number: int, comment_id: str) -> dict:
    discussion = _discussion_payload(repo, number)
    nodes = list(discussion["comments"]["nodes"])
    # Replies are comments too — a task can be dispatched from one, so search both levels.
    for node in discussion["comments"]["nodes"]:
        nodes.extend(node.get("replies", {}).get("nodes", []))

    for node in nodes:
        if str(node.get("databaseId")) == str(comment_id):
            return {
                "url": _dig(node, "url", what=f"discussion comment {comment_id}"),
                "comment_id": str(node["databaseId"]),
                "author": (node.get("author") or {}).get("login", ""),
                "updated_at": _dig(node, "updatedAt", what=f"discussion comment {comment_id}"),
                "kind": "discussion_comment",
                "body": node.get("body") or "",
            }
    raise NotFoundError(f"discussion comment {comment_id} not found on discussion #{number}")


def _fetch_discussion_body(repo: str, number: int) -> dict:
    discussion = _discussion_payload(repo, number)
    return {
        "url": _dig(discussion, "url", what=f"discussion #{number}"),
        "comment_id": f"discussion-{number}",
        "author": (discussion.get("author") or {}).get("login", ""),
        "updated_at": _dig(discussion, "updatedAt", what=f"discussion #{number}"),
        "kind": "discussion_body",
        "body": discussion.get("body") or "",
    }


def fetch_target(target: str, repo: str = DEFAULT_REPO) -> dict:
    """Resolve a dispatched target to its body + provenance, without authorizing it."""
    parsed = parse_target(target, repo)
    kind = parsed["kind"]
    if kind not in (*SUPPORTED_KINDS, "bare_number"):  # pragma: no cover - guards a future kind
        raise UnsupportedTargetError(f"unsupported target kind: {kind}")

    if kind == "issue_comment":
        return _fetch_issue_comment(repo, parsed["number"], parsed["comment_id"])
    if kind == "discussion_comment":
        return _fetch_discussion_comment(repo, parsed["number"], parsed["comment_id"])
    if kind == "issue_body":
        return _fetch_issue_body(repo, parsed["number"])
    if kind == "discussion_body":
        return _fetch_discussion_body(repo, parsed["number"])

    # Bare number: an issue and a discussion can share a number, so try the issue
    # first and fall back, rather than guessing from the digits. Only a genuine
    # 404 falls through — a 500, a rate limit or a permission failure means "we
    # do not know what #n is", and answering with a same-numbered discussion
    # would execute a different task.
    try:
        return _fetch_issue_body(repo, parsed["number"])
    except NotFoundError:
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
    except NotFoundError:
        # 404 is the documented answer for "not a collaborator".
        return "none"
    return row.get("permission", "none")


def authorize(author: str, repo: str = DEFAULT_REPO) -> str:
    """Return the permission if the author may dispatch tasks; raise otherwise.

    Trust is repository-scoped before it is author-scoped: write access on some
    other repository is not write access here, so an untrusted repo is refused
    before any login is looked up.
    """
    _require_trusted_repo(repo)
    permission = effective_permission(author, repo)
    if permission not in WRITE_PERMISSIONS:
        raise RefusedError(
            f"refused: author {author or '<unknown>'} has permission={permission}; "
            f"need one of {sorted(WRITE_PERMISSIONS)}"
        )
    return permission


def body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def extract_attachments(body: str) -> list[str]:
    """URLs of images/attachments referenced by the body, sorted and deduplicated.

    Recorded so the durable provenance names what the task pointed at: markdown
    images `![...](url)`, `<img src="...">`, and any bare GitHub-hosted asset URL
    (`github.com/user-attachments/…`, `*.githubusercontent.com/…`). The bytes
    behind these URLs are *not* hashed — only the body is — so a swapped image is
    not detected by the pin.
    """
    urls: set[str] = set()
    for pattern in (MARKDOWN_IMAGE_RE, HTML_IMAGE_RE):
        urls.update(match["url"].rstrip(">") for match in pattern.finditer(body))
    urls.update(match.group(0) for match in ASSET_URL_RE.finditer(body))
    return sorted(url for url in urls if url)


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


def _write_atomic(path: Path, payload: bytes) -> None:
    """Replace `path` in one step, so an interrupted write cannot leave half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def write_snapshot(out_dir: Path, fetched: dict, permission: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = fetched["body"]
    # Bytes, not `write_text`/`read_text`: those apply universal-newline translation,
    # which would silently rewrite the `\r\n` GitHub returns into `\n`. The snapshot
    # would then never match the live body and every re-check would report REWRITTEN.
    _write_atomic(out_dir / "comment.md", body.encode("utf-8"))
    provenance = {
        "url": fetched["url"],
        "comment_id": fetched["comment_id"],
        "author": fetched["author"],
        "permission": permission,
        "updated_at": fetched["updated_at"],
        "kind": fetched["kind"],
        "sha256": body_sha256(body),
        "attachments": extract_attachments(body),
    }
    # Body first, then the pin that describes it: the two writes are individually
    # atomic but not atomic together, and `read_snapshot` verifies the pair anyway.
    _write_atomic(
        out_dir / "provenance.json", (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return provenance


def read_snapshot(task_dir: Path, *, verify: bool = True) -> tuple[dict, str]:
    """Load the snapshot and check it still matches its own pin.

    Without the check, `recheck` compares the *live* body against whatever bytes
    happen to sit in `comment.md` and can report UNCHANGED while `sha256` in
    `provenance.json` describes different text — blessing a body that was never
    pinned and emitting false provenance for it.
    """
    provenance_path = task_dir / "provenance.json"
    body_path = task_dir / "comment.md"
    for path in (provenance_path, body_path):
        if not path.exists():
            raise SnapshotMissingError(f"no snapshot at {task_dir}: {path.name} is missing")

    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SnapshotIntegrityError(
            f"snapshot at {task_dir} is unreadable: {provenance_path.name} is not valid JSON"
        ) from exc
    if not isinstance(provenance, dict):
        raise SnapshotIntegrityError(f"snapshot at {task_dir} is unreadable: {provenance_path.name} is not an object")

    try:
        body = body_path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotIntegrityError(f"snapshot at {task_dir} is unreadable: {body_path.name} is not UTF-8") from exc

    if verify:
        pinned = provenance.get("sha256")
        actual = body_sha256(body)
        if pinned != actual:
            raise SnapshotIntegrityError(
                f"snapshot at {task_dir} does not match its pin: provenance.json records sha256 "
                f"{pinned or '<missing>'} but comment.md hashes to {actual}"
            )
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
    lines += [f"attachment: {url}" for url in provenance.get("attachments") or []]
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

    result = {"url": provenance["url"], "old_sha256": provenance["sha256"]}
    try:
        fetched = fetch_target(provenance["url"], args.repo)
    except NotFoundError as exc:
        # The pinned source is gone. Deletion removes every byte the run acted
        # on, so it is the truncation case taken to its limit: stop, do not
        # treat a vanished task as an unchanged one.
        result |= {"status": "DELETED", "new_sha256": None, "detail": str(exc)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_REWRITTEN

    # Authorization is re-evaluated, not trusted from the snapshot: access can be
    # revoked between dispatch and a gated action.
    permission = authorize(fetched["author"], args.repo)
    result["permission"] = permission
    result["new_sha256"] = body_sha256(fetched["body"])

    if str(fetched["comment_id"]) != str(provenance.get("comment_id")):
        result |= {
            "status": "MISMATCH",
            "detail": f"pinned comment_id {provenance.get('comment_id')} but the URL now resolves to {fetched['comment_id']}",
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_REWRITTEN

    status = classify_change(old_body, fetched["body"])
    result["status"] = status

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
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name, must be trusted (default: {DEFAULT_REPO})")
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
    except RefusedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except SnapshotIntegrityError as exc:
        # A snapshot that contradicts its own pin is a stop, not a usage error:
        # something changed the task text outside the contract.
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_REWRITTEN
    except TaskCommentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
