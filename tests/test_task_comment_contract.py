"""The task-comment contract (issue #196).

Phase 1 delivers tasks as GitHub comment URLs. `scripts/task_comment.py` is the
reference resolver; `docs/tooling/task-comment-contract.md` is the contract it
implements. These tests pin the four properties that make a mutable, publicly
writable comment safe to execute:

  1. explicit dispatch — no discovery mode exists;
  2. authorization on **effective repository permission**, never `authorAssociation`;
  3. pinning — body snapshot + `sha256`;
  4. the edit rule — append continues, rewrite stops at `WAIT_HUMAN`.

No test touches GitHub. Every lookup goes through `task_comment.run_gh`, which is
monkeypatched with a fake responder, so the permission endpoint in particular is
mocked rather than called.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVER = REPO_ROOT / "scripts" / "task_comment.py"

REPO = "amyteq/tt_pangu"


@pytest.fixture(scope="module")
def tc():
    spec = importlib.util.spec_from_file_location("task_comment", RESOLVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_gh(tc, *, permissions: dict[str, str], issue_comments=None, issues=None, discussions=None):
    """Build a fake `run_gh` from canned data.

    `permissions` maps a login to what `repos/{repo}/collaborators/{login}/permission`
    returns; a login that is absent raises, mimicking the 404 GitHub returns for a
    non-collaborator.
    """
    issue_comments = issue_comments or {}
    issues = issues or {}
    discussions = discussions or {}
    calls: list[list[str]] = []

    def fake_run_gh(args: list[str]) -> str:
        calls.append(args)
        # graphql: `api graphql -F owner=... -F name=... -F number=N -f query=...`
        if args[:2] == ["api", "graphql"]:
            number = None
            for i, token in enumerate(args):
                if token.startswith("number="):
                    number = int(token.split("=", 1)[1])
                elif token == "-F" and i + 1 < len(args) and args[i + 1].startswith("number="):
                    number = int(args[i + 1].split("=", 1)[1])
            payload = discussions.get(number)
            return json.dumps({"data": {"repository": {"discussion": payload}}})

        path = args[1]
        if "/collaborators/" in path:
            login = path.split("/collaborators/", 1)[1].split("/", 1)[0]
            if login not in permissions:
                raise tc.TaskCommentError("gh api failed: HTTP 404")
            return json.dumps({"permission": permissions[login]})
        if "/issues/comments/" in path:
            cid = path.rsplit("/", 1)[1]
            if cid not in issue_comments:
                raise tc.TaskCommentError("gh api failed: HTTP 404")
            return json.dumps(issue_comments[cid])
        if "/issues/" in path:
            number = path.rsplit("/", 1)[1]
            if number not in issues:
                raise tc.TaskCommentError("gh api failed: HTTP 404")
            return json.dumps(issues[number])
        raise AssertionError(f"unexpected gh call: {args}")

    fake_run_gh.calls = calls
    return fake_run_gh


def issue_comment_row(cid: str, author: str, body: str, updated: str = "2026-09-15T00:15:48Z"):
    return {
        "html_url": f"https://github.com/{REPO}/issues/196#issuecomment-{cid}",
        "id": int(cid),
        "user": {"login": author},
        "updated_at": updated,
        "body": body,
    }


# --------------------------------------------------------------------------
# Authorization — the six cases the issue's acceptance criteria name
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "permission"),
    [
        ("read-only org member", "read"),
        ("read-only collaborator", "read"),
        ("triage collaborator", "triage"),
    ],
)
def test_privileged_looking_but_unwritable_authors_are_refused(tc, monkeypatch, label, permission):
    """MEMBER / COLLABORATOR affiliation is not write access.

    This is the correction from the GPT-6 review of discussion #185 (finding 3):
    an `authorAssociation` check would pass every one of these authors.
    """
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"reader": permission}))
    with pytest.raises(tc.TaskCommentError) as excinfo:
        tc.authorize("reader", REPO)
    assert "refused:" in str(excinfo.value)
    assert f"permission={permission}" in str(excinfo.value), label


def test_non_collaborator_is_refused(tc, monkeypatch):
    """A 404 from the permission endpoint means `none`, not "unknown, proceed"."""
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={}))
    assert tc.effective_permission("stranger", REPO) == "none"
    with pytest.raises(tc.TaskCommentError, match="refused:"):
        tc.authorize("stranger", REPO)


def test_revoked_permission_is_refused_at_recheck(tc, monkeypatch, tmp_path):
    """Access is re-evaluated before a gated action, not trusted from the snapshot."""
    body = "do the thing\n"
    row = issue_comment_row("5672680663", "harrysun2006", body)
    url = row["html_url"]

    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"5672680663": row}),
    )
    task_dir = tmp_path / "task"
    fetched = tc.fetch_target(url, REPO)
    tc.write_snapshot(task_dir, fetched, tc.authorize(fetched["author"], REPO))

    # Permission revoked between dispatch and the gated action.
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={}, issue_comments={"5672680663": row}),
    )
    args = tc.build_parser().parse_args(["recheck", str(task_dir)])
    assert tc.main(["recheck", str(task_dir)]) == tc.EXIT_REFUSED
    assert args.task_dir == str(task_dir)


def test_write_and_admin_are_accepted(tc, monkeypatch):
    for permission in ("write", "admin"):
        monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"dev": permission}))
        assert tc.authorize("dev", REPO) == permission


def test_authorization_uses_the_permission_endpoint_not_author_association(tc, monkeypatch):
    """Pin the endpoint itself — the whole correction is *which* call is made."""
    fake = make_gh(tc, permissions={"dev": "write"})
    monkeypatch.setattr(tc, "run_gh", fake)
    tc.authorize("dev", REPO)
    assert any("/collaborators/dev/permission" in call[1] for call in fake.calls if len(call) > 1)


# --------------------------------------------------------------------------
# The edit rule — Decision 3's prefix test
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("line A\nline B\n", "line A\nline B\n", "UNCHANGED"),
        ("line A\nline B\n", "line A\nline B\n--- 追加 2026-09-17 ---\nline C\n", "APPENDED"),
        ("line A\nline B\n", "line A\nline B-CHANGED\n", "REWRITTEN"),
        ("line A\nline B\n", "line A\n", "REWRITTEN"),
        ("line A\nline B\n", "", "REWRITTEN"),
    ],
    ids=["unchanged", "appended", "rewritten", "truncated", "deleted"],
)
def test_classify_change(tc, old, new, expected):
    assert tc.classify_change(old, new) == expected


def test_appended_body_continues_and_can_adopt(tc, monkeypatch, tmp_path):
    original = "do the thing\n"
    row = issue_comment_row("1", "harrysun2006", original)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"1": row}))
    task_dir = tmp_path / "task"
    fetched = tc.fetch_target(row["html_url"], REPO)
    first = tc.write_snapshot(task_dir, fetched, tc.authorize(fetched["author"], REPO))

    extended = original + "--- 追加 2026-09-17 ---\nalso do the other thing\n"
    row_v2 = issue_comment_row("1", "harrysun2006", extended, updated="2026-09-17T09:00:00Z")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"1": row_v2}))

    assert tc.main(["recheck", str(task_dir)]) == tc.EXIT_APPENDED
    # Without --adopt the snapshot is untouched, so the pin still describes what ran.
    assert (task_dir / "comment.md").read_text(encoding="utf-8") == original

    assert tc.main(["recheck", str(task_dir), "--adopt"]) == tc.EXIT_APPENDED
    adopted, body = tc.read_snapshot(task_dir)
    assert body == extended
    assert adopted["sha256"] == tc.body_sha256(extended)
    assert adopted["sha256"] != first["sha256"]


def test_rewritten_body_stops_at_wait_human(tc, monkeypatch, tmp_path):
    original = "do the thing\n"
    row = issue_comment_row("2", "harrysun2006", original)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"2": row}))
    task_dir = tmp_path / "task"
    fetched = tc.fetch_target(row["html_url"], REPO)
    tc.write_snapshot(task_dir, fetched, tc.authorize(fetched["author"], REPO))

    rewritten = issue_comment_row("2", "harrysun2006", "do something else entirely\n")
    monkeypatch.setattr(
        tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"2": rewritten})
    )

    assert tc.main(["recheck", str(task_dir), "--adopt"]) == tc.EXIT_REWRITTEN
    # A rewrite must never be adopted, even with --adopt.
    assert (task_dir / "comment.md").read_text(encoding="utf-8") == original


# --------------------------------------------------------------------------
# URL shapes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "kind"),
    [
        (f"https://github.com/{REPO}/issues/196#issuecomment-5672680663", "issue_comment"),
        (f"https://github.com/{REPO}/discussions/185#discussioncomment-18426101", "discussion_comment"),
        (f"https://github.com/{REPO}/issues/196", "issue_body"),
        (f"https://github.com/{REPO}/discussions/185", "discussion_body"),
        ("196", "bare_number"),
        ("#196", "bare_number"),
    ],
)
def test_parse_target_shapes(tc, target, kind):
    assert tc.parse_target(target)["kind"] == kind


def test_unsupported_target_is_rejected(tc):
    with pytest.raises(tc.TaskCommentError, match="unsupported target"):
        tc.parse_target("https://example.invalid/not-a-task")


def test_discussion_comment_resolves(tc, monkeypatch):
    discussion = {
        "url": f"https://github.com/{REPO}/discussions/185",
        "body": "root",
        "updatedAt": "2026-09-13T22:12:29Z",
        "author": {"login": "harrysun2006"},
        "comments": {
            "nodes": [
                {
                    "url": f"https://github.com/{REPO}/discussions/185#discussioncomment-18426101",
                    "databaseId": 18426101,
                    "updatedAt": "2026-09-13T22:28:58Z",
                    "body": "the task",
                    "author": {"login": "harrysun2006"},
                    "replies": {"nodes": []},
                }
            ]
        },
    }
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion}))
    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-18426101", REPO)
    assert got["body"] == "the task"
    assert got["kind"] == "discussion_comment"


def test_discussion_reply_resolves(tc, monkeypatch):
    """A task can be dispatched from a reply, so replies must resolve too."""
    discussion = {
        "url": f"https://github.com/{REPO}/discussions/185",
        "body": "root",
        "updatedAt": "2026-09-13T22:12:29Z",
        "author": {"login": "harrysun2006"},
        "comments": {
            "nodes": [
                {
                    "url": f"https://github.com/{REPO}/discussions/185#discussioncomment-1",
                    "databaseId": 1,
                    "updatedAt": "2026-09-13T22:12:29Z",
                    "body": "top level",
                    "author": {"login": "harrysun2006"},
                    "replies": {
                        "nodes": [
                            {
                                "url": f"https://github.com/{REPO}/discussions/185#discussioncomment-2",
                                "databaseId": 2,
                                "updatedAt": "2026-09-14T01:03:50Z",
                                "body": "the real task",
                                "author": {"login": "harrysun2006"},
                            }
                        ]
                    },
                }
            ]
        },
    }
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion}))
    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-2", REPO)
    assert got["body"] == "the real task"


def test_bare_number_resolves_to_issue_body(tc, monkeypatch):
    issue = {
        "html_url": f"https://github.com/{REPO}/issues/196",
        "user": {"login": "harrysun2006"},
        "updated_at": "2026-09-15T00:16:04Z",
        "body": "issue body task",
    }
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issues={"196": issue}))
    got = tc.fetch_target("#196", REPO)
    assert got["kind"] == "issue_body"
    assert got["body"] == "issue body task"


# --------------------------------------------------------------------------
# Pinning, provenance, and explicit dispatch
# --------------------------------------------------------------------------


def test_snapshot_records_pin_and_verbatim_body(tc, monkeypatch, tmp_path):
    body = "## Task\n\nline one\nline two\n"
    row = issue_comment_row("42", "harrysun2006", body)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"42": row}))
    task_dir = tmp_path / "runs" / "slug" / "run-1" / "task"
    assert tc.main(["fetch", row["html_url"], "--out", str(task_dir)]) == tc.EXIT_OK

    provenance, snapshot = tc.read_snapshot(task_dir)
    assert snapshot == body, "the snapshot must be verbatim"
    assert provenance["sha256"] == tc.body_sha256(body)
    for field in ("url", "comment_id", "author", "updated_at", "permission", "kind"):
        assert field in provenance


def test_fetch_refuses_before_writing_a_snapshot(tc, monkeypatch, tmp_path):
    """An unauthorized task leaves nothing behind for a later step to pick up."""
    row = issue_comment_row("7", "reader", "malicious instructions")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"reader": "read"}, issue_comments={"7": row}))
    task_dir = tmp_path / "task"
    assert tc.main(["fetch", row["html_url"], "--out", str(task_dir)]) == tc.EXIT_REFUSED
    assert not (task_dir / "comment.md").exists()


def test_hash_is_over_verbatim_body_bytes(tc):
    """Pin what is hashed: the raw body, not a re-terminated or normalized copy.

    An early probe for this contract piped the body through `jq -r`, which appends
    a newline, and produced a different pin for the identical comment. Two
    implementations that disagree here silently disagree about which task ran.
    """
    body = "line A\r\nline B  "
    assert tc.body_sha256(body) == hashlib.sha256(body.encode("utf-8")).hexdigest()
    # The three ways a naive implementation mangles it, each a distinct hash:
    # a tool-appended newline (`jq -r`), line-ending conversion, and stripping.
    assert tc.body_sha256(body) != tc.body_sha256(body + "\n")
    assert tc.body_sha256(body) != tc.body_sha256(body.replace("\r\n", "\n"))
    assert tc.body_sha256(body) != tc.body_sha256(body.strip())


def test_snapshot_round_trips_crlf_unchanged(tc, monkeypatch, tmp_path):
    """A CRLF body must survive write -> read, or every re-check reports REWRITTEN."""
    body = "## Task\r\n\r\ndo the thing\r\n"
    row = issue_comment_row("99", "harrysun2006", body)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"99": row}))
    task_dir = tmp_path / "task"
    assert tc.main(["fetch", row["html_url"], "--out", str(task_dir)]) == tc.EXIT_OK

    provenance, snapshot = tc.read_snapshot(task_dir)
    assert snapshot == body
    assert provenance["sha256"] == tc.body_sha256(body)
    assert tc.classify_change(snapshot, body) == "UNCHANGED"


def test_provenance_block_carries_url_and_hash(tc):
    provenance = {
        "url": f"https://github.com/{REPO}/issues/196#issuecomment-1",
        "sha256": "abc123",
        "author": "harrysun2006",
        "permission": "admin",
        "updated_at": "2026-09-15T00:15:48Z",
    }
    block = tc.provenance_block(provenance, "runs/slug/run-1")
    assert provenance["url"] in block
    assert "abc123" in block
    assert "runs/slug/run-1" in block


def test_no_discovery_mode_exists(tc):
    """Explicit dispatch is enforced by the absence of a way to find work.

    If a `scan` / `poll` / `latest` subcommand ever appears, a privileged author's
    comment becomes auto-executable and the contract's third property is gone.
    """
    parser = tc.build_parser()
    subparsers = [action for action in parser._actions if isinstance(action, __import__("argparse")._SubParsersAction)]
    assert subparsers, "resolver must expose subcommands"
    names = set(subparsers[0].choices)
    assert names == {"fetch", "recheck", "provenance"}
    for banned in ("scan", "poll", "latest", "watch", "auto"):
        assert banned not in names

    # And `fetch` cannot be invoked without a target.
    with pytest.raises(SystemExit):
        parser.parse_args(["fetch", "--out", "/tmp/x"])
