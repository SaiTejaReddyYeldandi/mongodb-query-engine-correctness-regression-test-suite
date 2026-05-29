"""
Known-good queries for golden-output regression.

Each entry has a stable name. Its expected output is frozen into
tests/regression/golden/<name>.json by scripts/generate_golden.py. The
regression test re-runs the pipeline and asserts the output still matches the
frozen golden file -- catching silent changes across MongoDB versions.

We store outputs as a normalized multiset (sorted canonical strings) so the
comparison is robust to result ordering.
"""

GOLDEN_QUERIES = {
    "headcount_by_dept": [
        {"$group": {"_id": "$dept", "n": {"$sum": 1}}},
    ],
    "payroll_by_dept": [
        {"$group": {"_id": "$dept", "payroll": {"$sum": "$salary"}}},
    ],
    "avg_age_by_dept": [
        {"$group": {"_id": "$dept", "avg_age": {"$avg": "$age"}}},
    ],
    "active_eng_names": [
        {"$match": {"dept": "eng", "active": True}},
        {"$project": {"name": 1, "_id": 0}},
    ],
    "tag_frequency": [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
    ],
    "salary_with_bonus": [
        {"$project": {"name": 1, "total": {"$add": ["$salary", {"$multiply": ["$salary", 0.1]}]}, "_id": 0}},
    ],
}
