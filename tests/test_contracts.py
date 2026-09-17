"""ADR-0023 ledger contracts — schemas, the validator, and the real records.

Three things are being checked, and they are different kinds of check:

1. **The repository's real records validate**, and every entity has at least one.
   This is issue #191's acceptance criterion, and it runs against the actual
   `competitions/` tree rather than a fixture, so a record that drifts out of
   contract fails CI rather than being discovered later.

2. **The schemas stay inside the keyword subset** `tools/kca/contracts.py`
   implements, and are simultaneously conformant JSON Schema — the second half
   via the `jsonschema` library, so the hand-rolled subset cannot quietly diverge
   from the standard it claims to be a subset of.

3. **The invariants bite.** An invariant nothing ever trips is decoration, so each
   one is exercised against a record mutated to break it.

No DB, no network, no competition actions.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools" / "kca"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import contracts  # noqa: E402


@pytest.fixture(scope="module")
def report() -> contracts.Report:
    return contracts.validate()


@pytest.fixture(scope="module")
def schemas() -> dict:
    return contracts.load_schemas()


@pytest.fixture(scope="module")
def records() -> list[contracts.Record]:
    return contracts.discover_records()


def _by(records: list[contracts.Record], entity: str, competition: str) -> dict[str, contracts.Record]:
    return {r.ident: r for r in records if r.entity == entity and r.competition == competition}


def _mutate(record: contracts.Record, **changes) -> contracts.Record:
    """A copy of a real record with fields replaced — the basis of every invariant test."""
    data = copy.deepcopy(record.data)
    data.update(changes)
    return contracts.Record(record.entity, record.path, record.competition, data)


def _rules(findings) -> set[str]:
    return {finding.rule for finding in findings}


# ---------------------------------------------------------------------------
# 1. The repository's real records
# ---------------------------------------------------------------------------


def test_every_real_record_validates(report: contracts.Report):
    assert report.findings == [], "\n".join(str(finding) for finding in report.findings)


def test_every_entity_has_at_least_one_real_record(report: contracts.Report):
    """Issue #191's acceptance criterion: CI validates >=1 real record per entity."""
    assert contracts.missing_entities(report) == []
    assert set(report.counts()) == {spec.name for spec in contracts.ENTITIES}


def test_no_record_path_is_gitignored(records: list[contracts.Record]):
    """A record the VCS cannot see is not a record.

    `.gitignore` excludes `artifacts/` and `runs/` for bulk outputs, and those
    patterns also matched `competitions/<slug>/ledger/{artifacts,runs}/` — silently
    dropping every Run and Artifact record from the commit while the validator,
    reading the working tree, stayed green. Two re-include lines fix it; this test is
    what notices if they are ever removed.
    """
    paths = [str(record.path.relative_to(REPO_ROOT)) for record in records]
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=REPO_ROOT,
        input="\n".join(paths),
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == "", f"gitignored record(s):\n{proc.stdout}"
    assert proc.returncode == 1, proc.stderr


def test_the_nemotron_chain_is_complete_end_to_end(records: list[contracts.Record]):
    """Discussion #185 §5's chain, walked on the real 0.86 soup campaign.

    ResearchItem -> Idea -> Decision/Strategy -> Experiment -> Run -> Artifact
    -> Submission -> Score -> Finding. Every hop is a stored reference, not a
    convention, which is the whole claim the ADR makes about traceability.
    """
    slug = "nvidia-nemotron"
    idea = _by(records, "Idea", slug)["IDEA-0001"]
    assert "RI-0001" in idea.data["research_items"]

    experiment = _by(records, "Experiment", slug)["EXP-0002"]
    assert experiment.data["idea_id"] == "IDEA-0001"
    assert experiment.data["decision_id"] == "DEC-0001"
    assert experiment.data["strategy_id"] == "STRATEGY-001"
    assert experiment.data["parent_experiment"] == "EXP-0001"

    run = _by(records, "Run", slug)[experiment.data["runs"][0]]
    assert run.data["experiment_id"] == "EXP-0002"
    artifact = _by(records, "Artifact", slug)[run.data["artifacts"][0]]
    assert artifact.data["produced_by_run"] == run.ident

    submission = _by(records, "Submission", slug)["INT-BACKFILL-nemo-soup"]
    assert submission.data["run_id"] == run.ident
    assert submission.data["artifact"] == artifact.ident

    score = _by(records, "Score", slug)[submission.data["score_id"]]
    assert score.data["submission_ref"] == submission.data["ref"]
    assert (score.data["public_score"], score.data["private_score"]) == (0.86, 0.85)

    finding = _by(records, "Finding", slug)["FIND-0001"]
    assert score.ident in finding.data["from_scores"]
    assert experiment.ident in finding.data["from_experiments"]


