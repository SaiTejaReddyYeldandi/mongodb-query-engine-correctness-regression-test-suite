"""
Golden-output regression.

For every frozen golden file we re-run the pipeline against BOTH the oracle
(fast, no Docker) and real MongoDB (Docker), and assert the normalized output
still matches what was frozen. A mismatch means output silently changed --
either a MongoDB regression across versions or an unintended oracle change.

To intentionally update goldens (after verifying correctness):
    py scripts/generate_golden.py
"""
from __future__ import annotations

import json
import os

import pytest

from oracle import run_pipeline
from oracle.compare import normalize
from golden_queries import GOLDEN_QUERIES
from sample_data import EMPLOYEES

pytestmark = pytest.mark.regression

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _load(name):
    with open(os.path.join(GOLDEN_DIR, f"{name}.json")) as f:
        return json.load(f)


@pytest.mark.parametrize("name", list(GOLDEN_QUERIES))
def test_oracle_matches_golden(name):
    """Fast lane: the oracle output must still match the frozen golden."""
    golden = _load(name)
    result = run_pipeline([dict(d) for d in EMPLOYEES], GOLDEN_QUERIES[name])
    assert normalize(result) == golden["expected_normalized"]


@pytest.mark.mongo
@pytest.mark.parametrize("name", list(GOLDEN_QUERIES))
def test_mongo_matches_golden(data, name):
    """Docker lane: real MongoDB output must still match the frozen golden."""
    golden = _load(name)
    result = list(data.employees.aggregate(GOLDEN_QUERIES[name]))
    assert normalize(result) == golden["expected_normalized"]
