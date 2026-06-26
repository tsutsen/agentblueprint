#!/usr/bin/env python3
"""
shared.py — Canonical types and output formatting for all linters.

All linters should import from this module instead of defining their own
Issue and LayerResult types. This ensures consistent output across all
linters, which is critical for agents that parse lint results.

Usage in a linter:
    from shared import Issue, LayerResult, print_human, print_json_output, ID_PATTERNS
"""

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict, Union


# ── TypedDict schemas for semantic rules ─────────────────────────────────────


class _RuleBase(TypedDict, total=False):
    """Optional fields shared by all rule types."""
    label: str
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

    valid_section path includes the ID field: "components.id"
    """
    type: Literal["exists"]
    target: str
    valid_section: str
    ref_label: str


class UniqueRule(_TargetRuleBase):
    """Check that values in a field are unique."""
    type: Literal["unique"]
    target: str


class NoOverlapRule(_TargetRuleBase):
    """Check that list fields don't share values across items."""
    type: Literal["no_overlap"]
    target: str


class ItemCountRule(_TargetRuleBase):
    """Check list length against threshold."""
    type: Literal["item_count"]
    target: str
    count: int
    compare_mode: int


class PatternsRule(_TargetRuleBase):
    """Check text against regex patterns.

    For single-property checks, append to target path (e.g. "entities.fields.name").
    For multi-property checks on the same item, use extra_keys.
    """
    type: Literal["patterns"]
    target: str
    patterns: list
    negate: bool
    extra_keys: list[str]
    max_count: int


class CoverageRule(TypedDict, total=False):
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    type: Literal["coverage"]
    target: str
    should_cover_all: str
    severity: str
    category: str
    hint: str
    covered_label: str
    source_label: str


class OrphansRule(TypedDict, total=False):
    """Check for isolated items (no deps, no dependents).

    Note: uses 'warning' as the category field name (not 'category').
    """
    type: Literal["orphans"]
    target: str
    deps_field: str
    severity: str
    label: str
    hint: str
    id_field: str
    warning: str


# Union of all rule types
SemanticRule = Union[
    NonEmptyRule,
    ExistsRule,
    UniqueRule,
    NoOverlapRule,
    ItemCountRule,
    PatternsRule,
    CoverageRule,
    OrphansRule,
]


# Mapping from rule type to its TypedDict class
_RULE_TYPE_MAP: dict[str, type] = {
    "non_empty": NonEmptyRule,
    "exists": ExistsRule,
    "unique": UniqueRule,
    "no_overlap": NoOverlapRule,
    "item_count": ItemCountRule,
    "patterns": PatternsRule,
    "coverage": CoverageRule,
    "orphans": OrphansRule,
}


# ── Canonical ID patterns (single source of truth) ────────────────────────────
# All ID format patterns are defined here. Linters must use these instead of
# hardcoding patterns. If a pattern changes, update it in one place.

