"""
Type coercion edge cases: $toInt, $toString, $toDouble, $toBool, $type.

These are exactly the operations where engine and oracle can subtly disagree,
so we pin well-defined conversions. We use a dedicated mixed-type dataset.
"""
import pytest

pytestmark = pytest.mark.mongo

COERCION_DOCS = [
    {"_id": 1, "d": 3.7, "i": 5,  "s": "hello", "flag": True,  "arr": [1, 2]},
    {"_id": 2, "d": -2.9, "i": 0, "s": "world", "flag": False, "arr": []},
    {"_id": 3, "d": 10.0, "i": 42, "s": "abc",  "flag": True,  "arr": [9]},
]


@pytest.fixture()
def coercion(mongo_client):
    db = mongo_client.get_database("testdb")
    coll = db.get_collection("coercion")
    coll.drop()
    coll.insert_many([dict(d) for d in COERCION_DOCS])
    yield coll, [dict(d) for d in COERCION_DOCS]
    coll.drop()


def _check(agg, coercion, project):
    coll, docs = coercion
    agg(coll, docs, [{"$project": {**project, "_id": 1}}, {"$sort": {"_id": 1}}], ordered=True)


def test_toInt_truncates_double(agg, coercion):
    _check(agg, coercion, {"x": {"$toInt": "$d"}})


def test_toInt_of_bool(agg, coercion):
    _check(agg, coercion, {"x": {"$toInt": "$flag"}})


def test_toString_of_double(agg, coercion):
    _check(agg, coercion, {"x": {"$toString": "$d"}})


def test_toString_of_int(agg, coercion):
    _check(agg, coercion, {"x": {"$toString": "$i"}})


def test_toDouble_of_int(agg, coercion):
    _check(agg, coercion, {"x": {"$toDouble": "$i"}})


def test_toBool_of_int(agg, coercion):
    _check(agg, coercion, {"x": {"$toBool": "$i"}})


def test_type_of_each_field(agg, coercion):
    _check(agg, coercion, {
        "td": {"$type": "$d"},
        "ti": {"$type": "$i"},
        "ts": {"$type": "$s"},
        "tflag": {"$type": "$flag"},
        "tarr": {"$type": "$arr"},
    })
