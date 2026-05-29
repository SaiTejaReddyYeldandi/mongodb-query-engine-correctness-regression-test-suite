"""
Shared pytest fixtures.

We run a REAL MongoDB inside a throwaway Docker container (testcontainers),
controlled by MONGO_IMAGE so the CI matrix can target mongo:6.0/7.0/8.0.
Both MongoDB and the oracle are loaded from the SAME source data, so any
disagreement is a genuine engine/oracle discrepancy.
"""
from __future__ import annotations

import os
import sys

import pytest

# Make src/ importable (so `from oracle import ...` works)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))  # make tests/ modules importable

MONGO_IMAGE = os.environ.get("MONGO_IMAGE", "mongo:7.0")


from sample_data import EMPLOYEES, DEPARTMENTS  # noqa: E402


@pytest.fixture(scope="session")
def mongo_client():
    from pymongo import MongoClient
    from testcontainers.mongodb import MongoDbContainer
    with MongoDbContainer(MONGO_IMAGE) as container:
        client = MongoClient(container.get_connection_url())
        client.admin.command("ping")
        yield client
        client.close()


class _Dataset:
    """Bundles the live Mongo collections plus the raw docs for the oracle."""
    def __init__(self, db):
        self.db = db
        self.employees = db.get_collection("employees")
        self.departments = db.get_collection("departments")
        self.employees.drop()
        self.departments.drop()
        self.employees.insert_many([dict(d) for d in EMPLOYEES])
        self.departments.insert_many([dict(d) for d in DEPARTMENTS])

    @property
    def emp_docs(self):
        return [dict(d) for d in EMPLOYEES]

    @property
    def dept_docs(self):
        return [dict(d) for d in DEPARTMENTS]

    @property
    def collections(self):
        return {"departments": self.dept_docs, "employees": self.emp_docs}


@pytest.fixture()
def data(mongo_client):
    ds = _Dataset(mongo_client.get_database("testdb"))
    yield ds
    ds.employees.drop()
    ds.departments.drop()


@pytest.fixture()
def indexed_employees(mongo_client):
    """Employees collection WITH an index on `dept` and `salary` -- used by the
    explain() tests to assert IXSCAN vs COLLSCAN."""
    db = mongo_client.get_database("testdb")
    coll = db.get_collection("employees_indexed")
    coll.drop()
    coll.insert_many([dict(d) for d in EMPLOYEES])
    coll.create_index("dept")
    coll.create_index("salary")
    yield coll
    coll.drop()


@pytest.fixture()
def agg():
    """Return a helper that runs the SAME pipeline on Mongo and the oracle and
    asserts they agree. `ordered=True` only when the pipeline ends in $sort."""
    from oracle import run_pipeline
    from oracle.compare import assert_same_unordered, assert_same_ordered

    def _run(collection, oracle_docs, pipeline, ordered=False, collections=None):
        mongo_result = list(collection.aggregate(pipeline))
        oracle_result = run_pipeline(oracle_docs, pipeline, collections=collections)
        if ordered:
            assert_same_ordered(mongo_result, oracle_result)
        else:
            assert_same_unordered(mongo_result, oracle_result)
        return mongo_result, oracle_result

    return _run
