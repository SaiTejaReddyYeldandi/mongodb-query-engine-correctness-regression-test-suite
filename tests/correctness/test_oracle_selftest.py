"""
Self-tests for the ORACLE ITSELF (no MongoDB needed).

Why test the oracle? Because the oracle is the source of truth in every other
test. If the oracle were buggy, our correctness tests would happily agree on
a WRONG answer. So we pin the oracle's behaviour with hand-verified examples.
These run in milliseconds and require no Docker -- they are the "fast lane".
"""
from __future__ import annotations

import pytest

from oracle import run_pipeline

pytestmark = pytest.mark.oracle

DOCS = [
    {"_id": 1, "name": "Ann",  "dept": "eng",   "salary": 100, "tags": ["a", "b"]},
    {"_id": 2, "name": "Bob",  "dept": "eng",   "salary": 120, "tags": ["b"]},
    {"_id": 3, "name": "Cleo", "dept": "sales", "salary": 90,  "tags": []},
    {"_id": 4, "name": "Dan",  "dept": "sales", "salary": 200, "tags": ["c"]},
]


def test_match_gt():
    r = run_pipeline(DOCS, [{"$match": {"salary": {"$gt": 100}}}])
    assert {d["name"] for d in r} == {"Bob", "Dan"}


def test_group_sum_and_count():
    r = run_pipeline(DOCS, [{"$group": {"_id": "$dept",
                                        "total": {"$sum": "$salary"},
                                        "n": {"$sum": 1}}}])
    by_dept = {d["_id"]: d for d in r}
    assert by_dept["eng"] == {"_id": "eng", "total": 220, "n": 2}
    assert by_dept["sales"] == {"_id": "sales", "total": 290, "n": 2}


def test_unwind_drops_empty_arrays():
    r = run_pipeline(DOCS, [{"$unwind": "$tags"}])
    assert len(r) == 4                      # Cleo's [] is dropped
    assert sorted(d["tags"] for d in r) == ["a", "b", "b", "c"]


def test_project_excludes_id():
    r = run_pipeline(DOCS, [{"$project": {"name": 1, "_id": 0}}])
    assert all(set(d.keys()) == {"name"} for d in r)


def test_multistage_match_sort_limit_is_ordered():
    r = run_pipeline(DOCS, [
        {"$match": {"dept": "eng"}},
        {"$sort": {"salary": -1}},
        {"$project": {"name": 1, "salary": 1, "_id": 0}},
    ])
    assert r == [{"name": "Bob", "salary": 120}, {"name": "Ann", "salary": 100}]


def test_compound_group_key():
    r = run_pipeline(DOCS, [{"$group": {"_id": {"d": "$dept"}, "n": {"$sum": 1}}}])
    keys = sorted(d["_id"]["d"] for d in r)
    assert keys == ["eng", "sales"]
