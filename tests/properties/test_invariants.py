"""
Property-based tests (Hypothesis).

Instead of hand-picked examples, we assert ALGEBRAIC INVARIANTS that must hold
for ANY valid input, and let Hypothesis throw hundreds of randomized documents
and queries at them. When an invariant breaks, Hypothesis shrinks the failure
to a minimal reproducing example.

These run against the ORACLE only -> no Docker needed -> part of the fast lane.
A separate property test (test_match_matches_mongo) cross-checks the oracle
against real MongoDB on random predicates.
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from oracle import run_pipeline

pytestmark = pytest.mark.property

# ---- strategies: generate employee-like documents ------------------------
depts = st.sampled_from(["eng", "sales", "ops", "hr"])
small_str = st.sampled_from(["python", "go", "rust", "bash", "mongo"])

doc_strategy = st.fixed_dictionaries({
    "salary": st.integers(min_value=0, max_value=500),
    "age": st.integers(min_value=18, max_value=70),
    "dept": depts,
    "tags": st.lists(small_str, max_size=4),
})


@st.composite
def docs_with_ids(draw):
    raw = draw(st.lists(doc_strategy, min_size=0, max_size=12))
    return [{**d, "_id": i} for i, d in enumerate(raw)]


# ---- 1. Composability of $match -----------------------------------------
@given(docs=docs_with_ids(), t1=st.integers(0, 500), t2=st.integers(18, 70))
@settings(max_examples=150)
def test_match_then_match_equals_and(docs, t1, t2):
    """$match A then $match B  ==  $match {A and B}."""
    a = {"salary": {"$gte": t1}}
    b = {"age": {"$lte": t2}}
    sequential = run_pipeline(docs, [{"$match": a}, {"$match": b}])
    combined = run_pipeline(docs, [{"$match": {"$and": [a, b]}}])
    assert sequential == combined


# ---- 2. $limit idempotence ----------------------------------------------
@given(docs=docs_with_ids(), n=st.integers(0, 15), m=st.integers(0, 15))
@settings(max_examples=100)
def test_double_limit_equals_min(docs, n, m):
    """$limit n then $limit m  ==  $limit min(n, m)."""
    two = run_pipeline(docs, [{"$limit": n}, {"$limit": m}])
    one = run_pipeline(docs, [{"$limit": min(n, m)}])
    assert two == one


# ---- 3. $sort idempotence -----------------------------------------------
@given(docs=docs_with_ids())
@settings(max_examples=100)
def test_sort_is_idempotent(docs):
    """Sorting twice equals sorting once."""
    once = run_pipeline(docs, [{"$sort": {"salary": 1, "_id": 1}}])
    twice = run_pipeline(once, [{"$sort": {"salary": 1, "_id": 1}}])
    assert once == twice


# ---- 4. $group count conservation ---------------------------------------
@given(docs=docs_with_ids())
@settings(max_examples=100)
def test_group_counts_sum_to_total(docs):
    """The sum of per-group counts equals the total number of documents."""
    grouped = run_pipeline(docs, [{"$group": {"_id": "$dept", "n": {"$sum": 1}}}])
    assert sum(g["n"] for g in grouped) == len(docs)


# ---- 5. $unwind expands to total array length ---------------------------
@given(docs=docs_with_ids())
@settings(max_examples=100)
def test_unwind_count_equals_total_tags(docs):
    """Unwinding `tags` yields exactly sum(len(tags)) documents."""
    unwound = run_pipeline(docs, [{"$unwind": "$tags"}])
    assert len(unwound) == sum(len(d["tags"]) for d in docs)


# ---- 6. empty $match is identity ----------------------------------------
@given(docs=docs_with_ids())
@settings(max_examples=80)
def test_empty_match_is_identity(docs):
    assert run_pipeline(docs, [{"$match": {}}]) == docs


# ---- 7. $skip + $limit partitions a sorted stream -----------------------
@given(docs=docs_with_ids(), skip=st.integers(0, 12))
@settings(max_examples=100)
def test_skip_preserves_remainder(docs, skip):
    """After a stable sort, $skip k returns exactly the tail after the first k."""
    sort_stage = {"$sort": {"_id": 1}}
    full = run_pipeline(docs, [sort_stage])
    skipped = run_pipeline(docs, [sort_stage, {"$skip": skip}])
    assert skipped == full[skip:]


# ---- 8. cross-check oracle against REAL MongoDB on random predicates -----
@pytest.mark.mongo
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(threshold=st.integers(0, 250), dept=depts)
def test_match_matches_mongo(data, threshold, dept):
    """For random predicates, MongoDB and the oracle must agree."""
    from oracle.compare import normalize
    pipeline = [{"$match": {"dept": dept, "salary": {"$gte": threshold}}}]
    m = list(data.employees.aggregate(pipeline))
    o = run_pipeline(data.emp_docs, pipeline)
    assert normalize(m) == normalize(o)