def test_experiment_and_run_are_separate_records_with_failure_history(records: list[contracts.Record]):
    """The split the ADR is named for: one design, two attempts, no overwrite."""
    experiment = _by(records, "Experiment", "nvidia-nemotron")["EXP-0001"]
    runs = _by(records, "Run", "nvidia-nemotron")
    attempts = {runs[run_id].data["attempt"]: runs[run_id] for run_id in experiment.data["runs"]}

    assert sorted(attempts) == [1, 2]
    assert attempts[1].data["status"] == "failed"
    assert attempts[1].data["error_class"] != "none"
    assert attempts[1].data["error_summary"]
    assert attempts[2].data["status"] == "succeeded"
    assert attempts[2].data["supersedes"] == attempts[1].ident
    # The retry did not rewrite the design: both attempts share one Experiment.
    assert attempts[1].data["experiment_id"] == attempts[2].data["experiment_id"] == "EXP-0001"


def test_a_real_submission_carries_the_needs_reconciliation_state(records: list[contracts.Record]):
    """Issue #191 requires the state; sec-attack supplies a real instance of it."""
    submission = _by(records, "Submission", "sec-attack")["INT-BACKFILL-jed-v4"]
    assert submission.data["status"] == "needs_reconciliation"
    assert submission.data["reconciliation"]["required"] is True
    assert submission.data["reconciliation"]["outcome"] == "ambiguous"
    # Unknown outcome, so nothing may claim it landed or claim it did not.
    assert submission.data["selected_for_final"] is None


def test_the_eligible_best_is_what_reaches_competition_yaml(records: list[contracts.Record]):
    """ADR-0022 §3: an ineligible or unverified score never becomes `best`."""
    nemo = _by(records, "Competition", "nvidia-nemotron")["nvidia-nemotron"]
    nemo_score = _by(records, "Score", "nvidia-nemotron")["SCORE-0001"]
    assert nemo_score.data["is_eligible"] is True
    assert nemo.data["best"]["public_lb"] == nemo_score.data["public_score"]
    assert nemo.data["best"]["private_lb"] == nemo_score.data["private_score"]

    sec = _by(records, "Competition", "sec-attack")["sec-attack"]
    sec_score = _by(records, "Score", "sec-attack")["SCORE-0001"]
    assert sec_score.data["public_score"] == 7.2  # measured
    assert sec_score.data["is_eligible"] is None  # never established
    assert sec.data["best"]["public_lb"] is None  # so it is not the competition's best


# ---------------------------------------------------------------------------
# 2. The schemas
# ---------------------------------------------------------------------------


def test_schemas_use_only_the_supported_keyword_subset(schemas: dict):
    for entity, schema in schemas.items():
        used = contracts.collect_schema_keywords(schema)
        unsupported = used - contracts.SUPPORTED_KEYWORDS
        assert unsupported == set(), (
            f"{entity} uses {sorted(unsupported)}, which tools/kca/contracts.py does not implement. "
            "Either extend the validator or stay inside the subset."
        )


def test_schemas_validate_every_real_record_under_a_standard_implementation(
    schemas: dict, records: list[contracts.Record]
):
    """The subset is a subset of the real thing, not a private dialect."""
    jsonschema = pytest.importorskip("jsonschema", reason="`pip install -e .[dev]` provides it")
    for entity, schema in schemas.items():
        jsonschema.Draft202012Validator.check_schema(schema)
    for record in records:
        validator = jsonschema.Draft202012Validator(schemas[record.entity])
        errors = sorted(validator.iter_errors(record.data), key=lambda e: list(e.path))
        assert errors == [], f"{record.rel}: {[e.message for e in errors]}"


