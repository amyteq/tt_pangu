"""Unit tests for scripts/exp_cc.py secret masking and defaults.

These exercise the pure helpers (no Claude transcripts, no network):
- mask_secret_body keeps the first/last MASK_KEEP chars and stars the rest.
- mask_secret_like_text masks every known secret shape in place, leaves
  surrounding markdown / variable names readable, collapses private-key
  blocks, and is idempotent.
- the CLI default output directory is `.agent/worklogs`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXP_CC_PATH = REPO_ROOT / "scripts" / "exp_cc.py"


def _load_exp_cc():
    spec = importlib.util.spec_from_file_location("exp_cc_under_test", EXP_CC_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


exp_cc = _load_exp_cc()


# --- mask_secret_body -------------------------------------------------------


def test_mask_keeps_three_chars_each_end():
    s = "ABCDEFGHIJKLMNOP"  # len 16
    masked = exp_cc.mask_secret_body(s)
    assert masked.startswith("ABC")
    assert masked.endswith("NOP")
    assert masked == "ABC" + "*" * (len(s) - 6) + "NOP"
    assert len(masked) == len(s)


def test_mask_short_secret_fully_masked():
    # Too short to keep both ends without overlap -> all stars.
    assert exp_cc.mask_secret_body("abcdef") == "******"
    assert exp_cc.mask_secret_body("abc") == "***"
    assert exp_cc.mask_secret_body("") == ""


# --- mask_secret_like_text --------------------------------------------------


def test_masks_anthropic_token_keeps_ends():
    token = "sk-ant-api03-" + "A" * 40
    masked = exp_cc.mask_secret_like_text(f"key is {token} here")
    assert token not in masked
    assert masked.startswith("key is sk-")  # first 3 chars of the token kept
    assert masked.endswith("AAA here")  # last 3 chars kept
    assert "*" in masked


def test_masks_github_pat():
    pat = "github_pat_" + "B" * 40
    masked = exp_cc.mask_secret_like_text(pat)
    assert pat not in masked
    assert masked.startswith("git")
    assert masked.endswith("BBB")


def test_assignment_keeps_variable_name_visible():
    line = "ANTHROPIC_API_KEY=sk-ant-secretvalue1234567890abc"
    masked = exp_cc.mask_secret_like_text(line)
    # The variable name and = stay readable; only the value is masked.
    assert masked.startswith("ANTHROPIC_API_KEY=sk-")
    assert "secretvalue1234567890" not in masked
    assert masked.endswith("abc")


def test_private_key_block_collapsed():
    block = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB\n"
        "MoreBase64HereThatIsDefinitelySecret==\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    masked = exp_cc.mask_secret_like_text(f"before\n{block}\nafter")
    assert "b3BlbnNzaC1rZXkt" not in masked
    assert "MoreBase64HereThatIsDefinitelySecret" not in masked
    assert "[REDACTED]" in masked
    assert "before" in masked and "after" in masked


def test_masking_is_idempotent():
    token = "ghp_" + "C" * 36
    once = exp_cc.mask_secret_like_text(token)
    twice = exp_cc.mask_secret_like_text(once)
    assert once == twice


def test_non_secret_text_untouched():
    text = "# Heading\n\nJust ordinary prose with a short word api.\n"
    assert exp_cc.mask_secret_like_text(text) == text


def test_scan_still_detects_after_pattern_refactor():
    token = "sk-ant-" + "D" * 30
    locations = exp_cc.scan_secret_like_lines(f"x = {token}")
    assert any(loc["label"] == "Anthropic API key" for loc in locations)


# --- CLI defaults -----------------------------------------------------------


def test_default_output_dir_is_local_worklogs():
    parser = exp_cc.build_parser()
    args = parser.parse_args([])
    assert args.output_dir == ".agent/worklogs"


# --- filename disambiguation (no overwrite on same name) --------------------


def _cand(
    name="",
    job_id="",
    session_id="",
    status="completed",
    source="test",
    state_path=None,
):
    from pathlib import Path

    return exp_cc.Candidate(
        source=source,
        job_id=job_id,
        session_id=session_id,
        name=name,
        status=status,
        cwd="",
        state_path=Path(state_path) if state_path else None,
        raw={},
    )


def test_unique_names_keep_clean_stem():
    cands = [_cand(name="M7"), _cand(name="M8")]
    assert exp_cc.assign_output_names(cands) == ["M7", "M8"]


def test_same_name_sessions_do_not_collide():
    cands = [
        _cand(name="loop", session_id="aaaaaaaa1111"),
        _cand(name="loop", session_id="bbbbbbbb2222"),
        _cand(name="solo"),
    ]
    names = exp_cc.assign_output_names(cands)
    assert len(set(names)) == 3  # no overwrite
    assert names[2] == "solo"  # unique name stays clean
    assert names[0].startswith("loop_") and names[1].startswith("loop_")
    # Stable: derived from the session id, so re-running yields the same stems.
    assert names[0] == "loop_aaaaaaaa"
    assert names[1] == "loop_bbbbbbbb"


def test_same_name_no_id_falls_back_to_counter():
    cands = [_cand(name="dup"), _cand(name="dup")]
    names = exp_cc.assign_output_names(cands)
    assert len(set(names)) == 2


# --- dedupe merges the same session from different sources ------------------


def test_dedupe_merges_same_session_id_across_sources():
    # The exact bug: one record from `claude agents --json` (session id, no job
    # id, non-terminal) and one from state.json (both ids, terminal). Same
    # session -> must collapse to ONE, not two dump files.
    cli = _cand(
        name="fix1",
        job_id="",
        session_id="12f67fe6-f215",
        status="working",
        source="claude agents --json",
    )
    state = _cand(
        name="fix1",
        job_id="12f67fe6",
        session_id="12f67fe6-f215",
        status="completed",
        source="state.json",
        state_path="/jobs/12f67fe6/state.json",
    )
    merged = exp_cc.dedupe([cli, state])
    assert len(merged) == 1
    m = merged[0]
    assert m.session_id == "12f67fe6-f215"
    assert m.job_id == "12f67fe6"  # filled from the state.json record
    assert m.status == "completed"  # terminal status preferred
    # ...and it now yields a single clean filename, no _<id> / _2 suffix.
    assert exp_cc.assign_output_names(merged) == ["fix1"]


def test_dedupe_keeps_genuinely_distinct_sessions():
    a = _cand(name="loop", session_id="aaaa-1")
    b = _cand(name="loop", session_id="bbbb-2")
    merged = exp_cc.dedupe([a, b])
    assert len(merged) == 2  # different session ids -> not merged


# --- header is content-only (no timestamp, no output path) ------------------


def test_header_has_no_timestamp_or_output():
    from pathlib import Path

    header = exp_cc.build_header(_cand(name="M7"), Path("/x/t.jsonl"))
    assert "Exported at" not in header
    assert "Output" not in header  # output path varied per run -> churn
    assert "Session name: `M7`" in header


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


def test_database_url_password_is_detected_and_masked():
    password = "SyntheticOnly" + "aB7%21" * 4
    text = "postgresql://demo:" + password + "@db.example.invalid/postgres"
    assert any(x["label"] == "database URL password" for x in exp_cc.scan_secret_like_lines(text))
    assert password not in exp_cc.mask_secret_like_text(text)
    assert "@db.example.invalid/postgres" in exp_cc.mask_secret_like_text(text)


def test_pgpassword_assignment_is_detected_and_masked():
    password = "SyntheticOnly" + "xY9" * 6
    text = "PGPASSWORD='" + password + "'"
    assert any(x["label"] == "Postgres env password" for x in exp_cc.scan_secret_like_lines(text))
    assert password not in exp_cc.mask_secret_like_text(text)


def test_secret_scan_diagnostics_withhold_the_entire_match():
    password = "SyntheticOnly" + "xY9" * 6
    text = "postgresql://demo:" + password + "@db.example.invalid/postgres"
    locations = exp_cc.scan_secret_like_lines(text)
    assert locations
    assert all(x["match_preview"] == "[redacted]" for x in locations)
    assert password[-3:] not in repr(locations)
