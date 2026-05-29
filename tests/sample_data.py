"""Single source of truth for test datasets, imported by conftest and the
golden regression tests so Mongo and the oracle always load identical data."""

EMPLOYEES = [
    {"_id": 1, "name": "Ann",  "dept": "eng",   "salary": 100, "age": 34, "tags": ["python", "mongo"], "active": True},
    {"_id": 2, "name": "Bob",  "dept": "eng",   "salary": 120, "age": 41, "tags": ["go"],              "active": True},
    {"_id": 3, "name": "Cleo", "dept": "sales", "salary": 90,  "age": 29, "tags": [],                  "active": False},
    {"_id": 4, "name": "Dan",  "dept": "sales", "salary": 200, "age": 52, "tags": ["python"],          "active": True},
    {"_id": 5, "name": "Eve",  "dept": "eng",   "salary": 150, "age": 38, "tags": ["rust", "go"],      "active": True},
    {"_id": 6, "name": "Finn", "dept": "ops",   "salary": 80,  "age": 26, "tags": ["python", "bash"],  "active": False},
    {"_id": 7, "name": "Gwen", "dept": "ops",   "salary": 130, "age": 47, "tags": [],                  "active": True},
]

DEPARTMENTS = [
    {"_id": "eng",   "label": "Engineering", "floor": 3, "budget": 1000},
    {"_id": "sales", "label": "Sales",       "floor": 1, "budget": 500},
    {"_id": "ops",   "label": "Operations",  "floor": 2, "budget": 750},
    {"_id": "hr",    "label": "HR",          "floor": 2, "budget": 300},
]