def test_every_entity_has_a_schema_and_a_documented_record_path(schemas: dict):
    readme = (REPO_ROOT / "contracts" / "README.md").read_text()
    for spec in contracts.ENTITIES:
        assert schemas[spec.name]["title"] == spec.name
        assert f"[`{spec.schema_file}`](./{spec.schema_file})" in readme, spec.name
        assert spec.record_path in readme, spec.name


def test_ledger_records_are_closed_and_competition_is_open(schemas: dict):
    assert schemas["Competition"]["additionalProperties"] is True
    for spec in contracts.ENTITIES:
        if spec.name == "Competition":
            continue
        assert schemas[spec.name]["additionalProperties"] is False, spec.name
        # Every declared property is required: a missing key is a bug, not an override.
        assert set(schemas[spec.name]["required"]) == set(schemas[spec.name]["properties"]), spec.name


# ADR-0023 §1: a declared property is required, so an unknown value is an explicit
# `null` rather than an absent key. These nine are the entire exemption list, pinned
# here so it cannot grow without an edit that says so.
OPTIONAL_PROPERTIES = {
    ("Competition", "aliases"),
    ("Competition", "tracking_issue"),
    ("Competition", "resume_state"),
    ("Competition", "state_reason"),
    ("Competition", "decision_id"),
    ("Competition", "retry_at"),
    ("Competition", "external_ref"),
    ("Submission", "screen.beats_best"),
    ("Submission", "screen.min_margin"),
}


def test_only_the_named_properties_are_optional(schemas: dict):
    """At every nesting level, a declared property is required unless it is on the list."""

    def walk(schema, entity: str, prefix: str) -> set[tuple[str, str]]:
        optional: set[tuple[str, str]] = set()
        if not isinstance(schema, dict):
            return optional
        properties = schema.get("properties")
        if isinstance(properties, dict):
            required = set(schema.get("required") or ())
            for name, sub in properties.items():
                path = f"{prefix}{name}"
                if name not in required:
                    optional.add((entity, path))
                optional |= walk(sub, entity, f"{path}.")
        if "items" in schema:
            optional |= walk(schema["items"], entity, f"{prefix}[].")
        return optional

    found: set[tuple[str, str]] = set()
    for spec in contracts.ENTITIES:
        found |= walk(schemas[spec.name], spec.name, "")
    assert found == OPTIONAL_PROPERTIES


def test_the_research_item_id_prefix_avoids_the_budget_reservation_prefix():
    """`RES-` is taken by ADR-0022 §6 budget reservations, so ResearchItem uses `RI-`."""
    spec = contracts.ENTITY_BY_NAME["ResearchItem"]
    assert spec.id_pattern is not None and spec.id_pattern.startswith("^RI-")
    assert "RES-" not in spec.id_pattern


# ---------------------------------------------------------------------------
# 3. The schema keyword implementation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema, value, rule",
    [
        ({"type": "string"}, 7, "type"),
        ({"type": ["string", "null"]}, 7, "type"),
        ({"enum": ["a", "b"]}, "c", "enum"),
        ({"type": "string", "pattern": "^EXP-"}, "RUN-0001", "pattern"),
        ({"type": "string", "minLength": 1}, "", "minLength"),
        ({"type": "integer", "minimum": 1}, 0, "minimum"),
        ({"type": "array", "minItems": 1}, [], "minItems"),
        ({"type": "object", "required": ["a"], "properties": {}}, {}, "required"),
        ({"type": "object", "additionalProperties": False, "properties": {}}, {"a": 1}, "additionalProperties"),
        ({"type": "array", "items": {"type": "string"}}, [1], "type"),
    ],
)
def test_each_implemented_keyword_rejects_what_it_should(schema, value, rule):
    assert _rules(contracts.iter_schema_errors(schema, value, "x")) == {rule}


