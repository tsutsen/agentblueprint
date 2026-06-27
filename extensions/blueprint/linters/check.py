#!/usr/bin/env python3
"""
check.py — Abstract check base and shared check functions.

Provides the CheckDef TypedDict that both rules and gates extend,
plus pure check functions that evaluate conditions on resolved data.

Rules (rules.py) and gates (gates.py) import from here.

All check_* functions are pure: they take data and return structured results.
The caller (rule or gate handler) formats CheckResult.results into its
own output type (LayerResult issues or CompletenessGate instances).
"""

import re
from collections import namedtuple
from typing import TypedDict

# Unified result wrapper for dispatch_check()
CheckResult = namedtuple("CheckResult", ["fn", "results", "values", "parent_ids"])


# ── Abstract check base ──────────────────────────────────────────────────────
# Both SemanticRule (rules.py) and GateDef (gates.py) extend this.


class CheckDef(TypedDict, total=False):
    """Abstract base for rules and gates.

    Concrete fields shared by both:
        check         — dispatch key (e.g. "non_empty", "has_count")
        target        — dot-separated path to resolve
        target_label  — human label for the target item
        category      — issue/gate category identifier
        hint          — optional hint text
    """
    check: str
    target: str
    target_label: str
    category: str
    hint: str


# ── Shared check functions ───────────────────────────────────────────────────
# Pure functions that evaluate conditions on resolved data.
# Used by both rule handlers (rules.py) and gate handlers (gates.py).


def check_non_empty(values: list, parent_ids: list) -> list[tuple[str, str]]:
    """Check which items are empty/missing.

    Returns list of (parent_id, detail) for items that are empty.
    """
    failures = []
    for val, pid in zip(values, parent_ids):
        if val is None:
            failures.append((pid, "field is missing"))
        elif isinstance(val, list) and not val:
            failures.append((pid, "has no items"))
        elif isinstance(val, str) and not val.strip():
            failures.append((pid, "has empty value"))
    return failures


def check_count(values: list, min_count: int) -> tuple[bool, str]:
    """Check that list has at least min_count items.

    Returns (passed, detail).
    """
    list_items = [v for v in values if isinstance(v, list)]
    total = sum(len(v) for v in list_items) if list_items else len(values)
    if total >= min_count:
        return True, f"{total} item(s) found"
    return False, f"Only {total} item(s), need at least {min_count}"


def check_coverage(target_refs: set, should_cover_ids: list) -> list:
    """Check which items in should_cover_ids are NOT in target_refs.

    Returns list of uncovered IDs.
    """
    return [iid for iid in should_cover_ids if iid not in target_refs]


def check_all_have(items: list, field: str, min_length: int = 0) -> list[tuple[str, str]]:
    """Check which items are missing a field or have it below min_length.

    Returns list of (id, detail) for items that fail.
    """
    failures = []
    for item in items:
        if not isinstance(item, dict):
            continue
        val = item.get(field)
        iid = item.get("id", str(item))
        if val is None:
            failures.append((iid, f"missing '{field}'"))
        elif isinstance(val, str) and len(val) < min_length:
            failures.append((iid, f"'{field}' too short ({len(val)} chars)"))
        elif isinstance(val, (list, dict)) and len(val) < min_length:
            failures.append((iid, f"'{field}' too short ({len(val)} items)"))
    return failures


def check_none_match(items: list, field: str, pattern: str) -> list[tuple[str, str]]:
    """Check which items have a field matching a pattern.

    Returns list of (id, value) for items that match.
    """
    matches = []
    for item in items:
        if not isinstance(item, dict):
            continue
        val = item.get(field, "")
        iid = item.get("id", str(item))
        if isinstance(val, str) and re.search(pattern, val, re.IGNORECASE):
            matches.append((iid, val))
    return matches


def check_value(value, expected: str) -> tuple[bool, str]:
    """Check a scalar value against an expected condition.

    expected formats:
        "truthy" — value is truthy
        "confirmed" — value == "confirmed"
        ">=N" — numeric comparison
    """
    if expected == "truthy":
        if value:
            return True, f"value is '{value}'"
        return False, f"value is {value!r}"
    elif expected == "confirmed":
        if value == "confirmed":
            return True, "status is confirmed"
        return False, f"status is '{value}'"
    elif expected.startswith(">="):
        try:
            threshold = int(expected[2:])
            num = int(value) if not isinstance(value, int) else value
            if num >= threshold:
                return True, f"{num} >= {threshold}"
            return False, f"{num} < {threshold}"
        except (ValueError, TypeError):
            return False, f"cannot compare {value!r}"
    else:
        return str(value) == expected, f"expected '{expected}', got '{value}'"


# ── New pure checks extracted from rule handlers ──────────────────────────────


def check_exists(values: list, parent_ids: list, valid_set: set) -> list[tuple[str, str]]:
    """Check that resolved values exist in the valid set.

    Handles both single values and lists of refs via _normalize_ref.

    Returns list of (ref, parent_id) for refs not found in valid_set.
    """
    from path import _normalize_ref
    failures = []
    for val, pid in zip(values, parent_ids):
        if val is None:
            continue
        refs = _normalize_ref(val)
        for ref in refs:
            if ref and ref not in valid_set:
                failures.append((ref, pid))
    return failures


