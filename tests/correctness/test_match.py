"""
$match correctness: filter predicates. Each case runs on real MongoDB AND the
oracle and asserts agreement.
"""
import pytest

pytestmark = pytest.mark.mongo

MATCH_CASES = [
    pytest.param({"dept": "eng"},                              id="eq-implicit"),
    pytest.param({"salary": {"$gt": 100}},                     id="gt"),
    pytest.param({"salary": {"$gte": 120}},                    id="gte"),
    pytest.param({"age": {"$lt": 30}},                         id="lt"),
    pytest.param({"age": {"$lte": 34}},                        id="lte"),
    pytest.param({"dept": {"$ne": "eng"}},                     id="ne"),
    pytest.param({"dept": {"$in": ["eng", "ops"]}},            id="in"),
    pytest.param({"dept": {"$nin": ["eng"]}},                  id="nin"),
    pytest.param({"dept": "eng", "age": {"$lt": 40}},          id="implicit-and"),
    pytest.param({"salary": {"$gt": 90, "$lt": 200}},          id="range"),
    pytest.param({"active": True},                             id="bool"),
    pytest.param({"$or": [{"dept": "ops"}, {"salary": {"$gte": 150}}]}, id="or"),
    pytest.param({"tags": "python"},                           id="array-contains"),
    pytest.param({"tags": {"$size": 2}},                       id="array-size"),
    pytest.param({"$expr": {"$gt": ["$salary", {"$multiply": ["$age", 3]}]}}, id="expr"),
]


@pytest.mark.parametrize("query", MATCH_CASES)
def test_match(agg, data, query):
    agg(data.employees, data.emp_docs, [{"$match": query}])


def test_match_then_count(agg, data):
    agg(data.employees, data.emp_docs,
        [{"$match": {"dept": "eng"}}, {"$count": "n"}])
