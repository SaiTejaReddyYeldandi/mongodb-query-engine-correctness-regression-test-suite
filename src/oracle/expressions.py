"""
Aggregation EXPRESSION evaluator for the oracle.

In MongoDB there are two different little languages:

1. QUERY language  -- used inside $match: {salary: {$gt: 100}}
2. EXPRESSION language -- used inside $project / $group / $addFields:
                          {bonus: {$multiply: ["$salary", 0.1]}}

This module implements (2). An expression is evaluated against a single
document and may reference fields ("$salary"), variables ("$$this"), and
operators ({$add: [...]}) recursively.

Keeping this evaluator small and explicit is what makes it trustworthy as an
oracle: every operator below maps to one documented MongoDB behaviour.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any


def _field_path(document: dict, path: str) -> Any:
    cur: Any = document
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _bson_type(value: Any) -> str:
    """Return MongoDB's $type string for a Python value.
    NOTE: bool must be checked before int (bool subclasses int in Python)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, _dt.datetime):
        return "date"
    if isinstance(value, dict):
        return "object"
    return "object"


def evaluate(document: dict, expr: Any, variables: dict | None = None) -> Any:
    """Evaluate an aggregation expression against `document`."""
    variables = variables or {}

    # ---- field paths and variables -------------------------------------
    if isinstance(expr, str):
        if expr.startswith("$$"):
            name = expr[2:]
            if name == "ROOT":
                return document
            if name == "REMOVE":
                return _REMOVE
            return variables.get(name)
        if expr.startswith("$"):
            return _field_path(document, expr[1:])
        return expr  # plain string literal

    # ---- lists: evaluate each element -----------------------------------
    if isinstance(expr, list):
        return [evaluate(document, e, variables) for e in expr]

    # ---- dicts: either an operator, or an object literal ----------------
    if isinstance(expr, dict):
        operator_keys = [k for k in expr if k.startswith("$")]
        if operator_keys:
            if len(expr) != 1:
                raise ValueError(f"Expression object has multiple operators: {expr}")
            op = operator_keys[0]
            return _apply_operator(document, op, expr[op], variables)
        # object literal: evaluate each value
        return {k: evaluate(document, v, variables) for k, v in expr.items()}

    # ---- scalars (numbers, bools, None) ---------------------------------
    return expr


# Sentinel for $$REMOVE (used by conditional projection); a field set to this
# is omitted from output.
class _Remove:
    pass


_REMOVE = _Remove()


def _num(values: list) -> list:
    """Filter out None for numeric aggregation, matching Mongo's ignore-null."""
    return [v for v in values if v is not None]