def check_unique(values: list, parent_ids: list) -> list[tuple[str, str, str]]:
    """Check that resolved values are unique.

    Returns list of (value, first_pid, duplicate_pid) for duplicates.
    """
    seen: dict[str, str] = {}
    duplicates = []
    for val, pid in zip(values, parent_ids):
        if not val:
            continue
        str_val = str(val)
        if str_val in seen:
            duplicates.append((str_val, seen[str_val], pid))
        else:
            seen[str_val] = pid or val
    return duplicates


def check_no_overlap(values: list, parent_ids: list) -> list[tuple[str, str, str]]:
    """Check that list fields don't share values across parent items.

    Returns list of (item, first_pid, duplicate_pid) for overlaps.
    """
    seen: dict[str, str] = {}
    overlaps = []
    for val, pid in zip(values, parent_ids):
        if not isinstance(val, list):
            continue
        for item in val:
            if item in seen and seen[item] != pid:
                overlaps.append((item, seen[item], pid))
            seen[item] = pid
    return overlaps


def check_item_count(
    values: list, parent_ids: list, count: int, compare_mode: str = "more"
) -> list[tuple[str, str]]:
    """Check list length against threshold.

    compare_mode: "more" = warn if > count, "equal" = warn if == count, "less" = warn if < count

    Returns list of (parent_id, detail) for items that fail.
    """
    failures = []
    for val, pid in zip(values, parent_ids):
        if not isinstance(val, list):
            continue
        n = len(val)
        if compare_mode == "more" and n > count:
            failures.append((pid, f"has {n} items (maximum {count})"))
        elif compare_mode == "equal" and n == count:
            failures.append((pid, f"has exactly {n} items"))
        elif compare_mode == "less" and n < count:
            failures.append((pid, f"has {n} items (minimum {count})"))
    return failures


def check_patterns(
    values: list,
    parent_ids: list,
    patterns: list,
    negate: bool = False,
    extra_keys: list[str] | None = None,
    group_sizes: list[int] | None = None,
    max_count: int | None = None,
) -> list[tuple[str, str]]:
    """Check text values against regex patterns.

    When negate=True (format validation): flag values that DON'T match any pattern.
    When negate=False (forbidden content): flag values that DO match.

    For multi-property checks, use extra_keys with dict values.
    group_sizes is used with max_count to skip items from large parents.

    Returns list of (parent_id, detail) for items that fail.
    """
    failures = []
    pattern_labels = []
    compiled = []
    for p in patterns:
        if isinstance(p, str):
            compiled.append(re.compile(p, re.IGNORECASE))
            pattern_labels.append(p)
        else:
            compiled.append(re.compile(p[0], re.IGNORECASE))
            pattern_labels.append(p[1] if len(p) > 1 else p[0])

    for idx, (val, pid) in enumerate(zip(values, parent_ids)):
        # Check group size limit
        if max_count is not None and group_sizes and idx < len(group_sizes):
            if group_sizes[idx] > max_count:
                continue

        # Extract text
        if extra_keys and isinstance(val, dict):
            texts = [val.get(k, "") for k in extra_keys]
        elif isinstance(val, str):
            texts = [val]
        else:
            continue

        for text in texts:
            matches = []
            any_match = False
            for i, pattern in enumerate(compiled):
                if negate:
                    if re.fullmatch(pattern.pattern, text):
                        any_match = True
                else:
                    found = re.findall(pattern.pattern, text.lower())
                    if found:
                        matches.append((pattern_labels[i], found))
                        any_match = True

            if negate and not any_match:
                msg = f"value '{text}' doesn't match expected pattern: {', '.join(pattern_labels)}"
                failures.append((pid, msg))
            elif not negate and matches:
                msg = f"{', '.join(f'{l}: {m}' for l, m in matches)}"
                failures.append((pid, msg))

    return failures


def check_orphans(items: list) -> list[str]:
    """Check for isolated items (no *Refs outgoing, no *Refs incoming).

    Auto-discovers all *Refs/*Ref fields on items.

    Returns list of isolated item IDs.
    """
    if not items or not isinstance(items[0], dict):
        return []

    # Auto-discover all *Refs fields
    ref_fields = set()
    for item in items:
        for key in item:
            if key.endswith("Refs") or key.endswith("Ref"):
                ref_fields.add(key)

    if not ref_fields:
        return []

    # Build referenced set
    from path import _normalize_ref
    referenced_ids = set()
    for item in items:
        for f in ref_fields:
            for ref in _normalize_ref(item.get(f, [])):
                referenced_ids.add(ref)

    # Find isolated items
    isolated = []
    for item in items:
        iid = item.get("id", "")
        if not iid:
            continue
        has_outgoing = any(item.get(f) for f in ref_fields)
        is_referenced = iid in referenced_ids
        if not has_outgoing and not is_referenced:
            isolated.append(iid)

    return isolated


