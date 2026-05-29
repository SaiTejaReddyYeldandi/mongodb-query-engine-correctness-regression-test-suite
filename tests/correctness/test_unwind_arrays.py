"""
Nested array operations: $unwind (incl. options), $filter, $map, $arrayElemAt.
"""
import pytest

pytestmark = pytest.mark.mongo


def test_unwind_tags(agg, data):
    agg(data.employees, data.emp_docs, [{"$unwind": "$tags"}])


def test_unwind_preserve_empty(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$unwind": {"path": "$tags", "preserveNullAndEmptyArrays": True}}])


def test_unwind_with_index(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$unwind": {"path": "$tags", "includeArrayIndex": "tag_idx"}}])


def test_unwind_then_group_tag_frequency(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$unwind": "$tags"},
         {"$group": {"_id": "$tags", "count": {"$sum": 1}}}])


def test_unwind_group_sort_ordered(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$unwind": "$tags"},
         {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
         {"$sort": {"count": -1, "_id": 1}}],
        ordered=True)


def test_filter_array(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$project": {"py": {"$filter": {"input": "$tags", "as": "t",
                                          "cond": {"$eq": ["$$t", "python"]}}}, "_id": 0}}])


def test_map_array(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$project": {"upper_tags": {"$map": {"input": "$tags", "as": "t",
                                               "in": {"$toUpper": "$$t"}}}, "_id": 0}}])
