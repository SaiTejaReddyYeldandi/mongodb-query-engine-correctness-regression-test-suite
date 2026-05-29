"""Generate/refresh golden output files from the trusted oracle.

Run:  py scripts/generate_golden.py
Writes tests/regression/golden/<name>.json for every query in GOLDEN_QUERIES.
Re-run intentionally when you've verified a new expected output is correct.
"""
import json
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "tests", "regression"))

from oracle import run_pipeline                  # noqa: E402
from oracle.compare import normalize             # noqa: E402
from golden_queries import GOLDEN_QUERIES        # noqa: E402

# Mirror of conftest.EMPLOYEES (kept here so the generator is standalone).
EMPLOYEES = [
    {"_id": 1, "name": "Ann",  "dept": "eng",   "salary": 100, "age": 34, "tags": ["python", "mongo"], "active": True},
    {"_id": 2, "name": "Bob",  "dept": "eng",   "salary": 120, "age": 41, "tags": ["go"],              "active": True},
    {"_id": 3, "name": "Cleo", "dept": "sales", "salary": 90,  "age": 29, "tags": [],                  "active": False},
    {"_id": 4, "name": "Dan",  "dept": "sales", "salary": 200, "age": 52, "tags": ["python"],          "active": True},
    {"_id": 5, "name": "Eve",  "dept": "eng",   "salary": 150, "age": 38, "tags": ["rust", "go"],      "active": True},
    {"_id": 6, "name": "Finn", "dept": "ops",   "salary": 80,  "age": 26, "tags": ["python", "bash"],  "active": False},
    {"_id": 7, "name": "Gwen", "dept": "ops",   "salary": 130, "age": 47, "tags": [],                  "active": True},
]

OUT_DIR = os.path.join(HERE, "..", "tests", "regression", "golden")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, pipeline in GOLDEN_QUERIES.items():
        result = run_pipeline([dict(d) for d in EMPLOYEES], pipeline)
        golden = {"pipeline": pipeline, "expected_normalized": normalize(result)}
        path = os.path.join(OUT_DIR, f"{name}.json")
        with open(path, "w") as f:
            json.dump(golden, f, indent=2)
        print(f"wrote {path}  ({len(result)} docs)")


if __name__ == "__main__":
    main()
