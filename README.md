# MongoDB Query Engine Correctness & Regression Test Suite

A testing project that checks whether MongoDB's aggregation queries return the
**correct** results — not just whether they run without errors. It runs the same
checks against **MongoDB 6.0, 7.0, and 8.0**, so we also catch behaviour that
changes between versions.

> **In one line:** I built a test suite that proves MongoDB's aggregation engine
> gives the right answer, by computing every query a second time in plain Python
> (called an *oracle*) and comparing the two. On top of that I added
> property-based testing, query-plan checks, and golden-output regression, and I
> run everything against three MongoDB versions using Docker.

This README is written so that anyone with basic MongoDB and SDET knowledge can
read it top to bottom and understand exactly **what** the project does and
**how** it was built. It is also detailed enough that I can re-read it after a
month and recall everything, and use it as interview preparation.

---

## Table of contents

1. [The problem we are solving](#1-the-problem-we-are-solving)
2. [The main idea: oracle testing](#2-the-main-idea-oracle-testing)
3. [What the project demonstrates](#3-what-the-project-demonstrates)
4. [How the pieces fit together](#4-how-the-pieces-fit-together)
5. [Folder structure — every file explained](#5-folder-structure--every-file-explained)
6. [How to run it — step by step](#6-how-to-run-it--step-by-step)
7. [How the two test lanes work](#7-how-the-two-test-lanes-work)
8. [Inside the oracle](#8-inside-the-oracle)
9. [Each type of test, explained](#9-each-type-of-test-explained)
10. [Real bugs this suite caught](#10-real-bugs-this-suite-caught)
11. [Important design decisions and why](#11-important-design-decisions-and-why)
12. [Continuous integration (CI)](#12-continuous-integration-ci)
13. [Glossary — every term used](#13-glossary--every-term-used)
14. [Interview questions and answers](#14-interview-questions-and-answers)
15. [Tools and libraries used](#15-tools-and-libraries-used)

---

## 1. The problem we are solving

Most database tests only check one thing: **"did the query run without an
error?"** That is a weak check. A query can run perfectly fine and still give
the **wrong** answer — a `$group` that counts wrong, a `$lookup` that quietly
drops some matched rows, a type conversion that rounds a number differently.

These are called **silent correctness bugs**. There is no crash and no error
message. The query just returns wrong data, and that wrong data then flows into
reports, dashboards, and business decisions. Nobody notices until much later.

This project answers the harder question: **"is the answer actually correct?"**
And it also answers a second question most test suites ignore: **"is it correct
on every MongoDB version?"** — because upgrading from 6.0 to 7.0 to 8.0 can
quietly change how some operators behave.

---

## 2. The main idea: oracle testing

The whole project is built on one simple idea. You cannot trust a result just
because it did not throw an error. So we calculate every result **two
independent ways** and check that both agree:

1. **Real MongoDB** — the actual database engine, running inside a temporary
   Docker container (using a library called `testcontainers`).
2. **The oracle** — a small, plain-Python version of the aggregation pipeline,
   written to be simple enough that anyone can read it and trust it by eye.

```
                  same pipeline + same data
                +--------------+----------------+
                |                               |
                v                               v
         real MongoDB engine             Python oracle
       (testcontainers Docker)     (src/oracle/*.py, easy to read)
                |                               |
                +-----------> assert equal <---+
```

If both sides **agree**, we are confident the answer is correct — two completely
different implementations rarely make the exact same mistake. If they
**disagree**, we have found a real problem: either a genuine MongoDB issue, a
behaviour change between versions, or a mistake in our own understanding of how
the query should work. Since the oracle is small and easy to read, it is usually
easy to figure out which side is right.

> The word **"oracle"** in software testing simply means *a trusted source of
> the correct answer* that you compare your system against. It has nothing to do
> with the Oracle database company.

**But who checks the oracle?** Good question. If the oracle itself had a bug,
both sides could agree on a *wrong* answer. To prevent that, the oracle has its
own set of **self-tests** (`test_oracle_selftest.py`) with hand-written expected
values that a person verified manually. This closes the loop — a broken oracle
cannot quietly hide a broken engine.

---

## 3. What the project demonstrates

These are the five core skills the project shows, and where each one lives:

| # | Skill | What it proves | Where it is |
|---|-------|----------------|-------------|
| 1 | **Oracle-pattern correctness** | Results are *right*, not just runnable | `tests/correctness/`, `src/oracle/` |
| 2 | **Property-based testing** | Holds true for *any* input, finds rare edge cases | `tests/properties/` |
| 3 | **Query-plan analysis** | Performance is right — the index is actually used | `tests/explain/` |
| 4 | **Golden-output regression** | Catches silent output changes across versions | `tests/regression/` |
| 5 | **CI across real DB versions** | Works on Mongo 6/7/8, automatically | `.github/workflows/tests.yml` |

---

## 4. How the pieces fit together

There are two main halves: the **oracle** (our reference engine in Python) and
the **tests** (which compare the oracle against real MongoDB).

The oracle copies MongoDB's own design, which internally uses **two small
languages**:

- **Query language** — used inside `$match`, for example `{salary: {$gt: 100}}`.
  It returns true or false for each document. Built in `aggregation.py`.
- **Expression language** — used inside `$project`, `$group`, and `$addFields`,
  for example `{bonus: {$multiply: ["$salary", 0.1]}}`. It computes a value.
  Built in `expressions.py`.

Here is what happens in a single correctness test:

```
sample_data.py  -->  load the SAME documents into  -->  MongoDB (Docker)  --+
                                                  -->  oracle (Python)  ----+
                                                                            |
                                                                            v
                                                          compare.py checks both are equal
```

Because **both sides load from the same source list** (`sample_data.py`), any
difference between them is a true engine-vs-oracle difference, never just a data
mismatch.

---

## 5. Folder structure — every file explained

```
src/oracle/
  expressions.py   The EXPRESSION evaluator. This is the "value computing" half
                   of the oracle. It implements $add, $subtract, $multiply,
                   $divide, $concat, $toUpper/$toLower, $cond, $ifNull, $size,
                   $arrayElemAt, $filter, $map, $toInt, $toString, $toDouble,
                   $toBool, $type, and more. It also handles $$ variables
                   (like $$this used inside $filter and $map).

  aggregation.py   The pipeline STAGES plus the $match query language, plus the
                   main run_pipeline() function. Stages: $match, $project,
                   $addFields/$set, $group, $unwind, $lookup, $count, $sort,
                   $limit, $skip. run_pipeline(docs, pipeline, collections=...)
                   passes documents through each stage in order, exactly like
                   collection.aggregate(pipeline) does in MongoDB.

  compare.py       Order-independent result comparison. The normalize() function
                   turns a result list into a sorted list of canonical JSON
                   strings, so two results that differ only in order are treated
                   as equal. Provides assert_same_unordered() and
                   assert_same_ordered().

tests/
  sample_data.py   The SINGLE SOURCE OF TRUTH for the datasets (employees and
                   departments). Both MongoDB and the oracle load from here, so
                   the data can never drift apart between them.

  conftest.py      Shared pytest fixtures used by all tests:
                     - mongo_client      : starts ONE MongoDB container for the
                                           whole test session using
                                           testcontainers. The version is picked
                                           by the MONGO_IMAGE environment
                                           variable (default mongo:7.0).
                     - data              : a fresh employees + departments
                                           collection for each test, plus the raw
                                           documents for the oracle.
                     - indexed_employees : a collection WITH indexes, used by the
                                           explain() tests.
                     - agg               : the helper that runs the SAME pipeline
                                           on both Mongo and the oracle and
                                           asserts the results match.

  correctness/     The oracle-pattern tests (Mongo vs oracle):
    test_match.py             $match predicates (gt, in, or, expr, and more)
    test_group.py             $group accumulators and compound keys
    test_project_addfields.py $project / $addFields / $set computed fields
    test_unwind_arrays.py     $unwind options, $filter, $map, $arrayElemAt
    test_lookup.py            $lookup joins (including empty-match joins)
    test_type_coercion.py     $toInt/$toString/$toDouble/$toBool/$type edge cases
    test_multistage.py        realistic multi-stage analytics pipelines
    test_oracle_selftest.py   tests the ORACLE itself (no Docker needed)

  properties/
    test_invariants.py        Property-based tests using Hypothesis. Checks
                              algebraic laws on hundreds of random inputs.

  explain/
    test_explain_index_usage.py  Reads explain() output to assert IXSCAN vs
                                 COLLSCAN and documents-examined counts.

  regression/
    golden_queries.py         The named, known-good queries.
    golden/*.json             Their frozen expected outputs (the "golden" files).
    test_golden_regression.py Re-runs each query on the oracle AND Mongo, and
                              asserts the output still matches the frozen golden.

scripts/
  generate_golden.py          Regenerates the golden JSON files from the trusted
                              oracle. Run this ONLY after an intentional,
                              verified change to the expected output.

.github/workflows/tests.yml   CI pipeline: the fast lane runs on every push, then
                              the full suite runs against mongo:6.0/7.0/8.0 in a
                              parallel matrix.

pytest.ini                    Test configuration and custom markers (mongo,
                              oracle, property, regression).
requirements.txt              Pinned versions of all dependencies.
```

---

## 6. How to run it — step by step

> On **Windows** use `py -m ...`. On **macOS/Linux** use `python -m ...`.

### Step 0 — install dependencies (only once)

```bash
py -m pip install -r requirements.txt
```

### Step 1 — fast lane (NO Docker needed, finishes in seconds)

This runs the pure-Python oracle self-tests, the Hypothesis property tests, and
the oracle side of the golden regression:

```bash
py -m pytest -m "not mongo" -v
```

You should see around 19 tests pass. This is your quick feedback loop while
working on the oracle.

### Step 2 — full suite (needs Docker Desktop RUNNING)

The `mongo`-marked tests start a real MongoDB inside Docker.

1. Install **Docker Desktop**, open it, and wait until it shows
   **"Engine running"** (the whale icon turns green).
2. Check that Docker is working:
   ```bash
   docker run --rm hello-world
   ```
3. Run everything (the first run downloads the MongoDB image once — that is
   normal and only happens the first time):
   ```bash
   py -m pytest -v
   ```

You should see **93 tests pass**.

### Step 3 — test against a specific MongoDB version

```bash
# PowerShell (Windows)
$env:MONGO_IMAGE="mongo:8.0"; py -m pytest -v
$env:MONGO_IMAGE="mongo:6.0"; py -m pytest -v

# bash (macOS/Linux)
MONGO_IMAGE=mongo:8.0 python -m pytest -v
```

### Step 4 — run subsets or run in parallel

```bash
py -m pytest -n auto -v        # run in parallel using all CPU cores
py -m pytest -m oracle         # only the pure-Python oracle self-tests
py -m pytest -m property       # only the Hypothesis property tests
py -m pytest -m regression     # only the golden-output checks
py -m pytest tests/explain     # only the index-usage assertions
```

### Step 5 — regenerate golden files (only when output changes on purpose)

```bash
py scripts/generate_golden.py
```

### Optional — Allure report

Allure is a reporting tool that turns the test results into a clean, browsable
web dashboard (pass/fail graphs, timings, tests grouped by file). It is purely
**optional and cosmetic** — the 93 passing tests are the real deliverable, and
the project is complete without it. Allure just gives a nicer way to *view*
results you already produce.

There are two separate pieces, and both are needed to view the report locally:

1. **The `allure-pytest` plugin** (a Python package) — already installed via
   `requirements.txt`. This is what *writes* the raw results.
2. **The Allure command-line tool** (a separate Java program) — this is what
   *displays* those results as a report. It is NOT a Python package, so
   `pip install` will not provide it.

**Step A — generate the raw results** (this part needs no extra setup):

```bash
py -m pytest --alluredir=allure-results
```

This creates an `allure-results/` folder full of JSON files.

**Step B — install the Allure CLI** (one-time). On Windows the easiest way is
Scoop (a Windows package manager):

```powershell
# install Scoop, then the Allure CLI
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
irm get.scoop.sh | iex
scoop install allure
```

**Step C — install Java** (the Allure CLI is a Java program; without Java you
get an error like `JAVA_HOME is not set and no 'java' command could be found`):

```powershell
scoop bucket add java
scoop install temurin-jdk
```

Now **close PowerShell and open a fresh window** (so the new PATH / JAVA_HOME
take effect), then confirm Java is available:

```powershell
java -version
```

**Step D — view the report:**

```powershell
cd C:\Users\17r01\Desktop\mongo-test-suite
allure serve allure-results
```

This builds the report and opens it in your browser.

> If you only want the report rendered in CI rather than locally, you can skip
> all of this: the GitHub Actions workflow already uploads the Allure result
> files as an artifact for each MongoDB version, and anyone can render them with
> the Allure CLI.

---

## 7. How the two test lanes work

The tests always run in **host Python** (your normal machine Python). The
`mongo`-marked tests additionally talk to a MongoDB running inside Docker:

```
py -m pytest  -->  testcontainers  -->  Docker Desktop  -->  mongo:X.Y container
   (host)            (library)          (must be running)       (real engine)
```

There is **nothing extra to build or containerize yourself**. Running
`py -m pytest` while Docker is running *is* "running the project against real
MongoDB," and it is exactly what the CI does. If Docker is **not** running, the
`mongo`-marked tests fail at setup with a Docker connection error, but the fast
lane (`-m "not mongo"`) still passes.

**Why have two lanes?** Speed. The fast lane needs no Docker and finishes in a
couple of seconds, so I can change the oracle and get feedback instantly. The
full lane is the real proof, but it is slower because it starts a database.

---

## 8. Inside the oracle

`run_pipeline(documents, pipeline, collections=None)` is the entry point. It
makes a deep copy of the input documents, then passes them through each stage in
order. Every stage is a small function shaped like
`stage_x(docs, spec, ctx) -> docs`.

Two small languages, kept separate on purpose (just like MongoDB does it):

- **Query language** (`_matches_query` in `aggregation.py`) — used by `$match`.
  Supports `$eq/$ne/$gt/$gte/$lt/$lte`, `$in/$nin`, `$and/$or`, `$exists`,
  `$size`, `$expr` (which bridges into the expression language), and plain
  equality. Arrays match if any element equals a scalar — this matches MongoDB's
  own behaviour.

- **Expression language** (`evaluate` in `expressions.py`) — used by
  `$project/$group/$addFields`. It resolves `$field` paths, `$$variables`,
  plain literals, and operator objects like `{$multiply: [...]}`. It is
  recursive, so something like
  `{$concat: [{$toUpper: "$name"}, "-", "$dept"]}` is evaluated from the inside
  out.

**The "missing" idea (important).** MongoDB treats *null* and *missing* (field
absent) as two different things. For example, `$arrayElemAt` on an index that is
out of range returns *missing*, and `$project` then drops that field completely
(the document comes back without the key, not with a `null` value). The oracle
models this with a private `_REMOVE` sentinel so it can reproduce that exact
behaviour. This detail caused a couple of the real bugs described below.

---

## 9. Each type of test, explained

**Correctness tests (the oracle pattern).** Each test defines a pipeline, runs
it on both Mongo and the oracle from the same data, and asserts the results are
equal. Many of these are *parametrized* — a single test function expands into
many test cases (for example, `test_match` runs once for each predicate in a
list). This is how a small number of functions becomes around 93 tests.

**Property-based tests (Hypothesis).** Instead of picking inputs by hand,
Hypothesis generates hundreds of random valid documents and checks **algebraic
laws** — rules that must hold true for *any* input:
- `$match A` then `$match B` is the same as `$match {$and: [A, B]}`
- `$limit n` then `$limit m` is the same as `$limit min(n, m)`
- sorting twice is the same as sorting once
- the sum of all per-group counts equals the total number of documents
- `$unwind tags` produces exactly sum(length of each tags array) documents
- an empty `$match {}` returns the input unchanged (it is the identity)
- after a stable sort, `$skip k` returns exactly the part after the first k

When a property fails, Hypothesis **shrinks** the failing case down to the
smallest input that still breaks it — a tiny, readable example. One property
test (`test_match_matches_mongo`) also cross-checks the oracle against real Mongo
using random predicates.

**explain() / query-plan tests.** Getting the right output is not the whole
story — *how* MongoDB gets that output matters for performance. These tests run
`explain()` and assert:
- a query on an **indexed** field uses an **IXSCAN** (index scan),
- a query on a **non-indexed** field falls back to a **COLLSCAN** (full scan),
- an index scan **examines only a few documents**.
The explain() output shape is slightly different across Mongo 6/7/8, so it is
parsed *defensively* — we recursively collect every `stage` value instead of
relying on a fixed path. That is why the same test passes on all three versions.

**Golden-output regression tests.** Six known-good queries have their outputs
frozen into JSON files in `tests/regression/golden/`. Each query is re-run on
both the oracle and real Mongo, and the output is compared to the frozen file.
If a future MongoDB version (or an accidental oracle change) alters the output,
the test fails loudly. The outputs are stored in normalized (order-independent)
form so the check is stable.

---

## 10. Real bugs this suite caught

These are genuine differences the oracle pattern found while building the
project. In all three cases MongoDB was right and the oracle was corrected.
These make great interview stories because they prove the method actually works.

1. **`$arrayElemAt` on an empty array.** MongoDB returns *missing* (so `$project`
   drops the field and you get `{}`), but the oracle first returned `null`. Fixed
   the oracle to return the *missing* sentinel instead.

2. **`$toString` of a whole-number double.** MongoDB prints `10.0` as `"10"`
   (drops the trailing `.0`) but keeps `3.7` as `"3.7"`. The oracle first
   produced `"10.0"`. Fixed it to match MongoDB.

3. **`$ifNull` over a missing value.** MongoDB treats *missing* the same as
   *null* — both trigger the fallback value — so
   `$ifNull[$arrayElemAt(empty array), "none"]` returns `"none"`. After fix #1
   made `$arrayElemAt` return the missing sentinel, the oracle's `$ifNull` had to
   learn that the sentinel counts as null too. Fixed.

**The key lesson (worth saying in an interview):** bug #3 was *caused by* the fix
for bug #1. One correct change exposed a second hidden assumption, and the suite
caught it immediately instead of letting a subtle wrong behaviour slip through.
That chain reaction is exactly the value of cross-validation.

(One non-correctness issue also came up: Hypothesis warned about reusing a
function-scoped fixture across its generated examples. That reuse is intentional
and safe here, so it is suppressed with
`suppress_health_check=[HealthCheck.function_scoped_fixture]`.)

---

## 11. Important design decisions and why

**Order-independent comparison.** A `$group` stage returns its groups in no
particular order, so comparing the two result lists directly would give false
failures. We normalize both sides into a sorted set before comparing — *except*
when a pipeline ends in `$sort`, where the order is defined and we check it
exactly (`assert_same_ordered`).

**Test the oracle itself.** If the oracle had a bug, Mongo and the oracle could
"agree" on a wrong answer. Hand-verified self-tests pin the oracle's behaviour
and need no Docker, so the foundation is solid.

**Single source of truth for data.** Both sides load from `sample_data.py`, so a
mismatch is always a real logic difference, never just a difference in the test
data.

**Defensive explain() parsing.** The plan JSON is shaped slightly differently in
each Mongo major version, so we search recursively for `stage` values instead of
hard-coding a path. This is what lets the same test pass on 6.0, 7.0, and 8.0.

**Two test lanes with markers.** `-m "not mongo"` gives a fast, Docker-free inner
loop; the full suite is the real proof. The markers (`mongo`, `oracle`,
`property`, `regression`) let me slice the suite however I need.

**Pinned dependencies.** `requirements.txt` pins exact versions so the suite is
reproducible and the CI is deterministic.

---

## 12. Continuous integration (CI)

`.github/workflows/tests.yml` has two jobs:

1. **fast-lane** — installs dependencies and runs `pytest -m "not mongo"` on
   every push. It takes only a few seconds and acts as a gate for the heavier
   job.
2. **correctness-matrix** — runs the full suite in parallel against
   `mongo:6.0`, `mongo:7.0`, and `mongo:8.0` using a build matrix with
   `fail-fast: false` (so if one version fails, the others still run and report).
   Allure results are uploaded as an artifact for each version.

This matrix is the literal proof of "correct across versions": the exact same
tests, three different engines, automatically, on every push.

---

## 13. Glossary — every term used

- **Oracle** — a trusted, independent source of the correct answer, used for
  comparison. Here it is the plain-Python pipeline implementation.
- **Aggregation pipeline** — MongoDB's chain of data-processing stages
  (`$match`, `$group`, and so on); documents flow through each stage in order.
- **Stage** — one step of a pipeline.
- **MQL** — MongoDB Query Language.
- **Query language vs expression language** — `$match` uses predicates like
  `{$gt: 100}`; `$project`/`$group` use value expressions like
  `{$multiply: [...]}`. They are two different mini-languages.
- **Accumulator** — a `$group` operator that combines values across a group:
  `$sum`, `$avg`, `$min`, `$max`, `$push`, `$first`, `$last`, `$addToSet`.
- **`$lookup`** — a left-outer join to another collection.
- **`$unwind`** — splits an array field into one document per element.
- **Type coercion** — converting between types (`$toInt`, `$toString`, and so
  on); the edge cases (whole-number doubles, booleans, nulls) are where engines
  quietly differ.
- **null vs missing** — `null` is a present value; *missing* means the field is
  absent. MongoDB treats them differently (for example in `$project` output and
  in `$ifNull`).
- **Property-based testing** — generate many random inputs and assert
  *invariants* that must always hold, instead of picking examples by hand.
- **Invariant** — a rule that is true for every input (for example, group counts
  must sum to the total document count).
- **Shrinking** — Hypothesis reducing a failing input to the smallest example
  that still fails.
- **explain()** — MongoDB's query-plan report.
- **IXSCAN / COLLSCAN** — index scan (fast, uses an index) vs collection scan
  (reads every document).
- **docsExamined** — how many documents the engine looked at; lower is better.
- **Golden file** — a frozen, known-good expected output saved to disk.
- **Regression** — a previously-correct behaviour breaking silently.
- **testcontainers** — a library that starts real services (here MongoDB) in
  temporary Docker containers from inside the tests.
- **Fixture (pytest)** — reusable setup/teardown for tests (for example, starting
  MongoDB and loading the data).
- **Parametrized test** — one test function run with many input cases.
- **Marker (pytest)** — a label like `@pytest.mark.mongo` used to select or group
  tests.
- **CI matrix** — running the same job across several configurations (here, three
  MongoDB versions) in parallel.
- **Allure** — a reporting tool that turns test results into a browsable report.

---

## 14. Interview questions and answers

Read the question, answer it out loud, then check against the model answer.

**Q1. What does this project actually do?**
It cross-validates MongoDB aggregation results against an independent Python
reference (an oracle) to prove correctness, then adds property-based testing,
explain()-plan checks, and golden-output regression, all run against Mongo 6/7/8
in a Docker CI matrix.

**Q2. Why not just check that the query "works"?**
"Works" only means it did not error. A query can run fine and still return wrong
data — a miscounted group, a dropped join match, a different rounding. Those
silent correctness bugs are exactly what an oracle catches.

**Q3. Why is the oracle trustworthy? Couldn't it have bugs too?**
It is deliberately small and easy to read, so two independent implementations
sharing the *same* bug is very unlikely. And the oracle has its own hand-verified
self-tests, so a buggy oracle cannot quietly hide a buggy engine.

**Q4. How do you handle `$group` returning rows in any order?**
I normalize both results into a sorted set of canonical JSON strings before
comparing, so order differences do not cause false failures. When a pipeline
ends in `$sort`, the order is defined, so I compare it exactly instead.

**Q5. What do property-based tests give you over normal example tests?**
They check laws that must hold for *any* input across hundreds of random cases,
finding edge cases I would never pick by hand — for example, filter-then-filter
equals filter on the combined condition, or unwind produces exactly the sum of
array lengths. On failure, Hypothesis shrinks to a minimal reproducible example.

**Q6. You test output — what about performance?**
The explain() tests assert the planner uses an index (IXSCAN) where one exists,
falls back to a collection scan (COLLSCAN) where it does not, and examines only a
few documents. That is performance correctness, not just output correctness.

**Q7. How do the explain() tests survive different MongoDB versions?**
The explain() JSON shape changes between major versions, so I parse it
defensively — recursively collecting every `stage` value instead of hard-coding
a path. That is why the same checks pass on 6.0, 7.0, and 8.0.

**Q8. How does golden-output regression work, and how do you update it?**
Known-good query outputs are frozen into JSON and re-checked against both the
oracle and real Mongo. A silent change fails the test. To update it on purpose, I
re-run `scripts/generate_golden.py` after verifying the new output is correct.

**Q9. Walk me through what happens when I run `pytest`.**
pytest runs in host Python. For mongo-marked tests, a session fixture uses
testcontainers to start a real MongoDB container; a per-test fixture loads
employees and departments from sample_data.py into both Mongo and the oracle; the
`agg` helper runs the same pipeline through both and asserts they are equal; and
the container is shut down at the end of the session.

**Q10. Tell me about a real bug you found.**
Three of them. `$arrayElemAt` on an empty array returns *missing* in Mongo
(field omitted), not null. `$toString` of `10.0` is `"10"`, not `"10.0"`. And
`$ifNull` treats *missing* like null — which only showed up *after* I fixed
`$arrayElemAt`, because that fix changed what `$ifNull` received. One correct
change exposed a second hidden assumption, and the suite caught it instantly.
That chain reaction is the whole point of cross-validation.

**Q11. Why testcontainers instead of mocking MongoDB?**
A mock would only test my *assumptions* about MongoDB, not MongoDB itself. The
entire goal is to validate the *real engine*, so I run a real one in a temporary
container.

**Q12. How is this set up for CI?**
A fast lane (no Docker) gates a full matrix job that runs the same suite against
mongo:6.0/7.0/8.0 in parallel with fail-fast disabled, so one version's failure
does not hide another's.

**Q13. What would you add next?**
More operators in the oracle (`$bucket`, `$facet`, window functions), a bigger
random dataset for the Mongo-vs-oracle property test, fuzzing of whole random
*pipelines* (not just predicates), and limits on docsExamined to catch
performance regressions.

---

## 15. Tools and libraries used

Python, pytest, pytest-xdist, pymongo, Hypothesis, Docker, testcontainers,
MongoDB 6/7/8, GitHub Actions matrix, Allure.
