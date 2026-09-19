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


@pytest.mark.parametrize(
    ("target", "why"),
    [
        (f"https://gİthub.com/{REPO}/issues/196#issuecomment-1", "U+0130 folds to `i` under Unicode IGNORECASE"),
        (f"https://github.com/{REPO}/iſſues/196", "U+017F folds to `s`, so `iſſues` matched `issues`"),
        ("１９６", "fullwidth digits are `\\d`, and `int()` reads them as 196"),
        ("١٩٦", "Arabic-Indic digits, likewise"),
        (f"https://github.com/{REPO}/issues/١٩٦", "non-ASCII digits inside a URL"),
    ],
    ids=["dotted-capital-i-host", "long-s-path", "fullwidth-number", "arabic-indic-number", "non-ascii-in-url"],
)
def test_non_ascii_lookalike_targets_are_rejected(tc, target, why):
    """F003: Python's case-insensitive matching folds Unicode, and `\\d` is Unicode-wide.

    `gİthub.com` full-matched the host pattern and resolved as an ordinary
    `issue_comment` against the real repository — a lookalike address treated as
    trusted. Non-ASCII digits are the same bug in the number: `int("١٩٦") == 196`.
    """
    with pytest.raises(tc.UnsupportedTargetError) as excinfo:
        tc.parse_target(target, REPO)
    assert "must be plain ASCII" in str(excinfo.value), why


@pytest.mark.parametrize(
    ("target", "kind"),
    [
        (f"https://github.com/{REPO}/ISSUES/196", "issue_body"),
        (f"https://github.com/{REPO}/Discussions/185", "discussion_body"),
        (f"https://github.com/{REPO}/issues/196#ISSUECOMMENT-1", "issue_comment"),
    ],
)
def test_a_case_shifted_path_resolves_to_the_object_it_reads_as(tc, target, kind):
    """F003: the host pattern is case-insensitive, so the captured noun could be `ISSUES`.

    `"ISSUES" == "issues"` is False, and the kind was chosen by that comparison —
    so `/ISSUES/196` fell through to `discussion_body` and a URL that reads
    "issue 196" fetched *discussion* 196.
    """
    assert tc.parse_target(target, REPO)["kind"] == kind


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


def test_a_different_comment_on_the_same_issue_is_rejected(tc, monkeypatch):
    """F003: bind the object's identity, not just the issue it sits on.

    The container check (`is this comment on issue #196?`) passes for every
    comment on the issue. A response requested as comment `77` that carries
    `html_url` and `id` for comment `88` was pinned as if it were `77`, and
    `recheck` would then follow the substituted URL for the rest of the run.
    """
    row = issue_comment_row("88", "harrysun2006", "a different comment on the same issue")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"77": row}))
    with pytest.raises(tc.UnsupportedTargetError) as excinfo:
        tc.fetch_target(f"https://github.com/{REPO}/issues/196#issuecomment-77", REPO)
    assert "88" in str(excinfo.value)


def test_a_returned_id_that_contradicts_its_own_anchor_is_rejected(tc, monkeypatch):
    """Anchor and `id` are checked independently — one can lie while the other agrees."""
    row = issue_comment_row("77", "harrysun2006", "body")
    row["id"] = 88  # the anchor says 77, the object says 88
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"77": row}))
    with pytest.raises(tc.UnsupportedTargetError, match="returned comment id 88"):
        tc.fetch_target(f"https://github.com/{REPO}/issues/196#issuecomment-77", REPO)


