#!/usr/bin/env python3
"""
shared.py — Canonical types and output formatting for all linters.

All linters should import from this module instead of defining their own
Issue and LayerResult types. This ensures consistent output across all
linters, which is critical for agents that parse lint results.

Usage in a linter:
    from shared import Issue, LayerResult, print_human, print_json_output, ID_PATTERNS
"""

import json
import re
from dataclasses import dataclass, field


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
    "milestone": {"pattern": r"^M\d+$", "example": "M1", "hint": "Format: M followed by digits (e.g. M1, M12)"},
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


def check_duplicates(ids: list[str], label: str, result: "LayerResult") -> None:
    """Check for duplicate IDs in a list.
    
    Args:
        ids: List of ID strings.
        label: Label for the error message (e.g. "component", "REQ").
        result: LayerResult to append errors to.
    """
    seen = set()
    for id_ in ids:
        if id_ in seen:
            result.add("error", "duplicate_id",
                f"Duplicate {label} id '{id_}'.",
                hint=f"Each {label} must have a unique identifier.")
        seen.add(id_)


def _extract_num(id_str: str) -> int:
    """Extract the numeric part from REQ-001, NFR-002, etc."""
    m = re.search(r"(\d+)$", id_str)
    return int(m.group(1)) if m else -1


def check_sequential(ids: list[str], label: str, result: "LayerResult") -> None:
    """Warn when IDs skip numbers, e.g. REQ-001, REQ-003 (missing REQ-002).
    
    Args:
        ids: List of ID strings.
        label: Label for the warning message (e.g. "REQ", "US").
        result: LayerResult to append warnings to.
    """
    nums = sorted([_extract_num(i) for i in ids])
    for i, n in enumerate(nums):
        expected = i + 1
        if n != expected:
            result.add("warning", "id_gap",
                f"{label} numbering skips from {expected-1:03d} to {n:03d}.",
                hint=f"Consider renumbering to keep {label} IDs sequential.")
            break  # report first gap only


