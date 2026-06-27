#!/usr/bin/env python3
"""
rules.py — Declarative rule handlers, schemas, and dispatch.

Defines TypedDict schemas for all rule types, the handler registry,
and the _run_new_semantic_rules dispatch function.

All linters import SemanticRule from here to type-annotate their
SEMANTIC_RULES lists.
"""

import re
from dataclasses import dataclass
from typing import Literal, TypedDict, Union

from shared import LayerResult, Resolved, _normalize_ref, resolve_path


# ── TypedDict schemas for semantic rules ─────────────────────────────────────


class _RuleBase(TypedDict, total=False):
    """Optional fields shared by all rule types."""
    target_label: str
    category: str
    severity: str
    hint: str


class _TargetRuleBase(_RuleBase, total=False):
    """Base for rules that operate on a single target path."""
    target: str


class NonEmptyRule(_TargetRuleBase):
    """Check that a field is not empty/missing."""
    type: Literal["non_empty"]
    target: str


class ExistsRule(_TargetRuleBase):
    """Check that field values resolve to valid targets.

    'inside' path includes the ID field: "components.id"
    """
    type: Literal["exists"]
    target: str
    inside: str
    ref_label: str


class IsUniqueRule(_TargetRuleBase):
    """Check that values in a field are unique."""
    type: Literal["is_unique"]
    target: str


class NotSharedRule(_TargetRuleBase):
    """Check that list items are not shared across parent items."""
    type: Literal["not_shared"]
    target: str


class HasItemCountRule(_TargetRuleBase):
    """Check list length against threshold."""
    type: Literal["has_item_count"]
    target: str
    count: int
    compare_mode: int


class ContainsPatternsRule(_TargetRuleBase):
    """Check text against regex patterns.

    For single-property checks, append to target path (e.g. "entities.fields.name").
    For multi-property checks on the same item, use extra_keys.
    """
    type: Literal["contains_patterns"]
    target: str
    patterns: list
    negate: bool
    extra_keys: list[str]
    max_count: int


class CoversAllRule(_TargetRuleBase):
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    type: Literal["covers_all"]
    target: str
    should_cover_all: str
    covered_label: str


class NotOrphanRule(_TargetRuleBase):
    """Check for isolated items (no *Refs outgoing, no *Refs incoming).

    Auto-discovers all *Refs/*Ref fields — no deps_field needed.
    """
    type: Literal["not_orphan"]
    target: str


class HasNoCyclesRule(_TargetRuleBase):
    """Check that dependency graph has no cycles.

    'deps' specifies the key holding dependency references (default: 'dependencies').
    """
    type: Literal["has_no_cycles"]
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


# ── Rule handlers ─────────────────────────────────────────────────────────────


def handle_non_empty(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check that resolved values are not empty/missing."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "empty")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")

    # Use shared check function
    from shared import check_non_empty
    for pid, detail in check_non_empty(resolved.values, resolved.parent_ids):
        hint_text = hint or f"Provide a value for {target_label.lower()} '{pid}'."
        result.add(severity, category,
            f"{target_label} '{pid}': {detail}.",
            hint=hint_text)