def test_discussion_comment_whose_url_points_elsewhere_is_rejected(tc, monkeypatch):
    """The GraphQL node is bound to its address too, not only to its `databaseId`.

    `provenance["url"]` is what every later re-check re-fetches, so a node whose
    `url` names another discussion would move the pin to a thread nobody
    dispatched.
    """
    payload = {
        "data": {
            "repository": {
                "discussion": {
                    "url": f"https://github.com/{REPO}/discussions/185",
                    "body": "root",
                    "updatedAt": "2026-09-13T22:12:29Z",
                    "author": {"login": "harrysun2006"},
                    "comments": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "DC_kwDO7",
                                "databaseId": 7,
                                "url": f"https://github.com/{REPO}/discussions/999#discussioncomment-7",
                                "updatedAt": "2026-09-13T22:28:58Z",
                                "body": "the task",
                                "author": {"login": "harrysun2006"},
                                "replies": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
                            }
                        ],
                    },
                }
            }
        }
    }
    monkeypatch.setattr(tc, "run_gh", lambda args: json.dumps(payload))
    with pytest.raises(tc.UnsupportedTargetError, match="discussion #185"):
        tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-7", REPO)


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


def _graphql_calls(fake) -> int:
    return len([call for call in fake.calls if call[:2] == ["api", "graphql"]])


def big_discussion(number: int = 185, *, comments: int = 101, replies: int = 101, body: str = "the body") -> dict:
    """A thread long enough that eager expansion costs a request per reply page."""
    nodes = [
        comment(cid, f"comment {cid}", replies=[comment(cid * 10_000 + i, f"reply {i}") for i in range(replies)])
        for cid in range(1, comments + 1)
    ]
    return discussion(number, nodes, body=body)


def test_a_discussion_body_costs_one_graphql_call(tc, monkeypatch):
    """F008: the body is in the first response; the comment connection is not needed.

    Body resolution went through the exhaustive path anyway — 103 calls for a
    discussion with 101 comments and 101 replies each, for a field that arrived
    in call one.
    """
    fake = make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: big_discussion()})
    monkeypatch.setattr(tc, "run_gh", fake)

    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185", REPO)
    assert got["body"] == "the body"
    assert _graphql_calls(fake) == 1


def test_finding_an_early_comment_does_not_expand_the_whole_thread(tc, monkeypatch):
    """F008: pages are searched as they arrive, and reply threads only if needed."""
    fake = make_gh(tc, permissions={"harrysun2006": "admin"}, discussions={185: big_discussion()})
    monkeypatch.setattr(tc, "run_gh", fake)

    got = tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-1", REPO)
    assert got["body"] == "comment 1"
    assert _graphql_calls(fake) == 1, "the target is on the first page; nothing else has to be fetched"


def test_the_page_cap_is_one_budget_for_the_whole_lookup(tc, monkeypatch):
    """F008: a per-connection cap multiplies by the number of reply threads.

    With a cap of N pages *each*, a discussion with T threads could spend N*T
    requests before giving up. One budget for the lookup stops at N.
    """
    monkeypatch.setattr(tc, "MAX_GRAPHQL_PAGES", 3)
    fake = make_gh(
        tc,
        permissions={"harrysun2006": "admin"},
        discussions={185: big_discussion(comments=5, replies=150)},
    )
    monkeypatch.setattr(tc, "run_gh", fake)

    with pytest.raises(tc.GhError, match="budget"):
        tc.fetch_target(f"https://github.com/{REPO}/discussions/185#discussioncomment-404404", REPO)
    assert _graphql_calls(fake) == 3, "the budget is spent across connections, not restarted per thread"


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


def test_a_missing_gh_binary_exits_with_a_documented_code(tc, monkeypatch, tmp_path, capsys):
    """F006: process-launch failure happens before any HTTP status exists.

    `subprocess.run(["gh", ...])` raised `FileNotFoundError` straight out of the
    resolver, so a machine without the GitHub CLI got exit `1` and a traceback —
    a code the contract does not define and a caller cannot classify.
    """

    def no_gh(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "gh")

    monkeypatch.setattr(tc.subprocess, "run", no_gh)
    with pytest.raises(tc.GhError, match="gh could not be run"):
        tc.run_gh(["api", "repos/x/y/issues/1"])
    assert tc.main(["fetch", "196", "--out", str(tmp_path / "task")]) == tc.EXIT_USAGE
    assert "GitHub CLI must be installed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "payload",
    [{"errors": ["boom"]}, {"errors": "boom"}, {"errors": [{"message": "boom"}]}],
    ids=["list-of-strings", "bare-string", "documented-shape"],
)
def test_graphql_error_payloads_of_any_shape_are_reported_not_raised(tc, monkeypatch, payload):
    """F006: `{"errors": ["boom"]}` raised `AttributeError` — untyped, exit `1`."""
    assert tc._graphql_errors(payload) == "boom"
    monkeypatch.setattr(tc, "run_gh", lambda args: json.dumps(payload))
    with pytest.raises(tc.GhError, match="boom"):
        tc.fetch_target(f"https://github.com/{REPO}/discussions/185", REPO)