def find_orphans(items: list[dict], id_key: str, deps_key: str, result: "LayerResult",
                   label: str = "", warning: str = "isolated", hint: str = "") -> None:
    """Warn if items are isolated (no dependencies and no dependents).
    
    Args:
        items: List of item dicts.
        id_key: Key in each item that holds the ID.
        deps_key: Key in each item that holds the list of dependencies.
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g. "Component").
        warning: Category for the warning.
        hint: Custom hint message (default: generic).
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
            result.add("warning", warning,
                f"{label or iid} is isolated: no dependencies and no dependents.",
                hint=hint or f"An isolated {label.lower() or 'item'} may indicate a design issue.")


def validate_coverage(covered_items: list[dict], source_items: list[dict],
                      covered_key: str, refs_key: str,
                      result: "LayerResult", covered_label: str,
                      source_label: str = "") -> None:
    """Validate that every item in covered_items is referenced by at least one item in source.
    
    Args:
        covered_items: List of items to check coverage for (e.g., FRs from GoalSpec).
        source_items: List of source items that should reference covered items (e.g., components).
        covered_key: Key in each covered item that holds the ID (e.g., "id").
        refs_key: Key in source items that holds the list of refs (e.g., "reqRefs").
        result: LayerResult to append warnings to.
        covered_label: Label for error messages (e.g., "GoalSpec FR").
        source_label: Label for the source items (e.g., "component").
    """
    if not covered_items or not source_items:
        return
    
    # Collect all IDs from covered items
    covered_ids = {item.get(covered_key, "") for item in covered_items}
    
    # Collect all refs from source items
    covered_refs = set()
    for item in source_items:
        for ref in item.get(refs_key, []):
            covered_refs.add(ref)
    
    # Find uncovered items
    for item in covered_items:
        iid = item.get(covered_key, "")
        desc = item.get("description", "")
        desc_short = desc[:60] + "..." if desc else ""
        
        if iid not in covered_refs:
            result.add("warning", "uncovered",
                f"{covered_label} {iid} ('{desc_short}') is not covered by any {source_label}.",
                hint=f"Add ref '{iid}' to a {source_label or 'source item'} responsible for this.")


def validate_non_empty(items: list[dict], key: str, id_key: str, result: "LayerResult",
                       label: str = "", category: str = "empty", hint: str = "") -> None:
    """Warn if items have an empty list field.
    
    Args:
        items: List of items to check.
        key: Key in each item that holds the list to check (e.g., "componentRefs").
        id_key: Key in each item that holds the ID/name (e.g., "id" or "name").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Subsystem").
        category: Category for the warning (e.g., "empty").
        hint: Custom hint message (default: generic).
    """
    for item in items:
        iid = item.get(id_key, "?")
        refs = item.get(key, [])
        if not refs:
            result.add("warning", category,
                f"{label or iid} '{iid}' has no {key}.",
                hint=hint or f"Assign items to this {label.lower() or 'item'} or remove it.")


def validate_no_overlap(items: list[dict], refs_key: str, id_key: str, result: "LayerResult",
                        label: str = "", category: str = "overlap", hint: str = "") -> None:
    """Warn if an item is assigned to multiple groups.
    
    Args:
        items: List of group items (e.g., subsystems).
        refs_key: Key in each item that holds the list of refs (e.g., "componentRefs").
        id_key: Key in each item that holds the group ID/name (e.g., "name").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Subsystem").
        category: Category for the warning (e.g., "overlap").
        hint: Custom hint message (default: generic).
    """
    item_to_groups: dict[str, list[str]] = {}
    for item in items:
        iid = item.get(id_key, "?")
        for ref in item.get(refs_key, []):
            item_to_groups.setdefault(ref, []).append(iid)
    
    for item, groups in item_to_groups.items():
        if len(groups) > 1:
            result.add("warning", category,
                f"Item '{item}' is assigned to multiple {label.lower() or 'groups'}: {', '.join(groups)}.",
                hint=hint or f"Each {label.lower() or 'item'} should belong to exactly one {label.lower() or 'group'}.")


def validate_exists(items: list[dict], refs: str | list[str], valid: set[str] | dict[str, set[str]],
                  result: "LayerResult", label: str = "", ref_label: str = "",
                  category: str = "missing", hint: str = "") -> None:
    """Validate that items reference values in the valid set(s).
    
    Args:
        items: List of items to check.
        refs: Single ref key (e.g., "dataRef") or list of ref keys (e.g., ["reqRefs", "nfrRefs"]).
        valid: Single valid set (for single ref key) or dict mapping ref keys to valid sets.
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Component").
        ref_label: Label for the reference type (e.g., "DataSpec entity").
        category: Category for the warning (e.g., "missing").
        hint: Custom hint message (default: generic).
    
    Examples:
        # Single ref key
        validate_exists(steps, "dataRef", entity_names, result, "Flow step", "DataSpec entity")
        
        # Multiple ref keys
        validate_exists(components, ["reqRefs", "nfrRefs"], {"reqRefs": req_ids, "nfrRefs": nfr_ids}, result, "Component")
    """
    # Normalize to list of refs and dict of valid sets
    if isinstance(refs, str):
        refs = [refs]
        if isinstance(valid, set):
            valid = {refs[0]: valid}
    
    for item in items:
        iid = item.get("id", "?")
        for refs_key in refs:
            for ref in item.get(refs_key, []):
                if ref not in valid.get(refs_key, set()):
                    result.add("error", category,
                        f"{label} '{iid}': {refs_key} ref '{ref}' not found.",
                        hint=f"Add '{ref}' to the target spec or correct the reference.")


def validate_item_count(items: list[dict], key: str, count: int, compare_mode: int,
                        id_key: str, result: "LayerResult", label: str = "",
                        category: str = "count", hint: str = "") -> None:
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
    """
    for item in items:
        iid = item.get(id_key, "?")
        refs = item.get(key, [])
        n = len(refs)
        
        if compare_mode == 1 and n > count:
            result.add("warning", category,
                f"{label} '{iid}' has {n} {key} — consider splitting.",
                hint=hint or f"A {label.lower()} with >{count} {key} may be too complex. Consider splitting.")
        elif compare_mode == 0 and n == count:
            result.add("warning", category,
                f"{label} '{iid}' has exactly {n} {key}.",
                hint=hint or f"A {label.lower()} should not have exactly {count} {key}.")
        elif compare_mode == -1 and n < count:
            result.add("warning", category,
                f"{label} '{iid}' has {n} {key} (minimum {count}).",
                hint=hint or f"A {label.lower()} should have at least {count} {key}.")
    # Normalize to list of refs and dict of valid sets
    if isinstance(refs, str):
        refs = [refs]
        if isinstance(valid, set):
            valid = {refs[0]: valid}
    
    for item in items:
        iid = item.get("id", "?")
        for refs_key in refs:
            for ref in item.get(refs_key, []):
                if ref not in valid.get(refs_key, set()):
                    result.add("error", category,
                        f"{label} '{iid}': {refs_key} ref '{ref}' not found.",
                        hint=f"Add '{ref}' to the target spec or correct the reference.")


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


# Backwards compatibility alias
ID_FORMATS = ID_PATTERNS


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