@pytest.mark.parametrize(
    "schema, value",
    [
        ({"type": ["string", "null"]}, None),
        ({"type": "string", "pattern": "^EXP-"}, "EXP-0001"),
        # A keyword only applies to its own type: a null is not checked for pattern.
        ({"type": ["string", "null"], "pattern": "^EXP-", "minLength": 3}, None),
        ({"type": ["number", "null"], "minimum": 0}, None),
        ({"enum": [0, 1, 2, 3, 4, None]}, None),
    ],
)
def test_each_implemented_keyword_accepts_what_it_should(schema, value):
    assert list(contracts.iter_schema_errors(schema, value, "x")) == []


def test_booleans_are_not_integers_and_do_not_satisfy_numeric_enums():
    """Python says True == 1; JSON Schema does not, and scenario/rank fields care."""
    assert _rules(contracts.iter_schema_errors({"type": "integer"}, True, "x")) == {"type"}
    assert _rules(contracts.iter_schema_errors({"enum": [0, 1]}, True, "x")) == {"enum"}
    assert list(contracts.iter_schema_errors({"type": "boolean"}, True, "x")) == []


def test_yaml_dates_are_normalised_to_iso_strings(tmp_path: Path):
    """`last_updated: 2026-09-15` is a YAML date, and the contracts declare strings."""
    path = tmp_path / "record.yaml"
    path.write_text("plain: 2026-09-15\nquoted: '2026-09-15'\nstamp: 2026-09-15 03:22:00Z\n")
    loaded = contracts.read_yaml(path)
    assert loaded["plain"] == "2026-09-15"
    assert loaded["quoted"] == "2026-09-15"
    assert loaded["stamp"] == "2026-09-15T03:22:00Z"


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path):
    path = tmp_path / "record.yaml"
    path.write_text("id: EXP-0001\nid: EXP-0002\n")
    with pytest.raises(Exception, match="duplicate YAML key"):
        contracts.read_yaml(path)


# ---------------------------------------------------------------------------
# 4. The invariants (ADR-0023 §5) — each one is made to fire
# ---------------------------------------------------------------------------


def test_i1_a_record_filename_must_match_its_id(records: list[contracts.Record]):
    run = _by(records, "Run", "nvidia-nemotron")["RUN-0001"]
    assert "I1" in _rules(contracts.iter_invariant_errors([_mutate(run, id="RUN-9999")]))


def test_i1_a_submission_filename_must_carry_its_ref(records: list[contracts.Record]):
    submission = _by(records, "Submission", "nvidia-nemotron")["INT-BACKFILL-nemo-soup"]
    assert "I1" in _rules(contracts.iter_invariant_errors([_mutate(submission, ref="INT-BACKFILL-other")]))


def test_i2_a_record_must_name_the_competition_it_lives_under(records: list[contracts.Record]):
    run = _by(records, "Run", "nvidia-nemotron")["RUN-0001"]
    assert "I2" in _rules(contracts.iter_invariant_errors([_mutate(run, competition="sec-attack")]))


def test_i4_a_reference_to_a_missing_record_is_an_error(records: list[contracts.Record]):
    experiment = _by(records, "Experiment", "nvidia-nemotron")["EXP-0002"]
    broken = _mutate(experiment, idea_id="IDEA-9999")
    assert "I4" in _rules(contracts.iter_invariant_errors([broken]))


def test_i5_a_retry_must_name_the_attempt_it_supersedes(records: list[contracts.Record]):
    runs = _by(records, "Run", "nvidia-nemotron")
    broken = _mutate(runs["RUN-0002"], supersedes=None)
    assert "I5" in _rules(contracts.iter_invariant_errors([broken]))


def test_i5_a_succeeded_run_is_never_retried(records: list[contracts.Record]):
    """The rule that keeps a retry from erasing history: you retry a failure, not a success."""
    runs = _by(records, "Run", "nvidia-nemotron")
    first = _mutate(runs["RUN-0001"], status="succeeded", error_class="none", error_summary=None)
    findings = list(contracts.iter_invariant_errors([first, runs["RUN-0002"]]))
    assert any(f.rule == "I5" and "never retried" in f.message for f in findings)


