#!/usr/bin/env python3
"""
rules.py — Declarative rule handlers, schemas, and dispatch.

Defines TypedDict schemas for all rule types, the handler registry,
and the _run_new_semantic_rules dispatch function.

Architecture (shared with gates.py):
  - Pure check functions live in check.py
  - Shared build_args live in check.py as _CHECK_BUILDERS
  - Each rule type is defined in _RULE_DEFS with:
      check: str          — key in _CHECK_BUILDERS
      format: lambda       — (spec, data, result) -> list[Issue]
  - format lambdas use named Issue(severity, category, message, hint)
  - _make_rule_handler() wraps builder + format into a dispatchable handler
  - _RULE_HANDLERS maps rule type -> handler (auto-generated from _RULE_DEFS)

All linters import SemanticRule from here to type-annotate their
SEMANTIC_RULES lists.
"""

from dataclasses import dataclass, astuple
from typing import Literal, TypedDict, Union

from check import CheckDef, CheckResult, dispatch_check, _CHECK_BUILDERS
from path import resolve_path
from linter_types import Issue, LayerResult, Resolved


# ── TypedDict schemas for semantic rules ─────────────────────────────────────


class _RuleBase(CheckDef, total=False):
    """Optional fields shared by all rule types (extends CheckDef)."""
    severity: str


class _TargetRuleBase(_RuleBase, total=False):
    """Base for rules that operate on a single target path."""
    target: str


class NonEmptyRule(_TargetRuleBase):
    """Check that a field is not empty/missing."""
    check: Literal["non_empty"]
    target: str


class ExistsRule(_TargetRuleBase):
    """Check that field values resolve to valid targets.

    'inside' path includes the ID field: "components.id"
    """
    check: Literal["exists"]
    target: str
    inside: str
    ref_label: str


class IsUniqueRule(_TargetRuleBase):
    """Check that values in a field are unique."""
    check: Literal["is_unique"]
    target: str


class NotSharedRule(_TargetRuleBase):
    """Check that list items are not shared across parent items."""
    check: Literal["not_shared"]
    target: str


class HasItemCountRule(_TargetRuleBase):
    """Check list length against threshold."""
    check: Literal["has_item_count"]
    target: str
    count: int
    compare_mode: Literal["more", "less", "equal"]


class ContainsPatternsRule(_TargetRuleBase):
    """Check text against regex patterns.

    For single-property checks, append to target path (e.g. "entities.fields.name").
    For multi-property checks on the same item, use extra_keys.
    """
    check: Literal["contains_patterns"]
    target: str
    patterns: list
    negate: bool
    extra_keys: list[str]
    max_count: int


class CoversAllRule(_TargetRuleBase):
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    check: Literal["covers_all"]
    target: str
    should_cover_all: str
    covered_label: str


class NotOrphanRule(_TargetRuleBase):
    """Check for isolated items (no *Refs outgoing, no *Refs incoming).

    Auto-discovers all *Refs/*Ref fields — no deps_field needed.
    """
    check: Literal["not_orphan"]
    target: str


class HasNoCyclesRule(_TargetRuleBase):
    """Check that dependency graph has no cycles.

    'deps' specifies the key holding dependency references (default: 'dependencies').
    """
    check: Literal["has_no_cycles"]
    target: str
    deps: str


# Union of all rule types
SemanticRule = Union[
    NonEmptyRule,
    ExistsRule,
    IsUniqueRule,
    NotSharedRule,
    HasItemCountRule,
    ContainsPatternsRule,
    CoversAllRule,
    NotOrphanRule,
    HasNoCyclesRule,
]


# ── Rule handler factory ─────────────────────────────────────────────────────
# All rule handlers follow the same pattern:
#   1) Look up the shared build_args from _CHECK_BUILDERS[check_name]
#   2) Call a pure check function via dispatch_check()
#   3) Format CheckResult.results into Issue objects → LayerResult.add() calls
#
# _make_rule_handler() generates a handler from:
#   - check_name: key in _CHECK_BUILDERS (shared build_args for rules + gates)
#   - format_fn: (spec, data, result) -> list[Issue]


def _make_rule_handler(check_name: str, format_fn):
    """Generate a rule handler from check name and result formatter."""
    builder = _CHECK_BUILDERS[check_name]
    def handler(resolved, rule, result, spec, extra_specs):
        args = builder(rule, resolved, spec, extra_specs)
        cr = dispatch_check(args[0], *args[1:],
                            values=resolved.values, parent_ids=resolved.parent_ids)
        for issue in format_fn(rule, resolved, cr):
            result.add(*astuple(issue))
    return handler


