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


def _extract_num(id_str: str) -> int:
    """Extract the numeric part from REQ-001, NFR-002, etc."""
    m = re.search(r"(\d+)$", id_str)
    return int(m.group(1)) if m else -1


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
                text = nested_item if isinstance(nested_item, str) else nested_item.get("text", "")
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
        ref_value = item.get(refs_key)
        # Handle both string and list refs
        if isinstance(ref_value, str):
            ref_value = [ref_value]
        elif ref_value is None:
            ref_value = []
        for ref in ref_value:
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


def validate_exists(items: list, refs: str | list[str] = None, valid: set[str] | dict[str, set[str]] = None,
                  result: "LayerResult" = None, label: str = "", ref_label: str = "",
                  category: str = "missing", hint: str = "") -> None:
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
                result.add("error", category,
                    f"{label}: '{item}' not found in {ref_label or 'valid set'}.",
                    hint=f"Add '{item}' to {ref_label or 'the target'} or correct the reference.")
    elif isinstance(first, dict):
        # List of dicts with ref keys
        if isinstance(refs, str):
            refs = [refs]
            if isinstance(valid, set):
                valid = {refs[0]: valid}
        
        for item in items:
            iid = item.get("id", "?")
            for refs_key in refs:
                ref_value = item.get(refs_key)
                # Handle both string and list refs
                if isinstance(ref_value, str):
                    ref_value = [ref_value]
                elif ref_value is None:
                    ref_value = []
                for ref in ref_value:
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


def validate_non_empty(items: list[dict], key: str, id_key: str, result: "LayerResult",
                       label: str = "", category: str = "empty", hint: str = "") -> None:
    """Warn if items have an empty list or string field.
    
    Args:
        items: List of items to check.
        key: Key in each item that holds the field to check (e.g., "componentRefs" or "dataRef").
        id_key: Key in each item that holds the ID/name (e.g., "id" or "name").
        result: LayerResult to append warnings to.
        label: Label for error messages (e.g., "Subsystem" or "Flow step").
        category: Category for the warning (e.g., "empty" or "empty_field").
        hint: Custom hint message (default: generic).
    """
    for item in items:
        iid = item.get(id_key, "?")
        field = item.get(key)
        
        if field is None:
            result.add("warning", category,
                f"{label or iid} '{iid}': {key} is missing.",
                hint=hint or f"Provide a value for {key}.")
        elif isinstance(field, list) and not field:
            result.add("warning", category,
                f"{label or iid} '{iid}' has no {key}.",
                hint=hint or f"Assign items to this {label.lower() or 'item'} or remove it.")
        elif isinstance(field, str) and not field.strip():
            result.add("warning", category,
                f"{label or iid} '{iid}' has an empty {key}.",
                hint=hint or f"Provide a value for {key}.")


def find_patterns(items: list[dict], text_key: str = None, patterns: list[tuple[str, str]] = None,
                  id_key: str = "id", result: "LayerResult" = None, label: str = "",
                  category: str = "pattern_match", hint: str = "",
                  match_fn: callable = None, nested_key: str = None, max_count: int = None,
                  text_keys: list[str] = None) -> None:
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
            texts = [n if isinstance(n, str) else n.get("text", "") for n in nested_items]
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
                
                result.add("warning", category, msg, hint=hint or f"Review {label.lower() or 'item'} for {category}.")


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
    
    # Valid from another section in the same spec
    if "valid_section" in rule:
        items = _get_nested(spec, rule["valid_section"])
        key = rule.get("valid_key", "id")
        return {item.get(key, "") for item in items}
    
    # Valid from an extra spec (e.g., goal, data, api)
    if "valid_extra_spec" in rule:
        extra = extra_specs.get(rule["valid_extra_spec"])
        if extra:
            items = _get_nested(extra, rule.get("valid_section", ""))
            key = rule.get("valid_key", "id")
            return {item.get(key, "") for item in items}
    
    return set()


