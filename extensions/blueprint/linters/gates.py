#!/usr/bin/env python3
"""
gates.py — Declarative completeness gates.

Gates and rules share the same backbone (check.py):
  - Shared build_args: _CHECK_BUILDERS
  - Shared dispatch: dispatch_check()
  - Both use format: (spec, data, result) -> list[OutputClass]

The only difference is output:
  - Rules → list[Issue] (one per violation, iterates over result.results)
  - Gates → list[CompletenessGate] (one verdict, looks at all results together)

CheckDef and shared check functions live in check.py.
"""

from dataclasses import dataclass
from typing import Literal, TypedDict, Union

from check import (
    CheckDef, CheckResult, dispatch_check, _CHECK_BUILDERS,
)
from path import resolve_path
from linter_types import (
    CompletenessGate,
    CompletenessScore,
    Resolved,
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


# ── Gate handler factory ─────────────────────────────────────────────────────
# All gate handlers follow the same pattern:
#   1) Look up the shared build_args from _CHECK_BUILDERS[check_name]
#   2) Call a pure check function via dispatch_check()
#   3) Format CheckResult.results into list[CompletenessGate]
#
# _make_gate_handler() generates a handler from:
#   - check_name: key in _CHECK_BUILDERS (shared build_args for rules + gates)
#   - format_fn: (spec, data, result) -> list[CompletenessGate]


def _make_gate_handler(check_name: str, format_fn):
    """Generate a gate handler from check name and result formatter."""
    builder = _CHECK_BUILDERS[check_name]
    def handler(resolved, gate, spec, extra_specs):
        args = builder(gate, resolved, spec, extra_specs)
        cr = dispatch_check(args[0], *args[1:],
                            values=resolved.values, parent_ids=resolved.parent_ids)
        return format_fn(gate, resolved, cr)
    return handler


# ── Gate definitions (data-driven) ───────────────────────────────────────────

_GATE_DEFS = {
    "non_empty": {
        "check": "non_empty",
        "format": lambda spec, data, result: [
            CompletenessGate(
                description=spec.get("description",
                    f"{spec.get('target_label', data.parent_label)} is not empty"),
                passed=len(result.results) == 0, required_at=spec["required_at"],
                detail=("Empty: " + ", ".join(f"'{pid}': {d}" for pid, d in result.results)
                        if result.results else "")
            )
        ],
    },
    "has_count": {
        "check": "count",
        "format": lambda spec, data, result: [
            CompletenessGate(
                description=spec.get("description",
                    f"{spec.get('target_label', data.parent_label)} has at least {spec['count']} item(s)"),
                passed=result.results[0], required_at=spec["required_at"],
                detail=result.results[1]
            )
        ],
    },
    "covers_all": {
        "check": "coverage",
        "format": lambda spec, data, result: [
            CompletenessGate(
                description=spec.get("description",
                    f"All {spec.get('covered_label', '')} covered by {spec.get('target_label', 'source')}"),
                passed=len(result.results) == 0, required_at=spec["required_at"],
                detail=("Uncovered: " + ", ".join(str(u) for u in result.results)
                        if result.results else "")
            )
        ],
    },
    "all_have": {
        "check": "all_have",
        "format": lambda spec, data, result: [
            CompletenessGate(
                description=spec.get("description",
                    f"All {spec.get('target_label', data.parent_label)} have {spec['field']}"),
                passed=len(result.results) == 0, required_at=spec["required_at"],
                detail=(f"Missing {spec['field']}: " + ", ".join(pid for pid, _ in result.results)
                        if result.results else "")
            )
        ],
    },
    "none_match": {
        "check": "none_match",
        "format": lambda spec, data, result: [
            CompletenessGate(
                description=spec.get("description",
                    f"No {spec.get('target_label', data.parent_label)} have {spec['field']} matching {spec['pattern']}"),
                passed=len(result.results) == 0, required_at=spec["required_at"],
                detail=("Matched: " + ", ".join(pid for pid, _ in result.results)
                        if result.results else "")
            )
        ],
    },
    "value_check": {
        "check": "value",
        "format": lambda spec, data, result: [
            CompletenessGate(
                description=spec.get("description",
                    f"{spec.get('target_label', data.parent_label)} is {spec['expected']}"),
                passed=result.results[0], required_at=spec["required_at"],
                detail=result.results[1]
            )
        ],
    },
}


# ── Gate handler registry ────────────────────────────────────────────────────

@dataclass
class GateHandler:
    """Gate handler: resolves target, checks condition, returns CompletenessGate list."""
    func: callable


_GATE_HANDLERS: dict[str, GateHandler] = {
    name: GateHandler(_make_gate_handler(defn["check"], defn["format"]))
    for name, defn in _GATE_DEFS.items()
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
