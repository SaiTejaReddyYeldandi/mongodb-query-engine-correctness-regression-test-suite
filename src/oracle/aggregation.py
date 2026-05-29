"""
The Oracle: pure-Python reference implementation of a subset of the MongoDB
aggregation pipeline. See expressions.py for the expression sub-language.

WHY THIS EXISTS
---------------
To prove MongoDB returns CORRECT answers we recompute the same result a second,
independent way in code simple enough to audit by hand, then assert agreement.
This file implements the pipeline STAGES; expressions.py implements the
expression language used inside $project / $group / $addFields.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from .expressions import evaluate, _REMOVE, _Remove


# --------------------------------------------------------------------------
# Field path resolution (shared helper, also re-exported for tests).
# --------------------------------------------------------------------------
def resolve_field_path(document: dict, path: str) -> Any:
    cur: Any = document
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def resolve_expression(document: dict, expr: Any) -> Any:
    """Backwards-compatible thin wrapper kept for Milestone-1 tests."""
    return evaluate(document, expr)


# --------------------------------------------------------------------------
# $match  -- QUERY language (not expression language)
# --------------------------------------------------------------------------
_COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "$eq": lambda a, b: a == b,
    "$ne": lambda a, b: a != b,
    "$gt": lambda a, b: a is not None and a > b,
    "$gte": lambda a, b: a is not None and a >= b,
    "$lt": lambda a, b: a is not None and a < b,
    "$lte": lambda a, b: a is not None and a <= b,
    "$in": lambda a, b: a in b,
    "$nin": lambda a, b: a not in b,
}


def _matches_condition(value: Any, condition: Any) -> bool:
    if isinstance(condition, dict) and all(k.startswith("$") for k in condition):
        for op, operand in condition.items():
            if op == "$exists":
                exists = value is not None
                if exists != bool(operand):
                    return False
            elif op == "$size":
                if not (isinstance(value, list) and len(value) == operand):
                    return False
            elif op in _COMPARATORS:
                if not _COMPARATORS[op](value, operand):
                    return False
            else:
                raise NotImplementedError(f"Oracle query operator {op} not supported")
        return True
    return value == condition


def _matches_query(document: dict, query: dict) -> bool:
    for field, condition in query.items():
        if field == "$and":
            if not all(_matches_query(document, s) for s in condition):
                return False
        elif field == "$or":
            if not any(_matches_query(document, s) for s in condition):
                return False
        elif field == "$expr":
            if not evaluate(document, condition):
                return False
        else:
            value = resolve_field_path(document, field)
            # arrays: Mongo matches if ANY element matches a scalar equality
            if isinstance(value, list) and not (
                isinstance(condition, dict) and any(k.startswith("$") for k in condition)
            ):
                if condition not in value and value != condition:
                    return False
            elif not _matches_condition(value, condition):
                return False
    return True


def stage_match(docs, spec, ctx):
    return [d for d in docs if _matches_query(d, spec)]


# --------------------------------------------------------------------------
# $project
# --------------------------------------------------------------------------
def stage_project(docs, spec, ctx):
    out = []
    for d in docs:
        new_doc: dict = {}
        include_id = spec.get("_id", 1)
        if include_id and "_id" in d:
            new_doc["_id"] = d["_id"]
        for field, rule in spec.items():
            if field == "_id":
                continue
            if rule in (1, True):
                v = resolve_field_path(d, field)
                if v is not None:
                    new_doc[field] = v
            elif rule in (0, False):
                continue
            else:
                v = evaluate(d, rule)
                if not isinstance(v, _Remove):
                    new_doc[field] = v
        out.append(new_doc)
    return out


# --------------------------------------------------------------------------
# $addFields / $set
# --------------------------------------------------------------------------
def stage_add_fields(docs, spec, ctx):
    out = []
    for d in docs:
        clone = copy.deepcopy(d)
        for field, expr in spec.items():
            v = evaluate(d, expr)
            if isinstance(v, _Remove):
                clone.pop(field, None)
            else:
                clone[field] = v
        out.append(clone)
    return out


# --------------------------------------------------------------------------
# $group
# --------------------------------------------------------------------------
def _group_key(doc, id_spec):
    if isinstance(id_spec, dict) and not any(k.startswith("$") for k in id_spec):
        return tuple(sorted((k, evaluate(doc, v)) for k, v in id_spec.items()))
    return evaluate(doc, id_spec)


def stage_group(docs, spec, ctx):
    id_spec = spec["_id"]
    accumulators = {k: v for k, v in spec.items() if k != "_id"}
    groups: dict[Any, list] = {}
    order: list = []
    for d in docs:
        key = _group_key(d, id_spec)
        hkey = key if not isinstance(key, list) else tuple(key)
        if hkey not in groups:
            groups[hkey] = (key, [])
            order.append(hkey)
        groups[hkey][1].append(d)

    out = []
    for hkey in order:
        key, members = groups[hkey]
        if isinstance(key, tuple) and key and isinstance(key[0], tuple):
            id_value: Any = {k: v for k, v in key}
        else:
            id_value = key
        res: dict = {"_id": id_value}
        for out_field, acc in accumulators.items():
            (op, operand), = acc.items()
            vals = [evaluate(m, operand) for m in members]
            non_null = [v for v in vals if v is not None]
            if op == "$sum":
                res[out_field] = len(members) if operand == 1 else sum(non_null)
            elif op == "$avg":
                res[out_field] = (sum(non_null) / len(non_null)) if non_null else None
            elif op == "$min":
                res[out_field] = min(non_null) if non_null else None
            elif op == "$max":
                res[out_field] = max(non_null) if non_null else None
            elif op == "$first":
                res[out_field] = vals[0] if vals else None
            elif op == "$last":
                res[out_field] = vals[-1] if vals else None
            elif op == "$push":
                res[out_field] = vals
            elif op == "$addToSet":
                seen, uniq = [], []
                for v in vals:
                    if v not in seen:
                        seen.append(v)
                        uniq.append(v)
                res[out_field] = uniq
            else:
                raise NotImplementedError(f"Oracle accumulator {op} not supported")
        out.append(res)
    return out


# --------------------------------------------------------------------------
# $unwind (supports preserveNullAndEmptyArrays + includeArrayIndex)
# --------------------------------------------------------------------------
def stage_unwind(docs, spec, ctx):
    if isinstance(spec, str):
        path, preserve, index_field = spec[1:], False, None
    else:
        path = spec["path"][1:]
        preserve = spec.get("preserveNullAndEmptyArrays", False)
        index_field = spec.get("includeArrayIndex")
    out = []
    for d in docs:
        arr = resolve_field_path(d, path)
        if isinstance(arr, list) and arr:
            for i, el in enumerate(arr):
                c = copy.deepcopy(d)
                c[path] = el
                if index_field:
                    c[index_field] = i
                out.append(c)
        elif preserve:
            c = copy.deepcopy(d)
            if not isinstance(arr, list) or not arr:
                c.pop(path, None)
            if index_field:
                c[index_field] = None
            out.append(c)
    return out


# --------------------------------------------------------------------------
# $lookup (equality join). Reads foreign collection from ctx["collections"].
# --------------------------------------------------------------------------
def stage_lookup(docs, spec, ctx):
    from_coll = spec["from"]
    local_field = spec["localField"]
    foreign_field = spec["foreignField"]
    as_field = spec["as"]
    foreign_docs = ctx.get("collections", {}).get(from_coll, [])
    out = []
    for d in docs:
        clone = copy.deepcopy(d)
        local_val = resolve_field_path(d, local_field)
        local_set = local_val if isinstance(local_val, list) else [local_val]
        matches = []
        for fd in foreign_docs:
            fval = resolve_field_path(fd, foreign_field)
            fvals = fval if isinstance(fval, list) else [fval]
            if any(lv == fv for lv in local_set for fv in fvals):
                matches.append(copy.deepcopy(fd))
        clone[as_field] = matches
        out.append(clone)
    return out


# --------------------------------------------------------------------------
# $count, $sort, $limit, $skip
# --------------------------------------------------------------------------
def stage_count(docs, spec, ctx):
    return [{spec: len(docs)}]


def stage_sort(docs, spec, ctx):
    out = list(docs)
    for field, direction in reversed(list(spec.items())):
        out.sort(
            key=lambda d, f=field: (resolve_field_path(d, f) is None,
                                    resolve_field_path(d, f)),
            reverse=(direction == -1),
        )
    return out


def stage_limit(docs, spec, ctx):
    return docs[:spec]


def stage_skip(docs, spec, ctx):
    return docs[spec:]


_STAGES: dict[str, Callable] = {
    "$match": stage_match,
    "$project": stage_project,
    "$addFields": stage_add_fields,
    "$set": stage_add_fields,
    "$group": stage_group,
    "$unwind": stage_unwind,
    "$lookup": stage_lookup,
    "$count": stage_count,
    "$sort": stage_sort,
    "$limit": stage_limit,
    "$skip": stage_skip,
}


def run_pipeline(documents: list[dict], pipeline: list[dict],
                 collections: dict[str, list[dict]] | None = None) -> list[dict]:
    """Run an aggregation pipeline through the oracle.

    `collections` maps collection-name -> documents and is needed for $lookup.
    """
    ctx = {"collections": collections or {}}
    docs = copy.deepcopy(documents)
    for stage in pipeline:
        (name, spec), = stage.items()
        if name not in _STAGES:
            raise NotImplementedError(f"Oracle stage {name} not supported")
        docs = _STAGES[name](docs, spec, ctx)
    return docs
