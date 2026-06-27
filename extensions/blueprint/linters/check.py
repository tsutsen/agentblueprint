#!/usr/bin/env python3
"""
check.py — Abstract check base and shared check functions.

Provides the CheckDef TypedDict that both rules and gates extend,
plus pure check functions that evaluate conditions on resolved data.

Rules (rules.py) and gates (gates.py) import from here.
shared.py calls into this module when needed.
"""

import re
from typing import Literal, TypedDict


# ── Abstract check base ──────────────────────────────────────────────────────
# Both SemanticRule (rules.py) and GateDef (gates.py) extend this.


class CheckDef(TypedDict, total=False):
    """Abstract base for rules and gates.

    Concrete fields shared by both:
        type          — dispatch key (e.g. "non_empty", "has_count")
        target        — dot-separated path to resolve
        target_label  — human label for the target item
        category      — issue/gate category identifier
        hint          — optional hint text
    """
    type: str
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