# ── Rule definitions (data-driven) ───────────────────────────────────────────

_RULE_DEFS = {
    "non_empty": {
        "check": "non_empty",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "empty"),
                message=f"{spec.get('target_label', data.parent_label)} '{pid}': {detail}.",
                hint=spec.get("hint") or f"Provide a value for {spec.get('target_label', data.parent_label).lower()} '{pid}'.",
            )
            for pid, detail in result.results
        ],
    },

    "exists": {
        "check": "exists",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "error"),
                category=spec.get("category", "missing"),
                message=f"{spec.get('target_label', data.parent_label)} '{pid}': ref '{ref}' not found in {spec.get('ref_label', 'valid set')}.",
                hint=spec.get("hint") or f"Add '{ref}' to the target or correct the reference.",
            )
            for ref, pid in result.results
        ],
    },

    "is_unique": {
        "check": "unique",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "duplicate"),
                message=f"Duplicate {spec.get('target_label', data.parent_label).lower()} '{val}' (also '{first_pid}').",
                hint=spec.get("hint") or f"Each {spec.get('target_label', data.parent_label).lower()} must have a unique identifier.",
            )
            for val, first_pid, dup_pid in result.results
        ],
    },

    "not_shared": {
        "check": "no_overlap",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "overlap"),
                message=f"Item '{item}' is assigned to multiple {spec.get('target_label', data.parent_label).lower()}: {first_pid} and {dup_pid}.",
                hint=spec.get("hint") or f"Each item should belong to exactly one {spec.get('target_label', data.parent_label).lower()}.",
            )
            for item, first_pid, dup_pid in result.results
        ],
    },

    "has_item_count": {
        "check": "item_count",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "count"),
                message=f"{spec.get('target_label', data.parent_label)} '{pid}': {detail}.",
                hint=spec.get("hint", ""),
            )
            for pid, detail in result.results
        ],
    },

    "contains_patterns": {
        "check": "patterns",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "pattern_match"),
                message=f"{spec.get('target_label', data.parent_label)} '{pid}': {detail}.",
                hint=spec.get("hint") or f"Review {spec.get('target_label', data.parent_label).lower()} for {spec.get('category', 'pattern_match')}.",
            )
            for pid, detail in result.results
        ],
    },

    "covers_all": {
        "check": "coverage",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "uncovered"),
                message=f"{spec.get('covered_label', '?')} {iid} is not covered by any {spec.get('target_label', 'source')}.",
                hint=spec.get("hint") or f"Add ref '{iid}' to a {spec.get('target_label', 'source').lower()} responsible for this.",
            )
            for iid in result.results
        ],
    },

    "not_orphan": {
        "check": "orphans",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "warning"),
                category=spec.get("category", "isolated"),
                message=f"{spec.get('target_label', data.parent_label)} '{iid}' is isolated: no dependencies and no dependents.",
                hint=spec.get("hint") or f"An isolated {spec.get('target_label', data.parent_label).lower()} may indicate a design issue.",
            )
            for iid in result.results
        ],
    },

    "has_no_cycles": {
        "check": "has_no_cycles",
        "format": lambda spec, data, result: [
            Issue(
                severity=spec.get("severity", "error"),
                category=spec.get("category", "circular_dependency"),
                message=f"Circular {spec.get('target_label', data.parent_label).lower()} dependency detected: {' → '.join(cycle)}.",
                hint=spec.get("hint") or "Refactor to break the cycle — introduce an abstraction or invert a dependency.",
            )
            for cycle in result.results
        ],
    },
}


# ── Rule handler registry (auto-generated) ────────────────────────────────────

@dataclass
class RuleHandler:
    """Rule handler: resolves target, checks condition, returns Issue list."""
    func: callable


_RULE_HANDLERS: dict[str, RuleHandler] = {
    name: RuleHandler(_make_rule_handler(defn["check"], defn["format"]))
    for name, defn in _RULE_DEFS.items()
}


# ── Rule schema validation ────────────────────────────────────────────────────

# Required fields per rule type (beyond 'type' itself)
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "non_empty":         ["target", "category"],
    "exists":            ["target", "inside", "category"],
    "is_unique":         ["target", "category"],
    "not_shared":        ["target", "category"],
    "has_item_count":    ["target", "count", "category"],
    "contains_patterns": ["target", "patterns", "category"],
    "covers_all":        ["target", "should_cover_all", "category"],
    "not_orphan":        ["target", "category"],
    "has_no_cycles":     ["target", "category"],
}

