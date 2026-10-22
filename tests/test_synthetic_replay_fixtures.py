"""Publication fixtures must be generated locally, with usable replay contracts."""

import csv
import io
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _rows(name):
    return list(csv.DictReader(io.StringIO((ROOT / "tests/fixtures" / name).read_text())))


def test_checked_in_fixtures_match_the_offline_generator():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_replay_fixtures.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_training_fixtures_have_replayable_targets_and_synthetic_identifiers():
    for name, target in [("titanic", "Survived"), ("spaceship-titanic", "Transported")]:
        rows = _rows(f"{name}/train.csv")
        assert len(rows) == 200
        assert len({row[target] for row in rows}) == 2
        assert all(row["Name"].startswith("Synthetic ") for row in rows)
        assert any(row["Age"] == "" for row in rows)
    houses = _rows("house-prices/train.csv")
    assert len(houses) == 200
    assert all(float(row["SalePrice"]) > 0 for row in houses)
    assert all(row["Neighborhood"].startswith("Fixture") for row in houses)
    assert any(row["LotFrontage"] == "" for row in houses)


def test_spaceship_submission_preserves_test_ids_without_training_overlap():
    train_ids = {row["PassengerId"] for row in _rows("spaceship-titanic/train.csv")}
    test = _rows("spaceship-titanic/test.csv")
    sample = _rows("spaceship-titanic/sample_submission.csv")
    assert len(test) == len(sample) == 40
    assert [row["PassengerId"] for row in test] == [row["PassengerId"] for row in sample]
    assert len({row["PassengerId"] for row in test}) == len(test)
    assert train_ids.isdisjoint(row["PassengerId"] for row in test)
