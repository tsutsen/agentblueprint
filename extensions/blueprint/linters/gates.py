#!/usr/bin/env python3
"""
gates.py — Declarative completeness gates.

Gates and rules share the same abstract CheckDef structure (check.py):
  - Both resolve a `target` path via resolve_path()
  - Both dispatch by `type` to a handler
  - Both carry target_label, category, hint

The only difference is output:
  - Rules → Issue(severity, category, message) on LayerResult
  - Gates → CompletenessGate(description, passed, required_at) on CompletenessScore

CheckDef and shared check functions live in check.py.
"""

from dataclasses import dataclass
from typing import Literal, TypedDict, Union

from check import CheckDef, check_all_have, check_count, check_coverage, check_non_empty, check_none_match, check_value
from shared import (
    CompletenessGate,
    CompletenessScore,
    Resolved,
    _normalize_ref,
    resolve_path,
)


# ── Gate-specific TypedDicts ─────────────────────────────────────────────────


class NonEmptyGate(CheckDef):
    """Target list/field is not empty."""
    type: Literal["non_empty"]
    required_at: str


class HasCountGate(CheckDef):
    """Target list has at least `count` items."""
    type: Literal["has_count"]
    required_at: str
    count: int


class CoversAllGate(CheckDef):
    """All items in `should_cover_all` are referenced by `target`."""
    type: Literal["covers_all"]
    required_at: str
    should_cover_all: str
    covered_label: str


class AllHaveGate(CheckDef):
    """Every item in target has a non-empty `field`."""
    type: Literal["all_have"]
    required_at: str
    field: str
    min_length: int


class NoneMatchGate(CheckDef):
    """No item in target has a field matching the pattern."""
    type: Literal["none_match"]
    required_at: str
    field: str
    pattern: str


class ValueCheckGate(CheckDef):
    """Spec-level scalar at `target` passes a condition."""
    type: Literal["value_check"]
    required_at: str
    expected: str  # "truthy", "confirmed", ">=N"


# Union of all gate types
GateDef = Union[
    NonEmptyGate,
    HasCountGate,
    CoversAllGate,
    AllHaveGate,
    NoneMatchGate,
    ValueCheckGate,
]


# ── Gate handlers ────────────────────────────────────────────────────────────
# Each handler receives the Resolved data for the target path,
# the gate dict, and the spec/extra_specs.
# Returns a list of CompletenessGate instances (one per gate check).


def handle_gate_non_empty(
    resolved: Resolved, gate: dict, spec: dict, extra_specs: dict
) -> list[CompletenessGate]:
    """Check that target list/field is not empty."""
    required_at = gate["required_at"]
    description = gate.get("description",
        f"{gate.get('target_label', resolved.parent_label)} is not empty")
    hint = gate.get("hint", "")

    failures = check_non_empty(resolved.values, resolved.parent_ids)

    if not failures:
        return [CompletenessGate(description=description, passed=True,
                                  required_at=required_at)]

    details = [f"'{pid}': {detail}" for pid, detail in failures]
    return [CompletenessGate(
        description=description, passed=False, required_at=required_at,
        detail=f"Empty: {', '.join(details)}"
    )]


def handle_gate_has_count(
    resolved: Resolved, gate: dict, spec: dict, extra_specs: dict
) -> list[CompletenessGate]:
    """Check that target list has at least `count` items."""
    required_at = gate["required_at"]
    count = gate["count"]
    target_label = gate.get("target_label", resolved.parent_label)
    description = gate.get("description",
        f"{target_label} has at least {count} item(s)")

    passed, detail = check_count(resolved.values, count)

    return [CompletenessGate(
        description=description, passed=passed, required_at=required_at,
        detail=detail
    )]


def handle_gate_covers_all(
    resolved: Resolved, gate: dict, spec: dict, extra_specs: dict
) -> list[CompletenessGate]:
    """Check that all items in should_cover_all are referenced by target."""
    required_at = gate["required_at"]
    covered_label = gate.get("covered_label", "")
    target_label = gate.get("target_label", "source")
    description = gate.get("description",
        f"All {covered_label} covered by {target_label}")

    # Resolve the should_cover_all path
    should_cover_resolved = resolve_path(gate["should_cover_all"], spec, extra_specs)

    target_refs = set()
    for val in resolved.values:
        for ref in _normalize_ref(val):
            target_refs.add(ref)

    should_cover_ids = [
        item.get("id", str(item)) if isinstance(item, dict) else str(item)
        for item in should_cover_resolved.values
    ]
    uncovered = check_coverage(target_refs, should_cover_ids)

    if not uncovered:
        return [CompletenessGate(description=description, passed=True,
                                  required_at=required_at)]

    return [CompletenessGate(
        description=description, passed=False, required_at=required_at,
        detail=f"Uncovered: {', '.join(str(u) for u in uncovered)}"
    )]


