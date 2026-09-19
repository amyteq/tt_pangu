"""contracts — READ_ONLY validator for the ADR-0023 ledger contracts.

Two passes, and the split is deliberate (contracts/README.md says the same thing
from the schema side):

1. **Shape.** Each record is validated against its entity's JSON Schema under
   `contracts/`. Only the keyword subset those schemas actually use is
   implemented here — `type`, `enum`, `const`, `properties`, `required`,
   `additionalProperties`, `items`, `pattern`, `minimum`, `minItems`,
   `minLength`. That keeps `kca contracts validate` dependency-free, so it runs
   from a bare checkout and from phase 2 alike; `tests/test_contracts.py` asserts
   the schemas never reach outside the subset, and separately re-validates every
   record with the `jsonschema` library so the subset stays conformant rather
   than merely self-consistent.

2. **Invariants.** The things a per-record schema structurally cannot say: ids are
   unique, foreign keys resolve, and the retry rule holds. ADR-0023 §5 is the
   list; `INVARIANTS` below is the implementation and the two are meant to be
   read together.

This module is READ_ONLY: it reads `contracts/`, `competitions/` and nothing else.
No DB, no network, no writes.

Exit codes: 0 when every record validates, 1 when any does not.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

from _types import EXIT_OK, EXIT_RUNTIME, SideEffect
from _util import REPO_ROOT, warn

CONTRACTS_DIR = REPO_ROOT / "contracts"
COMPETITIONS_DIR = REPO_ROOT / "competitions"

# Keywords the schemas may use. Split so a reader can see which carry an
# assertion and which are documentation; tests/test_contracts.py pins the union.
SCHEMA_ANNOTATIONS = frozenset({"$schema", "$id", "title", "description"})
SCHEMA_ASSERTIONS = frozenset(
    {
        "type",
        "enum",
        "const",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "pattern",
        "minimum",
        "minItems",
        "minLength",
    }
)
SUPPORTED_KEYWORDS = SCHEMA_ANNOTATIONS | SCHEMA_ASSERTIONS

# A side state must record how to come back (ADR-0022 §3).
SIDE_STATES = frozenset({"WAIT_HUMAN", "PAUSED_BUDGET", "RETRY_AT", "NEEDS_RECONCILIATION", "FAILED", "STOPPED"})

# `<utc-timestamp>-<intent-id>.yaml` (ADR-0022 §5). The timestamp is a date plus
# a compact time so the name sorts and stays filesystem-safe on every platform.
SUBMISSION_STEM_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{6}Z$")

BACKFILL_REF_PREFIX = "INT-BACKFILL-"


@dataclass(frozen=True)
class EntitySpec:
    """Where one entity's schema lives, and where its records live."""

    name: str
    schema_file: str
    id_field: str
    # Path of the record directory relative to competitions/<slug>/, or None for
    # the Competition record, which is a single file.
    record_subdir: str | None
    id_pattern: str | None

    @property
    def record_path(self) -> str:
        """The documented location of one record, for `kca contracts schemas`."""
        if self.record_subdir is None:
            return "competitions/<slug>/competition.yaml"
        if self.name == "Submission":
            # ADR-0022 §5 A6 fixes this path; ADR-0023 §4 pins <intent-id> = `ref`.
            return "competitions/<slug>/submissions/<utc-timestamp>-<ref>.yaml"
        return f"competitions/<slug>/{self.record_subdir}/<id>.yaml"


ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("Competition", "competition.yaml", "slug", None, None),
    EntitySpec("ResearchItem", "research-item.yaml", "id", "ledger/research", r"^RI-\d{4,}$"),
    EntitySpec("Idea", "idea.yaml", "id", "ledger/ideas", r"^IDEA-\d{4,}$"),
    EntitySpec("Decision", "decision.yaml", "id", "ledger/decisions", r"^DEC-\d{4,}$"),
    EntitySpec("Strategy", "strategy.yaml", "id", "ledger/strategies", r"^STRATEGY-\d{3,}$"),
    EntitySpec("Experiment", "experiment.yaml", "id", "ledger/experiments", r"^EXP-\d{4,}$"),
    EntitySpec("Run", "run.yaml", "id", "ledger/runs", r"^RUN-\d{4,}$"),
    EntitySpec("Artifact", "artifact.yaml", "id", "ledger/artifacts", r"^ART-\d{4,}$"),
    EntitySpec("Submission", "submission.yaml", "ref", "submissions", r"^INT-(BACKFILL-)?[0-9A-Za-z-]+$"),
    EntitySpec("Score", "score.yaml", "id", "ledger/scores", r"^SCORE-\d{4,}$"),
    EntitySpec("Finding", "finding.yaml", "id", "ledger/findings", r"^FIND-\d{4,}$"),
)

