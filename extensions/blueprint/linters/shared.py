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


class CoversAllRule(TypedDict, total=False):
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    type: Literal["covers_all"]
    target: str
    should_cover_all: str
    severity: str
    category: str
    hint: str
    covered_label: str
    target_label: str


class NotOrphanRule(TypedDict, total=False):
    """Check for isolated items (no *Refs outgoing, no *Refs incoming).

    Auto-discovers all *Refs/*Ref fields — no deps_field needed.
    """
    type: Literal["not_orphan"]
    target: str
    severity: str
    category: str
    target_label: str
    hint: str





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
]


# Mapping from rule type to its TypedDict class
_RULE_TYPE_MAP: dict[str, type] = {
    "non_empty": NonEmptyRule,
    "exists": ExistsRule,
    "is_unique": IsUniqueRule,
    "not_shared": NotSharedRule,
    "has_item_count": HasItemCountRule,
    "contains_patterns": ContainsPatternsRule,
    "covers_all": CoversAllRule,
    "not_orphan": NotOrphanRule,
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
                    f"Duplicate {target_label} ID '{id_str}' (also '{seen[norm]}').",
                    hint=hint or f"Each {target_label} must have a unique ID."
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
                        f"{target_label} '{iid}' has a duplicate {id_key}: '{text}' "
                        f"is identical to one claimed by '{seen[norm]}'.",
                        hint=hint or f"Each {id_key} must be owned by exactly one {target_label.lower()}.",
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
                    f"{target_label} '{iid}': dependency '{dep}' is not defined.",
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
                    f"Circular {target_label.lower()} dependency detected: {cycle_str}.",
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
                    f"{target_label}: '{item}' not found in {ref_label or 'valid set'}.",
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
                            f"{target_label} '{iid}': {refs_key} ref '{ref}' not found.",
                            hint=f"Add '{ref}' to the target spec or correct the reference.")


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
                f"{target_label} '{name}': glossaryRef '{ref}' not found in Glossary.",
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
                    f"{target_label} '{item_id}': no glossaryRefs.",
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
                f"{target_label} '{name}': glossaryRef '{ref}' not found in Glossary.",
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


# ── Path-based rule system ────────────────────────────────────────────────────

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
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")
    for val, pid in zip(resolved.values, resolved.parent_ids):
        if val is None:
            result.add(severity, category,
                f"{target_label} '{pid}': field is missing.",
                hint=hint or "Provide a value.")
        elif isinstance(val, list) and not val:
            result.add(severity, category,
                f"{target_label} '{pid}' has no items.",
                hint=hint or f"Assign items to this {target_label.lower()} or remove it.")
        elif isinstance(val, str) and not val.strip():
            result.add(severity, category,
                f"{target_label} '{pid}' has an empty field.",
                hint=hint or f"Provide a value.")


def handle_exists(resolved: Resolved, valid: set, rule: dict, result: LayerResult) -> None:
    """Check that resolved values exist in the valid set."""
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


def handle_unique(resolved: Resolved, rule: dict, result: LayerResult) -> None:
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


def handle_no_overlap(resolved: Resolved, rule: dict, result: LayerResult) -> None:
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


def handle_item_count(resolved: Resolved, rule: dict, result: LayerResult) -> None:
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


def handle_coverage(resolved_should_cover_all: Resolved, resolved_target: Resolved, rule: dict, result: LayerResult) -> None:
    """Check that target items reference all items in should_cover_all.

    target path includes the ref field: "overview.subsystems.componentRefs"
    """
    severity = rule.get("severity", "warning")
    category = rule.get("category", "uncovered")
    hint_template = rule.get("hint")
    covered_label = rule.get("covered_label", resolved_should_cover_all.parent_label)
    target_label = rule.get("target_label", "source")

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
                f"Add ref '{iid}' to a {target_label} responsible for this.")
            result.add(severity, category,
                f"{covered_label} {iid} ('{desc_short}') is not covered by any {target_label}.",
                hint=hint_text)


def handle_orphans(resolved: Resolved, rule: dict, result: LayerResult) -> None:
    """Warn if items are isolated (no *Refs outgoing, no *Refs incoming).

    Auto-discovers all *Refs fields on items — no deps_field needed.
    """
    severity = rule.get("severity", "warning")
    category = rule.get("category", "isolated")
    target_label = rule.get("target_label", resolved.parent_label)
    hint = rule.get("hint", "")

    items = resolved.values
    if not items:
        return

    # Discover all *Refs fields from the items
    ref_fields = set()
    for item in items:
        if isinstance(item, dict):
            for key in item:
                if key.endswith("Refs") or key.endswith("Ref"):
                    ref_fields.add(key)

    # Collect all IDs referenced by any *Refs field
    referenced_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for field in ref_fields:
            for ref in _normalize_ref(item.get(field)):
                referenced_ids.add(ref)

    for item in items:
        if not isinstance(item, dict):
            continue
        iid = item.get("id", "")
        # Check if this item references anything via any *Refs field
        has_outgoing = any(item.get(f) for f in ref_fields)
        is_referenced = iid in referenced_ids
        if not has_outgoing and not is_referenced:
            result.add(severity, category,
                f"{target_label} '{iid}' is isolated: no dependencies and no dependents.",
                hint=hint or f"An isolated {target_label.lower()} may indicate a design issue.")


# ── Rule handler registry (new) ───────────────────────────────────────────────

@dataclass
class RuleHandler:
    func: callable
    needs_valid: bool = False
    needs_coverage: bool = False
    needs_orphans: bool = False


_RULE_HANDLERS = {
    "non_empty":         RuleHandler(handle_non_empty),
    "exists":            RuleHandler(handle_exists, needs_valid=True),
    "is_unique":         RuleHandler(handle_unique),
    "not_shared":        RuleHandler(handle_no_overlap),
    "has_item_count":    RuleHandler(handle_item_count),
    "contains_patterns": RuleHandler(handle_patterns),
    "covers_all":        RuleHandler(handle_coverage, needs_coverage=True),
    "not_orphan":        RuleHandler(handle_orphans, needs_orphans=True),
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
                    valid_path = rule["inside"]
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
        _run_new_semantic_rules(self.SEMANTIC_RULES, self.spec, self.result, self.extra_specs)
    
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