def test_i5_two_runs_cannot_claim_the_same_attempt(records: list[contracts.Record]):
    runs = _by(records, "Run", "nvidia-nemotron")
    clash = _mutate(runs["RUN-0002"], attempt=1, supersedes=None)
    findings = list(contracts.iter_invariant_errors([runs["RUN-0001"], clash]))
    assert any(f.rule == "I5" and "already recorded" in f.message for f in findings)


def test_i5_a_failed_run_must_record_its_cause(records: list[contracts.Record]):
    run = _by(records, "Run", "nvidia-nemotron")["RUN-0001"]
    broken = _mutate(run, error_class="none", error_summary=None)
    assert "I5" in _rules(contracts.iter_invariant_errors([broken]))


def test_i6_experiment_and_run_must_agree_in_both_directions(records: list[contracts.Record]):
    experiment = _by(records, "Experiment", "nvidia-nemotron")["EXP-0001"]
    runs = _by(records, "Run", "nvidia-nemotron")
    dropped = _mutate(experiment, runs=["RUN-0002"])
    findings = list(contracts.iter_invariant_errors([dropped, runs["RUN-0001"], runs["RUN-0002"]]))
    assert any(f.rule == "I6" and "not listed" in f.message for f in findings)


def test_i7_a_backfilled_submission_ref_can_never_read_as_an_authorization(records: list[contracts.Record]):
    submission = _by(records, "Submission", "nvidia-nemotron")["INT-BACKFILL-nemo-soup"]
    promoted = _mutate(submission, provenance="live")
    assert "I7" in _rules(contracts.iter_invariant_errors([promoted]))


def test_i7_a_live_experiment_must_carry_the_repro_fields(records: list[contracts.Record]):
    experiment = _by(records, "Experiment", "nvidia-nemotron")["EXP-0002"]
    promoted = _mutate(experiment, provenance="live")
    findings = [f for f in contracts.iter_invariant_errors([promoted]) if f.rule == "I7"]
    missing = {f.message for f in findings}
    assert any("config_hash" in m for m in missing)
    assert any("seed" in m for m in missing)


def test_i8_a_failed_hard_gate_blocks_a_live_dispatch(records: list[contracts.Record]):
    """require_repro / rules_check are hard gates (ADR-0022 §5); beats_best is not."""
    submission = _by(records, "Submission", "sec-attack")["INT-BACKFILL-jed-xl-v1"]
    live = _mutate(
        submission,
        provenance="live",
        ref="INT-20260629-000000-ab12",
        artifact_sha256="0" * 64,
        screen={"require_repro": "fail", "rules_check": "pass"},
    )
    assert "I8" in _rules(contracts.iter_invariant_errors([live]))


def test_i9_a_closing_window_scenario_needs_a_human_decision(records: list[contracts.Record]):
    submission = _by(records, "Submission", "nvidia-nemotron")["INT-BACKFILL-nemo-soup"]
    for scenario in (0, 4):
        broken = _mutate(submission, scenario=scenario, decision_id=None)
        assert "I9" in _rules(contracts.iter_invariant_errors([broken])), scenario


def test_i10_an_unknown_outcome_cannot_be_reported_as_present(records: list[contracts.Record]):
    submission = _by(records, "Submission", "sec-attack")["INT-BACKFILL-jed-v4"]
    reconciliation = dict(submission.data["reconciliation"], outcome="present")
    assert "I10" in _rules(contracts.iter_invariant_errors([_mutate(submission, reconciliation=reconciliation)]))


def test_i10_only_a_proven_absence_permits_a_replacement_dispatch(records: list[contracts.Record]):
    """The duplicate-submission guard: supersede a record only once it is known absent."""
    existing = _by(records, "Submission", "sec-attack")["INT-BACKFILL-jed-v4"]
    replacement = _mutate(existing, ref="INT-BACKFILL-jed-v4", supersedes="INT-BACKFILL-jed-v4")
    findings = list(contracts.iter_invariant_errors([existing, replacement]))
    assert any(f.rule == "I10" and "absent" in f.message for f in findings)


