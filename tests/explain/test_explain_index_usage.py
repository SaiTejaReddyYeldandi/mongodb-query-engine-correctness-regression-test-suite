"""
explain() plan parsing: assert *performance* characteristics, not just output.

We verify that:
  - a query on an INDEXED field uses an index scan (IXSCAN),
  - a query on a NON-indexed field falls back to a collection scan (COLLSCAN),
  - the number of documents examined is sane.

The explain() document shape differs across MongoDB 6/7/8, so we parse it
defensively by recursively collecting all "stage" values rather than relying
on a fixed path.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.mongo


def _collect_values(node, key):
    """Recursively collect every value stored under `key` anywhere in a nested
    dict/list structure (robust to version differences in explain output)."""
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                found.append(v)
            found.extend(_collect_values(v, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(_collect_values(item, key))
    return found


def _find_numbers(node, key):
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, (int, float)):
                out.append(v)
            out.extend(_find_numbers(v, key))
    elif isinstance(node, list):
        for item in node:
            out.extend(_find_numbers(item, key))
    return out


def _explain(coll, pipeline):
    db = coll.database
    return db.command(
        "explain",
        {"aggregate": coll.name, "pipeline": pipeline, "cursor": {}},
        verbosity="executionStats",
    )


def test_indexed_field_uses_ixscan(indexed_employees):
    plan = _explain(indexed_employees, [{"$match": {"dept": "eng"}}])
    stages = _collect_values(plan, "stage")
    assert "IXSCAN" in stages, f"expected IXSCAN, got stages={stages}"
    assert "COLLSCAN" not in stages, f"unexpected COLLSCAN in {stages}"


def test_indexed_range_uses_ixscan(indexed_employees):
    plan = _explain(indexed_employees, [{"$match": {"salary": {"$gte": 120}}}])
    stages = _collect_values(plan, "stage")
    assert "IXSCAN" in stages, f"expected IXSCAN, got stages={stages}"


def test_unindexed_field_uses_collscan(indexed_employees):
    # `age` has no index -> engine must scan the whole collection
    plan = _explain(indexed_employees, [{"$match": {"age": {"$gt": 40}}}])
    stages = _collect_values(plan, "stage")
    assert "COLLSCAN" in stages, f"expected COLLSCAN, got stages={stages}"


def test_indexed_query_examines_fewer_docs(indexed_employees):
    plan = _explain(indexed_employees, [{"$match": {"dept": "eng"}}])
    examined = _find_numbers(plan, "totalDocsExamined") or _find_numbers(plan, "docsExamined")
    assert examined, "could not find docsExamined in explain output"
    # 3 engineers exist; an index scan should examine far fewer than 7 total
    assert min(examined) <= 3, f"index scan examined too many docs: {examined}"
