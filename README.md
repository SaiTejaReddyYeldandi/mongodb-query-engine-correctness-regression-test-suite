# MongoDB Query Engine Correctness & Regression Test Suite

A query-engine-focused test suite that validates **MongoDB Query Language (MQL)
correctness** — not just that aggregation pipelines run, but that they return
the *right* answers — across MongoDB **6.0, 7.0, and 8.0**.

## Core idea: the oracle pattern

Every aggregation pipeline is executed two independent ways and the results are
asserted equal:

```
            same pipeline + same data
          ┌──────────────┴───────────────┐
          ▼                               ▼
   real MongoDB engine             Python oracle
   (testcontainers Docker)   (src/oracle/*.py, audit-by-eye simple)
          │                               │
          └──────────► assert equal ◄─────┘
```

A disagreement is a genuine correctness signal. The oracle is deliberately tiny
so it is trustworthy as ground truth, and it is itself pinned by self-tests.

## What it covers (≈93 tests)

| Area | What is validated |
|------|-------------------|
| `$match` | comparison/`$in`/`$or`/`$expr`/array/`$size` predicates vs oracle |
| `$group` | `$sum $avg $min $max $first $last $push`, compound keys, group-all |
| `$project`/`$addFields`/`$set` | computed fields, arithmetic, string, `$cond`, `$ifNull` |
| nested arrays | `$unwind` (+`preserveNullAndEmptyArrays`, `includeArrayIndex`), `$filter`, `$map`, `$arrayElemAt`, `$size` |
| `$lookup` | equality joins, empty-match joins, join→unwind→group reports |
| type coercion | `$toInt $toString $toDouble $toBool $type` edge cases |
| multi-stage | realistic analytics pipelines end-to-end |
| **property-based** | algebraic invariants via Hypothesis (e.g. `$match A;$match B == $match A∧B`) |
| **explain()** | asserts IXSCAN vs COLLSCAN and docsExamined |
| **golden regression** | frozen known-good outputs catch silent changes across versions |

## Layout

```
src/oracle/
  expressions.py   the aggregation EXPRESSION evaluator ($add, $filter, $type, …)
  aggregation.py   pipeline STAGES ($match $group $unwind $lookup $project …)
  compare.py       order-independent result comparison
tests/
  sample_data.py             single source of truth for datasets
  conftest.py                testcontainers MongoDB fixture + `agg` helper
  correctness/               oracle-pattern tests (Mongo vs oracle)
  properties/                Hypothesis property tests
  explain/                   IXSCAN/COLLSCAN assertions
  regression/golden/         frozen golden JSON outputs
scripts/generate_golden.py   (re)generate golden files
.github/workflows/tests.yml  fast lane + Mongo 6/7/8 matrix
```

## Running it

On Windows use `py -m ...`; on macOS/Linux use `python -m ...`.

```bash
pip install -r requirements.txt           # py -m pip install -r requirements.txt

# FAST LANE — oracle + property invariants, NO Docker needed (seconds):
pytest -m "not mongo"

# FULL SUITE — needs Docker Desktop running:
pytest                                     # defaults to mongo:7.0
MONGO_IMAGE=mongo:8.0 pytest               # pick a version
pytest -n auto                             # run in parallel

# Subsets by marker:
pytest -m oracle        # pure-Python oracle self-tests
pytest -m property      # Hypothesis invariants
pytest -m regression    # golden-output checks
pytest tests/explain    # index-usage assertions

# Regenerate golden files after an INTENTIONAL, verified output change:
python scripts/generate_golden.py
```

## Allure reporting

```bash
pytest --alluredir=allure-results
allure serve allure-results               # requires the Allure CLI
```

## CI

`.github/workflows/tests.yml` runs the fast lane on every push, then the full
suite in parallel against mongo:6.0, 7.0, and 8.0 (`fail-fast: false` so one
version's failure doesn't mask the others), uploading Allure results per leg.

## Interview talking points

- **"How do you know the result is correct?"** — cross-validated against an
  independent reference implementation (the oracle), not just asserted to run.
- **"How do you find edge cases?"** — property-based testing generates hundreds
  of random valid inputs and checks algebraic invariants; Hypothesis shrinks
  any failure to a minimal repro.
- **"You test output — what about performance?"** — explain() parsing asserts
  the planner uses an index (IXSCAN) where expected and examines few documents.
- **"How do you catch cross-version regressions?"** — golden-output files plus a
  Docker matrix across three MongoDB majors in CI.