def test_i11_a_rejected_idea_keeps_its_reason_and_a_revival_cites_new_evidence(
    records: list[contracts.Record],
):
    idea = _by(records, "Idea", "nvidia-nemotron")["IDEA-0001"]
    assert "I11" in _rules(contracts.iter_invariant_errors([_mutate(idea, status="rejected")]))
    revived = _mutate(idea, re_proposal_of="IDEA-0001", new_evidence=None)
    assert "I11" in _rules(contracts.iter_invariant_errors([revived]))


def test_i12_a_hash_without_its_algorithm_is_not_an_identity(records: list[contracts.Record]):
    artifact = _by(records, "Artifact", "nvidia-nemotron")["ART-0001"]
    assert "I12" in _rules(contracts.iter_invariant_errors([_mutate(artifact, hash_algo=None)]))


def test_i13_a_rank_needs_its_denominator(records: list[contracts.Record]):
    score = _by(records, "Score", "nvidia-nemotron")["SCORE-0001"]
    assert "I13" in _rules(contracts.iter_invariant_errors([_mutate(score, public_total=None)]))


def test_i14_a_side_state_records_how_to_come_back(records: list[contracts.Record]):
    """ADR-0022 §3, checked here as well as in test_competition_contract.py."""
    competition = _by(records, "Competition", "nvidia-nemotron")["nvidia-nemotron"]
    stuck = _mutate(competition, state="WAIT_HUMAN")
    findings = [f for f in contracts.iter_invariant_errors([stuck]) if f.rule == "I14"]
    assert {"resume_state", "state_reason"} <= {word for f in findings for word in f.message.split()}


def test_i14_a_verified_submission_limit_needs_its_provenance(records: list[contracts.Record]):
    """ADR-0022 §5 A3: a number without a dated source is not verified."""
    competition = _by(records, "Competition", "nvidia-nemotron")["nvidia-nemotron"]
    budget = copy.deepcopy(competition.data["budget"])
    budget["submissions"]["verified_daily_limit"] = 5
    findings = [f for f in contracts.iter_invariant_errors([_mutate(competition, budget=budget)]) if f.rule == "I14"]
    assert len(findings) == 3  # source, date, reset boundary


def test_i15_and_i16_status_fields_agree_with_their_dates(records: list[contracts.Record]):
    strategy = _by(records, "Strategy", "nvidia-nemotron")["STRATEGY-001"]
    assert "I15" in _rules(contracts.iter_invariant_errors([_mutate(strategy, status="active")]))
    decision = _by(records, "Decision", "nvidia-nemotron")["DEC-0001"]
    assert "I16" in _rules(contracts.iter_invariant_errors([_mutate(decision, decided_at=None)]))
    assert "I16" in _rules(contracts.iter_invariant_errors([_mutate(decision, selected="not_an_option")]))


# ---------------------------------------------------------------------------
# 5. The CLI surface
# ---------------------------------------------------------------------------


def test_kca_contracts_validate_exits_zero_on_a_clean_tree(capsys):
    import argparse

    args = argparse.Namespace(competition=None, require_all_entities=True, verbose=False)
    assert contracts.cmd_validate(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["side_effect"] == "READ_ONLY"
    assert payload["entities_without_records"] == []
    assert payload["records"] == sum(payload["counts"].values())


def test_kca_contracts_schemas_lists_every_entity(capsys):
    import argparse

    assert contracts.cmd_schemas(argparse.Namespace(verbose=False)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["entity"] for row in payload["entities"]] == [spec.name for spec in contracts.ENTITIES]
    submission = next(row for row in payload["entities"] if row["entity"] == "Submission")
    # ADR-0022 §5 A6 owns this directory; ADR-0023 §4 pins <intent-id> = `ref`.
    assert submission["record_path"] == "competitions/<slug>/submissions/<utc-timestamp>-<ref>.yaml"


def test_the_command_is_registered_read_only_and_needs_no_database():
    sys.path.insert(0, str(TOOLS_DIR / "agent"))
    from command_registry import REGISTRY

    spec = REGISTRY.get("contracts")
    assert spec is not None
    assert spec.side_effect == "READ_ONLY"
    assert spec.requires_db is False
