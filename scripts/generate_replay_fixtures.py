"""Generate small, original synthetic fixtures without reading competition data."""

from __future__ import annotations

import argparse
import csv
import io
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VERSION = "synthetic-2026-10-22"


def _csv(rows: list[dict]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _titanic() -> list[dict]:
    rng = random.Random(22101)
    rows = []
    for i in range(200):
        pclass = rng.randint(1, 3)
        sex = rng.choice(["female", "male"])
        age = rng.randint(2, 78)
        survived = int(sex == "female" or (pclass == 1 and age < 40))
        if rng.random() < 0.15:
            survived = 1 - survived
        rows.append(
            {
                "PassengerId": 900001 + i,
                "Survived": survived,
                "Pclass": pclass,
                "Name": f"Synthetic passenger {i:04d}",
                "Sex": sex,
                "Age": "" if i % 17 == 0 else age,
                "SibSp": rng.randint(0, 3),
                "Parch": rng.randint(0, 2),
                "Ticket": f"FIXTURE-{i:04d}",
                "Fare": round(12 + (4 - pclass) * 19 + rng.random() * 8, 2),
                "Cabin": "" if i % 5 == 0 else f"{rng.choice('ABC')}{i + 1}",
                "Embarked": rng.choice(["C", "Q", "S"]),
            }
        )
    return rows


def _house_prices() -> list[dict]:
    rng = random.Random(22102)
    rows = []
    for i in range(200):
        quality = rng.randint(3, 9)
        area = rng.randint(650, 2800)
        garage_cars = rng.randint(0, 3)
        year = rng.randint(1950, 2010)
        rows.append(
            {
                "Id": 900001 + i,
                "MSSubClass": rng.choice([20, 30, 60, 70]),
                "MSZoning": rng.choice(["RL", "RM", "FV"]),
                "LotFrontage": "" if i % 19 == 0 else rng.randint(40, 100),
                "LotArea": area * 3 + rng.randint(1000, 5000),
                "Street": rng.choice(["Pave", "Grvl"]),
                "LotShape": rng.choice(["Reg", "IR1", "IR2"]),
                "Neighborhood": rng.choice(["FixtureNorth", "FixtureSouth", "FixtureEast"]),
                "OverallQual": quality,
                "OverallCond": rng.randint(3, 8),
                "YearBuilt": year,
                "YearRemodAdd": min(2015, year + rng.randint(0, 20)),
                "GrLivArea": area,
                "FullBath": rng.randint(1, 3),
                "HalfBath": rng.randint(0, 1),
                "BedroomAbvGr": rng.randint(1, 5),
                "TotRmsAbvGrd": rng.randint(4, 10),
                "GarageCars": garage_cars,
                "GarageArea": garage_cars * 230,
                "SalePrice": 35000 + area * 62 + quality * 15000 + garage_cars * 8000 + rng.randint(-12000, 12000),
            }
        )
    return rows


def _spaceship(*, start: int, count: int, training: bool) -> list[dict]:
    rng = random.Random(22103 + start)
    rows = []
    for i in range(start, start + count):
        cryo = bool(rng.getrandbits(1))
        home = rng.choice(["Earth", "Europa", "Mars"])
        transported = cryo or home == "Europa"
        if rng.random() < 0.15:
            transported = not transported
        row = {
            "PassengerId": f"{9000 + i:04d}_01",
            "HomePlanet": home,
            "CryoSleep": cryo,
            "Cabin": "" if i % 23 == 0 else f"{rng.choice('ABCDEF')}/{i + 1}/{rng.choice('PS')}",
            "Destination": rng.choice(["TRAPPIST-1e", "PSO J318.5-22", "55 Cancri e"]),
            "Age": "" if i % 17 == 0 else rng.randint(2, 80),
            "VIP": bool(i % 13 == 0),
            "RoomService": 0 if cryo else rng.randint(0, 1200),
            "FoodCourt": 0 if cryo else rng.randint(0, 1800),
            "ShoppingMall": 0 if cryo else rng.randint(0, 900),
            "Spa": 0 if cryo else rng.randint(0, 1400),
            "VRDeck": 0 if cryo else rng.randint(0, 1000),
            "Name": f"Synthetic traveller {i:04d}",
        }
        if training:
            row["Transported"] = transported
        rows.append(row)
    return rows


def fixture_contents() -> dict[str, str]:
    test = _spaceship(start=300, count=40, training=False)
    return {
        "titanic/train.csv": _csv(_titanic()),
        "house-prices/train.csv": _csv(_house_prices()),
        "spaceship-titanic/train.csv": _csv(_spaceship(start=0, count=200, training=True)),
        "spaceship-titanic/test.csv": _csv(test),
        "spaceship-titanic/sample_submission.csv": _csv(
            [{"PassengerId": row["PassengerId"], "Transported": False} for row in test]
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed fixtures without modifying them.")
    args = parser.parse_args()
    mismatches = []
    for name, content in fixture_contents().items():
        path = ROOT / "tests/fixtures" / name
        if args.check:
            if not path.exists() or path.read_bytes() != content.encode():
                mismatches.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode())
    for name in mismatches:
        print(f"Synthetic fixture differs: {name}")
    print(f"{FIXTURE_VERSION}: {'check' if args.check else 'generation'} {'failed' if mismatches else 'passed'}")
    return int(bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())
