"""The task-comment contract (issue #196).

Phase 1 delivers tasks as GitHub comment URLs. `scripts/task_comment.py` is the
reference resolver; `docs/tooling/task-comment-contract.md` is the contract it
implements. These tests pin the four properties that make a mutable, publicly
writable comment safe to execute:

  1. explicit dispatch — no discovery mode exists;
  2. authorization on **effective repository permission**, never `authorAssociation`,
     and only on a trusted repository;
  3. pinning — body snapshot + `sha256`, verified on every read;
  4. the edit rule — append continues; rewrite, truncation or deletion stops at
     `WAIT_HUMAN`.

No test touches GitHub. Every lookup goes through `task_comment.run_gh`, which is
monkeypatched with a fake responder, so the permission endpoint in particular is
mocked rather than called. The fake pages GraphQL the way GitHub does, because
"the 101st comment" is a real failure mode and a one-node fixture cannot see it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVER = REPO_ROOT / "scripts" / "task_comment.py"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CONTRACT_MD = REPO_ROOT / "docs" / "tooling" / "task-comment-contract.md"

REPO = "amyteq/tt_pangu"
GRAPHQL_PAGE = 100


@pytest.fixture(scope="module")
def tc():
    spec = importlib.util.spec_from_file_location("task_comment", RESOLVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Fixtures: a fake `gh` that answers like the real one, including pagination
# --------------------------------------------------------------------------


def discussion(number: int, comments: list[dict], *, body: str = "root", author: str = "harrysun2006") -> dict:
    return {
        "number": number,
        "url": f"https://github.com/{REPO}/discussions/{number}",
        "body": body,
        "updatedAt": "2026-09-13T22:12:29Z",
        "author": author,
        "comments": comments,
    }


def comment(cid: int, body: str, *, author: str = "harrysun2006", replies: list[dict] | None = None) -> dict:
    return {
        "databaseId": cid,
        "id": f"DC_kwDO{cid}",
        "body": body,
        "author": author,
        "updatedAt": "2026-09-13T22:28:58Z",
        "replies": list(replies or []),
    }


def issue_comment_row(cid: str, author: str, body: str, updated: str = "2026-09-15T00:15:48Z", number: int = 196):
    return {
        "html_url": f"https://github.com/{REPO}/issues/{number}#issuecomment-{cid}",
        "id": int(cid),
        "user": {"login": author},
        "updated_at": updated,
        "body": body,
    }


def issue_row(number: int, author: str, body: str, **extra):
    row = {
        "html_url": f"https://github.com/{REPO}/issues/{number}",
        "user": {"login": author},
        "updated_at": "2026-09-15T00:16:04Z",
        "body": body,
    }
    row.update(extra)
    return row


def _graphql_variables(args: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    index = 0
    while index < len(args):
        if args[index] in ("-f", "-F") and index + 1 < len(args):
            key, _, value = args[index + 1].partition("=")
            variables[key] = value
            index += 2
        else:
            index += 1
    return variables


def _page(items: list, after: str | None, prefix: str) -> tuple[list, dict]:
    """Slice one GraphQL page and build its `pageInfo`, cursor scheme `prefix:offset`."""
    start = int(after.split(":", 1)[1]) if after else 0
    window = items[start : start + GRAPHQL_PAGE]
    has_next = len(items) > start + GRAPHQL_PAGE
    end_cursor = f"{prefix}:{start + GRAPHQL_PAGE}" if has_next else None
    return window, {"hasNextPage": has_next, "endCursor": end_cursor}


def _render_reply(number: int, reply: dict) -> dict:
    return {
        "url": f"https://github.com/{REPO}/discussions/{number}#discussioncomment-{reply['databaseId']}",
        "databaseId": reply["databaseId"],
        "updatedAt": reply["updatedAt"],
        "body": reply["body"],
        "author": {"login": reply["author"]},
    }


def make_gh(
    tc,
    *,
    permissions: dict[str, str] | None = None,
    issue_comments=None,
    issues=None,
    discussions=None,
    failures: dict[str, Exception] | None = None,
):
    """Build a fake `run_gh` from canned data.

    `permissions` maps a login to what `repos/{repo}/collaborators/{login}/permission`
    returns; a login that is absent raises `NotFoundError`, mimicking the 404 GitHub
    returns for a non-collaborator. `failures` maps a path fragment to an exception,
    so a 500 or a malformed answer can be told apart from a 404. Discussions are
    paged at 100 nodes, exactly like the real API.
    """
    permissions = permissions or {}
    issue_comments = issue_comments or {}
    issues = issues or {}
    discussions = discussions or {}
    failures = failures or {}
    calls: list[list[str]] = []

    by_node_id = {
        node["id"]: (disc["number"], node) for disc in discussions.values() for node in disc["comments"] if "id" in node
    }

    def _graphql(args: list[str]) -> str:
        variables = _graphql_variables(args)
        query = variables.pop("query", "")

        if "node(id:" in query:
            number, node = by_node_id[variables["commentId"]]
            window, page_info = _page(node["replies"], variables.get("after"), "r")
            replies = {"pageInfo": page_info, "nodes": [_render_reply(number, reply) for reply in window]}
            return json.dumps({"data": {"node": {"replies": replies}}})

        number = int(variables["number"])
        disc = discussions.get(number)
        if disc is None:
            return json.dumps({"data": {"repository": {"discussion": None}}})
        window, page_info = _page(disc["comments"], variables.get("after"), "c")
        nodes = []
        for node in window:
            reply_window, reply_info = _page(node["replies"], None, "r")
            nodes.append(
                {
                    "id": node["id"],
                    "url": f"https://github.com/{REPO}/discussions/{number}#discussioncomment-{node['databaseId']}",
                    "databaseId": node["databaseId"],
                    "updatedAt": node["updatedAt"],
                    "body": node["body"],
                    "author": {"login": node["author"]},
                    "replies": {
                        "pageInfo": reply_info,
                        "nodes": [_render_reply(number, reply) for reply in reply_window],
                    },
                }
            )
        payload = {
            "url": disc["url"],
            "body": disc["body"],
            "updatedAt": disc["updatedAt"],
            "author": {"login": disc["author"]},
            "comments": {"pageInfo": page_info, "nodes": nodes},
        }
        return json.dumps({"data": {"repository": {"discussion": payload}}})

    def fake_run_gh(args: list[str]) -> str:
        calls.append(args)
        if args[:2] == ["api", "graphql"]:
            return _graphql(args)

        path = args[1]
        for fragment, error in failures.items():
            if fragment in path:
                raise error
        if "/collaborators/" in path:
            login = path.split("/collaborators/", 1)[1].split("/", 1)[0]
            if login not in permissions:
                raise tc.NotFoundError("gh api failed: HTTP 404")
            return json.dumps({"permission": permissions[login]})
        if "/issues/comments/" in path:
            cid = path.rsplit("/", 1)[1]
            if cid not in issue_comments:
                raise tc.NotFoundError("gh api failed: HTTP 404")
            return json.dumps(issue_comments[cid])
        if "/issues/" in path:
            number = path.rsplit("/", 1)[1]
            if number not in issues:
                raise tc.NotFoundError("gh api failed: HTTP 404")
            return json.dumps(issues[number])
        raise AssertionError(f"unexpected gh call: {args}")

    fake_run_gh.calls = calls
    return fake_run_gh


def pin(tc, task_dir: Path, row: dict, permission: str = "admin") -> dict:
    """Fetch + authorize + snapshot, the state every re-check test starts from."""
    fetched = tc.fetch_target(row["html_url"], REPO)
    return tc.write_snapshot(task_dir, fetched, permission)


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
    with pytest.raises(tc.RefusedError) as excinfo:
        tc.authorize("reader", REPO)
    assert "refused:" in str(excinfo.value)
    assert f"permission={permission}" in str(excinfo.value), label


def test_non_collaborator_is_refused(tc, monkeypatch):
    """A 404 from the permission endpoint means `none`, not "unknown, proceed"."""
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={}))
    assert tc.effective_permission("stranger", REPO) == "none"
    with pytest.raises(tc.RefusedError, match="refused:"):
        tc.authorize("stranger", REPO)


def test_revoked_permission_is_refused_at_recheck(tc, monkeypatch, tmp_path):
    """Access is re-evaluated before a gated action, not trusted from the snapshot."""
    row = issue_comment_row("5672680663", "harrysun2006", "do the thing\n")

    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"5672680663": row}),
    )
    task_dir = tmp_path / "task"
    pin(tc, task_dir, row)

    # Permission revoked between dispatch and the gated action.
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={}, issue_comments={"5672680663": row}))
    assert tc.main(["recheck", str(task_dir)]) == tc.EXIT_REFUSED


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


def test_write_access_on_another_repository_is_not_write_access_here(tc, monkeypatch):
    """F003: trust is repository-scoped. `--repo` names a repo; it cannot extend the carve-out.

    Without this an admin of `attacker/evil` could dispatch a task from a comment
    on their own repository and pass the authorization check.
    """
    fake = make_gh(tc, permissions={"attacker": "admin"})
    monkeypatch.setattr(tc, "run_gh", fake)
    assert "attacker/evil" not in tc.TRUSTED_REPOS
    with pytest.raises(tc.RefusedError, match="not in the trusted set"):
        tc.authorize("attacker", "attacker/evil")
    # Refused before the login is even looked up.
    assert fake.calls == []


def test_fetch_from_an_untrusted_repo_exits_refused_and_writes_nothing(tc, monkeypatch, tmp_path):
    row = issue_comment_row("11", "attacker", "rm -rf things")
    row["html_url"] = "https://github.com/attacker/evil/issues/1#issuecomment-11"
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"attacker": "admin"}, issue_comments={"11": row}))
    task_dir = tmp_path / "task"
    argv = ["--repo", "attacker/evil", "fetch", row["html_url"], "--out", str(task_dir)]
    assert tc.main(argv) == tc.EXIT_REFUSED
    assert not task_dir.exists()


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
    ids=["unchanged", "appended", "rewritten", "truncated", "emptied"],
)
def test_classify_change(tc, old, new, expected):
    assert tc.classify_change(old, new) == expected


def test_appended_body_continues_and_can_adopt(tc, monkeypatch, tmp_path):
    original = "do the thing\n"
    row = issue_comment_row("1", "harrysun2006", original)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"1": row}))
    task_dir = tmp_path / "task"
    first = pin(tc, task_dir, row)

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
    pin(tc, task_dir, row)

    rewritten = issue_comment_row("2", "harrysun2006", "do something else entirely\n")
    monkeypatch.setattr(
        tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"2": rewritten})
    )

    assert tc.main(["recheck", str(task_dir), "--adopt"]) == tc.EXIT_REWRITTEN
    # A rewrite must never be adopted, even with --adopt.
    assert (task_dir / "comment.md").read_text(encoding="utf-8") == original


def test_deleted_source_comment_stops_at_wait_human(tc, monkeypatch, tmp_path, capsys):
    """F006: deletion is truncation taken to its limit — stop, do not exit `2`.

    The API-level case, not `classify_change("body", "")`: the comment object is
    gone, so the lookup 404s and there is no body to classify at all.
    """
    row = issue_comment_row("3", "harrysun2006", "do the thing\n")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"3": row}))
    task_dir = tmp_path / "task"
    pin(tc, task_dir, row)

    # The author deleted the comment between dispatch and the gated action.
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={}))
    assert tc.main(["recheck", str(task_dir), "--adopt"]) == tc.EXIT_REWRITTEN
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "DELETED"
    assert result["new_sha256"] is None
    assert (task_dir / "comment.md").read_text(encoding="utf-8") == "do the thing\n"


def test_deleted_discussion_comment_stops_at_wait_human(tc, monkeypatch, tmp_path, capsys):
    """The same, through GraphQL: the discussion survives, the comment does not."""
    node = comment(18426101, "the task")
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, [node])}),
    )
    url = f"https://github.com/{REPO}/discussions/185#discussioncomment-18426101"
    task_dir = tmp_path / "task"
    tc.write_snapshot(task_dir, tc.fetch_target(url, REPO), "admin")

    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, [])}),
    )
    assert tc.main(["recheck", str(task_dir)]) == tc.EXIT_REWRITTEN
    assert json.loads(capsys.readouterr().out)["status"] == "DELETED"


def test_recheck_stops_when_the_url_resolves_to_a_different_object(tc, monkeypatch, tmp_path, capsys):
    """A pinned URL that now answers with another comment id is not "unchanged"."""
    row = issue_comment_row("4", "harrysun2006", "do the thing\n")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"4": row}))
    task_dir = tmp_path / "task"
    pin(tc, task_dir, row)

    provenance = json.loads((task_dir / "provenance.json").read_text(encoding="utf-8"))
    provenance["comment_id"] = "999"
    (task_dir / "provenance.json").write_text(json.dumps(provenance) + "\n", encoding="utf-8")

    assert tc.main(["recheck", str(task_dir)]) == tc.EXIT_REWRITTEN
    assert json.loads(capsys.readouterr().out)["status"] == "MISMATCH"


# --------------------------------------------------------------------------
# URL shapes — host-, repository- and whole-string-bound
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target", "kind"),
    [
        (f"https://github.com/{REPO}/issues/196#issuecomment-5672680663", "issue_comment"),
        (f"https://github.com/{REPO}/discussions/185#discussioncomment-18426101", "discussion_comment"),
        (f"https://github.com/{REPO}/issues/196", "issue_body"),
        (f"https://github.com/{REPO}/discussions/185", "discussion_body"),
        (f"https://github.com/{REPO}/issues/196/", "issue_body"),
        (f"http://www.github.com/{REPO}/issues/196", "issue_body"),
        ("196", "bare_number"),
        ("#196", "bare_number"),
    ],
)
def test_parse_target_shapes(tc, target, kind):
    assert tc.parse_target(target)["kind"] == kind


@pytest.mark.parametrize(
    ("target", "why"),
    [
        ("https://example.invalid/not-a-task", "not a GitHub item URL"),
        (f"https://evil.example/{REPO}/issues/196#issuecomment-1", "another host wearing our path"),
        ("https://github.com/attacker/evil/issues/196#issuecomment-1", "another repository"),
        (f"https://github.com.evil.example/{REPO}/issues/196", "lookalike host"),
        (f"see https://github.com/{REPO}/issues/196 for details", "URL buried in prose"),
        (f"https://github.com/{REPO}/issues/196#discussioncomment-1", "anchor of the wrong kind"),
        (f"https://github.com/{REPO}/pull/228#issuecomment-1", "pull request"),
        (f"https://github.com/{REPO}/issues/196#issuecomment-1 && rm -rf /", "trailing payload"),
    ],
)
def test_out_of_scope_targets_are_rejected(tc, target, why):
    """F003: the target is matched whole, against this host and this repository.

    An unanchored `search` accepted every one of these: a different host, a
    different repository, and a URL with text around it.
    """
    with pytest.raises(tc.TaskCommentError) as excinfo:
        tc.parse_target(target, REPO)
    assert isinstance(excinfo.value, tc.UnsupportedTargetError), why


def test_parse_target_binds_to_the_repo_it_is_given(tc):
    """The same URL is in scope for its own repository and out of scope for another."""
    url = f"https://github.com/{REPO}/issues/196"
    assert tc.parse_target(url, REPO)["kind"] == "issue_body"
    with pytest.raises(tc.UnsupportedTargetError, match="out-of-scope"):
        tc.parse_target(url, "other/repo")


def test_unsupported_target_is_rejected(tc):
    with pytest.raises(tc.TaskCommentError, match="unsupported target"):
        tc.parse_target("https://example.invalid/not-a-task")


def test_issue_comment_from_another_issue_is_rejected(tc, monkeypatch):
    """Comment ids are global: `issues/comments/{id}` will answer for any issue or PR."""
    row = issue_comment_row("77", "harrysun2006", "a task for another thread", number=42)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"77": row}))
    with pytest.raises(tc.TaskCommentError, match="not issue #196"):
        tc.fetch_target(f"https://github.com/{REPO}/issues/196#issuecomment-77", REPO)


def test_discussion_comment_resolves(tc, monkeypatch):
    node = comment(18426101, "the task")
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, [node])}),
    )
    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-18426101", REPO)
    assert got["body"] == "the task"
    assert got["kind"] == "discussion_comment"


def test_discussion_reply_resolves(tc, monkeypatch):
    """A task can be dispatched from a reply, so replies must resolve too."""
    node = comment(1, "top level", replies=[comment(2, "the real task")])
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, [node])}),
    )
    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-2", REPO)
    assert got["body"] == "the real task"


def test_discussion_comment_past_the_first_page_resolves(tc, monkeypatch):
    """F004: `first:100` with no pagination reports the 101st comment as missing."""
    nodes = [comment(cid, f"comment {cid}") for cid in range(1, 151)]
    fake = make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, nodes)})
    monkeypatch.setattr(tc, "run_gh", fake)

    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-150", REPO)
    assert got["body"] == "comment 150"
    graphql_calls = [call for call in fake.calls if call[:2] == ["api", "graphql"]]
    assert len(graphql_calls) == 2, "the second page must actually be requested"


def test_discussion_reply_past_the_first_page_resolves(tc, monkeypatch):
    """Replies page independently of their parent comment, so they page too."""
    replies = [comment(cid, f"reply {cid}") for cid in range(1000, 1000 + 250)]
    nodes = [comment(1, "top level", replies=replies)]
    fake = make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, nodes)})
    monkeypatch.setattr(tc, "run_gh", fake)

    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-1249", REPO)
    assert got["body"] == "reply 1249"
    reply_calls = [call for call in fake.calls if any("commentId=" in arg for arg in call)]
    assert len(reply_calls) == 2, "replies 101-250 need two further pages"


def test_missing_discussion_comment_is_not_found(tc, monkeypatch):
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: discussion(185, [comment(1, "x")])}),
    )
    with pytest.raises(tc.NotFoundError, match="not found"):
        tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-999", REPO)


# --------------------------------------------------------------------------
# Bare numbers — the fallback may only swallow a genuine 404
# --------------------------------------------------------------------------


def test_bare_number_resolves_to_issue_body(tc, monkeypatch):
    issue = issue_row(196, "harrysun2006", "issue body task")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issues={"196": issue}))
    got = tc.fetch_target("#196", REPO)
    assert got["kind"] == "issue_body"
    assert got["body"] == "issue body task"


def test_bare_number_falls_back_to_the_discussion_on_a_real_404(tc, monkeypatch):
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(
            tc,
            permissions={"harrysun2006": "admin"},
            issues={},
            discussions={185: discussion(185, [], body="discussion body task")},
        ),
    )
    got = tc.fetch_target("185", REPO)
    assert got["kind"] == "discussion_body"
    assert got["body"] == "discussion body task"


@pytest.mark.parametrize(
    "stderr",
    ["gh api failed: HTTP 500", "gh api failed: HTTP 403 (SAML enforcement)", "gh api returned non-JSON output"],
)
def test_bare_number_does_not_fall_back_on_a_non_404_failure(tc, monkeypatch, stderr):
    """F002: a 500, an auth failure or a garbled answer is not "this is not an issue".

    Falling through to a same-numbered discussion executes a different task than
    the one that was dispatched. The injected error is the *base* class, so this
    is a behaviour test: the old `except TaskCommentError` swallowed all three
    and returned the discussion body.
    """
    monkeypatch.setattr(
        tc,
        "run_gh",
        make_gh(
            tc,
            permissions={"harrysun2006": "admin"},
            discussions={196: discussion(196, [], body="a DIFFERENT task")},
            failures={"/issues/196": tc.TaskCommentError(stderr)},
        ),
    )
    with pytest.raises(tc.TaskCommentError) as excinfo:
        tc.fetch_target("196", REPO)
    assert str(excinfo.value) == stderr, "the real failure must surface, not a fallback"


def test_pull_request_is_not_an_issue_task(tc, monkeypatch):
    """F002: `repos/{repo}/issues/{n}` also serves pull requests."""
    row = issue_row(228, "harrysun2006", "PR description", pull_request={"url": "..."})
    row["html_url"] = f"https://github.com/{REPO}/pull/228"
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issues={"228": row}))
    with pytest.raises(tc.TaskCommentError, match="pull request") as excinfo:
        tc.fetch_target("228", REPO)
    assert isinstance(excinfo.value, tc.UnsupportedTargetError)


def test_run_gh_maps_404_to_not_found_and_everything_else_to_gh_error(tc, monkeypatch):
    """The 404-vs-other distinction the fallback depends on is made at the seam."""

    def fake_subprocess_run(argv, **kwargs):
        stderr = fake_subprocess_run.stderr
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr=stderr)

    monkeypatch.setattr(tc.subprocess, "run", fake_subprocess_run)

    fake_subprocess_run.stderr = "gh: Not Found (HTTP 404)"
    with pytest.raises(tc.NotFoundError):
        tc.run_gh(["api", "repos/x/y/issues/1"])

    fake_subprocess_run.stderr = "gh: Internal Server Error (HTTP 500)"
    with pytest.raises(tc.GhError) as excinfo:
        tc.run_gh(["api", "repos/x/y/issues/1"])
    assert not isinstance(excinfo.value, tc.NotFoundError)


def test_unusable_api_response_exits_with_a_documented_code(tc, monkeypatch, tmp_path):
    """F006: a shape surprise must not escape as an undocumented exit `1`."""
    monkeypatch.setattr(
        tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issues={"196": {"body": "no html_url"}})
    )
    with pytest.raises(tc.MalformedResponseError):
        tc.fetch_target("196", REPO)
    argv = ["fetch", f"https://github.com/{REPO}/issues/196", "--out", str(tmp_path / "task")]
    assert tc.main(argv) == tc.EXIT_USAGE


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
    for field in ("url", "comment_id", "author", "updated_at", "permission", "kind", "attachments"):
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


def test_recheck_refuses_a_snapshot_that_does_not_match_its_own_pin(tc, monkeypatch, tmp_path):
    """F001: classify the *pinned* body, never whatever bytes happen to be on disk.

    Provenance for body A beside a local body B returned `UNCHANGED` when the live
    body was also B — blessing text that was never pinned and printing provenance
    that describes different bytes.
    """
    pinned_body = "do the thing\n"
    row = issue_comment_row("5", "harrysun2006", pinned_body)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"5": row}))
    task_dir = tmp_path / "task"
    provenance = pin(tc, task_dir, row)

    # The live comment and the local file agree; only the pin disagrees.
    tampered = "do something else entirely\n"
    (task_dir / "comment.md").write_bytes(tampered.encode("utf-8"))
    row_live = issue_comment_row("5", "harrysun2006", tampered)
    monkeypatch.setattr(
        tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"5": row_live})
    )

    assert tc.classify_change(tampered, row_live["body"]) == "UNCHANGED", "the old code's comparison"
    assert tc.main(["recheck", str(task_dir)]) == tc.EXIT_REWRITTEN
    with pytest.raises(tc.SnapshotIntegrityError, match="does not match its pin"):
        tc.read_snapshot(task_dir)
    assert provenance["sha256"] == tc.body_sha256(pinned_body)


def test_provenance_of_a_tampered_snapshot_is_not_printed(tc, monkeypatch, tmp_path, capsys):
    """The same check guards the block posted back to the tracking issue."""
    row = issue_comment_row("6", "harrysun2006", "do the thing\n")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"6": row}))
    task_dir = tmp_path / "task"
    pin(tc, task_dir, row)
    (task_dir / "comment.md").write_bytes(b"different bytes\n")

    assert tc.main(["provenance", str(task_dir)]) == tc.EXIT_REWRITTEN
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("label", "mutate", "expected"),
    [
        ("missing snapshot", None, "EXIT_USAGE"),
        ("unparseable provenance", "{not json", "EXIT_REWRITTEN"),
    ],
)
def test_broken_snapshots_exit_with_documented_codes(tc, tmp_path, label, mutate, expected):
    """F006: a malformed snapshot escaped as an undocumented exit `1`."""
    task_dir = tmp_path / "task"
    if mutate is not None:
        task_dir.mkdir()
        (task_dir / "provenance.json").write_text(mutate, encoding="utf-8")
        (task_dir / "comment.md").write_text("body", encoding="utf-8")
    assert tc.main(["recheck", str(task_dir)]) == getattr(tc, expected)


def test_snapshot_writes_are_atomic(tc, monkeypatch, tmp_path):
    """An interrupted write must not leave a half-file that reads as the pinned body."""
    replaced: list[tuple[str, str]] = []
    real_replace = tc.os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(tc.os, "replace", spy)
    row = issue_comment_row("8", "harrysun2006", "do the thing\n")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"8": row}))
    task_dir = tmp_path / "task"
    pin(tc, task_dir, row)

    assert [Path(dst).name for _, dst in replaced] == ["comment.md", "provenance.json"]
    assert not list(task_dir.glob("*.tmp"))


# --------------------------------------------------------------------------
# Attachments — F007, the provenance schema the contract promises
# --------------------------------------------------------------------------


def test_attachment_urls_are_recorded_in_provenance(tc, monkeypatch, tmp_path):
    body = (
        "## Task\n\n"
        "![screenshot](https://github.com/user-attachments/assets/abc-123)\n"
        '<img src="https://user-images.githubusercontent.com/1/two.png" width="400">\n'
        "bare: https://github.com/user-attachments/assets/def-456\n"
        "not an attachment: https://example.com/page and [a link](https://example.com/doc)\n"
    )
    row = issue_comment_row("55", "harrysun2006", body)
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"55": row}))
    task_dir = tmp_path / "task"
    assert tc.main(["fetch", row["html_url"], "--out", str(task_dir)]) == tc.EXIT_OK

    provenance, _ = tc.read_snapshot(task_dir)
    assert provenance["attachments"] == [
        "https://github.com/user-attachments/assets/abc-123",
        "https://github.com/user-attachments/assets/def-456",
        "https://user-images.githubusercontent.com/1/two.png",
    ]
    block = tc.provenance_block(provenance, "runs/slug/run-1")
    for url in provenance["attachments"]:
        assert f"attachment: {url}" in block


def test_a_body_without_attachments_records_an_empty_list(tc):
    assert tc.extract_attachments("plain task text, https://example.com/not-an-asset\n") == []


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


# --------------------------------------------------------------------------
# The trust surface — F005: CLAUDE.md, the contract and the resolver agree
# --------------------------------------------------------------------------

CARVE_OUT_RE = re.compile(r"One deliberate exception, and only one: \*\*(?P<sentence>.+?)\*\*", re.DOTALL)

# One phrase per kind the resolver will promote from data to instruction. If a
# kind is added, `CLAUDE.md` has to name it here or the surfaces have drifted.
KIND_PHRASES = {
    "issue_comment": "issue comment",
    "discussion_comment": "discussion comment or reply",
    "issue_body": "body of an issue or discussion",
    "discussion_body": "body of an issue or discussion",
}


def carve_out_sentence() -> str:
    match = CARVE_OUT_RE.search(CLAUDE_MD.read_text(encoding="utf-8"))
    assert match, "CLAUDE.md principle 1 no longer states the trust carve-out"
    return match["sentence"].strip()


def test_carve_out_covers_exactly_the_kinds_the_resolver_resolves(tc):
    """F005: `CLAUDE.md` granted instruction status to "a comment"; the resolver also
    executes issue and discussion bodies. A harness reading one and a harness reading
    the other disagreed about what is executable."""
    sentence = carve_out_sentence()
    assert set(KIND_PHRASES) == set(tc.SUPPORTED_KINDS)
    for kind, phrase in KIND_PHRASES.items():
        assert phrase in sentence, f"{kind} is resolvable but CLAUDE.md does not name it"


def test_carve_out_excludes_every_other_github_surface():
    sentence = carve_out_sentence()
    for excluded in ("pull-request", "commit comments", "wikis", "gists"):
        assert excluded in sentence, f"the carve-out must say {excluded} stay data"
    assert "this repository" in sentence or "*this* repository" in sentence


def test_the_contract_quotes_the_carve_out_verbatim():
    """The document explains the rule; `CLAUDE.md` *is* the rule. A paraphrase drifts."""
    quoted = f"> {carve_out_sentence()}"
    assert quoted in CONTRACT_MD.read_text(encoding="utf-8"), "the contract's quote no longer matches CLAUDE.md"
