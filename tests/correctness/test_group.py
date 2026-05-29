"""
$group correctness: grouping keys and accumulators.
Group output order is undefined, so comparisons are order-independent
(the `agg` helper defaults to unordered).
"""
import pytest

pytestmark = pytest.mark.mongo

GROUP_CASES = [
    pytest.param({"_id": "$dept", "n": {"$sum": 1}},                       id="count"),
    pytest.param({"_id": "$dept", "total": {"$sum": "$salary"}},           id="sum"),
    pytest.param({"_id": "$dept", "avg": {"$avg": "$salary"}},             id="avg"),
    pytest.param({"_id": "$dept", "lo": {"$min": "$age"}},                 id="min"),
    pytest.param({"_id": "$dept", "hi": {"$max": "$age"}},                 id="max"),
    pytest.param({"_id": "$active", "n": {"$sum": 1}},                     id="group-by-bool"),
    pytest.param({"_id": None, "grand_total": {"$sum": "$salary"}},        id="group-all"),
    pytest.param({"_id": {"d": "$dept", "a": "$active"}, "n": {"$sum": 1}}, id="compound-key"),
    pytest.param({"_id": "$dept", "total": {"$sum": "$salary"},
                  "avg": {"$avg": "$salary"}, "n": {"$sum": 1}},           id="multi-acc"),
]


@pytest.mark.parametrize("group", GROUP_CASES)
def test_group(agg, data, group):
    agg(data.employees, data.emp_docs, [{"$group": group}])


def test_group_push_with_stable_input(agg, data):
    # $push order follows input order -> sort first for determinism
    agg(data.employees, data.emp_docs,
        [{"$sort": {"_id": 1}},
         {"$group": {"_id": "$dept", "names": {"$push": "$name"}}}])


def test_group_first_last(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$sort": {"salary": 1}},
         {"$group": {"_id": "$dept",
                     "cheapest": {"$first": "$name"},
                     "priciest": {"$last": "$name"}}}])


def test_group_then_sort_is_ordered(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$group": {"_id": "$dept", "total": {"$sum": "$salary"}}},
         {"$sort": {"total": -1}}],
        ordered=True)
