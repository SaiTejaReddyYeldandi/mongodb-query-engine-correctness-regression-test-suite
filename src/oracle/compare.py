"""
Helpers for comparing MongoDB results against oracle results.

THE ORDER PROBLEM
-----------------
A $group stage returns groups in an *unspecified* order. So:

    [{"_id": "A", "n": 2}, {"_id": "B", "n": 1}]

and

    [{"_id": "B", "n": 1}, {"_id": "A", "n": 2}]

are the *same correct answer*. If we compared the raw lists we'd get spurious
failures. So unless a pipeline ends in $sort (which DOES fix order), we
compare in an order-independent way by sorting both sides on a canonical key.
"""
from __future__ import annotations

import json
from typing import Any


def _canonical(doc: dict) -> str:
    """A stable string key for a document, so we can sort a list of docs
    deterministically regardless of dict key order."""
    return json.dumps(doc, sort_keys=True, default=str)


def normalize(results: list[dict]) -> list[str]:
    """Order-independent normalized form: sorted list of canonical strings."""
    return sorted(_canonical(d) for d in results)


def assert_same_unordered(mongo_result: list[dict], oracle_result: list[dict]) -> None:
    """Assert two result sets are equal ignoring document order."""
    m = normalize(mongo_result)
    o = normalize(oracle_result)
    assert m == o, (
        "Result mismatch (order-independent).\n"
        f"  MongoDB ({len(mongo_result)} docs): {mongo_result}\n"
        f"  Oracle  ({len(oracle_result)} docs): {oracle_result}"
    )


def assert_same_ordered(mongo_result: list[dict], oracle_result: list[dict]) -> None:
    """Assert two result sets are equal *including* order.

    Use this only when the pipeline ends in $sort/$limit so order is defined.
    """
    assert mongo_result == oracle_result, (
        "Result mismatch (ordered).\n"
        f"  MongoDB: {mongo_result}\n"
        f"  Oracle:  {oracle_result}"
    )