def check_has_no_cycles(items: list, deps_field: str = "dependencies") -> list[list[str]]:
    """Check that dependency graph has no cycles.

    Uses 3-color DFS (WHITE/GRAY/BLACK) to correctly detect cycles
    even when nodes are reachable from multiple starting points.

    Returns list of cycle paths (each a list of node IDs forming the cycle).
    Returns empty list if no cycles found.
    """
    from path import _normalize_ref

    if not items or not isinstance(items[0], dict):
        return []

    # Build dependency graph
    graph: dict[str, list[str]] = {}
    for item in items:
        iid = item.get("id", "")
        if iid:
            graph[iid] = list(_normalize_ref(item.get(deps_field, [])))

    # Detect cycles via 3-color DFS
    # WHITE (0) = unvisited, GRAY (1) = in current path, BLACK (2) = fully explored
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for dep in graph.get(node, []):
            if dep not in color:
                # dep not in graph nodes (external ref), skip
                continue
            if color[dep] == GRAY:
                # Found a cycle: extract cycle from path
                cycles.append(path[path.index(dep):] + [dep])
            elif color[dep] == WHITE:
                dfs(dep, path)
        path.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            dfs(node, [])

    return cycles


# ── Shared build_args for check dispatch ─────────────────────────────────────
# Called by both rule handlers (rules.py) and gate handlers (gates.py) to
# construct positional args for a pure check function.
#
# Each builder: (def_dict, resolved, spec, extra_specs) -> (check_name, *args)
# The `def_dict` is the rule or gate definition dict.
# `resolved` is the Resolved namedtuple from resolve_path().
# `spec` / `extra_specs` are the primary spec and cross-spec context.
#
# This eliminates duplicated build_args lambdas in rules.py and gates.py.

from path import _normalize_ref, resolve_path

_CHECK_BUILDERS: dict[str, callable] = {
    "non_empty":    lambda d, res, s, e: ("non_empty", res.values, res.parent_ids),
    "count":        lambda d, res, s, e: ("count", res.values, d["count"]),
    "coverage":     lambda d, res, s, e: (
        "coverage",
        {_ref for v in res.values for _ref in _normalize_ref(v)},
        [i.get("id", str(i)) if isinstance(i, dict) else str(i)
         for i in resolve_path(d["should_cover_all"], s, e).values],
    ),
    "all_have":     lambda d, res, s, e: ("all_have", res.values, d["field"], d.get("min_length", 0)),
    "none_match":   lambda d, res, s, e: ("none_match", res.values, d["field"], d["pattern"]),
    "value":        lambda d, res, s, e: ("value", res.values[0] if res.values else None, d["expected"]),
    "exists":       lambda d, res, s, e: (
        "exists", res.values, res.parent_ids,
        {str(v) for v in resolve_path(d["inside"], s, e).values},
    ),
    "unique":       lambda d, res, s, e: ("unique", res.values, res.parent_ids),
    "no_overlap":   lambda d, res, s, e: ("no_overlap", res.values, res.parent_ids),
    "item_count":   lambda d, res, s, e: (
        "item_count", res.values, res.parent_ids, d["count"], d.get("compare_mode", "more"),
    ),
    "patterns":     lambda d, res, s, e: (
        "patterns", res.values, res.parent_ids,
        d.get("patterns", []), d.get("negate", False), d.get("extra_keys", []),
        res.group_sizes, d.get("max_count"),
    ),
    "orphans":      lambda d, res, s, e: ("orphans", res.values),
    "has_no_cycles": lambda d, res, s, e: (
        "has_no_cycles", res.values, d.get("deps", "dependencies"),
    ),
}


# ── Unified dispatcher ───────────────────────────────────────────────────────
# Called by both rule handlers (rules.py) and gate handlers (gates.py) to
# invoke a pure check function and wrap results in a CheckResult namedtuple.

_CHECK_REGISTRY: dict[str, callable] = {
    "non_empty":    check_non_empty,
    "count":        check_count,
    "coverage":     check_coverage,
    "all_have":     check_all_have,
    "none_match":   check_none_match,
    "value":        check_value,
    # Newly extracted checks
    "exists":       check_exists,
    "unique":       check_unique,
    "no_overlap":   check_no_overlap,
    "item_count":   check_item_count,
    "patterns":     check_patterns,
    "orphans":      check_orphans,
    "has_no_cycles": check_has_no_cycles,
}


def dispatch_check(
    check_name: str,
    *args,
    values: list,
    parent_ids: list,
) -> "CheckResult":
    """Invoke a pure check function and wrap results uniformly.

    Args:
        check_name: key in _CHECK_REGISTRY (e.g. "non_empty", "count")
        *args: positional args for the check function
        values: resolved values (for CheckResult wrapper)
        parent_ids: resolved parent IDs (for CheckResult wrapper)

    Returns:
        CheckResult(fn=check_fn, results=..., values=values, parent_ids=...)
    """
    fn = _CHECK_REGISTRY.get(check_name)
    if fn is None:
        raise ValueError(f"Unknown check: '{check_name}'")
    return CheckResult(fn=fn, results=fn(*args), values=values, parent_ids=parent_ids)