def handle_gate_all_have(
    resolved: Resolved, gate: dict, spec: dict, extra_specs: dict
) -> list[CompletenessGate]:
    """Check that every item has a non-empty field."""
    required_at = gate["required_at"]
    field_name = gate["field"]
    min_length = gate.get("min_length", 0)
    target_label = gate.get("target_label", resolved.parent_label)
    description = gate.get("description",
        f"All {target_label} have {field_name}")

    items = resolved.values
    failures = check_all_have(items, field_name, min_length)

    if not failures:
        return [CompletenessGate(description=description, passed=True,
                                  required_at=required_at)]

    ids = [pid for pid, _ in failures]
    return [CompletenessGate(
        description=description, passed=False, required_at=required_at,
        detail=f"Missing {field_name}: {', '.join(str(i) for i in ids)}"
    )]


def handle_gate_none_match(
    resolved: Resolved, gate: dict, spec: dict, extra_specs: dict
) -> list[CompletenessGate]:
    """Check that no item matches a forbidden pattern."""
    required_at = gate["required_at"]
    field_name = gate["field"]
    pattern = gate["pattern"]
    target_label = gate.get("target_label", resolved.parent_label)
    description = gate.get("description",
        f"No {target_label} have {field_name} matching {pattern}")

    items = resolved.values
    matches = check_none_match(items, field_name, pattern)

    if not matches:
        return [CompletenessGate(description=description, passed=True,
                                  required_at=required_at)]

    ids = [pid for pid, val in matches]
    return [CompletenessGate(
        description=description, passed=False, required_at=required_at,
        detail=f"Matched: {', '.join(str(i) for i in ids)}"
    )]


def handle_gate_value_check(
    resolved: Resolved, gate: dict, spec: dict, extra_specs: dict
) -> list[CompletenessGate]:
    """Check that a spec-level scalar passes a condition."""
    required_at = gate["required_at"]
    expected = gate["expected"]
    description = gate.get("description",
        f"{gate.get('target_label', resolved.parent_label)} is {expected}")

    value = resolved.values[0] if resolved.values else None
    passed, detail = check_value(value, expected)

    return [CompletenessGate(
        description=description, passed=passed, required_at=required_at,
        detail=detail
    )]


# ── Gate handler registry ────────────────────────────────────────────────────

@dataclass
class GateHandler:
    """Gate handler: resolves target, checks condition, returns gates list."""
    func: callable


_GATE_HANDLERS = {
    "non_empty":     GateHandler(handle_gate_non_empty),
    "has_count":     GateHandler(handle_gate_has_count),
    "covers_all":    GateHandler(handle_gate_covers_all),
    "all_have":      GateHandler(handle_gate_all_have),
    "none_match":    GateHandler(handle_gate_none_match),
    "value_check":   GateHandler(handle_gate_value_check),
}


# ── Gate runner ──────────────────────────────────────────────────────────────


def run_gates(
    gates: list[GateDef],
    spec: dict,
    extra_specs: dict,
    spec_name: str = "",
    status: str = "draft",
) -> CompletenessScore:
    """Execute declarative gates and return a CompletenessScore.

    Args:
        gates: list of GateDef dicts (declarative gate specifications)
        spec: the primary spec dict
        extra_specs: cross-spec refs (e.g. {"goal": goal_spec})
        spec_name: spec identifier (e.g. "goalspec")
        status: current lifecycle status

    Returns:
        CompletenessScore with all gates evaluated
    """
    all_gates: list[CompletenessGate] = []

    for gate_def in gates:
        gate_type = gate_def.get("type")
        handler = _GATE_HANDLERS.get(gate_type)

        if not handler:
            all_gates.append(CompletenessGate(
                description=f"Unknown gate type: {gate_type}",
                passed=False, required_at=gate_def.get("required_at", "draft"),
                detail=f"No handler for gate type '{gate_type}'"
            ))
            continue

        try:
            resolved = resolve_path(gate_def["target"], spec, extra_specs)
            results = handler.func(resolved, gate_def, spec, extra_specs)
            all_gates.extend(results)
        except Exception as e:
            all_gates.append(CompletenessGate(
                description=f"Gate '{gate_type}' ({gate_def.get('target', '?')})",
                passed=False, required_at=gate_def.get("required_at", "draft"),
                detail=f"Error: {e}"
            ))

    return CompletenessScore(
        spec=spec_name or status,
        status=status,
        gates=all_gates,
    )