# Known fields per rule type (for detecting typos — includes 'check' itself)
_KNOWN_FIELDS: dict[str, set[str]] = {
    "non_empty":         {"check", "target", "target_label", "category", "severity", "hint"},
    "exists":            {"check", "target", "inside", "ref_label",
                          "target_label", "category", "severity", "hint"},
    "is_unique":         {"check", "target", "target_label", "category", "severity", "hint"},
    "not_shared":        {"check", "target", "target_label", "category", "severity", "hint"},
    "has_item_count":    {"check", "target", "count", "compare_mode",
                          "target_label", "category", "severity", "hint"},
    "contains_patterns": {"check", "target", "patterns", "negate", "extra_keys", "max_count",
                          "target_label", "category", "severity", "hint"},
    "covers_all":        {"check", "target", "should_cover_all", "covered_label", "target_label",
                          "severity", "category", "hint"},
    "not_orphan":        {"check", "target", "category",
                          "target_label", "severity", "hint"},
    "has_no_cycles":     {"check", "target", "deps", "target_label",
                          "category", "severity", "hint"},
}


def _validate_rule(rule: dict) -> list[str]:
    """Validate a rule dict against its TypedDict schema.

    Returns list of error messages (empty = valid).
    """
    errors = []
    rule_type = rule.get("check", "")
    if not rule_type:
        errors.append("missing 'check'")
        return errors

    required = _REQUIRED_FIELDS.get(rule_type, [])
    known = _KNOWN_FIELDS.get(rule_type, set())

    # Check required fields
    for req in required:
        if req not in rule:
            errors.append(f"missing required field '{req}'")

    # Check for unknown fields (typos)
    for key in rule:
        if key not in known:
            errors.append(f"unknown field '{key}'")

    # Type constraints
    if "count" in rule and not isinstance(rule["count"], int):
        errors.append("'count' must be an integer")
    if "patterns" in rule and not isinstance(rule["patterns"], list):
        errors.append("'patterns' must be a list")
    if "extra_keys" in rule and not isinstance(rule["extra_keys"], list):
        errors.append("'extra_keys' must be a list")
    if "compare_mode" in rule and rule.get("compare_mode") not in ("more", "less", "equal"):
        errors.append("'compare_mode' must be 'more', 'less', or 'equal'")
    if "negate" in rule and not isinstance(rule["negate"], bool):
        errors.append("'negate' must be a boolean")
    if "max_count" in rule and not isinstance(rule["max_count"], int):
        errors.append("'max_count' must be an integer")

    return errors


# ── Backward-compatible handler names ─────────────────────────────────────────
# Kept for test_bugfixes.py and any external code that checks for these names.
# They alias the auto-generated handlers.

handle_non_empty         = _RULE_HANDLERS["non_empty"].func
handle_exists            = _RULE_HANDLERS["exists"].func
handle_unique            = _RULE_HANDLERS["is_unique"].func
handle_no_overlap        = _RULE_HANDLERS["not_shared"].func
handle_item_count        = _RULE_HANDLERS["has_item_count"].func
handle_patterns          = _RULE_HANDLERS["contains_patterns"].func
handle_coverage          = _RULE_HANDLERS["covers_all"].func
handle_orphans           = _RULE_HANDLERS["not_orphan"].func
handle_has_no_cycles     = _RULE_HANDLERS["has_no_cycles"].func


# ── Rule runner ───────────────────────────────────────────────────────────────

def _run_new_semantic_rules(rules: list, spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Execute declarative semantic rules using the new path-based system."""
    for rule in rules:
        rule_type = rule.get("check")
        handler = _RULE_HANDLERS.get(rule_type)
        if not handler:
            result.add("warning", "unknown_rule", f"Unknown rule type: {rule_type}")
            continue

        # Validate rule schema
        schema_errors = _validate_rule(rule)
        if schema_errors:
            result.add("error", "rule_schema",
                f"Rule '{rule_type}' schema errors: {'; '.join(schema_errors)}")
            continue

        try:
            resolved = resolve_path(rule["target"], spec, extra_specs)
            handler.func(resolved, rule, result, spec, extra_specs)
        except Exception as e:
            result.add("error", "rule_bug",
                f"Rule '{rule_type}' ({rule.get('target', '?')}): {e}")