def handle_exists(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check that resolved values exist in the valid set."""
    # Resolve the valid set from inside path
    valid_path = rule["inside"]
    valid_resolved = resolve_path(valid_path, spec, extra_specs)
    valid = set()
    for v in valid_resolved.values:
        valid.add(str(v))

    severity = rule.get("severity", "error")
    category = rule.get("category", "missing")
    target_label = rule.get("target_label", resolved.parent_label)
    ref_label = rule.get("ref_label", "valid set")
    hint = rule.get("hint", "")
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if val is None:
            continue
        # Handle both single values and lists of refs
        refs = _normalize_ref(val)
        for ref in refs:
            if ref and ref not in valid:
                result.add(severity, category,
                    f"{target_label} '{pid}': ref '{ref}' not found in {ref_label}.",
                    hint=hint or f"Add '{ref}' to the target or correct the reference.")


def handle_unique(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check that resolved values are unique."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "duplicate")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")
    seen: dict[str, str] = {}
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if not val:
            continue
        str_val = str(val)
        if str_val in seen:
            result.add(severity, category,
                f"Duplicate {target_label.lower()} '{str_val}' (also '{seen[str_val]}').",
                hint=hint or f"Each {target_label.lower()} must have a unique identifier.")
        else:
            seen[str_val] = pid or val


def handle_no_overlap(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check that list fields don't share values across parent items."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "overlap")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")
    seen: dict[str, str] = {}
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if not isinstance(val, list):
            continue
        for item in val:
            if item in seen and seen[item] != pid:
                result.add(severity, category,
                    f"Item '{item}' is assigned to multiple {target_label.lower()}: {seen[item]} and {pid}.",
                    hint=hint or f"Each item should belong to exactly one {target_label.lower()}.")
            seen[item] = pid


def handle_item_count(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check list length against threshold."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "count")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")
    count = rule["count"]
    compare_mode = rule.get("compare_mode", 1)
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if not isinstance(val, list):
            continue
        n = len(val)
        if compare_mode == 1 and n > count:
            result.add(severity, category,
                f"{target_label} '{pid}' has {n} items — consider splitting.",
                hint=hint or f"A {target_label.lower()} with >{count} items may be too complex.")
        elif compare_mode == 0 and n == count:
            result.add(severity, category,
                f"{target_label} '{pid}' has exactly {n} items.",
                hint=hint)
        elif compare_mode == -1 and n < count:
            result.add(severity, category,
                f"{target_label} '{pid}' has {n} items (minimum {count}).",
                hint=hint or f"A {target_label.lower()} should have at least {count} items.")


def handle_patterns(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check text values against regex patterns.

    When `negate` is True (format validation): flag values that DON'T match any pattern.
    When `negate` is False (default, forbidden content): flag values that DO match.

    For single-property checks, use target path: "entities.fields.name"
    For multi-property checks on the same item, use extra_keys: ["layout", "wireframe"]
    """
    severity = rule.get("severity", "warning")
    category = rule.get("category", "pattern_match")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")
    patterns = rule.get("patterns", [])
    extra_keys = rule.get("extra_keys", [])
    max_count = rule.get("max_count")
    negate = rule.get("negate", False)

    for idx, (val, pid) in enumerate(zip(resolved.values, resolved.parent_ids)):
        # Check group size limit (skip items from parents with too many nested items)
        if max_count is not None and resolved.group_sizes and idx < len(resolved.group_sizes):
            if resolved.group_sizes[idx] > max_count:
                continue

        # Extract text — extra_keys for multi-property, or raw string from path
        if extra_keys and isinstance(val, dict):
            texts = [val.get(k, "") for k in extra_keys]
        elif isinstance(val, str):
            texts = [val]
        else:
            continue

        for text in texts:
            matches = []
            any_match = False
            for p in patterns:
                if isinstance(p, str):
                    pattern, pattern_label = p, p
                else:
                    pattern, pattern_label = p
                if negate:
                    # Format validation: check if text matches the expected pattern
                    if re.fullmatch(pattern, text):
                        any_match = True
                else:
                    # Forbidden content: check if pattern is found in text
                    found = re.findall(pattern, text.lower())
                    if found:
                        matches.append((pattern_label, found))
                        any_match = True

            if negate and not any_match:
                # Format validation failed — text didn't match any pattern
                msg = f"{target_label} '{pid}': value '{text}' doesn't match expected pattern: {', '.join(str(p) for p in patterns)}"
                result.add(severity, category, msg, hint=hint or f"Review {target_label.lower()} for {category}.")
            elif not negate and matches:
                # Forbidden content found
                msg = f"{target_label} '{pid}': {', '.join(f'{l}: {m}' for l, m in matches)}."
                result.add(severity, category, msg, hint=hint or f"Review {target_label.lower()} for {category}.")


def handle_coverage(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    # Resolve the should_cover_all path
    should_cover_all_resolved = resolve_path(rule["should_cover_all"], spec, extra_specs)

    severity = rule.get("severity", "warning")
    category = rule.get("category", "uncovered")
    hint_template = rule.get("hint")
    covered_label = rule.get("covered_label", should_cover_all_resolved.parent_label)
    target_label = rule.get("target_label", "source")

    # Collect refs from target path
    covered_refs = set()
    for item in resolved.values:
        for ref in _normalize_ref(item):
            covered_refs.add(ref)

    # Use shared check function to find uncovered IDs
    should_cover_ids = [
        item.get("id", str(item)) if isinstance(item, dict) else str(item)
        for item in should_cover_all_resolved.values
    ]
    from shared import check_coverage
    for iid in check_coverage(covered_refs, should_cover_ids):
        # Look up description from items
        desc = ""
        for item in should_cover_all_resolved.values:
            if isinstance(item, dict) and item.get("id") == iid:
                desc = item.get("description", "")
                break
        desc_short = desc[:60] + "..." if desc else ""
        hint_text = (hint_template or
            f"Add ref '{iid}' to a {target_label} responsible for this.")
        result.add(severity, category,
            f"{covered_label} {iid} ('{desc_short}') is not covered by any {target_label}.",
            hint=hint_text)


def handle_orphans(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Warn if items are isolated (no *Refs outgoing, no *Refs incoming).

    Auto-discovers all *Refs fields on items — no deps_field needed.
    """
    severity = rule.get("severity", "warning")
    category = rule.get("category", "isolated")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")

    items = resolved.values
    if not items or not isinstance(items[0], dict):
        return

    # Auto-discover all *Refs fields
    ref_fields = []
    for item in items:
        for key in item:
            if key.endswith("Refs") or key.endswith("Ref"):
                ref_fields.append(key)

    if not ref_fields:
        return

    # Build referenced set
    referenced_ids = set()
    for item in items:
        for f in ref_fields:
            for ref in _normalize_ref(item.get(f, [])):
                referenced_ids.add(ref)

    # Check each item
    for item in items:
        iid = item.get("id", "")
        if not iid:
            continue

        # Check if this item references anything via any *Refs field
        has_outgoing = any(item.get(f) for f in ref_fields)
        is_referenced = iid in referenced_ids
        if not has_outgoing and not is_referenced:
            result.add(severity, category,
                f"{target_label} '{iid}' is isolated: no dependencies and no dependents.",
                hint=hint or f"An isolated {target_label.lower()} may indicate a design issue.")


def handle_has_no_cycles(resolved: Resolved, rule: dict, result: LayerResult, spec: dict, extra_specs: dict) -> None:
    """Check that dependency graph has no cycles."""
    severity = rule.get("severity", "error")
    category = rule.get("category", "circular_dependency")
    target_label = rule.get("target_label", resolved.parent_label)
    deps_field = rule.get("deps", "dependencies")
    hint = rule.get("hint", "")

    items = resolved.values
    if not items or not isinstance(items[0], dict):
        return

    # Build dependency graph
    graph: dict[str, list[str]] = {}
    for item in items:
        iid = item.get("id", "")
        if iid:
            graph[iid] = list(_normalize_ref(item.get(deps_field, [])))

    # Detect cycles via DFS
    visited = set()
    path = []

    def dfs(node):
        if node in path:
            return path[path.index(node):]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        for dep in graph.get(node, []):
            cycle = dfs(dep)
            if cycle:
                return cycle
        path.pop()
        return None

    for node in graph:
        if node not in visited:
            cycle = dfs(node)
            if cycle:
                cycle_str = " → ".join(cycle + [cycle[0]])
                result.add(severity, category,
                    f"Circular {target_label.lower()} dependency detected: {cycle_str}.",
                    hint=hint or f"Refactor to break the cycle — introduce an abstraction or invert a dependency.")
                return  # Report first cycle only


# ── Rule handler registry ─────────────────────────────────────────────────────

@dataclass
class RuleHandler:
    func: callable


_RULE_HANDLERS = {
    "non_empty":         RuleHandler(handle_non_empty),
    "exists":            RuleHandler(handle_exists),
    "is_unique":         RuleHandler(handle_unique),
    "not_shared":        RuleHandler(handle_no_overlap),
    "has_item_count":    RuleHandler(handle_item_count),
    "contains_patterns": RuleHandler(handle_patterns),
    "covers_all":        RuleHandler(handle_coverage),
    "not_orphan":        RuleHandler(handle_orphans),
    "has_no_cycles":     RuleHandler(handle_has_no_cycles),
}


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

# Known fields per rule type (for detecting typos — includes 'type' itself)
_KNOWN_FIELDS: dict[str, set[str]] = {
    "non_empty":         {"type", "target", "target_label", "category", "severity", "hint"},
    "exists":            {"type", "target", "inside", "ref_label",
                          "target_label", "category", "severity", "hint"},
    "is_unique":         {"type", "target", "target_label", "category", "severity", "hint"},
    "not_shared":        {"type", "target", "target_label", "category", "severity", "hint"},
    "has_item_count":    {"type", "target", "count", "compare_mode",
                          "target_label", "category", "severity", "hint"},
    "contains_patterns": {"type", "target", "patterns", "negate", "extra_keys", "max_count",
                          "target_label", "category", "severity", "hint"},
    "covers_all":        {"type", "target", "should_cover_all", "covered_label", "target_label",
                          "severity", "category", "hint"},
    "not_orphan":        {"type", "target", "category",
                          "target_label", "severity", "hint"},
    "has_no_cycles":     {"type", "target", "deps", "target_label",
                          "category", "severity", "hint"},
}


def _validate_rule(rule: dict) -> list[str]:
    """Validate a rule dict against its TypedDict schema.

    Returns list of error messages (empty = valid).
    """
    errors = []
    rule_type = rule.get("type", "")
    if not rule_type:
        errors.append("missing 'type'")
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
    if "compare_mode" in rule and rule.get("compare_mode") not in (-1, 0, 1):
        errors.append("'compare_mode' must be -1, 0, or 1")
    if "negate" in rule and not isinstance(rule["negate"], bool):
        errors.append("'negate' must be a boolean")
    if "max_count" in rule and not isinstance(rule["max_count"], int):
        errors.append("'max_count' must be an integer")

    return errors


def _run_new_semantic_rules(rules: list, spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Execute declarative semantic rules using the new path-based system."""
    for rule in rules:
        rule_type = rule.get("type")
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