ID_PATTERNS = {
    # ── GoalSpec ──────────────────────────────────────────────────────────────
    "req": {"pattern": r"^REQ-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "REQ-001-createAccount", "hint": "Format: REQ-NNN-lowerCamelCase"},
    "nfr": {"pattern": r"^NFR-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "NFR-001-responseTime", "hint": "Format: NFR-NNN-lowerCamelCase"},
    "us": {"pattern": r"^US-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "US-001-login", "hint": "Format: US-NNN-lowerCamelCase"},
    "sc": {"pattern": r"^SC-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "SC-001-dataIntegrity", "hint": "Format: SC-NNN-lowerCamelCase"},
    "ng": {"pattern": r"^NG-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "NG-001-webSearch", "hint": "Format: NG-NNN-lowerCamelCase"},
    # ── Glossary ──────────────────────────────────────────────────────────────
    "gl": {"pattern": r"^GL-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "GL-001-Authentication", "hint": "Format: GL-NNN-PascalCase"},
    "dg": {"pattern": r"^DG-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "DG-001-MinimizeCognitiveLoad", "hint": "Format: DG-NNN-PascalCase"},
    "scr": {"pattern": r"^SCR-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "SCR-001-LandingPage", "hint": "Format: SCR-NNN-PascalCase"},

    "dt": {"pattern": r"^DT-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "DT-001-PrimaryColor", "hint": "Format: DT-NNN-PascalCase"},
    "pat": {"pattern": r"^PAT-\d{3}$", "example": "PAT-001", "hint": "Format: PAT-NNN (3-digit zero-padded)"},
    "prs": {"pattern": r"^PRS-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "PRS-001-PowerDeveloper", "hint": "Format: PRS-NNN-PascalCase"},
    "spc": {"pattern": r"^SPC-\d{3}$", "example": "SPC-001", "hint": "Format: SPC-NNN (3-digit zero-padded)"},
    "uj": {"pattern": r"^UJ-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "UJ-001-findProduct", "hint": "Format: UJ-NNN-lowerCamelCase"},
    "uxac": {"pattern": r"^UXAC-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "UXAC-001-touchTarget", "hint": "Format: UXAC-NNN-lowerCamelCase"},
    "vdr": {"pattern": r"^VDR-\d{3}$", "example": "VDR-001", "hint": "Format: VDR-NNN (3-digit zero-padded)"},
    # ── ArchitectureSpec ──────────────────────────────────────────────────────
    "comp": {"pattern": r"^COMP-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "COMP-001-AuthService", "hint": "Format: COMP-NNN-PascalCase"},
    "con": {"pattern": r"^CON-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "CON-001-AuthenticationRequired", "hint": "Format: CON-NNN-PascalCase"},
    "flw": {"pattern": r"^FLW-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "FLW-001-SessionCreation", "hint": "Format: FLW-NNN-PascalCase"},
    # ── DataSpec ──────────────────────────────────────────────────────────────
    "ent": {"pattern": r"^ENT-\d{3}-[A-Z][A-Za-z0-9]*$", "example": "ENT-001-User", "hint": "Format: ENT-NNN-PascalCase"},
    "num": {"pattern": r"^NUM-\d{3}-[A-Z][A-Za-z0-9]*$", "example": "NUM-001-Status", "hint": "Format: NUM-NNN-PascalCase"},
    "prim": {"pattern": r"^PRIM-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "PRIM-001-UserId", "hint": "Format: PRIM-NNN-PascalCase"},
    "rel": {"pattern": r"^REL-\d{3}-[A-Z][a-zA-Z0-9]*$", "example": "REL-001-UserOrders", "hint": "Format: REL-NNN-PascalCase"},
    # ── ApiSpec ───────────────────────────────────────────────────────────────
    "fn": {"pattern": r"^FN-\d{3}-[a-z][A-Za-z0-9]*$", "example": "FN-001-authenticate", "hint": "Format: FN-NNN-lowerCamelCase"},
    # ── TestSpec ──────────────────────────────────────────────────────────────
    "tst": {"pattern": r"^TST-\d{3}-[a-z][A-Za-z0-9]*$", "example": "TST-001-exportReportAsPDF", "hint": "Format: TST-NNN-lowerCamelCase"},
    "fc": {"pattern": r"^FC-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "FC-001-authenticate", "hint": "Format: FC-NNN-lowerCamelCase"},
    # ── TaskPlan / Issues ─────────────────────────────────────────────────────
    "ep": {"pattern": r"^EP-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "EP-001-userOnboarding", "hint": "Format: EP-NNN-lowerCamelCase"},
    "is": {"pattern": r"^IS-\d{3}-[a-z][a-zA-Z0-9]*$", "example": "IS-001-implementLogin", "hint": "Format: IS-NNN-lowerCamelCase"},
    "milestone": {"pattern": r"^MIL-\d+-[A-Z][a-zA-Z]*$", "example": "MIL-001-Setup", "hint": "Format: MIL-NNN-NamePascalCase (e.g. MIL-001-Setup)"},
}


def _validate_id(id_value: str, id_type: str) -> tuple[bool, str]:
    """Validate a single ID against its canonical pattern.
    
    Returns (is_valid, error_message).
    """
    if id_type not in ID_PATTERNS:
        return True, ""  # Unknown type, skip validation
    pattern = ID_PATTERNS[id_type]["pattern"]
    if re.match(pattern, id_value):
        return True, ""
    return False, f"ID '{id_value}' does not follow {ID_PATTERNS[id_type]['hint'].lower()}"


def _validate_ids(items: list[dict], id_key: str, id_type: str,
                  category: str, result: "LayerResult") -> None:
    """Validate IDs for a list of items (private - use validate_spec_ids)."""
    for item in items:
        iid = item.get(id_key, "")
        valid, msg = _validate_id(iid, id_type)
        if not valid:
            pattern = ID_PATTERNS[id_type]
            hint_text = pattern["hint"].replace("Format: ", "").lower()
            example = pattern["example"]
            result.add("error", category, msg,
                hint=f"Use format {hint_text} (e.g. '{example}').")



def validate_spec_ids(items_by_type: dict[str, list],
                      result: "LayerResult") -> None:
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


def _extract_num(id_str: str) -> int:
    """Extract the numeric part from REQ-001, NFR-002, etc.
    
    Splits by '-' and uses the second piece (always numeric).
    Returns -1 if the ID doesn't follow the expected format.
    """
    parts = id_str.split("-")
    if len(parts) < 2:
        return -1
    try:
        return int(parts[1])
    except ValueError:
        return -1


def validate_sequential(ids: list[str], label: str, result: "LayerResult") -> None:
    """Warn when IDs skip numbers, e.g. REQ-001, REQ-003 (missing REQ-002).
    
    Args:
        ids: List of ID strings.
        label: Label for the warning message (e.g. "REQ", "US").
        result: LayerResult to append warnings to.
    """
    nums = sorted([_extract_num(i) for i in ids])
    # Skip IDs that don't have numbers (e.g., "solo-developer")
    nums = [n for n in nums if n >= 0]
    if not nums:
        return
    for i, n in enumerate(nums):
        expected = i + 1
        if n != expected:
            result.add("warning", "id_gap",
                f"{label} numbering skips from {expected-1:03d} to {n:03d}.",
                hint=f"Consider renumbering to keep {label} IDs sequential.")
            break  # report first gap only


def find_orphans(items: list[dict], id_key: str, deps_key: str, result: "LayerResult",
                   label: str = "", warning: str = "isolated", hint: str = "",
                   severity: str = "warning") -> None:
    """Warn if items are isolated (no dependencies and no dependents).
    
    Args:
        items: List of item dicts.
        id_key: Key in each item that holds the ID.
        deps_key: Key in each item that holds the list of dependencies.
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g. "Component").
        warning: Category for the warning.
        hint: Custom hint message (default: generic).
        severity: Severity level: "error", "warning", or "info" (default: "warning").
    """
    if not items:
        return
    
    item_ids = {item.get(id_key, "") for item in items}
    depended_upon = set()
    for item in items:
        for dep in item.get(deps_key, []):
            depended_upon.add(dep)
    
    for item in items:
        iid = item.get(id_key, "")
        has_deps = len(item.get(deps_key, [])) > 0
        is_depended_on = iid in depended_upon
        if not has_deps and not is_depended_on:
            result.add(severity, warning,
                f"{label or iid} is isolated: no dependencies and no dependents.",
                hint=hint or f"An isolated {label.lower() or 'item'} may indicate a design issue.")


def find_duplicates(items: list, id_key: str = None, result: "LayerResult" = None,
                    label: str = "", category: str = "duplicate", hint: str = "",
                    normalize: callable = None) -> None:
    """Warn if items have duplicate values (flat list or nested).
    
    Args:
        items: List of IDs (flat) or list of items with nested lists.
        id_key: If flat list, key to extract IDs from (e.g., "id"). If nested, key for nested list.
        result: LayerResult to append warnings to.
        label: Label for the IDs (e.g., "REQ", "FLW") or parent items (e.g., "Component").
        category: Category for the warning.
        hint: Custom hint message.
        normalize: Optional function to normalize values (e.g., str.lower). Default: identity.
    """
    seen: dict[str, str] = {}  # normalized value → first value
    
    # Determine if flat list or nested
    if not items:
        return
    
    first = items[0]
    if isinstance(first, str):
        # Flat list of strings
        for id_str in items:
            norm = normalize(id_str) if normalize else id_str
            if norm in seen:
                result.add(
                    "warning", category,
                    f"Duplicate {label} ID '{id_str}' (also '{seen[norm]}').",
                    hint=hint or f"Each {label} must have a unique ID."
                )
            else:
                seen[norm] = id_str
    elif isinstance(first, dict):
        # List of dicts - check nested items
        for item in items:
            iid = item.get(id_key, "?") if id_key else "?"
            nested_items = item.get(id_key, []) if id_key else []
            
            for nested_item in nested_items:
                text = _extract_nested_texts([nested_item])[0]
                norm = normalize(text) if normalize else text
                
                if norm in seen:
                    result.add(
                        "warning", category,
                        f"{label} '{iid}' has a duplicate {id_key}: '{text}' "
                        f"is identical to one claimed by '{seen[norm]}'.",
                        hint=hint or f"Each {id_key} must be owned by exactly one {label.lower()}.",
                    )
                else:
                    seen[norm] = iid


def find_cycles(items: list[dict], id_key: str, deps_key: str, valid: set[str],
                result: "LayerResult", label: str = "", category: str = "circular_dependency",
                hint: str = "") -> bool:
    """Build dependency graph, validate refs, check for cycles, and report issues.
    
    Args:
        items: List of items with dependencies.
        id_key: Key in each item that holds the ID.
        deps_key: Key in each item that holds the list of dependencies.
        valid: Set of valid dependency IDs.
        result: LayerResult to append errors/warnings to.
        label: Label for error messages (e.g., "Component").
        category: Category for the warning (e.g., "circular_dependency").
        hint: Custom hint message (default: generic).
    
    Returns:
        True if a cycle was found, False otherwise.
    """
    # Build dependency graph and validate refs
    graph: dict[str, list[str]] = {}
    for item in items:
        iid = item.get(id_key, "")
        deps = item.get(deps_key, [])
        graph[iid] = deps
        
        # Validate dependency refs
        for dep in deps:
            if dep not in valid:
                result.add(
                    "error", "dependency_ref",
                    f"{label} '{iid}': dependency '{dep}' is not defined.",
                    hint=f"Add an item with id='{dep}' or correct the dependency reference."
                )
    
    # Check for cycles
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
                result.add(
                    "error", category,
                    f"Circular {label.lower()} dependency detected: {cycle_str}.",
                    hint=hint or "Refactor to break the cycle — introduce an abstraction or invert a dependency."
                )
                return True
    return False


def validate_coverage(covered_items: list[dict], source_items: list[dict],
                      covered_key: str, refs_key: str,
                      result: "LayerResult", covered_label: str,
                      source_label: str = "", severity: str = "warning") -> None:
    """Validate that every item in covered_items is referenced by at least one item in source.
    
    Args:
        covered_items: List of items to check coverage for (e.g., FRs from GoalSpec).
        source_items: List of source items that should reference covered items (e.g., components).
        covered_key: Key in each covered item that holds the ID (e.g., "id").
        refs_key: Key in source items that holds the list of refs (e.g., "reqRefs").
        result: LayerResult to append warnings to.
        covered_label: Label for error messages (e.g., "GoalSpec FR").
        source_label: Label for the source items (e.g., "component").
        severity: Severity level: "error", "warning", or "info" (default: "warning").
    """
    if not covered_items or not source_items:
        return
    
    # Collect all IDs from covered items
    covered_ids = {item.get(covered_key, "") for item in covered_items}
    
    # Collect all refs from source items
    covered_refs = set()
    for item in source_items:
        for ref in _normalize_ref(item.get(refs_key)):
            covered_refs.add(ref)
    
    # Find uncovered items
    for item in covered_items:
        iid = item.get(covered_key, "")
        desc = item.get("description", "")
        desc_short = desc[:60] + "..." if desc else ""
        
        if iid not in covered_refs:
            result.add(severity, "uncovered",
                f"{covered_label} {iid} ('{desc_short}') is not covered by any {source_label}.",
                hint=f"Add ref '{iid}' to a {source_label or 'source item'} responsible for this.")


def validate_no_overlap(items: list[dict], refs_key: str, id_key: str, result: "LayerResult",
                        label: str = "", category: str = "overlap", hint: str = "",
                        severity: str = "warning") -> None:
    """Warn if an item is assigned to multiple groups.
    
    Args:
        items: List of group items (e.g., subsystems).
        refs_key: Key in each item that holds the list of refs (e.g., "componentRefs").
        id_key: Key in each item that holds the group ID/name (e.g., "name").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Subsystem").
        category: Category for the warning (e.g., "overlap").
        hint: Custom hint message (default: generic).
        severity: Severity level: "error", "warning", or "info" (default: "warning").
    """
    item_to_groups: dict[str, list[str]] = {}
    for item in items:
        iid = item.get(id_key, "?")
        for ref in item.get(refs_key, []):
            item_to_groups.setdefault(ref, []).append(iid)
    
    for item, groups in item_to_groups.items():
        if len(groups) > 1:
            result.add(severity, category,
                f"Item '{item}' is assigned to multiple {label.lower() or 'groups'}: {', '.join(groups)}.",
                hint=hint or f"Each {label.lower() or 'item'} should belong to exactly one {label.lower() or 'group'}.")


def validate_exists(items: list, refs: str | list[str] = None, valid: set[str] | dict[str, set[str]] = None,
                  result: "LayerResult" = None, label: str = "", ref_label: str = "",
                  category: str = "missing", hint: str = "", severity: str = "error") -> None:
    """Validate that items reference values in the valid set(s).
    
    Args:
        items: List of items to check (dicts with keys, or flat list of strings).
        refs: If items are dicts, ref key or keys (e.g., "dataRef" or ["reqRefs"]).
              If items are strings, this is the valid set.
        valid: If items are dicts, valid sets mapping ref keys to sets.
               If items are strings, this is the valid set.
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Component").
        ref_label: Label for the reference type (e.g., "DataSpec entity").
        category: Category for the warning (e.g., "missing").
        hint: Custom hint message (default: generic).
        severity: Severity level: "error", "warning", or "info" (default: "error").
    
    Examples:
        # Flat list of strings
        validate_exists(refs, component_ids, result, label="Subsystem", ref_label="component")
        
        # Dicts with ref keys
        validate_exists(steps, "dataRef", entity_names, result, "Flow step", "DataSpec entity")
        
        # Multiple ref keys
        validate_exists(components, ["reqRefs", "nfrRefs"], {"reqRefs": req_ids, "nfrRefs": nfr_ids}, result, "Component")
    """
    # Determine if flat list or dicts
    if not items:
        return
    
    first = items[0]
    if isinstance(first, str):
        # Flat list of strings
        valid_set = valid if valid else set()
        for item in items:
            if item not in valid_set:
                result.add(severity, category,
                    f"{label}: '{item}' not found in {ref_label or 'valid set'}.",
                    hint=f"Add '{item}' to {ref_label or 'the target'} or correct the reference.")
    elif isinstance(first, dict):
        # List of dicts with ref keys
        refs = [refs] if isinstance(refs, str) else refs
        valid = {refs[0]: valid} if isinstance(valid, set) else valid
        
        for item in items:
            iid = item.get("id", "?")
            for refs_key in refs:
                for ref in _normalize_ref(item.get(refs_key)):
                    if ref not in valid.get(refs_key, set()):
                        result.add(severity, category,
                            f"{label} '{iid}': {refs_key} ref '{ref}' not found.",
                            hint=f"Add '{ref}' to the target spec or correct the reference.")


def validate_item_count(items: list[dict], key: str, count: int, compare_mode: int,
                        id_key: str, result: "LayerResult", label: str = "",
                        category: str = "count", hint: str = "",
                        severity: str = "warning") -> None:
    """Validate list field counts with flexible comparison.
    
    Args:
        items: List of items to check.
        key: Key in each item that holds the list to check (e.g., "responsibilities").
        count: Count threshold.
        compare_mode: Comparison mode.
            1: warn if count > threshold (n > 8)
            0: warn if count == threshold (n == 8)
            -1: warn if count < threshold (n < 8)
        id_key: Key in each item that holds the ID (e.g., "id").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Component").
        category: Category for the warning (e.g., "too_many").
        hint: Custom hint message (default: generic).
        severity: Severity level: "error", "warning", or "info" (default: "warning").
    """
    for item in items:
        iid = item.get(id_key, "?")
        refs = item.get(key, [])
        n = len(refs)
        
        if compare_mode == 1 and n > count:
            result.add(severity, category,
                f"{label} '{iid}' has {n} {key} — consider splitting.",
                hint=hint or f"A {label.lower()} with >{count} {key} may be too complex. Consider splitting.")
        elif compare_mode == 0 and n == count:
            result.add(severity, category,
                f"{label} '{iid}' has exactly {n} {key}.",
                hint=hint or f"A {label.lower()} should not have exactly {count} {key}.")
        elif compare_mode == -1 and n < count:
            result.add(severity, category,
                f"{label} '{iid}' has {n} {key} (minimum {count}).",
                hint=hint or f"A {label.lower()} should have at least {count} {key}.")


def validate_non_empty(items: list[dict], key: str, id_key: str, result: "LayerResult",
                       label: str = "", category: str = "empty", hint: str = "",
                       severity: str = "warning") -> None:
    """Warn if items have an empty list or string field.
    
    Args:
        items: List of items to check.
        key: Key in each item that holds the field to check (e.g., "componentRefs" or "dataRef").
        id_key: Key in each item that holds the ID/name (e.g., "id" or "name").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Subsystem" or "Flow step").
        category: Category for the warning (e.g., "empty" or "empty_field").
        hint: Custom hint message (default: generic).
        severity: Severity level: "error", "warning", or "info" (default: "warning").
    """
    for item in items:
        iid = item.get(id_key, "?")
        field = item.get(key)
        
        if field is None:
            result.add(severity, category,
                f"{label or iid} '{iid}': {key} is missing.",
                hint=hint or f"Provide a value for {key}.")
        elif isinstance(field, list) and not field:
            result.add(severity, category,
                f"{label or iid} '{iid}' has no {key}.",
                hint=hint or f"Assign items to this {label.lower() or 'item'} or remove it.")
        elif isinstance(field, str) and not field.strip():
            result.add(severity, category,
                f"{label or iid} '{iid}' has an empty {key}.",
                hint=hint or f"Provide a value for {key}.")


def find_patterns(items: list[dict], text_key: str = None, patterns: list[tuple[str, str]] = None,
                  id_key: str = "id", result: "LayerResult" = None, label: str = "",
                  category: str = "pattern_match", hint: str = "",
                  match_fn: callable = None, nested_key: str = None, max_count: int = None,
                  text_keys: list[str] = None, severity: str = "warning") -> None:
    """Warn if items match patterns in a text field (single or nested).
    
    Args:
        items: List of items to check.
        text_key: Key in each item that holds the text to check (e.g., "description").
                  Deprecated: use text_keys instead for multiple fields.
        patterns: List of (regex_pattern, label) tuples.
        id_key: Key in each item that holds the ID (default: "id").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Constraint").
        category: Category for the warning.
        hint: Custom hint message.
        match_fn: Optional custom match function.
        nested_key: If set, check nested list items (e.g., "responsibilities").
        max_count: If set, only check items with <= this many nested items.
        text_keys: List of text field keys to check (e.g., ["layout", "wireframe"]).
                   If provided, checks all fields; falls back to text_key if not provided.
        severity: Severity level: "error", "warning", or "info" (default: "warning").
    """
    import re
    
    for item in items:
        iid = item.get(id_key, "?")
        
        # Determine texts to check
        if nested_key:
            # Check nested items
            nested_items = item.get(nested_key, [])
            if max_count is not None and len(nested_items) > max_count:
                continue
            texts = _extract_nested_texts(nested_items)
        elif text_keys:
            # Check multiple text fields
            texts = [item.get(k, "") for k in text_keys]
        elif text_key:
            # Check single text field
            texts = [item.get(text_key, "")]
        else:
            continue
        
        for text in texts:
            if match_fn:
                matches = match_fn(text, patterns) if nested_key else match_fn(item, patterns)
            else:
                matches = []
                for p in patterns:
                    # Support both strings and (pattern, label) tuples
                    if isinstance(p, str):
                        pattern, pattern_label = p, p
                    else:
                        pattern, pattern_label = p
                    found = re.findall(pattern, text.lower())
                    if found:
                        matches.append((pattern_label, found))
            
            if matches:
                # Format message based on context
                if nested_key and max_count is not None:
                    # Vague pattern context
                    text_short = text[:80] + "..." if len(text) > 80 else text
                    msg = f"{label or iid} '{iid}' has a single vague responsibility: '{text_short}'."
                elif nested_key:
                    msg = f"{label or iid} '{iid}': {', '.join(f'{l}: {m}' for l, m in matches)}."
                else:
                    msg = f"{label or iid} '{iid}': {', '.join(f'{l}: {m}' for l, m in matches)}."
                
                result.add(severity, category, msg, hint=hint or f"Review {label.lower() or 'item'} for {category}.")


def extract_ids(items: list, key: str) -> list[str]:
    """Extract a field from a list of dicts."""
    return [item[key] for item in items if key in item]


def validate_project_and_version(spec: dict, spec_name: str, goal: dict,
                              result: "LayerResult") -> None:
    """Check project match and version pinning against GoalSpec.
    
    Args:
        spec: The spec to check.
        spec_name: Name for error messages (e.g. "archspec", "designspec").
        goal: The GoalSpec dict.
        result: LayerResult to append errors to.
    """
    if spec.get("project") != goal.get("project"):
        result.add("error", "project_match",
            f"Project mismatch: {spec_name}='{spec.get("project")}' goalspec='{goal.get("project")}'.",
            hint=f"Both specs must have identical 'project' values.")
    pinned = spec.get("goalSpecVersion")
    if pinned and pinned != goal.get("version"):
        result.add("error", "version_drift",
            f"{spec_name}.goalSpecVersion='{pinned}' does not match goalspec.version='{goal.get("version")}'.",
            hint=f"Update goalSpecVersion after reviewing {spec_name} against the updated GoalSpec.")


def _validate_glossary_ref(refs: list, label: str, name: str, gl_ids: set,
                           result: "LayerResult") -> bool:
    """Validate a single item's glossary refs (private helper)."""
    if not refs:
        return False
    for ref in refs:
        if gl_ids and ref not in gl_ids:
            result.add("error", "glossary_ref_missing",
                f"{label} '{name}': glossaryRef '{ref}' not found in Glossary.",
                hint=f"Add a glossary entry with id='{ref}' or correct the reference.")
    return True


def validate_glossary_refs(glossary: dict, result: "LayerResult",
                           checks: list[tuple[str, str, list]]) -> None:
    """Validate glossary refs for multiple fields.
    
    Args:
        glossary: The Glossary dict (or None).
        result: LayerResult to append errors/warnings to.
        checks: List of (label, refs_key, items) tuples.
            label: Label for error messages.
            refs_key: Key in each item that holds the refs list.
            items: List of items to check.
    
    Example:
        validate_glossary_refs(glossary, result, [
            ("Component", "glossaryRefs", spec.get("components", [])),
            ("Flow", "glossaryRefs", spec.get("dataFlow", [])),
        ])
    """
    gl_ids = set()
    if glossary:
        gl_ids = {t["id"] for t in glossary.get("terms", [])}
    
    for label, refs_key, items in checks:
        for item in items:
            item_id = item.get("id", item.get("screenRef", "?"))
            refs = item.get(refs_key, [])
            if not refs:
                result.add("warning", "glossary_ref_missing",
                    f"{label} '{item_id}': no glossaryRefs.",
                    hint=f"Add glossaryRefs (GL-NNN) for domain concepts.")
            else:
                _validate_glossary_ref(refs, label, item_id, gl_ids, result)


def _validate_glossary_ref(refs: list, label: str, name: str, gl_ids: set,
                           result: "LayerResult") -> bool:
    """Validate a single item's glossary refs (private helper)."""
    if not refs:
        return False
    for ref in refs:
        if gl_ids and ref not in gl_ids:
            result.add("error", "glossary_ref_missing",
                f"{label} '{name}': glossaryRef '{ref}' not found in Glossary.",
                hint=f"Add a glossary entry with id='{ref}' or correct the reference.")
    return True


# ── Canonical types ───────────────────────────────────────────────────────────

@dataclass
class Issue:
    """A single lint finding."""
    severity: str          # "error" | "warning" | "info"
    category: str          # e.g. "schema", "duplicate_id", "cross-ref"
    message: str           # Human-readable description of the issue
    hint: str = ""         # Optional suggestion for how to fix


@dataclass
class LayerResult:
    """Result from a single lint layer (one spec or cross-spec check)."""
    name: str = ""
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    @property
    def all_issues(self):
        return self.errors + self.warnings

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)


# ── Output formatting ────────────────────────────────────────────────────────

def print_human(result: LayerResult, path: str = ""):
    """Print human-readable lint report."""
    print(f"\n{'─'*60}")
    if path:
        print(f"  {result.name} Lint Report — {path}")
    else:
        print(f"  {result.name} Lint Report")
    print(f"{'─'*60}")

    if not result.all_issues:
        print("  ✓ All checks passed.\n")
        return

    if result.errors:
        print(f"\n  ERRORS ({len(result.errors)}):")
        for e in result.errors:
            print(f"    ✗ [{e.category}] {e.message}")
            if e.hint:
                print(f"      → {e.hint}")

    if result.warnings:
        print(f"\n  WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    ⚠ [{w.category}] {w.message}")
            if w.hint:
                print(f"      → {w.hint}")

    print(f"\n  {len(result.errors)} error(s), {len(result.warnings)} warning(s).\n")


def print_json_output(result: LayerResult):
    """Print JSON lint report."""
    out = {
        "clean": result.clean,
        "errors": [{"category": e.category, "message": e.message, "hint": e.hint} for e in result.errors],
        "warnings": [{"category": w.category, "message": w.message, "hint": w.hint} for w in result.warnings]
    }
    print(json.dumps(out, indent=2))


# ── Section-to-pattern mapping (single source of truth for ID validation) ─────
SECTION_ID_PATTERNS = {
    # GoalSpec
    "functionalRequirements": "req",
    "nonFunctionalRequirements": "nfr",
    "userStories": "us",
    "successCriteria": "sc",
    "nonGoals": "ng",
    # DesignSpec
    "designGoals": "dg",
    "personas": "prs",
    "userJourneys": "uj",
    "screenInventory": "scr",
    "screenSpecs": "spc",
    "interactionPatterns": "pat",
    "uxAcceptanceCriteria": "uxac",
    "visualDesignRequirements": "vdr",
    # ArchSpec
    "components": "comp",
    "dataFlow": "flw",
    "constraints": "con",
    # DataSpec
    "primitives": "prim",
    "enums": "num",
    "entities": "ent",
    "relationships": "rel",
    # ApiSpec
    "functions": "fn",
    # TestSpec
    "tests": "tst",
    "functionCoverage": "fc",
    # TaskPlan
    "epics": "ep",
    "milestones": "milestone",
    # Glossary
    "terms": "gl",
}


def _get_nested(spec: dict, path: str) -> list:
    """Get a nested list from a spec using dot-separated path.
    
    Args:
        spec: The spec dict.
        path: Dot-separated path (e.g., "overview.subsystems").
    
    Returns:
        List of items at the path, or empty list if not found.
    """
    keys = path.split(".")
    current = spec
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, {})
        else:
            return []
    if isinstance(current, list):
        return current
    return []


def _normalize_ref(ref_value: str | list[str] | None) -> list[str]:
    """Normalize a ref value to a list of strings.
    
    Handles string refs, list refs, and None.
    
    Args:
        ref_value: A ref string, list of refs, or None.
    
    Returns:
        List of ref strings (empty list if None).
    
    Examples:
        >>> _normalize_ref("REQ-001")
        ["REQ-001"]
        >>> _normalize_ref(["REQ-001", "REQ-002"])
        ["REQ-001", "REQ-002"]
        >>> _normalize_ref(None)
        []
    """
    if isinstance(ref_value, str):
        return [ref_value]
    return ref_value or []


def _extract_nested_texts(items: list) -> list[str]:
    """Extract text values from a list of strings or dicts.
    
    Args:
        items: List of strings or dicts with 'text' key.
    
    Returns:
        List of text strings.
    
    Examples:
        >>> _extract_nested_texts(["a", {"text": "b"}])
        ["a", "b"]
    """
    return [item if isinstance(item, str) else item.get("text", "") for item in items]


def _extract_nested_items(items: list, nested_key: str) -> list:
    """Extract nested items from a list of dicts, normalizing to dicts.
    
    Args:
        items: List of dicts with nested lists.
        nested_key: Key in each item that holds the nested list.
    
    Returns:
        Flattened list of nested items (strings converted to {"id": ...}).
    
    Examples:
        >>> _extract_nested_items([{"steps": ["a", {"id": "b"}]}], "steps")
        [{"id": "a"}, {"id": "b"}]
    """
    nested_items = []
    for item in items:
        for nested in item.get(nested_key, []):
            if isinstance(nested, dict):
                nested_items.append(nested)
            else:
                nested_items.append({"id": nested})
    return nested_items


def _resolve_valid_section(rule: dict, spec: dict, extra_specs: dict) -> set:
    """Resolve a 'valid' value for exists/no_overlap rules.
    
    Args:
        rule: The semantic rule dict.
        spec: The spec being linted.
        extra_specs: Extra specs passed to the linter (goal, data, api, etc.).
    
    Returns:
        Set of valid values.
    """
    # Direct valid set (e.g., a set of IDs)
    if "valid" in rule:
        return set(rule["valid"])
    
    # Valid from an extra spec (e.g., goal, data, api) - check first for cross-spec rules
    if "valid_extra_spec" in rule:
        extra = extra_specs.get(rule["valid_extra_spec"])
        if extra:
            items = _get_nested(extra, rule.get("valid_section", ""))
            key = rule.get("valid_key", "id")
            return {item.get(key, "") for item in items}
    
    # Valid from another section in the same spec
    if "valid_section" in rule:
        items = _get_nested(spec, rule["valid_section"])
        key = rule.get("valid_key", "id")
        return {item.get(key, "") for item in items}

    # Fallback: use the same section as the source
    section = rule.get("section")
    if section:
        items = _get_nested(spec, section)
        key = rule.get("valid_key", "id")
        return {item.get(key, "") for item in items}

    return set()


# ── Path-based rule system (new) ─────────────────────────────────────────────

@dataclass
class Resolved:
    """Result of resolving a target path."""
    values: list
    parent_ids: list
    parent_label: str = ""
    parent_items: list = None
    group_sizes: list = None


def resolve_path(path: str, spec: dict, extra_specs: dict) -> Resolved:
    """Navigate a dot-path through spec JSON and return resolved values with parent context.

    Segments:
      - First segment: top-level key in spec or extra_spec
      - Subsequent segments: properties on items, or nested lists (flattened)
      - Prefix `spec:` on first segment to use an extra_spec

    Examples:
      "components.reqRefs"          → each component's reqRefs list
      "dataFlow.steps.componentRef" → each step's componentRef string
      "goal:functionalRequirements" → functionalRequirements from extra_specs["goal"]
    """
    segments = path.split(".")
    if not segments:
        return Resolved([], [], "")

    # Check for extra_spec prefix
    first_segment = segments[0]
    extra_spec_name = None
    if ":" in first_segment:
        extra_spec_name, first_segment = first_segment.split(":", 1)

    # Pick root
    if extra_spec_name:
        root = extra_specs.get(extra_spec_name) or {}
    else:
        root = spec

    # Navigate first segment → root list
    items = root.get(first_segment, [])
    if not isinstance(items, list):
        items = [items] if items else []

    # Compute label from path
    label = path.replace(":", "").replace(".", " ").title().replace(" ", "").replace(":", " ")
    # Better: derive from first segment
    label = first_segment.replace("_", " ").title().replace(" ", "")
    # Handle camelCase-like names (dataFlow → Data Flow)
    import re as _re
    label = _re.sub(r"([A-Z])", r" \1", first_segment).title().replace("_", " ").strip()

    current_items = items
    parent_ids = []
    parent_items = []
    group_sizes = []

    for seg_idx in range(1, len(segments)):
        seg = segments[seg_idx]
        if not current_items:
            break

        first_item = current_items[0] if current_items else {}

        if isinstance(first_item, dict) and seg in first_item:
            val = first_item[seg]
            if isinstance(val, list):
                # Flatten nested lists
                new_items = []
                new_parent_ids = []
                new_parent_items = []
                new_group_sizes = []
                for i, item in enumerate(current_items):
                    nested = item.get(seg, [])
                    if isinstance(nested, list):
                        # Use parent_items for ID when available (e.g. refs.usRefs)
                        pi = parent_items[i] if i < len(parent_items) else item
                        pid = pi.get("id", pi.get("name", item.get("id", item.get("name", "?"))))
                        for nested_item in nested:
                            new_items.append(nested_item)
                            new_parent_ids.append(pid)
                            new_parent_items.append(pi)
                            new_group_sizes.append(len(nested))
                current_items = new_items
                parent_ids = new_parent_ids
                parent_items = new_parent_items
                group_sizes = new_group_sizes
            else:
                # Scalar or dict — check if we need to navigate further
                if seg_idx + 1 < len(segments) and isinstance(val, dict):
                    # Navigate into the dict and continue, preserving parent context
                    new_items = [item.get(seg, {}) for item in current_items]
                    # Preserve parent IDs from parent_items if available, else from current item
                    new_parent_ids = []
                    new_parent_items = []
                    new_group_sizes = []
                    for i, item in enumerate(current_items):
                        # Propagate existing parent context, or derive from current item
                        if parent_ids and i < len(parent_ids):
                            pid = parent_ids[i]
                            pi = parent_items[i] if i < len(parent_items) else item
                        else:
                            pi = item
                            pid = pi.get("id", pi.get("name", "?")) if isinstance(pi, dict) else "?"
                        new_parent_ids.append(pid)
                        new_parent_items.append(pi)
                        new_group_sizes.append(1)
                    current_items = new_items
                    parent_ids = new_parent_ids
                    parent_items = new_parent_items
                    group_sizes = new_group_sizes
                else:
                    # Scalar property — extract and return
                    values = []
                    new_parent_ids = []
                    new_parent_items = []
                    new_group_sizes = []
                    for i, item in enumerate(current_items):
                        values.append(item.get(seg) if isinstance(item, dict) else item)
                        # Use parent context if available, otherwise fall back to item's own id
                        if parent_ids and i < len(parent_ids):
                            pid = parent_ids[i]
                            pi = parent_items[i] if i < len(parent_items) else item
                        else:
                            pid = item.get("id", item.get("name", "?")) if isinstance(item, dict) else "?"
                            pi = item
                        new_parent_ids.append(pid)
                        new_parent_items.append(pi)
                        new_group_sizes.append(1)
                    return Resolved(
                        values=values,
                        parent_ids=new_parent_ids,
                        parent_label=label,
                        parent_items=new_parent_items,
                        group_sizes=new_group_sizes,
                    )
        elif isinstance(first_item, str):
            # Items are already scalars
            break

    # Reached end — return current items as values
    # For single-segment paths or dict-nesting where parent has no id, derive from items' own id/name
    if current_items:
        first = current_items[0]
        if isinstance(first, dict):
            if not parent_ids:
                # Single-segment path: use items' own identifiers
                for item in current_items:
                    pid = item.get("id", item.get("name", "?"))
                    parent_ids.append(pid)
                    parent_items.append(item)
                    group_sizes.append(1)
            elif all(pid == "?" for pid in parent_ids):
                # Dict-nesting where parent segment has no id (e.g. overview.subsystems)
                # Fall back to items' own identifiers
                for i, item in enumerate(current_items):
                    pid = item.get("id", item.get("name", "?"))
                    parent_ids[i] = pid
                    parent_items[i] = item
        elif isinstance(first, str):
            if not parent_ids:
                parent_ids = list(current_items)
                parent_items = list(current_items)
                group_sizes = [1] * len(current_items)
    return Resolved(
        values=current_items,
        parent_ids=parent_ids,
        parent_label=label,
        parent_items=parent_items,
        group_sizes=group_sizes,
    )


# ── Handler functions (new rule system) ───────────────────────────────────────


def handle_non_empty(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Check that resolved values are not empty/missing."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "empty")
    label = rule.get("label", resolved.parent_label)
    hint = rule.get("hint", "")
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if val is None:
            result.add(severity, category,
                f"{label} '{pid}': field is missing.",
                hint=hint or "Provide a value.")
        elif isinstance(val, list) and not val:
            result.add(severity, category,
                f"{label} '{pid}' has no items.",
                hint=hint or f"Assign items to this {label.lower()} or remove it.")
        elif isinstance(val, str) and not val.strip():
            result.add(severity, category,
                f"{label} '{pid}' has an empty field.",
                hint=hint or f"Provide a value.")


def handle_exists(resolved: Resolved, valid: set, rule: dict, result: LayerResult) -> None:
    """Check that resolved values exist in the valid set."""
    severity = rule.get("severity", "error")
    category = rule.get("category", "missing")
    label = rule.get("label", resolved.parent_label)
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
                    f"{label} '{pid}': ref '{ref}' not found in {ref_label}.",
                    hint=hint or f"Add '{ref}' to the target or correct the reference.")


def handle_unique(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Check that resolved values are unique."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "duplicate")
    label = rule.get("label", resolved.parent_label)
    hint = rule.get("hint", "")
    seen: dict[str, str] = {}
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if not val:
            continue
        str_val = str(val)
        if str_val in seen:
            result.add(severity, category,
                f"Duplicate {label.lower()} '{str_val}' (also '{seen[str_val]}').",
                hint=hint or f"Each {label.lower()} must have a unique identifier.")
        else:
            seen[str_val] = pid or val


def handle_no_overlap(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Check that list fields don't share values across parent items."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "overlap")
    label = rule.get("label", resolved.parent_label)
    hint = rule.get("hint", "")
    seen: dict[str, str] = {}
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if not isinstance(val, list):
            continue
        for item in val:
            if item in seen and seen[item] != pid:
                result.add(severity, category,
                    f"Item '{item}' is assigned to multiple {label.lower()}: {seen[item]} and {pid}.",
                    hint=hint or f"Each item should belong to exactly one {label.lower()}.")
            seen[item] = pid


def handle_item_count(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Check list length against threshold."""
    severity = rule.get("severity", "warning")
    category = rule.get("category", "count")
    label = rule.get("label", resolved.parent_label)
    hint = rule.get("hint", "")
    count = rule["count"]
    compare_mode = rule.get("compare_mode", 1)
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if not isinstance(val, list):
            continue
        n = len(val)
        if compare_mode == 1 and n > count:
            result.add(severity, category,
                f"{label} '{pid}' has {n} items — consider splitting.",
                hint=hint or f"A {label.lower()} with >{count} items may be too complex.")
        elif compare_mode == 0 and n == count:
            result.add(severity, category,
                f"{label} '{pid}' has exactly {n} items.",
                hint=hint)
        elif compare_mode == -1 and n < count:
            result.add(severity, category,
                f"{label} '{pid}' has {n} items (minimum {count}).",
                hint=hint or f"A {label.lower()} should have at least {count} items.")


def handle_patterns(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Check text values against regex patterns.

    When `negate` is True (format validation): flag values that DON'T match any pattern.
    When `negate` is False (default, forbidden content): flag values that DO match.

    For single-property checks, use target path: "entities.fields.name"
    For multi-property checks on the same item, use extra_keys: ["layout", "wireframe"]
    """
    import re
    severity = rule.get("severity", "warning")
    category = rule.get("category", "pattern_match")
    label = rule.get("label", resolved.parent_label)
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
                msg = f"{label} '{pid}': value '{text}' doesn't match expected pattern: {', '.join(str(p) for p in patterns)}"
                result.add(severity, category, msg, hint=hint or f"Review {label.lower()} for {category}.")
            elif not negate and matches:
                # Forbidden content found
                msg = f"{label} '{pid}': {', '.join(f'{l}: {m}' for l, m in matches)}."
                result.add(severity, category, msg, hint=hint or f"Review {label.lower()} for {category}.")


def handle_coverage(resolved_should_cover_all: Resolved, resolved_target: Resolved, rule: dict, result: LayerResult) -> None:
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    severity = rule.get("severity", "warning")
    category = rule.get("category", "uncovered")
    hint_template = rule.get("hint")
    covered_label = rule.get("covered_label", resolved_should_cover_all.parent_label)
    source_label = rule.get("source_label", "source")

    # Collect refs from target path (already flat list of ref values)
    covered_refs = set()
    for item in resolved_target.values:
        for ref in _normalize_ref(item):
            covered_refs.add(ref)

    # Find uncovered items
    covered_items = resolved_should_cover_all.values
    for item in covered_items:
        iid = item.get("id", str(item)) if isinstance(item, dict) else str(item)
        desc = item.get("description", "") if isinstance(item, dict) else ""
        desc_short = desc[:60] + "..." if desc else ""
        if iid not in covered_refs:
            hint_text = (hint_template or
                f"Add ref '{iid}' to a {source_label} responsible for this.")
            result.add(severity, category,
                f"{covered_label} {iid} ('{desc_short}') is not covered by any {source_label}.",
                hint=hint_text)


def handle_orphans(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Warn if items are isolated (no dependencies and no dependents)."""
    severity = rule.get("severity", "warning")
    label = rule.get("label", resolved.parent_label)
    warning = rule.get("warning", "isolated")
    hint = rule.get("hint", "")
    deps_field = rule.get("deps_field", "dependencies")
    id_field = rule.get("id_field", "id")

    items = resolved.values
    if not items:
        return

    item_ids = {item.get(id_field, "") for item in items if isinstance(item, dict)}
    depended_upon = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for dep in item.get(deps_field, []):
            depended_upon.add(dep)

    for item in items:
        if not isinstance(item, dict):
            continue
        iid = item.get(id_field, "")
        has_deps = len(item.get(deps_field, [])) > 0
        is_depended_on = iid in depended_upon
        if not has_deps and not is_depended_on:
            result.add(severity, warning,
                f"{label} '{iid}' is isolated: no dependencies and no dependents.",
                hint=hint or f"An isolated {label.lower()} may indicate a design issue.")


# ── Rule handler registry (new) ───────────────────────────────────────────────

@dataclass
class RuleHandler:
    func: callable
    needs_valid: bool = False
    needs_coverage: bool = False
    needs_orphans: bool = False


_RULE_HANDLERS = {
    "non_empty":    RuleHandler(handle_non_empty),
    "exists":       RuleHandler(handle_exists, needs_valid=True),
    "unique":       RuleHandler(handle_unique),
    "no_overlap":   RuleHandler(handle_no_overlap),
    "item_count":   RuleHandler(handle_item_count),
    "patterns":     RuleHandler(handle_patterns),
    "coverage":     RuleHandler(handle_coverage, needs_coverage=True),
    "orphans":      RuleHandler(handle_orphans, needs_orphans=True),
}


# Required fields per rule type (beyond 'type' itself)
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "non_empty":  ["target"],
    "exists":     ["target", "valid_section"],
    "unique":     ["target"],
    "no_overlap": ["target"],
    "item_count": ["target", "count"],
    "patterns":   ["target", "patterns"],
    "coverage":   ["target", "should_cover_all"],
    "orphans":    ["target", "deps_field"],
}

# Known fields per rule type (for detecting typos — includes 'type' itself)
_KNOWN_FIELDS: dict[str, set[str]] = {
    "non_empty":  {"type", "target", "label", "category", "severity", "hint"},
    "exists":     {"type", "target", "valid_section", "ref_label",
                   "label", "category", "severity", "hint"},
    "unique":     {"type", "target", "label", "category", "severity", "hint"},
    "no_overlap": {"type", "target", "label", "category", "severity", "hint"},
    "item_count": {"type", "target", "count", "compare_mode",
                   "label", "category", "severity", "hint"},
    "patterns":   {"type", "target", "patterns", "negate", "extra_keys", "max_count",
                   "label", "category", "severity", "hint"},
    "coverage":   {"type", "target", "should_cover_all", "covered_label", "source_label",
                   "severity", "category", "hint"},
    "orphans":    {"type", "target", "deps_field", "id_field", "warning",
                   "label", "severity", "hint"},
}


def _validate_rule(rule: dict) -> list[str]:
    """Validate a rule dict against its TypedDict schema.

    Returns a list of issue descriptions (empty if valid).
    """
    errors: list[str] = []
    rule_type = rule.get("type")
    if not rule_type:
        errors.append("missing 'type'")
        return errors

    required = _REQUIRED_FIELDS.get(rule_type, [])
    known = _KNOWN_FIELDS.get(rule_type)

    # Check required fields
    for field_name in required:
        if field_name not in rule:
            errors.append(f"missing required field '{field_name}'")

    # Check for unknown fields (typos)
    if known:
        for key in rule:
            if key not in known:
                errors.append(f"unknown field '{key}'")

    # Type checks for known typed fields
    if "count" in rule and not isinstance(rule["count"], int):
        errors.append("'count' must be an integer")
    if "compare_mode" in rule and rule["compare_mode"] not in (-1, 0, 1):
        errors.append("'compare_mode' must be -1, 0, or 1")
    if "patterns" in rule and not isinstance(rule["patterns"], list):
        errors.append("'patterns' must be a list")

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
            if handler.needs_coverage:
                should_cover_all = resolve_path(rule["should_cover_all"], spec, extra_specs)
                resolved = resolve_path(rule["target"], spec, extra_specs)
                handle_coverage(should_cover_all, resolved, rule, result)
            elif handler.needs_orphans:
                resolved = resolve_path(rule["target"], spec, extra_specs)
                handle_orphans(resolved, rule, result)
            else:
                resolved = resolve_path(rule["target"], spec, extra_specs)
                if handler.needs_valid:
                    valid_path = rule["valid_section"]
                    valid_resolved = resolve_path(valid_path, spec, extra_specs)
                    valid = set()
                    for v in valid_resolved.values:
                        valid.add(str(v))
                    handler.func(resolved, valid, rule, result)
                else:
                    handler.func(resolved, rule, result)
        except Exception as e:
            result.add("error", "rule_bug",
                f"Rule '{rule_type}' ({rule.get('target', '?')}): {e}")


def _make_rule_kwargs(rule: dict, extra_keys: list[str] = None) -> dict:
    """Extract common rule fields into kwargs for validation functions.
    
    Args:
        rule: The rule dict.
        extra_keys: Additional keys to include (e.g., ["ref_label", "covered_label"]).
    
    Returns:
        Dict with severity, category, hint, label, and any extra keys.
    """
    common_keys = {"severity", "category", "hint", "label"} | set(extra_keys or [])
    return {k: v for k, v in rule.items() if k in common_keys}


def _run_semantic_rules(rules: list, spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Execute declarative semantic rules against a spec.

    Routes new-format rules (with 'target') to the path-based dispatcher,
    and falls back to the legacy dispatcher for old-format rules (with 'section').
    """
    new_rules = [r for r in rules if "target" in r or "should_cover_all" in r]
    old_rules = [r for r in rules if "section" in r or "key" in r]

    if new_rules:
        _run_new_semantic_rules(new_rules, spec, result, extra_specs)
    if old_rules:
        _run_old_semantic_rules(old_rules, spec, result, extra_specs)


def _run_old_semantic_rules(rules: list, spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Legacy dispatch for old-format rules (section/key based).

    Kept for backward compatibility during migration. Will be removed after all rules migrate.
    """
    for rule in rules:
        section = rule.get("section")
        if section:
            items = _get_nested(spec, section)
            if not items:
                continue
        else:
            items = []

        rule_type = rule.get("type")

        if rule_type == "non_empty":
            key = rule.get("key")
            if rule.get("nested_key"):
                items = _extract_nested_items(items, rule["nested_key"])
                if not key:
                    key = rule.get("id_key", "id")

            validate_non_empty(
                items, key, rule.get("id_key", "id"), result,
                **_make_rule_kwargs(rule)
            )

        elif rule_type == "unique":
            key = rule.get("key", "id")
            values = [item.get(key, "") for item in items if item.get(key)]
            find_duplicates(values, result=result, **_make_rule_kwargs(rule))

        elif rule_type == "exists":
            key = rule.get("key")
            if rule.get("nested_key"):
                items = _extract_nested_items(items, rule["nested_key"])
            valid = _resolve_valid_section(rule, spec, extra_specs)
            if key is None and items and isinstance(items[0], dict):
                continue
            validate_exists(
                items, key, valid, result,
                **_make_rule_kwargs(rule, extra_keys=["ref_label"])
            )

        elif rule_type == "no_overlap":
            validate_no_overlap(
                items, rule["refs_key"], rule.get("id_key", "id"), result,
                **_make_rule_kwargs(rule)
            )

        elif rule_type == "item_count":
            validate_item_count(
                items, rule["key"], rule["count"], rule.get("compare_mode", 1),
                rule.get("id_key", "id"), result, **_make_rule_kwargs(rule)
            )

        elif rule_type == "patterns":
            find_patterns(
                items, text_key=rule.get("text_key"), patterns=rule.get("patterns", []),
                result=result, id_key=rule.get("id_key", "id"),
                **_make_rule_kwargs(rule, extra_keys=["nested_key", "max_count", "text_keys"])
            )

        elif rule_type == "coverage":
            covered = _get_nested(spec, rule.get("covered_section", rule.get("section", "")))
            if rule.get("valid_extra_spec") and not covered:
                extra = extra_specs.get(rule["valid_extra_spec"])
                if extra:
                    covered = _get_nested(extra, rule["covered_section"])
            source_items = _get_nested(spec, rule["source_section"])
            validate_coverage(
                covered, source_items, rule.get("covered_key", "id"), rule["refs_key"],
                result, rule.get("covered_label", ""), rule.get("source_label", ""),
                severity=rule.get("severity", "warning"),
            )

        elif rule_type == "orphans":
            find_orphans(
                items, rule.get("id_key", "id"), rule.get("deps_key", "dependencies"),
                result, rule.get("label", ""), rule.get("warning", "isolated"),
                rule.get("hint", ""), rule.get("severity", "warning"),
            )


def _validate_all_ids(spec: dict, result: LayerResult) -> None:
    """Validate all IDs in a spec against canonical patterns.
    
    Automatically extracts IDs from all sections defined in SECTION_ID_PATTERNS.
    Also checks that IDs are sequential (warns if gaps exist).
    """
    items_by_type = {}
    for section_path, pattern_type in SECTION_ID_PATTERNS.items():
        items = _get_nested(spec, section_path)
        if items:
            items_by_type[pattern_type] = items
    
    if items_by_type:
        validate_spec_ids(items_by_type, result)
        # Check sequential numbering for all ID types
        for id_type, items in items_by_type.items():
            ids = [item.get("id", "") for item in items]
            validate_sequential(ids, id_type, result)


def _strict_mode(result: LayerResult) -> None:
    """Convert all warnings to errors."""
    for w in result.warnings:
        w.severity = "error"
    result.errors.extend(result.warnings)
    result.warnings.clear()


# ── Base Linter ───────────────────────────────────────────────────────────────

class BaseLinter:
    """Base class for all spec linters.
    
    Subclasses define:
    - SPEC_NAME: Name for error messages (e.g., "archspec")
    - SEMANTIC_RULES: Declarative rules for semantic validation
    - MISC_CHECKS: List of (name, func) tuples for custom checks
    
    The run() method orchestrates the full lint pipeline.
    """
    
    SPEC_NAME: str = ""
    SEMANTIC_RULES: list = []
    MISC_CHECKS: list = []  # List of (name, func) tuples
    CROSS_SPEC_DEPS: list = []  # e.g., ["goal", "data", "api"]
    
    def __init__(self, spec: dict, schema_path: Optional[Path], strict: bool):
        self.spec = spec
        self.schema_path = schema_path
        self.strict = strict
        self.result = LayerResult(name=self.SPEC_NAME)
        self.extra_specs: dict = {}
    
    def run(self, **kwargs) -> LayerResult:
        """Main entry point — runs all checks in order."""
        self._store_extra_specs(kwargs)
        self._validate_schema()
        self._validate_ids()
        self._validate_cross_spec_consistency()
        self._run_semantic_rules()
        self._run_misc_checks()
        self._validate_glossary_refs()
        self._strict_mode()
        return self.result
    
    def _store_extra_specs(self, kwargs: dict) -> None:
        """Store extra specs passed to run()."""
        for dep in self.CROSS_SPEC_DEPS:
            if dep in kwargs:
                self.extra_specs[dep] = kwargs[dep]
    
    def _validate_schema(self) -> None:
        """Validate spec against its JSON schema."""
        if not self.schema_path:
            return
        schema = json.loads(self.schema_path.read_text())
        from lint_schemas import SchemaValidator
        for issue in SchemaValidator(schema).validate(self.spec):
            self.result.add(issue.severity, issue.category, issue.message, issue.hint)
    
    def _validate_ids(self) -> None:
        """Validate all IDs in the spec."""
        _validate_all_ids(self.spec, self.result)
    
    def _validate_cross_spec_consistency(self) -> None:
        """Check project match and version pinning."""
        goal = self.extra_specs.get("goal")
        if goal:
            validate_project_and_version(self.spec, self.SPEC_NAME, goal, self.result)
    
    def _run_semantic_rules(self) -> None:
        """Execute declarative semantic rules."""
        _run_semantic_rules(self.SEMANTIC_RULES, self.spec, self.result, self.extra_specs)
    
    def _run_misc_checks(self) -> None:
        """Run custom/spec-specific checks."""
        for name, func in self.MISC_CHECKS:
            func(self.spec, self.result, self.extra_specs)
    
    def _validate_glossary_refs(self) -> None:
        """Validate glossary refs for sections defined in GLOSSARY_CHECKS.
        
        GLOSSARY_CHECKS should be a list of (label, refs_key, section_path) tuples.
        Example: [("Component", "glossaryRefs", "components"), ...]
        """
        glossary = self.extra_specs.get("glossary")
        if not glossary or not hasattr(self, "GLOSSARY_CHECKS"):
            return
        
        # Convert section paths to actual items
        checks = []
        for label, refs_key, section_path in self.GLOSSARY_CHECKS:
            items = _get_nested(self.spec, section_path)
            checks.append((label, refs_key, items))
        
        validate_glossary_refs(glossary, self.result, checks)
    
    def _strict_mode(self) -> None:
        """Convert warnings to errors if strict mode."""
        if self.strict:
            _strict_mode(self.result)
    
    @classmethod
    def main(cls, extra_args: list[tuple] = []):
        """CLI entry point.
        
        Args:
            extra_args: List of (arg_name, kwargs) tuples for additional CLI args.
                       Each kwarg dict can include:
                       - help: Help text
                       - spec_name: Name of the extra spec (e.g., "goal", "data")
                       - required: Whether the arg is required
        """
        parser = argparse.ArgumentParser(description=f"Lint a {cls.SPEC_NAME} JSON.")
        parser.add_argument("input", help=f"Path to {cls.SPEC_NAME} JSON")
        parser.add_argument("--schema", help=f"Path to {cls.SPEC_NAME}.schema.json")
        parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
        parser.add_argument("--json", action="store_true", help="Output as JSON")
        
        # Add extra CLI args
        for arg in extra_args:
            arg_name = arg[0]
            kwargs = arg[1] if len(arg) > 1 else {}
            parser.add_argument(arg_name, **kwargs)
        
        args = parser.parse_args()
        
        spec = json.loads(Path(args.input).read_text())
        schema_path = Path(args.schema) if args.schema else None
        
        # Load extra specs
        extra_specs = {}
        for arg in extra_args:
            arg_name = arg[0]
            kwargs = arg[1] if len(arg) > 1 else {}
            spec_name = kwargs.get("spec_name", arg_name.lstrip("-").replace("-", ""))
            
            arg_value = getattr(args, arg_name.lstrip("-").replace("-", "_"), None)
            if arg_value:
                extra_specs[spec_name] = json.loads(Path(arg_value).read_text())
        
        linter = cls(spec, schema_path, args.strict)
        result = linter.run(**extra_specs)
        
        if args.json:
            print_json_output(result)
        else:
            print_human(result, str(args.input))
        
        sys.exit(0 if result.clean else 1)