ENTITY_BY_NAME = {spec.name: spec for spec in ENTITIES}


@dataclass
class Record:
    entity: str
    path: Path
    competition: str
    data: dict[str, Any]

    @property
    def rel(self) -> str:
        try:
            return str(self.path.relative_to(REPO_ROOT))
        except ValueError:
            return str(self.path)

    @property
    def ident(self) -> str:
        spec = ENTITY_BY_NAME[self.entity]
        value = self.data.get(spec.id_field)
        return str(value) if value is not None else "<no-id>"


@dataclass
class Finding:
    """One validation failure. `rule` is the schema keyword or the invariant id."""

    path: str
    rule: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "rule": self.rule, "message": self.message}

    def __str__(self) -> str:
        return f"{self.path} [{self.rule}] {self.message}"


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject a duplicated YAML key instead of silently keeping the last one."""


def _unique_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise yaml.YAMLError(f"duplicate YAML key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def normalise(value: Any) -> Any:
    """Turn YAML's native date/time scalars into the ISO strings the contracts declare.

    YAML types a plain `2026-06-15` as a `date`, and the repository's
    `competition.yaml` files have always written dates that way. JSON has no date
    type and neither does Supabase's `text` provenance columns, so the contracts
    declare these fields as strings — and this normalisation is what lets an author
    write the date unquoted without the contract having to grow a second type.
    A quoted string is passed through untouched.
    """
    if isinstance(value, dict):
        return {key: normalise(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalise(item) for item in value]
    if isinstance(value, datetime):
        stamp = value.astimezone(timezone.utc) if value.tzinfo else value
        return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return value


def read_yaml(path: Path) -> Any:
    return normalise(yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader))


# ---------------------------------------------------------------------------
# Pass 1 — JSON Schema (the declared subset)
# ---------------------------------------------------------------------------

_TYPE_CHECKS: dict[str, Any] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    # bool is a subclass of int in Python; JSON Schema treats them as distinct.
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_name(value: Any) -> str:
    for name, check in _TYPE_CHECKS.items():
        if name != "number" and check(value):
            return name
    return "number" if _TYPE_CHECKS["number"](value) else type(value).__name__


def _eq(a: Any, b: Any) -> bool:
    """Equality that keeps booleans out of numeric enums (True == 1 in Python)."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return bool(a == b)


