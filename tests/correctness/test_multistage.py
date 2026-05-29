"""
Realistic multi-stage pipelines combining several stages. These mimic the
kind of analytics queries an application actually runs.
"""
import pytest

pytestmark = pytest.mark.mongo


def test_top_earners_per_dept(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$match": {"active": True}},
         {"$group": {"_id": "$dept", "top": {"$max": "$salary"}}},
         {"$sort": {"top": -1}}],
        ordered=True)


def test_filter_project_sort_limit(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$match": {"dept": "eng"}},
         {"$project": {"name": 1, "salary": 1, "_id": 0}},
         {"$sort": {"salary": -1}},
         {"$limit": 2}],
        ordered=True)


def test_skip_and_limit_pagination(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$sort": {"salary": -1}},
         {"$skip": 2},
         {"$limit": 3},
         {"$project": {"name": 1, "salary": 1, "_id": 0}}],
        ordered=True)


def test_tag_popularity_report(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$match": {"active": True}},
         {"$unwind": "$tags"},
         {"$group": {"_id": "$tags", "n": {"$sum": 1}}},
         {"$sort": {"n": -1, "_id": 1}}],
        ordered=True)


def test_join_aggregate_report(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$lookup": {"from": "departments", "localField": "dept",
                      "foreignField": "_id", "as": "d"}},
         {"$unwind": "$d"},
         {"$group": {"_id": "$d.label",
                     "payroll": {"$sum": "$salary"},
                     "headcount": {"$sum": 1}}},
         {"$sort": {"payroll": -1}}],
        ordered=True,
        collections=data.collections)
