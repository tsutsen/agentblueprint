#!/usr/bin/env python3
"""
shared.py — Canonical types, output formatting, and linter infrastructure.

All linters should import from this module. Rule handlers, schemas, and
dispatch live in rules.py.

Usage in a linter:
    from shared import Issue, LayerResult, BaseLinter, print_human
    from rules import SemanticRule, _run_new_semantic_rules
"""

import argparse
import inspect
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from id_patterns import ID_PATTERNS


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


# ── Path-based rule system ────────────────────────────────────────────────────


def _derive_label(segment: str) -> str:
    """Derive a human-readable label from a path segment.

    Handles camelCase and snake_case:  "dataFlow" → "Data Flow",
    "functionalRequirements" → "Functional Requirements".
    """
    label = re.sub(r"([A-Z])", r" \1", segment).title().replace("_", " ").strip()
    return label


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
    label = _derive_label(first_segment)

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


def _apply_strict_mode(result: LayerResult) -> None:
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
        from rules import _run_new_semantic_rules
        _run_new_semantic_rules(self.SEMANTIC_RULES, self.spec, self.result, self.extra_specs)
    
    def _run_misc_checks(self) -> None:
        """Run custom/spec-specific checks."""
        for name, func in self.MISC_CHECKS:
            func(self.spec, self.result, self.extra_specs)

    def _strict_mode(self) -> None:
        """Convert warnings to errors if strict mode."""
        if self.strict:
            _apply_strict_mode(self.result)
    
    @classmethod
    def main(cls):
        """CLI entry point.
        
        Auto-generates --<dep> args from cls.CROSS_SPEC_DEPS.
        """
        parser = argparse.ArgumentParser(description=f"Lint a {cls.SPEC_NAME} JSON.")
        parser.add_argument("input", help=f"Path to {cls.SPEC_NAME} JSON")
        parser.add_argument("--schema", help=f"Path to {cls.SPEC_NAME}.schema.json")
        parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
        parser.add_argument("--json", action="store_true", help="Output as JSON")
        
        # Auto-generate --<dep> args from CROSS_SPEC_DEPS
        for dep in cls.CROSS_SPEC_DEPS:
            parser.add_argument(f"--{dep}",
                                help=f"Path to {dep}spec JSON for cross-spec checks")
        
        args = parser.parse_args()
        
        spec = json.loads(Path(args.input).read_text())
        schema_path = Path(args.schema) if args.schema else None
        
        # Load extra specs from auto-generated args
        extra_specs = {}
        for dep in cls.CROSS_SPEC_DEPS:
            arg_value = getattr(args, dep, None)
            if arg_value:
                extra_specs[dep] = json.loads(Path(arg_value).read_text())
        
        linter = cls(spec, schema_path, args.strict)
        result = linter.run(**extra_specs)
        
        if args.json:
            print_json_output(result)
        else:
            print_human(result, str(args.input))
        
        sys.exit(0 if result.clean else 1)
