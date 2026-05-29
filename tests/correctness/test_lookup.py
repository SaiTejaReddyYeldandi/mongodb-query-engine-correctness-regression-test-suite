"""
$lookup correctness: equality joins between employees and departments.

Joined-array order is not guaranteed, so we make pipelines deterministic
(via $unwind + $sort) or compare order-independent counts.
"""
import pytest

pytestmark = pytest.mark.mongo


def test_lookup_attaches_department(agg, data):
    # compare the SIZE of the joined array (order-independent fact)
    agg(data.employees, data.emp_docs,
        [{"$lookup": {"from": "departments", "localField": "dept",
                      "foreignField": "_id", "as": "d"}},
         {"$project": {"name": 1, "n_dept": {"$size": "$d"}, "_id": 0}}],
        collections=data.collections)


def test_lookup_unwind_denormalize(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$lookup": {"from": "departments", "localField": "dept",
                      "foreignField": "_id", "as": "d"}},
         {"$unwind": "$d"},
         {"$project": {"name": 1, "floor": "$d.floor", "budget": "$d.budget", "_id": 0}},
         {"$sort": {"name": 1}}],
        ordered=True,
        collections=data.collections)


def test_lookup_then_group_by_floor(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$lookup": {"from": "departments", "localField": "dept",
                      "foreignField": "_id", "as": "d"}},
         {"$unwind": "$d"},
         {"$group": {"_id": "$d.floor", "headcount": {"$sum": 1}}}],
        collections=data.collections)


def test_reverse_lookup_has_empty_match(agg, data):
    # HR department has no employees -> joined array must be empty for it
    agg(data.departments, data.dept_docs,
        [{"$lookup": {"from": "employees", "localField": "_id",
                      "foreignField": "dept", "as": "staff"}},
         {"$project": {"label": 1, "n_staff": {"$size": "$staff"}, "_id": 1}},
         {"$sort": {"_id": 1}}],
        ordered=True,
        collections=data.collections)
