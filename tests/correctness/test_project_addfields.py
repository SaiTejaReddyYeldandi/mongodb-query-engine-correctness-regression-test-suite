"""
$project / $addFields correctness: reshaping and computed fields.
"""
import pytest

pytestmark = pytest.mark.mongo

PROJECT_CASES = [
    pytest.param({"name": 1, "_id": 0},                                       id="include"),
    pytest.param({"name": 1, "dept": 1, "_id": 0},                            id="include-two"),
    pytest.param({"upper": {"$toUpper": "$name"}, "_id": 0},                  id="toUpper"),
    pytest.param({"label": {"$concat": ["$name", "@", "$dept"]}, "_id": 0},   id="concat"),
    pytest.param({"raise": {"$multiply": ["$salary", 2]}, "_id": 0},          id="multiply-int"),
    pytest.param({"tenth": {"$divide": ["$salary", 10]}, "_id": 0},           id="divide"),
    pytest.param({"seniority": {"$cond": [{"$gte": ["$age", 40]}, "senior", "junior"]}, "_id": 0}, id="cond"),
    pytest.param({"n_tags": {"$size": "$tags"}, "_id": 0},                    id="size"),
    pytest.param({"first_tag": {"$arrayElemAt": ["$tags", 0]}, "_id": 0},     id="arrayElemAt"),
]


@pytest.mark.parametrize("project", PROJECT_CASES)
def test_project(agg, data, project):
    agg(data.employees, data.emp_docs, [{"$project": project}])


def test_addfields_keeps_originals(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$addFields": {"bonus": {"$multiply": ["$salary", 0.1]}}}])


def test_set_alias_of_addfields(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$set": {"has_tags": {"$gt": [{"$size": "$tags"}, 0]}}}])


def test_project_ifnull(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$project": {"first_tag": {"$ifNull": [{"$arrayElemAt": ["$tags", 0]}, "none"]}, "_id": 0}}])