def iter_schema_errors(schema: dict[str, Any], value: Any, path: str) -> Iterator[Finding]:
    """Yield a Finding per schema violation, depth-first, deterministically."""
    declared = schema.get("type")
    if declared is not None:
        names = [declared] if isinstance(declared, str) else list(declared)
        if not any(_TYPE_CHECKS[name](value) for name in names if name in _TYPE_CHECKS):
            yield Finding(path, "type", f"expected {'|'.join(names)}, got {_type_name(value)}")
            return

    if "enum" in schema and not any(_eq(option, value) for option in schema["enum"]):
        yield Finding(path, "enum", f"{value!r} is not one of {schema['enum']!r}")
    if "const" in schema and not _eq(schema["const"], value):
        yield Finding(path, "const", f"{value!r} != {schema['const']!r}")

    if isinstance(value, str):
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, value) is None:
            yield Finding(path, "pattern", f"{value!r} does not match {pattern}")
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(value) < minimum_length:
            yield Finding(path, "minLength", f"length {len(value)} < {minimum_length}")

    if _TYPE_CHECKS["number"](value):
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            yield Finding(path, "minimum", f"{value} < {minimum}")

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(value) < minimum_items:
            yield Finding(path, "minItems", f"{len(value)} items < {minimum_items}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                yield from iter_schema_errors(item_schema, item, f"{path}[{index}]")

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                yield Finding(path, "required", f"missing key {key!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    yield Finding(path, "additionalProperties", f"unexpected key {key!r}")
        for key, sub_schema in properties.items():
            if key in value and isinstance(sub_schema, dict):
                yield from iter_schema_errors(sub_schema, value[key], f"{path}.{key}")


def collect_schema_keywords(schema: Any) -> set[str]:
    """Every keyword used anywhere in a schema document, for the subset test."""
    used: set[str] = set()
    if isinstance(schema, dict):
        for key, sub in schema.items():
            if key in ("properties",):
                for sub_schema in sub.values():
                    used |= collect_schema_keywords(sub_schema)
                used.add(key)
                continue
            if key in ("enum", "required", "const"):
                used.add(key)
                continue
            used.add(key)
            used |= collect_schema_keywords(sub)
    elif isinstance(schema, list):
        for item in schema:
            used |= collect_schema_keywords(item)
    return used


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_schemas(contracts_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    root = contracts_dir or CONTRACTS_DIR
    schemas: dict[str, dict[str, Any]] = {}
    for spec in ENTITIES:
        path = root / spec.schema_file
        if not path.exists():
            raise FileNotFoundError(f"missing contract schema: {path}")
        schemas[spec.name] = read_yaml(path)
    return schemas


def competition_dirs(competitions_dir: Path | None = None) -> list[Path]:
    root = competitions_dir or COMPETITIONS_DIR
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith("_") and (path / "competition.yaml").exists()
    )


def discover_records(competition: str | None = None, competitions_dir: Path | None = None) -> list[Record]:
    """Every ledger record in the tree, in a stable order."""
    records: list[Record] = []
    for comp_dir in competition_dirs(competitions_dir):
        slug = comp_dir.name
        if competition and slug != competition:
            continue
        for spec in ENTITIES:
            if spec.record_subdir is None:
                records.append(Record(spec.name, comp_dir / "competition.yaml", slug, {}))
                continue
            record_dir = comp_dir / spec.record_subdir
            if not record_dir.is_dir():
                continue
            for path in sorted(record_dir.glob("*.yaml")):
                records.append(Record(spec.name, path, slug, {}))
    for record in records:
        loaded = read_yaml(record.path)
        record.data = loaded if isinstance(loaded, dict) else {}
    return records


# ---------------------------------------------------------------------------
# Pass 2 — invariants (ADR-0023 §5)
# ---------------------------------------------------------------------------

# Every reference field, as entity -> {field: target entity}. Scalars and lists
# are both handled; a list field is named in LIST_REFS.
REFS: dict[str, dict[str, str]] = {
    "ResearchItem": {"related_ideas": "Idea"},
    "Idea": {"research_items": "ResearchItem", "related_experiments": "Experiment", "re_proposal_of": "Idea"},
    "Decision": {"supersedes": "Decision"},
    "Strategy": {"supersedes": "Strategy"},
    "Experiment": {
        "idea_id": "Idea",
        "strategy_id": "Strategy",
        "decision_id": "Decision",
        "parent_experiment": "Experiment",
        "runs": "Run",
        "artifacts": "Artifact",
        "findings": "Finding",
    },
    "Run": {"experiment_id": "Experiment", "supersedes": "Run", "artifacts": "Artifact"},
    "Artifact": {"produced_by_run": "Run"},
    "Submission": {
        "experiment_id": "Experiment",
        "run_id": "Run",
        "decision_id": "Decision",
        "score_id": "Score",
        "supersedes": "Submission",
    },
    "Score": {"submission_ref": "Submission", "experiment_id": "Experiment"},
    "Finding": {
        "from_experiments": "Experiment",
        "from_scores": "Score",
        "new_strategy": "Strategy",
        "supersedes": "Finding",
    },
}

LIST_REFS = frozenset(
    {
        "related_ideas",
        "research_items",
        "related_experiments",
        "runs",
        "artifacts",
        "findings",
        "from_experiments",
        "from_scores",
    }
)

# Fields a `live` record must have filled, per entity. ADR-0023 §5, invariant I7.
LIVE_REQUIRED: dict[str, tuple[str, ...]] = {
    "ResearchItem": ("fetched_at",),
    "Experiment": ("code_commit", "data_version", "config_hash", "split_id"),
    "Run": ("command", "started_at"),
    "Submission": ("artifact_sha256",),
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _index(records: list[Record]) -> dict[tuple[str, str, str], Record]:
    return {(record.competition, record.entity, record.ident): record for record in records}


def iter_invariant_errors(records: list[Record]) -> Iterator[Finding]:
    """Yield a Finding per broken invariant. Order follows ADR-0023 §5."""
    index = _index(records)
    seen: dict[tuple[str, str, str], str] = {}

    for record in records:
        rel, data, entity = record.rel, record.data, record.entity
        spec = ENTITY_BY_NAME[entity]

        # I1 — the filename and the record's own id agree.
        if entity == "Submission":
            stem = record.path.stem
            ref = str(data.get("ref") or "")
            expected_ts = stem[: -len(ref) - 1] if ref and stem.endswith(ref) else ""
            if not ref or not stem.endswith(f"-{ref}") or not SUBMISSION_STEM_TS.match(expected_ts):
                yield Finding(rel, "I1", f"filename must be <utc-timestamp>-<ref>.yaml for ref {ref!r}")
        elif spec.record_subdir is not None and record.path.stem != record.ident:
            yield Finding(rel, "I1", f"filename stem {record.path.stem!r} != id {record.ident!r}")
        if spec.id_pattern and record.ident != "<no-id>" and not re.match(spec.id_pattern, record.ident):
            yield Finding(rel, "I1", f"id {record.ident!r} does not match {spec.id_pattern}")

        # I2 — the record's `competition` matches the directory it lives in.
        if entity != "Competition":
            declared = data.get("competition")
            if declared != record.competition:
                yield Finding(rel, "I2", f"competition {declared!r} != directory {record.competition!r}")

        # I3 — ids are unique within a competition and entity.
        key = (record.competition, entity, record.ident)
        if key in seen and seen[key] != rel:
            yield Finding(rel, "I3", f"duplicate {entity} id {record.ident!r}, also in {seen[key]}")
        seen[key] = rel

        # I4 — every reference resolves, inside the same competition.
        for field_name, target in REFS.get(entity, {}).items():
            if field_name not in data:
                continue
            values = _as_list(data[field_name]) if field_name in LIST_REFS else _as_list(data.get(field_name))
            for value in values:
                if value is None:
                    continue
                if (record.competition, target, str(value)) not in index:
                    yield Finding(rel, "I4", f"{field_name} -> unknown {target} {value!r}")

        # I7 — a `live` record carries the fields reproducibility needs.
        if data.get("provenance") == "live":
            for field_name in LIVE_REQUIRED.get(entity, ()):
                if data.get(field_name) in (None, "", []):
                    yield Finding(rel, "I7", f"live record needs {field_name}")

        if entity == "Competition":
            yield from _competition_invariants(rel, data)
        elif entity == "Idea":
            yield from _idea_invariants(rel, data)
        elif entity == "Decision":
            yield from _decision_invariants(rel, data)
        elif entity == "Strategy":
            yield from _strategy_invariants(rel, data)
        elif entity == "Experiment":
            yield from _experiment_invariants(rel, data)
        elif entity == "Run":
            yield from _run_invariants(rel, data)
        elif entity == "Artifact":
            yield from _artifact_invariants(rel, data)
        elif entity == "Submission":
            yield from _submission_invariants(rel, data)
        elif entity == "Score":
            yield from _score_invariants(rel, data)

    yield from _retry_invariants(records)
    yield from _experiment_run_backrefs(records)
    yield from _supersede_invariants(records, index)


def _competition_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I14 — a side state records how to come back (ADR-0022 §3).
    if data.get("state") in SIDE_STATES:
        if not data.get("resume_state"):
            yield Finding(rel, "I14", f"state {data['state']} needs resume_state")
        if not data.get("state_reason"):
            yield Finding(rel, "I14", f"state {data['state']} needs state_reason")
    submissions = ((data.get("budget") or {}).get("submissions")) or {}
    limit, held = submissions.get("verified_daily_limit"), submissions.get("reserve_for_human")
    if limit is not None:
        # A verified limit is only verified with its provenance (ADR-0022 §5 A3).
        for provenance_field in ("verified_source", "verified_at", "verified_reset_boundary"):
            if not submissions.get(provenance_field):
                yield Finding(rel, "I14", f"verified_daily_limit set without {provenance_field}")
        if isinstance(held, int) and limit < held:
            yield Finding(rel, "I14", f"verified_daily_limit {limit} < reserve_for_human {held}")


def _idea_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I11 — a rejected idea keeps its reason; a revival cites new evidence.
    if data.get("status") in ("rejected", "refuted") and not data.get("rejection_reason"):
        yield Finding(rel, "I11", f"status {data['status']} needs rejection_reason")
    if data.get("re_proposal_of") and not data.get("new_evidence"):
        yield Finding(rel, "I11", "re_proposal_of needs new_evidence")


def _decision_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I16 — an approval names what was chosen and when.
    status = data.get("status")
    if status == "approved":
        if not data.get("selected"):
            yield Finding(rel, "I16", "approved decision needs selected")
        if not data.get("decided_at"):
            yield Finding(rel, "I16", "approved decision needs decided_at")
    if status == "pending" and data.get("selected"):
        yield Finding(rel, "I16", "pending decision must not carry selected")
    keys = {option.get("key") for option in data.get("options") or [] if isinstance(option, dict)}
    if data.get("selected") and keys and data["selected"] not in keys:
        yield Finding(rel, "I16", f"selected {data['selected']!r} is not one of the offered options")


def _strategy_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I15 — an active strategy has not ended.
    if data.get("status") == "active" and data.get("in_force_to"):
        yield Finding(rel, "I15", "active strategy must not have in_force_to")
    if data.get("status") in ("superseded", "retired") and not data.get("in_force_to"):
        yield Finding(rel, "I15", f"{data['status']} strategy needs in_force_to")


def _experiment_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I7 — `live` also means at least one seed, and a conclusion once evaluated.
    if data.get("provenance") == "live" and not data.get("seeds"):
        yield Finding(rel, "I7", "live experiment needs at least one seed")
    if data.get("status") == "evaluated" and not data.get("conclusion"):
        yield Finding(rel, "I6", "evaluated experiment needs a conclusion")
    if data.get("parent_experiment") == data.get("id"):
        yield Finding(rel, "I6", "parent_experiment must not be the experiment itself")


def _run_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I5 — failure history is kept with its cause.
    status, error_class = data.get("status"), data.get("error_class")
    if status == "failed":
        if error_class in (None, "none"):
            yield Finding(rel, "I5", "failed run needs an error_class other than `none`")
        if not data.get("error_summary"):
            yield Finding(rel, "I5", "failed run needs error_summary")
    if status == "succeeded" and error_class not in (None, "none"):
        yield Finding(rel, "I5", f"succeeded run must not carry error_class {error_class!r}")
    if (data.get("attempt") or 0) > 1 and not data.get("supersedes"):
        yield Finding(rel, "I5", f"attempt {data.get('attempt')} needs supersedes (the run it retries)")
    if data.get("attempt") == 1 and data.get("supersedes"):
        yield Finding(rel, "I5", "attempt 1 cannot supersede a run")
    if data.get("supersedes") == data.get("id"):
        yield Finding(rel, "I5", "a run cannot supersede itself")


def _artifact_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I12 — a hash without its algorithm is not an identity.
    has_hash, has_algo = data.get("content_hash") is not None, data.get("hash_algo") is not None
    if has_hash != has_algo:
        yield Finding(rel, "I12", "content_hash and hash_algo must be set together")


def _submission_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    ref = str(data.get("ref") or "")
    provenance, status = data.get("provenance"), data.get("status")
    is_backfill = ref.startswith(BACKFILL_REF_PREFIX)

    # I7 — a reconstructed record can never read as a dispatch authorization.
    if provenance == "backfilled" and not is_backfill:
        yield Finding(rel, "I7", f"backfilled submission ref must start with {BACKFILL_REF_PREFIX}")
    if provenance == "live" and is_backfill:
        yield Finding(rel, "I7", f"live submission ref must not start with {BACKFILL_REF_PREFIX}")

    # I8 — the two hard gates block a dispatch (ADR-0022 §5). Historical records
    # are exempt: a backfilled `fail` states what was true, not what may proceed.
    screen = data.get("screen") or {}
    if provenance == "live" and "fail" in (screen.get("require_repro"), screen.get("rules_check")):
        if status not in ("intent", "rejected", "superseded"):
            yield Finding(rel, "I8", f"require_repro/rules_check failed but status is {status!r}")

    # I9 — scenarios 0 and 4 are inside the closing window and human-gated.
    if data.get("scenario") in (0, 4) and not data.get("decision_id"):
        yield Finding(rel, "I9", f"scenario {data['scenario']} is human-gated and needs a decision_id")

    # I10 — an unknown outcome is never resolved by assumption.
    reconciliation = data.get("reconciliation") or {}
    outcome = reconciliation.get("outcome")
    if status == "needs_reconciliation":
        if reconciliation.get("required") is not True:
            yield Finding(rel, "I10", "needs_reconciliation requires reconciliation.required: true")
        if outcome in ("present", "not_required"):
            yield Finding(rel, "I10", f"needs_reconciliation contradicts outcome {outcome!r}")
    if outcome == "absent" and status in ("dispatched", "accepted", "scored"):
        yield Finding(rel, "I10", f"outcome `absent` contradicts status {status!r}")
    if status == "scored" and not data.get("score_id"):
        yield Finding(rel, "I10", "scored submission needs score_id")
    if status == "intent" and data.get("submitted_at"):
        yield Finding(rel, "I10", "an `intent` record has not been dispatched, so submitted_at must be null")


def _score_invariants(rel: str, data: dict[str, Any]) -> Iterator[Finding]:
    # I13 — a rank without its denominator is not a result.
    if data.get("public_rank") is not None and data.get("public_total") is None:
        yield Finding(rel, "I13", "public_rank needs public_total")
    if data.get("private_rank") is not None and data.get("private_total") is None:
        yield Finding(rel, "I13", "private_rank needs private_total")
    if data.get("private_score") is not None and not data.get("private_released_at"):
        yield Finding(rel, "I13", "private_score needs private_released_at")


def _retry_invariants(records: list[Record]) -> Iterator[Finding]:
    """I5 — the retry rule, across the Run records of one Experiment."""
    runs = [record for record in records if record.entity == "Run"]
    by_id = {(record.competition, record.ident): record for record in runs}
    attempts: dict[tuple[str, str, int], str] = {}
    for record in runs:
        experiment = str(record.data.get("experiment_id") or "")
        attempt = record.data.get("attempt")
        if not isinstance(attempt, int):
            continue
        key = (record.competition, experiment, attempt)
        if key in attempts:
            yield Finding(record.rel, "I5", f"attempt {attempt} of {experiment} already recorded in {attempts[key]}")
        attempts[key] = record.rel

        target = record.data.get("supersedes")
        if not target:
            continue
        earlier = by_id.get((record.competition, str(target)))
        if earlier is None:
            continue  # I4 already reported the dangling reference.
        if earlier.data.get("experiment_id") != experiment:
            yield Finding(record.rel, "I5", f"supersedes {target} belongs to a different experiment")
        earlier_attempt = earlier.data.get("attempt")
        if isinstance(earlier_attempt, int) and earlier_attempt >= attempt:
            yield Finding(record.rel, "I5", f"supersedes {target} has attempt {earlier_attempt} >= {attempt}")
        if earlier.data.get("status") not in ("failed", "cancelled"):
            yield Finding(
                record.rel,
                "I5",
                f"supersedes {target} has status {earlier.data.get('status')!r}: "
                "a succeeded run is never retried, it is superseded by a new experiment",
            )


def _experiment_run_backrefs(records: list[Record]) -> Iterator[Finding]:
    """I6 — Experiment.runs and Run.experiment_id agree in both directions."""
    experiments = {(record.competition, record.ident): record for record in records if record.entity == "Experiment"}
    actual: dict[tuple[str, str], set[str]] = {}
    for record in records:
        if record.entity != "Run":
            continue
        key = (record.competition, str(record.data.get("experiment_id") or ""))
        actual.setdefault(key, set()).add(record.ident)
    for key, experiment in experiments.items():
        listed = {str(value) for value in _as_list(experiment.data.get("runs"))}
        found = actual.get(key, set())
        for missing in sorted(found - listed):
            yield Finding(experiment.rel, "I6", f"Run {missing} names this experiment but is not listed in `runs`")
        for extra in sorted(listed - found):
            yield Finding(experiment.rel, "I6", f"`runs` lists {extra}, which does not name this experiment")


def _supersede_invariants(records: list[Record], index: dict[tuple[str, str, str], Record]) -> Iterator[Finding]:
    """I10 — a replacement submission only follows a reconciliation proving absence."""
    for record in records:
        if record.entity != "Submission":
            continue
        target = record.data.get("supersedes")
        if not target:
            continue
        earlier = index.get((record.competition, "Submission", str(target)))
        if earlier is None:
            continue  # I4 already reported it.
        outcome = (earlier.data.get("reconciliation") or {}).get("outcome")
        if outcome != "absent":
            yield Finding(
                record.rel,
                "I10",
                f"supersedes {target}, whose reconciliation outcome is {outcome!r}: only `absent` "
                "permits a replacement dispatch (ADR-0022 §5)",
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class Report:
    records: list[Record] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {spec.name: 0 for spec in ENTITIES}
        for record in self.records:
            tally[record.entity] += 1
        return tally


def validate(
    competition: str | None = None, competitions_dir: Path | None = None, contracts_dir: Path | None = None
) -> Report:
    """Validate every discovered record: shape first, then invariants."""
    schemas = load_schemas(contracts_dir)
    records = discover_records(competition, competitions_dir)
    report = Report(records=records)
    for record in records:
        report.findings.extend(iter_schema_errors(schemas[record.entity], record.data, record.rel))
    report.findings.extend(iter_invariant_errors(records))
    return report


def missing_entities(report: Report) -> list[str]:
    """Entities with no real record anywhere — the CI coverage floor."""
    return [name for name, count in report.counts().items() if count == 0]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        report = validate(args.competition)
    except (FileNotFoundError, yaml.YAMLError) as error:
        print(json.dumps({"ok": False, "side_effect": SideEffect.READ_ONLY.value, "error": str(error)}))
        return EXIT_RUNTIME

    gaps = missing_entities(report) if args.require_all_entities else []
    for finding in report.findings:
        warn(str(finding))
    for name in gaps:
        warn(f"no record found for entity {name}")

    print(
        json.dumps(
            {
                "ok": report.ok and not gaps,
                "side_effect": SideEffect.READ_ONLY.value,
                "competition": args.competition,
                "records": len(report.records),
                "counts": report.counts(),
                "errors": [finding.as_dict() for finding in report.findings],
                "entities_without_records": gaps,
            },
            ensure_ascii=False,
            indent=2 if args.verbose else None,
        )
    )
    return EXIT_OK if (report.ok and not gaps) else EXIT_RUNTIME


def cmd_schemas(args: argparse.Namespace) -> int:
    rows = [
        {
            "entity": spec.name,
            "schema": f"contracts/{spec.schema_file}",
            "id_field": spec.id_field,
            "id_pattern": spec.id_pattern,
            "record_path": spec.record_path,
        }
        for spec in ENTITIES
    ]
    print(
        json.dumps(
            {"ok": True, "side_effect": SideEffect.READ_ONLY.value, "entities": rows},
            ensure_ascii=False,
            indent=2 if args.verbose else None,
        )
    )
    return EXIT_OK


def add_parsers(sub: argparse._SubParsersAction) -> None:
    """Wire `kca contracts` into the top-level CLI."""
    parser = sub.add_parser("contracts", help="Ledger contract validation (READ_ONLY; ADR-0023).")
    group = parser.add_subparsers(dest="contracts_cmd", required=True)

    validate_parser = group.add_parser("validate", help="Validate ledger records against contracts/.")
    validate_parser.add_argument("--competition", default=None, help="Limit to one competition slug.")
    validate_parser.add_argument(
        "--require-all-entities",
        action="store_true",
        help="Also fail when any entity has no record in the tree (the CI coverage floor).",
    )
    validate_parser.add_argument("-v", "--verbose", action="store_true", help="Indent the JSON envelope.")
    validate_parser.set_defaults(func=cmd_validate)

    schemas_parser = group.add_parser("schemas", help="List entities, id patterns and record paths.")
    schemas_parser.add_argument("-v", "--verbose", action="store_true", help="Indent the JSON envelope.")
    schemas_parser.set_defaults(func=cmd_schemas)


__all__ = [
    "ENTITIES",
    "ENTITY_BY_NAME",
    "EntitySpec",
    "Finding",
    "Record",
    "Report",
    "SCHEMA_ANNOTATIONS",
    "SCHEMA_ASSERTIONS",
    "SUPPORTED_KEYWORDS",
    "add_parsers",
    "cmd_schemas",
    "cmd_validate",
    "collect_schema_keywords",
    "competition_dirs",
    "discover_records",
    "iter_invariant_errors",
    "iter_schema_errors",
    "load_schemas",
    "missing_entities",
    "normalise",
    "read_yaml",
    "validate",
]
