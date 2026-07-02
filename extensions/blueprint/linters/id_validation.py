#!/usr/bin/env python3
"""
id_validation.py — ID format validation helpers.

Provides functions to validate IDs against canonical patterns,
check sequential numbering, and verify cross-spec consistency.

All linters import from shared.py which re-exports these.
"""

import re

from id_patterns import ID_PATTERNS, SECTION_ID_PATTERNS
from linter_types import LayerResult


def _validate_id(id_value: str, id_type: str) -> tuple[bool, str]:
    """Validate a single ID against its canonical pattern.

    Returns (is_valid, error_message).
    """
    if id_type not in ID_PATTERNS:
        return True, ""  # Unknown type, skip validation
    pattern = ID_PATTERNS[id_type]["pattern"]
    if re.match(pattern, id_value):
        return True, ""
    return (
        False,
        f"ID '{id_value}' does not follow {ID_PATTERNS[id_type]['hint'].lower()}",
    )


def _validate_ids(
    items: list[dict], id_key: str, id_type: str, category: str, result: LayerResult
) -> None:
    """Validate IDs for a list of items (private - use validate_spec_ids)."""
    for item in items:
        iid = item.get(id_key, "")
        valid, msg = _validate_id(iid, id_type)
        if not valid:
            pattern = ID_PATTERNS[id_type]
            hint_text = pattern["hint"].replace("Format: ", "").lower()
            example = pattern["example"]
            result.add(
                "error",
                category,
                msg,
                hint=f"Use format {hint_text} (e.g. '{example}').",
            )


def validate_spec_ids(items_by_type: dict[str, list], result: LayerResult) -> None:
    """Validate all IDs in a spec at once.

    Args:
        items_by_type: Mapping of id_type → items list (e.g. {"comp": components, "flw": flows}).
        result: LayerResult to append errors to.

    Example:
        validate_spec_ids({
            "comp": spec.get("components", []),
            "flw": spec.get("dataFlow", []),
            "con": spec.get("constraints", []),
        }, result)
    """
    for id_type, items in items_by_type.items():
        if items:
            _validate_ids(items, "id", id_type, f"{id_type}_id_format", result)


def validate_sequential(ids: list[str], label: str, result: LayerResult) -> None:
    """Warn when IDs skip numbers, e.g. REQ-001, REQ-003 (missing REQ-002).

    Args:
        ids: List of ID strings.
        label: Label for the warning message (e.g. "REQ", "US").
        result: LayerResult to append warnings to.
    """

    def _extract_num(id_str: str) -> int:
        parts = id_str.split("-")
        if len(parts) < 2:
            return -1
        try:
            return int(parts[1])
        except ValueError:
            return -1

    nums = sorted([_extract_num(i) for i in ids])
    nums = [n for n in nums if n >= 0]
    if not nums:
        return
    for i, n in enumerate(nums):
        expected = i + 1
        if n != expected:
            result.add(
                "warning",
                "id_gap",
                f"{label} numbering skips from {expected - 1:03d} to {n:03d}.",
                hint=f"Consider renumbering to keep {label} IDs sequential.",
            )
            break  # report first gap only


def validate_project_and_version(
    spec: dict, spec_name: str, goal: dict, result: LayerResult
) -> None:
    """Check project match and version pinning against GoalSpec.

    Args:
        spec: The spec to check.
        spec_name: Name for error messages (e.g. "archspec", "designspec").
        goal: The GoalSpec dict.
        result: LayerResult to append errors to.
    """
    if spec.get("project") != goal.get("project"):
        result.add(
            "error",
            "project_match",
            f"Project mismatch: {spec_name}='{spec.get('project')}' goalspec='{goal.get('project')}'.",
            hint=f"Both specs must have identical 'project' values.",
        )
    pinned = spec.get("goalSpecVersion")
    if pinned:
        # Normalize: strip leading 'v' so both sides compare as plain semver
        pinned_clean = pinned.lstrip("v")
        goal_version = goal.get("version", "").lstrip("v")
        if pinned_clean != goal_version:
            result.add(
                "error",
                "version_drift",
                f"{spec_name}.goalSpecVersion='{pinned}' does not match goalspec.version='{goal.get('version')}'.",
                hint=f"Update goalSpecVersion after reviewing {spec_name} against the updated GoalSpec.",
            )


def _validate_all_ids(spec: dict, result: LayerResult) -> None:
    """Validate all IDs in a spec against canonical patterns.

    Automatically extracts IDs from all sections defined in SECTION_ID_PATTERNS.
    Also checks that IDs are sequential (warns if gaps exist).
    """

    def _get(path: str) -> list:
        current = spec
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key, {})
            else:
                return []
        return current if isinstance(current, list) else []

    items_by_type = {}
    for section_path, pattern_type in SECTION_ID_PATTERNS.items():
        items = _get(section_path)
        if items:
            items_by_type[pattern_type] = items

    if items_by_type:
        validate_spec_ids(items_by_type, result)
        # Check sequential numbering for all ID types
        for id_type, items in items_by_type.items():
            ids = [item.get("id", "") for item in items]
            validate_sequential(ids, id_type, result)