def _apply_operator(document: dict, op: str, args: Any, variables: dict) -> Any:
    ev = lambda e: evaluate(document, e, variables)

    # ----- arithmetic ----------------------------------------------------
    if op == "$add":
        return sum(_num([ev(a) for a in args]))
    if op == "$subtract":
        a, b = [ev(x) for x in args]
        return None if a is None or b is None else a - b
    if op == "$multiply":
        vals = [ev(a) for a in args]
        result = 1
        for v in vals:
            if v is None:
                return None
            result *= v
        return result
    if op == "$divide":
        a, b = [ev(x) for x in args]
        return None if a is None or b is None else a / b
    if op == "$mod":
        a, b = [ev(x) for x in args]
        return a % b
    if op == "$abs":
        v = ev(args)
        return None if v is None else abs(v)
    if op == "$ceil":
        import math
        v = ev(args)
        return None if v is None else math.ceil(v)
    if op == "$floor":
        import math
        v = ev(args)
        return None if v is None else math.floor(v)
    if op == "$round":
        if isinstance(args, list):
            v = ev(args[0])
            place = ev(args[1]) if len(args) > 1 else 0
        else:
            v, place = ev(args), 0
        return None if v is None else round(v, place)

    # ----- string --------------------------------------------------------
    if op == "$concat":
        parts = [ev(a) for a in args]
        if any(p is None for p in parts):
            return None
        return "".join(parts)
    if op == "$toUpper":
        v = ev(args)
        return "" if v is None else str(v).upper()
    if op == "$toLower":
        v = ev(args)
        return "" if v is None else str(v).lower()
    if op == "$strLenCP":
        v = ev(args)
        return len(v)

    # ----- comparison (return bool) -------------------------------------
    if op in ("$eq", "$ne", "$gt", "$gte", "$lt", "$lte"):
        a, b = [ev(x) for x in args]
        if op == "$eq":
            return a == b
        if op == "$ne":
            return a != b
        # None compares low in Mongo; keep simple total order for tests
        if a is None or b is None:
            return False
        return {"$gt": a > b, "$gte": a >= b, "$lt": a < b, "$lte": a <= b}[op]

    # ----- conditionals --------------------------------------------------
    if op == "$cond":
        if isinstance(args, list):
            cond, then, els = args
        else:
            cond, then, els = args["if"], args["then"], args["else"]
        return ev(then) if ev(cond) else ev(els)
    if op == "$ifNull":
        value = ev(args[0])
        # MongoDB's $ifNull treats a MISSING value the same as null: both
        # trigger the fallback. A nested $arrayElemAt out of range yields our
        # REMOVE sentinel (missing), so treat it as null here.
        if value is None or isinstance(value, _Remove):
            return ev(args[1])
        return value

    # ----- arrays --------------------------------------------------------
    if op == "$size":
        v = ev(args)
        return len(v) if isinstance(v, list) else 0
    if op == "$isArray":
        return isinstance(ev(args), list)
    if op == "$arrayElemAt":
        arr, idx = ev(args[0]), ev(args[1])
        if not isinstance(arr, list):
            return _REMOVE
        try:
            return arr[idx]
        except IndexError:
            # Out-of-range index yields "missing" in MongoDB; $project then
            # omits the field entirely (it does not become null).
            return _REMOVE
    if op == "$first":
        arr = ev(args)
        return arr[0] if isinstance(arr, list) and arr else None
    if op == "$last":
        arr = ev(args)
        return arr[-1] if isinstance(arr, list) and arr else None
    if op == "$in":
        needle, haystack = ev(args[0]), ev(args[1])
        return needle in (haystack or [])
    if op == "$filter":
        arr = ev(args["input"])
        as_name = args.get("as", "this")
        cond = args["cond"]
        if not isinstance(arr, list):
            return None
        out = []
        for element in arr:
            local = dict(variables)
            local[as_name] = element
            if evaluate(document, cond, local):
                out.append(element)
        return out
    if op == "$map":
        arr = ev(args["input"])
        as_name = args.get("as", "this")
        inner = args["in"]
        if not isinstance(arr, list):
            return None
        out = []
        for element in arr:
            local = dict(variables)
            local[as_name] = element
            out.append(evaluate(document, inner, local))
        return out

    # ----- type conversion ----------------------------------------------
    if op == "$type":
        return _bson_type(ev(args))
    if op == "$toString":
        v = ev(args)
        if v is None:
            return None
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, float):
            # MongoDB renders whole-number doubles without a trailing ".0"
            # (10.0 -> "10"), but keeps fractional parts (3.7 -> "3.7").
            return str(int(v)) if v.is_integer() else repr(v)
        return str(v)
    if op == "$toInt":
        v = ev(args)
        if v is None:
            return None
        if isinstance(v, bool):
            return 1 if v else 0
        return int(v)  # truncates toward zero for floats
    if op == "$toDouble":
        v = ev(args)
        return None if v is None else float(v)
    if op == "$toBool":
        v = ev(args)
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return v != 0
        return bool(v)
    if op == "$literal":
        return args

    raise NotImplementedError(f"Oracle expression operator not supported: {op}")