def test_an_unexpected_internal_error_exits_seventy_not_one(tc, monkeypatch, tmp_path, capsys):
    """F006: the catch-all. A bug is still a failure, and `1` is not a documented code.

    Anything the module does not raise deliberately — here a write that fails —
    lands on `70` (`EX_SOFTWARE`) with nothing on stdout, so no caller can read a
    crash as a result.
    """
    row = issue_comment_row("31", "harrysun2006", "do the thing\n")
    monkeypatch.setattr(tc, "run_gh", make_gh(tc, permissions={"harrysun2006": "admin"}, issue_comments={"31": row}))

    def boom(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(tc, "write_snapshot", boom)
    assert tc.main(["fetch", row["html_url"], "--out", str(tmp_path / "task")]) == tc.EXIT_INTERNAL
    captured = capsys.readouterr()
    assert captured.out == "", "a crash must not print anything a caller could read as a result"
    assert "internal error" in captured.err


def test_every_exit_code_the_resolver_can_return_is_documented():
    """The exit surface is the interface, so the document has to list all of it."""
    contract = CONTRACT_MD.read_text(encoding="utf-8")
    for code in ("0", "2", "3", "10", "20", "70"):
        assert f"| `{code}` |" in contract, f"exit {code} is reachable but the contract does not document it"


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


def test_image_syntax_inside_code_is_not_an_attachment(tc):
    """F009: a fenced block or a code span *displays* markdown, it does not reference it.

    A task that documents this very format had its own example recorded as a live
    attachment, which puts a fact in `provenance.json` and in the posted block
    that is simply not true of the comment.
    """
    body = (
        "## Task\n\n"
        "Write the block like this:\n\n"
        "```markdown\n"
        "![example](https://github.com/user-attachments/assets/in-a-fence)\n"
        "```\n\n"
        "~~~\n"
        '<img src="https://user-images.githubusercontent.com/1/in-a-tilde-fence.png">\n'
        "~~~\n\n"
        "Inline: `https://github.com/user-attachments/assets/in-a-span` is the shape.\n\n"
        "The actual screenshot: ![real](https://github.com/user-attachments/assets/real)\n"
    )
    assert tc.extract_attachments(body) == ["https://github.com/user-attachments/assets/real"]


def test_a_bare_asset_url_does_not_swallow_a_trailing_backtick(tc):
    """F009: the recorded URL was `…/asset``, which resolves to nothing."""
    body = "see https://github.com/user-attachments/assets/asset` for the screenshot\n"
    assert tc.extract_attachments(body) == ["https://github.com/user-attachments/assets/asset"]


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

# One row per kind the resolver promotes from data to instruction: the URL a
# human would actually be handed, and the phrase `CLAUDE.md` has to use for it.
# Checked against `SUPPORTED_KINDS`, so a new kind fails here until both the rule
# and a resolvable address exist for it.
TRUSTED_SURFACE = {
    "issue_comment": (f"https://github.com/{REPO}/issues/196#issuecomment-1", "comment on an issue"),
    "discussion_comment": (
        f"https://github.com/{REPO}/discussions/185#discussioncomment-1",
        "comment or reply on a discussion",
    ),
    "issue_body": (f"https://github.com/{REPO}/issues/196", "body of an issue or discussion"),
    "discussion_body": (f"https://github.com/{REPO}/discussions/185", "body of an issue or discussion"),
}

# The other direction: surfaces that stay data, each with the word the rule has to
# use to say so. Phrase-presence alone cannot catch prose *broader* than the
# resolver — "an issue comment" reads as covering PR conversation comments, which
# the resolver rejects — so every row asserts both sides at once.
UNTRUSTED_SURFACE = [
    (f"https://github.com/{REPO}/pull/228#issuecomment-1", "conversation comments", "PR conversation comment"),
    (f"https://github.com/{REPO}/pull/228", "pull-request bodies", "PR body"),
    (f"https://github.com/{REPO}/pull/228#discussion_r1", "review comments", "PR review comment"),
    (f"https://github.com/{REPO}/commit/deadbeef#commitcomment-1", "commit comments", "commit comment"),
    (f"https://github.com/{REPO}/wiki/Home", "wikis", "wiki page"),
    ("https://gist.github.com/harrysun2006/abc123", "gists", "gist"),
    (f"https://github.com/{REPO}/releases/tag/v1", "releases", "release"),
]


def carve_out_sentence() -> str:
    match = CARVE_OUT_RE.search(CLAUDE_MD.read_text(encoding="utf-8"))
    assert match, "CLAUDE.md principle 1 no longer states the trust carve-out"
    return match["sentence"].strip()


def test_trusted_surface_is_the_same_in_the_rule_and_in_the_resolver(tc):
    """F005: `CLAUDE.md` granted instruction status to "a comment"; the resolver also
    executes issue and discussion bodies. A harness reading one and a harness reading
    the other disagreed about what is executable."""
    sentence = carve_out_sentence()
    assert set(TRUSTED_SURFACE) == set(tc.SUPPORTED_KINDS)
    for kind, (url, phrase) in TRUSTED_SURFACE.items():
        assert tc.parse_target(url, REPO)["kind"] == kind, f"{kind} is named in the rule but does not resolve"
        assert phrase in sentence, f"{kind} is resolvable but CLAUDE.md does not name it"


def test_untrusted_surfaces_are_refused_by_the_resolver_and_named_by_the_rule(tc):
    """Every excluded surface has to be refused *and* said out loud.

    A surface the resolver rejects but the rule does not mention is prose broader
    than the runtime — exactly the F005 drift — and a surface the rule excludes
    but the resolver accepts is worse.
    """
    sentence = carve_out_sentence()
    for url, phrase, label in UNTRUSTED_SURFACE:
        with pytest.raises(tc.UnsupportedTargetError):
            tc.parse_target(url, REPO)
        assert phrase in sentence, f"the rule does not say a {label} stays data"


def test_a_pull_request_conversation_comment_is_data_in_both(tc):
    """F005: GitHub's `issues/comments/{id}` serves PR conversation comments too.

    In GitHub's data model a PR conversation comment *is* an issue comment; only
    its `html_url` (`/pull/<n>#issuecomment-<id>`) tells them apart, and the
    resolver matches `/issues/` and `/discussions/` alone. So the rule cannot
    just say "an issue comment" — a reader applying GitHub's sense of the term
    would trust a surface the runtime refuses.
    """
    sentence = carve_out_sentence()
    with pytest.raises(tc.UnsupportedTargetError):
        tc.parse_target(f"https://github.com/{REPO}/pull/228#issuecomment-1", REPO)
    assert "`/pull/` URL is data" in sentence
    assert "issues/comments/{id}" in sentence
    assert "comment *on an issue*" in sentence


def test_carve_out_excludes_every_other_github_surface():
    sentence = carve_out_sentence()
    for excluded in ("pull-request", "commit comments", "wikis", "gists"):
        assert excluded in sentence, f"the carve-out must say {excluded} stay data"
    assert "this repository" in sentence or "*this* repository" in sentence


def test_the_contract_quotes_the_carve_out_verbatim():
    """The document explains the rule; `CLAUDE.md` *is* the rule. A paraphrase drifts."""
    quoted = f"> {carve_out_sentence()}"
    assert quoted in CONTRACT_MD.read_text(encoding="utf-8"), "the contract's quote no longer matches CLAUDE.md"