def _run_semantic_rules(rules: list, spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Execute declarative semantic rules against a spec.
    
    Args:
        rules: List of rule dicts. Each rule has a "type" and optional fields:
        spec: The spec being linted.
        result: LayerResult to append findings to.
        extra_specs: Extra specs passed to the linter (goal, data, api, etc.).
    
    Rule Types:
        non_empty: Check that a field is not empty.
            Required: section, key
            Optional: id_key, label, category, hint
            Example: {"type": "non_empty", "section": "components", "key": "reqRefs"}
        
        exists: Check that refs in items exist in a valid set.
            Required: section, key, valid_section (or valid_extra_spec + valid_section)
            Optional: nested_key, valid_key, label, ref_label, category, hint
            Example: {"type": "exists", "section": "components", "key": "reqRefs",
                      "valid_extra_spec": "goal", "valid_section": "functionalRequirements"}
        
        no_overlap: Check that items don't overlap across groups.
            Required: section, refs_key, id_key
            Optional: label, category, hint
            Example: {"type": "no_overlap", "section": "subsystems", "refs_key": "componentRefs"}
        
        item_count: Check that a list field has a specific count.
            Required: section, key, count, compare_mode, id_key
            Optional: label, category, hint
            compare_mode: 1=warn if >count, -1=warn if <count, 0=warn if ==count
            Example: {"type": "item_count", "section": "components", "key": "responsibilities",
                      "count": 8, "compare_mode": 1}
        
        patterns: Check that text matches regex patterns.
            Required: section, patterns
            Optional: text_key, nested_key, max_count, label, category, hint, match_fn
            patterns: list of strings or (pattern, label) tuples
            Example: {"type": "patterns", "section": "constraints", "text_key": "description",
                      "patterns": ["postgres", "mysql"]}
        
        coverage: Check that covered items are referenced by source items.
            Required: covered_section, source_section, covered_key, refs_key
            Optional: covered_label, source_label
            Example: {"type": "coverage", "covered_section": "components",
                      "source_section": "subsystems", "refs_key": "componentRefs"}
        
        orphans: Check that items have dependencies or dependents.
            Required: section
            Optional: id_key, deps_key, label, warning, hint
            Example: {"type": "orphans", "section": "components", "deps_key": "dependencies"}
    """
    for rule in rules:
        # Some rules (like coverage) don't have a single "section" key
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
                # Nested items (e.g., steps within flows)
                nested_items = []
                for item in items:
                    for nested in item.get(rule["nested_key"], []):
                        if isinstance(nested, dict):
                            nested_items.append(nested)
                        else:
                            nested_items.append({"id": nested})
                items = nested_items
                key = rule.get("id_key", "id")  # Use id_key for nested items
            
            validate_non_empty(
                items,
                key,
                rule.get("id_key", "id"),
                result,
                **{k: v for k, v in rule.items() if k in ("label", "category", "hint")}
            )
        
        elif rule_type == "exists":
            key = rule.get("key")
            if rule.get("nested_key"):
                # Nested items (e.g., steps within flows)
                nested_items = []
                for item in items:
                    for nested in item.get(rule["nested_key"], []):
                        if isinstance(nested, dict):
                            nested_items.append(nested)
                        else:
                            nested_items.append({"id": nested})
                items = nested_items
            
            valid = _resolve_valid_section(rule, spec, extra_specs)
            validate_exists(
                items,
                key,
                valid,
                result,
                **{k: v for k, v in rule.items() if k in ("label", "ref_label", "category", "hint")}
            )
        
        elif rule_type == "no_overlap":
            validate_no_overlap(
                items,
                rule["refs_key"],
                rule.get("id_key", "id"),
                result,
                **{k: v for k, v in rule.items() if k in ("label", "category", "hint")}
            )
        
        elif rule_type == "item_count":
            validate_item_count(
                items,
                rule["key"],
                rule["count"],
                rule.get("compare_mode", 1),
                rule.get("id_key", "id"),
                result,
                **{k: v for k, v in rule.items() if k in ("label", "category", "hint")}
            )
        
        elif rule_type == "patterns":
            find_patterns(
                items,
                text_key=rule.get("text_key"),
                patterns=rule.get("patterns", []),
                result=result,
                id_key=rule.get("id_key", "id"),
                label=rule.get("label", ""),
                category=rule.get("category", "pattern_match"),
                hint=rule.get("hint", ""),
                match_fn=rule.get("match_fn"),
                nested_key=rule.get("nested_key"),
                max_count=rule.get("max_count"),
                text_keys=rule.get("text_keys"),
            )
        
        elif rule_type == "coverage":
            # Cross-section coverage: covered items must be referenced by source items
            covered = _get_nested(spec, rule.get("covered_section", rule.get("section", "")))
            
            # If covered_section is in an extra spec, load it
            if rule.get("valid_extra_spec") and not covered:
                extra = extra_specs.get(rule["valid_extra_spec"])
                if extra:
                    covered = _get_nested(extra, rule["covered_section"])
            
            source_items = _get_nested(spec, rule["source_section"])
            validate_coverage(
                covered,
                source_items,
                rule.get("covered_key", "id"),
                rule["refs_key"],
                result,
                rule.get("covered_label", ""),
                rule.get("source_label", ""),
            )
        
        elif rule_type == "orphans":
            find_orphans(
                items,
                rule.get("id_key", "id"),
                rule.get("deps_key", "dependencies"),
                result,
                rule.get("label", ""),
                rule.get("warning", "isolated"),
                rule.get("hint", ""),
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
            validate_sequential(ids, id_type.upper(), result)


def _strict_mode(result: LayerResult) -> None:
    """Convert all warnings to errors."""
    for w in result.warnings:
        w.severity = "error"
        result.errors.append(w)
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
        from schema_validator import SchemaValidator
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
