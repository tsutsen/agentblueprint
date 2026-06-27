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
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from id_patterns import ID_PATTERNS, SECTION_ID_PATTERNS


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


def validate_sequential(ids: list[str], label: str, result: "LayerResult") -> None:
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

    # Parse path: handle "spec:key" prefix
    first_segment = segments[0]
    extra_spec_name = None
    if ":" in first_segment:
        extra_spec_name, first_segment = first_segment.split(":", 1)

    # Navigate first segment → root list
    root = (extra_specs.get(extra_spec_name) or {}) if extra_spec_name else spec
    items = root.get(first_segment, [])
    if not isinstance(items, list):
        items = [items] if items else []

    label = re.sub(r"([A-Z])", r" \1", first_segment).title().replace("_", " ").strip()

    current_items = items
    parent_ids: list[str] = []
    parent_items: list[dict] = []
    group_sizes: list[int] = []

    # Navigate remaining segments
    for seg_idx in range(1, len(segments)):
        seg = segments[seg_idx]
        if not current_items:
            break

        first_item = current_items[0]
        if isinstance(first_item, str):
            break  # items are already scalars

        if isinstance(first_item, dict) and seg in first_item:
            val = first_item[seg]
            if isinstance(val, list):
                current_items, parent_ids, parent_items, group_sizes = (
                    _flatten_list_segment(current_items, seg, parent_ids, parent_items)
                )
            elif seg_idx + 1 < len(segments) and isinstance(val, dict):
                # Navigate into the dict and continue
                current_items, parent_ids, parent_items, group_sizes = (
                    _navigate_dict_segment(current_items, seg, parent_ids, parent_items)
                )
            else:
                # Terminal scalar — extract and return
                return _extract_scalars(current_items, seg, parent_ids, parent_items, label)

    return _resolve_final(current_items, parent_ids, parent_items, group_sizes, label)


def _get_item_id(item: dict, fallback: str = "?") -> str:
    """Derive identifier from an item dict."""
    if not isinstance(item, dict):
        return fallback
    return item.get("id", item.get("name", fallback))


def _get_parent_context(i: int, item: dict, parent_ids: list[str], parent_items: list[dict]) -> tuple[str, dict]:
    """Resolve parent_id and parent_item for index i.

    Propagates existing parent context, or derives from the item itself.
    """
    if parent_ids and i < len(parent_ids):
        return parent_ids[i], (parent_items[i] if i < len(parent_items) else item)
    return _get_item_id(item, "?"), item


def _flatten_list_segment(
    items: list, seg: str, parent_ids: list[str], parent_items: list[dict]
) -> tuple[list, list[str], list[dict], list[int]]:
    """Flatten a nested list segment (e.g. components.reqRefs).

    Each nested item inherits the parent's id.
    """
    new_items, new_ids, new_parents, new_sizes = [], [], [], []
    for i, item in enumerate(items):
        nested = item.get(seg, [])
        if not isinstance(nested, list):
            continue
        pi = parent_items[i] if i < len(parent_items) else item
        pid = _get_item_id(pi, _get_item_id(item, "?"))
        for nested_item in nested:
            new_items.append(nested_item)
            new_ids.append(pid)
            new_parents.append(pi)
            new_sizes.append(len(nested))
    return new_items, new_ids, new_parents, new_sizes


def _navigate_dict_segment(
    items: list, seg: str, parent_ids: list[str], parent_items: list[dict]
) -> tuple[list, list[str], list[dict], list[int]]:
    """Navigate into a dict segment and continue traversing.

    Preserves existing parent context or derives from current item.
    """
    new_items = [item.get(seg, {}) for item in items]
    new_ids, new_parents, new_sizes = [], [], []
    for i, item in enumerate(items):
        pid, pi = _get_parent_context(i, item, parent_ids, parent_items)
        new_ids.append(pid)
        new_parents.append(pi)
        new_sizes.append(1)
    return new_items, new_ids, new_parents, new_sizes


def _extract_scalars(
    items: list, seg: str, parent_ids: list[str], parent_items: list[dict], label: str
) -> Resolved:
    """Extract scalar values from the terminal segment."""
    values, new_ids, new_parents, new_sizes = [], [], [], []
    for i, item in enumerate(items):
        values.append(item.get(seg) if isinstance(item, dict) else item)
        pid, pi = _get_parent_context(i, item, parent_ids, parent_items)
        new_ids.append(pid)
        new_parents.append(pi)
        new_sizes.append(1)
    return Resolved(values, new_ids, label, new_parents, new_sizes)


def _resolve_final(
    items: list, parent_ids: list[str], parent_items: list[dict],
    group_sizes: list[int], label: str,
) -> Resolved:
    """Finalize after loop — handle empty or unresolved parent_ids."""
    if not items:
        return Resolved([], [], label, [], [])

    first = items[0]
    if isinstance(first, dict):
        if not parent_ids:
            # Single-segment path: use items' own identifiers
            for item in items:
                parent_ids.append(_get_item_id(item, "?"))
                parent_items.append(item)
                group_sizes.append(1)
        elif all(pid == "?" for pid in parent_ids):
            # Dict-nesting where parent has no id (e.g. overview.subsystems)
            for i, item in enumerate(items):
                parent_ids[i] = _get_item_id(item, "?")
                parent_items[i] = item
    elif isinstance(first, str):
        if not parent_ids:
            parent_ids = list(items)
            parent_items = list(items)
            group_sizes = [1] * len(items)

    return Resolved(items, parent_ids, label, parent_items, group_sizes)


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
