"""Cross-file checks for the phase-1 records agents actually read (ADR-0022).

These check documents and YAML, not the future budget/approval runtime. No
credentials, external APIs, or competition actions are involved.
"""

from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
ADR = (ROOT / "docs/adr/0022-long-run-competition-operating-model.md").read_text()
TEMPLATE = ROOT / "competitions/_templates/competition.yaml"
LIVE = sorted(p for p in (ROOT / "competitions").glob("*/competition.yaml") if not p.parent.name.startswith("_"))
YAML_BLOCKS = re.findall(r"```yaml\n(.*?)\n```", ADR, re.S)


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject silently overwritten configuration, including nested mappings."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        assert key not in result, f"duplicate YAML key: {key}"
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(text):
    return yaml.load(text, Loader=UniqueKeyLoader)


def leaf_keys(value, prefix=()):
    return {
        path
        for key, child in value.items()
        for path in (leaf_keys(child, (*prefix, key)) if isinstance(child, dict) else {(*prefix, key)})
    }


@pytest.mark.parametrize("path", [TEMPLATE, *LIVE], ids=lambda p: p.parent.name)
def test_budget_and_state_records_match_the_canonical_contract(path):
    record = read_yaml(path.read_text())
    template = read_yaml(TEMPLATE.read_text())
    documented = next(read_yaml(block)["budget"] for block in YAML_BLOCKS if "\nbudget:\n" in block)
    assert leaf_keys(record["budget"]) == leaf_keys(template["budget"]) == leaf_keys(documented)
    assert "phase" not in record
    assert record["status"] in {"open", "closed", "unknown"}
    main_table, side_table = ADR.split("**Canonical state tokens.**", 1)[1].split("**Side states**", 1)
    side_table = side_table.split("**A side state must record", 1)[0]
    main_states = set(re.findall(r"^\| `([A-Z_]+)` \|", main_table, re.M))
    side_states = set(re.findall(r"^\| `([A-Z_]+)` \|", side_table, re.M))
    assert record["state"] in main_states | side_states
    if record["state"] in side_states:
        assert record["resume_state"] in main_states
        assert record["state_reason"]
    if record.get("autonomy_config"):
        config = read_yaml((path.parent / record["autonomy_config"]).read_text())
        assert isinstance(config, dict)
    budget = record["budget"]
    limit = budget["submissions"]["verified_daily_limit"]
    held = budget["submissions"]["reserve_for_human"]
    assert type(held) is int and held >= 0
    if limit is not None:
        assert type(limit) is int and limit >= held
        for key in ("verified_source", "verified_at", "verified_reset_boundary"):
            assert budget["submissions"][key], key


@pytest.mark.parametrize("path", LIVE, ids=lambda p: p.parent.name)
def test_dashboard_mirrors_state_and_status(path):
    record = read_yaml(path.read_text())
    slug = record["slug"]
    dashboard = (ROOT / "competitions/README.md").read_text()
    rows = [line for line in dashboard.splitlines() if line.startswith(f"| [{slug}]")]
    assert len(rows) == 1
    cells = [cell.strip() for cell in rows[0].split("|")]
    assert cells[2] == record["state"]
    assert cells[4] == record["status"]
    if record["status"] == "closed" and record["best"]["public_lb"] is None:
        assert "unknown" in cells[6].lower()


def test_intent_example_and_ledger_share_an_action_identity():
    examples = [read_yaml(block) for block in YAML_BLOCKS]
    intent = next(e for e in examples if "budget_reservations" in e)
    reservation = next(e for e in examples if "reserved_at" in e)
    terminal = next(e for e in examples if "outcome" in e)
    assert intent["ref"] != intent["experiment_id"]
    assert intent["scenario"] in {1, 2, 3}
    assert intent["external_id"] is None  # persisted before the external call
    assert reservation["ref"] == intent["ref"]
    assert intent["budget_reservations"][f"{reservation['scope']}/{reservation['dimension']}"] == reservation["id"]
    assert terminal["id"] == reservation["id"]
    assert 0 <= terminal["amount"] <= reservation["amount"]


def test_existing_autonomy_annotation_preserves_the_documented_gate_floor():
    old_adr = (ROOT / "docs/adr/0021-kca-autonomy-model.md").read_text()
    schema = read_yaml(re.search(r"```yaml\n(.*?)\n```", old_adr, re.S).group(1))
    expected = set(schema["_base"]["autonomy"]["human_gated"])
    assert len(expected) == 7
    for path in LIVE:
        record = read_yaml(path.read_text())
        if not record.get("autonomy_config"):
            continue
        config = read_yaml((path.parent / record["autonomy_config"]).read_text())
        block = config.get("autonomy", config.get("_base", {}).get("autonomy"))
        if block is not None:
            assert expected <= set(block["human_gated"])
