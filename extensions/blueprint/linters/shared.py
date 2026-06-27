#!/usr/bin/env python3
"""
shared.py — Canonical types, output formatting, and linter infrastructure.

All linters should import from this module.

Module layout:
    check.py   — CheckDef abstract base + shared check functions
    rules.py   — Rule schemas, handlers, registry, dispatch (imports from check)
    gates.py   — Gate schemas, handlers, registry, dispatch (imports from check)
    shared.py  — Types, resolve_path, BaseLinter, completeness, output formatting

Usage in a linter:
    from shared import Issue, LayerResult, BaseLinter, print_human
    from rules import SemanticRule, _run_new_semantic_rules
    from gates import GateDef, run_gates  # for per-spec completeness
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
    return (
        False,
        f"ID '{id_value}' does not follow {ID_PATTERNS[id_type]['hint'].lower()}",
    )


def _validate_ids(
    items: list[dict], id_key: str, id_type: str, category: str, result: "LayerResult"
) -> None:
    """Validate IDs for a list of items (private - use validate_spec_ids)."""
    for item in items:
        iid = item.get(id_key, "")
        valid, msg = _validate_id(iid, id_type)
        if not valid:
            pattern = ID_PATTERNS[id_type]
            hint_text = pattern["hint"].replace("Format: ", "").lower()
            example = pattern["example"]
            result.add(
                "error",
                category,
                msg,
                hint=f"Use format {hint_text} (e.g. '{example}').",
            )


def validate_spec_ids(items_by_type: dict[str, list], result: "LayerResult") -> None:
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
            result.add(
                "warning",
                "id_gap",
                f"{label} numbering skips from {expected - 1:03d} to {n:03d}.",
                hint=f"Consider renumbering to keep {label} IDs sequential.",
            )
            break  # report first gap only


def validate_project_and_version(
    spec: dict, spec_name: str, goal: dict, result: "LayerResult"
) -> None:
    """Check project match and version pinning against GoalSpec.

    Args:
        spec: The spec to check.
        spec_name: Name for error messages (e.g. "archspec", "designspec").
        goal: The GoalSpec dict.
        result: LayerResult to append errors to.
    """
    if spec.get("project") != goal.get("project"):
        result.add(
            "error",
            "project_match",
            f"Project mismatch: {spec_name}='{spec.get('project')}' goalspec='{goal.get('project')}'.",
            hint=f"Both specs must have identical 'project' values.",
        )
    pinned = spec.get("goalSpecVersion")
    if pinned and pinned != goal.get("version"):
        result.add(
            "error",
            "version_drift",
            f"{spec_name}.goalSpecVersion='{pinned}' does not match goalspec.version='{goal.get('version')}'.",
            hint=f"Update goalSpecVersion after reviewing {spec_name} against the updated GoalSpec.",
        )


# ── Canonical types ───────────────────────────────────────────────────────────


@dataclass
class Issue:
    """A single lint finding."""

    severity: str  # "error" | "warning" | "info"
    category: str  # e.g. "schema", "duplicate_id", "cross-ref"
    message: str  # Human-readable description of the issue
    hint: str = ""  # Optional suggestion for how to fix


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
    print(f"\n{'─' * 60}")
    if path:
        print(f"  {result.name} Lint Report — {path}")
    else:
        print(f"  {result.name} Lint Report")
    print(f"{'─' * 60}")

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
        "errors": [
            {"category": e.category, "message": e.message, "hint": e.hint}
            for e in result.errors
        ],
        "warnings": [
            {"category": w.category, "message": w.message, "hint": w.hint}
            for w in result.warnings
        ],
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

    # Navigate remaining segments (segments[1:])
    return _traverse_segments(
        segments[1:],
        items,
        label,
        parent_ids=[],
        parent_items=[],
        group_sizes=[],
    )


def _traverse_segments(
    segments: list[str],
    items: list,
    label: str,
    parent_ids: list[str],
    parent_items: list[dict],
    group_sizes: list[int],
) -> Resolved:
    """Walk remaining path segments, flattening lists and navigating dicts.

    Returns early via _extract_scalars on terminal segments.
    Falls through to _resolve_final when loop completes.
    """
    current_items = items
    for seg_idx, seg in enumerate(segments):
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
                current_items, parent_ids, parent_items, group_sizes = (
                    _navigate_dict_segment(current_items, seg, parent_ids, parent_items)
                )
            else:
                return _extract_scalars(
                    current_items, seg, parent_ids, parent_items, label
                )

    return _resolve_final(current_items, parent_ids, parent_items, group_sizes, label)


def _get_item_id(item: dict, fallback: str = "?") -> str:
    """Derive identifier from an item dict."""
    if not isinstance(item, dict):
        return fallback
    return item.get("id", item.get("name", fallback))


def _get_parent_context(
    i: int, item: dict, parent_ids: list[str], parent_items: list[dict]
) -> tuple[str, dict]:
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
    items: list,
    parent_ids: list[str],
    parent_items: list[dict],
    group_sizes: list[int],
    label: str,
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


# ── Strict mode ───────────────────────────────────────────────────────────────

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

        _run_new_semantic_rules(
            self.SEMANTIC_RULES, self.spec, self.result, self.extra_specs
        )

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
        parser = argparse.ArgumentParser(description=f"Lint {cls.SPEC_NAME} JSON.")
        parser.add_argument("input", help=f"Path to {cls.SPEC_NAME} JSON")
        parser.add_argument("--schema", help=f"Path to {cls.SPEC_NAME}.schema.json")
        parser.add_argument(
            "--strict", action="store_true", help="Treat warnings as errors"
        )
        parser.add_argument("--json", action="store_true", help="Output as JSON")

        # Auto-generate --<dep> args from CROSS_SPEC_DEPS
        for dep in cls.CROSS_SPEC_DEPS:
            parser.add_argument(
                f"--{dep}", help=f"Path to {dep}spec JSON for cross-spec checks"
            )

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


# ── Completeness gates ──────────────────────────────────────────────────────

@dataclass
class CompletenessGate:
    """A single readiness condition for a spec."""
    description: str
    passed: bool
    required_at: str   # "draft" | "review" | "confirmed"
    detail: str = ""


@dataclass
class CompletenessScore:
    spec: str
    status: str           # the spec's own lifecycle status
    gates: list[CompletenessGate] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.gates)

    @property
    def passed(self) -> int:
        return sum(1 for g in self.gates if g.passed)

    @property
    def score_pct(self) -> int:
        return int(100 * self.passed / self.total) if self.total else 0

    @property
    def ready_for_review(self) -> bool:
        return all(g.passed for g in self.gates if g.required_at in ("draft", "review"))

    @property
    def ready_for_confirm(self) -> bool:
        return all(g.passed for g in self.gates)

    @property
    def blocking_gates(self) -> list[CompletenessGate]:
        """Gates that must pass for the current status but haven't."""
        status_order = {"draft": 0, "review": 1, "confirmed": 2}
        current = status_order.get(self.status, 0)
        return [
            g for g in self.gates
            if not g.passed and status_order.get(g.required_at, 0) <= current
        ]


def gate(desc: str, passed: bool, required_at: str, detail: str = "") -> CompletenessGate:
    return CompletenessGate(description=desc, passed=passed,
                             required_at=required_at, detail=detail)


# ── Assessment functions ──────────────────────────────────────────────────────

def assess_goalspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft")
    frs = spec.get("functionalRequirements", [])
    nfrs = spec.get("nonFunctionalRequirements", [])
    stories = spec.get("userStories", [])
    criteria = spec.get("successCriteria", [])
    non_goals = spec.get("nonGoals", [])

    fr_ids = {fr["id"] for fr in frs}
    story_refs = {ref for us in stories for ref in us.get("reqRefs", [])}
    sc_refs = {ref for sc in criteria for ref in sc.get("refs", {}).get("reqRefs", [])}

    tbd_nfrs = [n for n in nfrs if
                str(n.get("scale", "")).upper().startswith("TBD") or
                str(n.get("meter", "")).upper().startswith("TBD")]

    gates = [
        gate("Has project objective", bool(spec.get("objective", {}).get("statement")), "draft"),
        gate("Has at least one functional requirement", len(frs) >= 1, "draft"),
        gate("Has at least one user story", len(stories) >= 1, "draft"),
        gate("Has at least one success criterion", len(criteria) >= 1, "draft"),
        gate("Has at least one non-goal", len(non_goals) >= 1, "draft"),
        gate("All FRs covered by at least one story", fr_ids <= story_refs, "review",
             detail=f"Uncovered: {fr_ids - story_refs}" if not fr_ids <= story_refs else ""),
        gate("All FRs gated by at least one success criterion", fr_ids <= sc_refs, "review",
             detail=f"Uncovered: {fr_ids - sc_refs}" if not fr_ids <= sc_refs else ""),
        gate("All NFRs have Scale and Meter defined (no TBD)", len(tbd_nfrs) == 0, "review",
             detail=f"TBD NFRs: {[n['id'] for n in tbd_nfrs]}" if tbd_nfrs else ""),
        gate("Objective re-confirmed after completion",
             spec.get("objective", {}).get("confirmedAfterCompletion", False), "confirmed"),
        gate("Status is confirmed", status == "confirmed", "confirmed"),
    ]
    return CompletenessScore(spec="goalspec", status=status, gates=gates)


def assess_glossary(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft") if "status" in spec else "draft"
    terms = spec.get("terms", [])
    gates = [
        gate("Has at least 3 terms", len(terms) >= 3, "draft"),
        gate("All terms have definitions >= 10 chars",
             all(len(t.get("definition", "")) >= 10 for t in terms), "draft"),
        gate("Has at least 5 terms", len(terms) >= 5, "review"),
        gate("All terms have examples or related terms",
             all(t.get("examples") or t.get("relatedTerms") for t in terms), "confirmed"),
    ]
    return CompletenessScore(spec="glossary", status=status, gates=gates)


def assess_designspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft")
    screens = spec.get("screenInventory", [])
    screen_ids = {s["id"] for s in screens}
    spec_refs = {s["screenRef"] for s in spec.get("screenSpecs", [])}
    journeys = spec.get("userJourneys", [])
    uxac = spec.get("uxAcceptanceCriteria", [])
    patterns = spec.get("interactionPatterns", [])

    unspecced = screen_ids - spec_refs

    gates = [
        gate("Has design goals", len(spec.get("designGoals", [])) >= 1, "draft"),
        gate("Has at least one persona", len(spec.get("personas", [])) >= 1, "draft"),
        gate("Has at least one user journey", len(journeys) >= 1, "draft"),
        gate("Has screen inventory", len(screens) >= 1, "draft"),
        gate("All screens have specs",
             len(unspecced) == 0, "review",
             detail=f"Missing specs: {unspecced}" if unspecced else ""),
        gate("Has interaction patterns", len(patterns) >= 1, "review"),
        gate("Has UX acceptance criteria", len(uxac) >= 1, "review"),
        gate("Has visual design requirements",
             len(spec.get("visualDesignRequirements", [])) >= 1, "review"),
        gate("Has accessibility requirements",
             len(spec.get("accessibilityRequirements", [])) >= 1, "review"),
        gate("Has design system components",
             len(spec.get("designSystem", {}).get("components", [])) >= 1, "confirmed"),
        gate("All journeys reference user stories",
             all(len(j.get("usRefs", [])) >= 1 for j in journeys), "confirmed"),
    ]
    return CompletenessScore(spec="designspec", status=status, gates=gates)


def assess_archspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft")
    components = spec.get("components", [])
    flows = spec.get("dataFlow", [])
    constraints = spec.get("constraints", [])

    comps_with_reqs = [c for c in components if c.get("reqRefs")]
    comps_with_deps_or_dependents = set()
    for c in components:
        for dep in c.get("dependencies", []):
            comps_with_deps_or_dependents.add(c["id"])
            comps_with_deps_or_dependents.add(dep)

    gates = [
        gate("Has system overview summary",
             len(spec.get("overview", {}).get("summary", "")) >= 30, "draft"),
        gate("Has at least one subsystem",
             len(spec.get("overview", {}).get("subsystems", [])) >= 1, "draft"),
        gate("Has at least 2 components", len(components) >= 2, "draft"),
        gate("Has at least one data flow", len(flows) >= 1, "draft"),
        gate("Has at least one constraint", len(constraints) >= 1, "draft"),
        gate("All components have REQ refs",
             len(comps_with_reqs) == len(components), "review",
             detail=f"{len(components) - len(comps_with_reqs)} component(s) missing reqRefs"),
        gate("All components participate in at least one dependency",
             len(comps_with_deps_or_dependents) == len(components), "review",
             detail="Isolated components found" if len(comps_with_deps_or_dependents) < len(components) else ""),
        gate("goalSpecVersion is set", bool(spec.get("goalSpecVersion")), "review"),
        gate("dataSpecVersion is set", bool(spec.get("dataSpecVersion")), "confirmed"),
        gate("apiSpecVersion is set", bool(spec.get("apiSpecVersion")), "confirmed"),
    ]
    return CompletenessScore(spec="archspec", status=status, gates=gates)


def assess_dataspec(spec: dict) -> CompletenessScore:
    status = spec.get("status", "draft") if "status" in spec else "draft"
    entities = spec.get("entities", [])
    relationships = spec.get("relationships", [])
    enums = spec.get("enums", [])

    entities_with_desc = [e for e in entities if e.get("description")]
    entities_with_examples = [
        e for e in entities
        if any(f.get("example") for f in e.get("fields", []))
    ]
    rel_participants = set()
    for r in relationships:
        rel_participants.add(r.get("from"))
        rel_participants.add(r.get("to"))
    entity_names = {e["name"] for e in entities}
    orphans = entity_names - rel_participants

    # Find entities only referenced as field types, never in relationships
    type_referenced = set()
    for entity in entities:
        for field_def in entity.get("fields", []):
            base = field_def.get("type", "").replace("[]", "")
            if base in entity_names and base != entity["name"]:
                type_referenced.add(base)
    standalone = type_referenced - rel_participants

    # Orphan percentage
    orphan_pct = (len(orphans) / len(entities) * 100) if entities else 0

    gates = [
        gate("Has at least one entity", len(entities) >= 1, "draft"),
        gate("Has at least one relationship", len(relationships) >= 1, "draft"),
        gate("All entities have descriptions",
             len(entities_with_desc) == len(entities), "review",
             detail=f"{len(entities)-len(entities_with_desc)} entity/entities missing descriptions"),
        gate("No orphan entities",
             len(orphans) == 0 or len(entities) <= 1, "review",
             detail=f"Orphans: {orphans}" if orphans and len(entities) > 1 else ""),
        gate("Orphan entities < 20%",
             orphan_pct < 20, "review",
             detail=f"{orphan_pct:.0f}% of entities are orphans ({len(orphans)}/{len(entities)})"),
        gate("All entities have at least one field with an example",
             len(entities_with_examples) == len(entities), "confirmed",
             detail=f"{len(entities)-len(entities_with_examples)} entity/entities missing field examples"),
        gate("No standalone type-only entities",
             len(standalone) == 0 or len(standalone) <= 2, "review",
             detail=f"Standalone type-only entities: {standalone}" if standalone else ""),
        gate("Has enums if domain uses categorical values",
             True, "draft",   # advisory — can't auto-detect need for enums
             detail="Review whether domain categorical values should be enums"),
    ]
    return CompletenessScore(spec="dataspec", status=status, gates=gates)


def assess_apispec(spec: dict, data: Optional[dict] = None) -> CompletenessScore:
    status = spec.get("status", "draft") if "status" in spec else "draft"
    functions = spec.get("functions", [])

    fns_with_desc = [f for f in functions if f.get("description")]
    fns_with_errors = [f for f in functions if f.get("errors")]
    fns_with_entity = [f for f in functions if f.get("entity")]
    fns_pure_declared = [f for f in functions if "pure" in f]

    gates = [
        gate("Has at least one function", len(functions) >= 1, "draft"),
        gate("All functions have descriptions",
             len(fns_with_desc) == len(functions), "review",
             detail=f"{len(functions)-len(fns_with_desc)} function(s) missing descriptions"),
        gate("All functions have documented error conditions",
             len(fns_with_errors) == len(functions), "review",
             detail=f"{len(functions)-len(fns_with_errors)} function(s) with no errors documented"),
        gate("All functions declare entity affinity",
             len(fns_with_entity) == len(functions), "review",
             detail=f"{len(functions)-len(fns_with_entity)} function(s) missing entity field"),
        gate("All functions declare pure/impure",
             len(fns_pure_declared) == len(functions), "confirmed",
             detail=f"{len(functions)-len(fns_pure_declared)} function(s) missing 'pure' field"),
        gate("dataSpecVersion is set", bool(spec.get("dataSpecVersion")), "review"),
    ]
    return CompletenessScore(spec="apispec", status=status, gates=gates)


def assess_testspec(spec: dict, api: Optional[dict] = None) -> CompletenessScore:
    status = spec.get("status", "draft")
    tests = spec.get("tests", [])
    coverage = spec.get("functionCoverage", [])

    fn_ids = {fn["id"] for fn in api.get("functions", [])} if api else set()
    tested_fns = {t["fnRef"] for t in tests if t.get("fnRef")}
    error_tests = [t for t in tests if t.get("category") == "error-path"]
    coverage_fns = {c["fnRef"] for c in coverage}

    all_out_of_scope = all(c.get("outOfScope") for c in coverage)
    verification = spec.get("verificationStatus", "pending")

    gates = [
        gate("Has at least one test", len(tests) >= 1, "draft"),
        gate("Has functionCoverage summary", len(coverage) >= 1, "draft"),
        gate("Has error-path tests", len(error_tests) >= 1, "review"),
        gate("All ApiSpec functions have tests",
             fn_ids <= tested_fns, "review",
             detail=f"Untested: {fn_ids - tested_fns}" if api and not fn_ids <= tested_fns else ""),
        gate("All functions have out-of-scope declarations",
             all_out_of_scope, "review",
             detail="Some functionCoverage entries missing outOfScope" if not all_out_of_scope else ""),
        gate("functionCoverage covers all tested functions",
             tested_fns <= coverage_fns, "review",
             detail=f"Missing: {tested_fns - coverage_fns}" if not tested_fns <= coverage_fns else ""),
        gate("apiSpecVersion is set", bool(spec.get("apiSpecVersion")), "review"),
        gate("Independent verification completed",
             verification == "passed", "confirmed",
             detail=f"verificationStatus is '{verification}'" if verification != "passed" else ""),
    ]
    return CompletenessScore(spec="testspec", status=status, gates=gates)


def assess_taskplan(plan: dict, goal_spec: Optional[dict] = None,
                    design_spec: Optional[dict] = None,
                    arch_spec: Optional[dict] = None) -> CompletenessScore:
    """Completeness gates for TaskPlan.

    Validates that epics cover requirements from GoalSpec, capabilities from
    DesignSpec, and components from ArchitectureSpec.
    """
    epics = plan.get("epics", [])
    milestones = plan.get("milestones", [])

    # Collect all epic text for matching
    epic_texts = []
    for epic in epics:
        text = ' '.join([
            epic.get("title", ""),
            epic.get("summary", ""),
            epic.get("objective", ""),
            " ".join(epic.get("scope", {}).get("inScope", [])),
        ]).lower()
        epic_texts.append(text)

    gates = [
        # Draft: basic structure
        gate("Has at least one milestone", len(milestones) >= 1, "draft"),
        gate("Has at least one epic", len(epics) >= 1, "draft"),
        gate("Every epic covers at least one requirement", all(
            epic.get("requirements") for epic in epics
        ), "draft"),
        gate("All epics assigned to a milestone", all(
            epic.get("milestone") for epic in epics
        ), "draft"),

        # Review: quality and completeness
        gate("All epics have acceptance criteria", all(
            epic.get("acceptanceCriteria") for epic in epics
        ), "review"),
        gate("All epics have scope (inScope + outOfScope)", all(
            epic.get("scope", {}).get("inScope") and epic.get("scope", {}).get("outOfScope")
            for epic in epics
        ), "review"),
        gate("All epics have explicit dependencies", all(
            epic.get("dependencies", {}).get("blockedBy") is not None or
            epic.get("dependencies", {}).get("blocks") is not None
            for epic in epics
        ), "review"),
        gate("Epics are in dependency order", True, "review",
             detail="Dependency order validated by lint_taskplan.py"),
        gate("No circular dependencies", True, "review",
             detail="Circular dependency check validated by lint_taskplan.py"),
        gate("All milestones have demonstrable outcomes", all(
            m.get("outcome") and len(m.get("outcome", "")) >= 10
            for m in milestones
        ), "review"),
        gate("All epics have an objective", all(
            epic.get("objective") for epic in epics
        ), "review"),
        gate("All acceptance criteria are meaningful length", all(
            all(len(ac.strip()) >= 15 for ac in epic.get("acceptanceCriteria", []))
            for epic in epics
        ), "review"),
        gate("All scope items are meaningful length", all(
            all(len(item.strip()) >= 10 for item in epic.get("scope", {}).get("inScope", []))
            and all(len(item.strip()) >= 10 for item in epic.get("scope", {}).get("outOfScope", []))
            for epic in epics
        ), "review"),

        # Cross-spec: GoalSpec coverage
        gate("All GoalSpec requirements covered by epics", True, "review",
             detail="Requirement coverage validated by lint_taskplan.py"),
    ]

    # Cross-spec: DesignSpec capability coverage
    if design_spec:
        capabilities = design_spec.get("capabilities", [])
        if capabilities:
            uncovered = []
            for cap in capabilities:
                cap_name = cap.get("name", "").lower()
                if not cap_name:
                    continue
                if not any(cap_name in text for text in epic_texts):
                    uncovered.append(cap.get("name"))
            gates.append(gate(
                "All DesignSpec capabilities covered by epics",
                len(uncovered) == 0, "review",
                detail=f"Uncovered: {', '.join(uncovered)}" if uncovered else ""
            ))

    # Cross-spec: ArchitectureSpec component coverage
    if arch_spec:
        components = arch_spec.get("components", [])
        if components:
            uncovered = []
            for comp in components:
                comp_name = comp.get("name", "").lower()
                if not comp_name:
                    continue
                if not any(comp_name in text for text in epic_texts):
                    uncovered.append(comp.get("name"))
            gates.append(gate(
                "All ArchitectureSpec components covered by epics",
                len(uncovered) == 0, "review",
                detail=f"Uncovered: {', '.join(uncovered)}" if uncovered else ""
            ))

    if goal_spec:
        gates.append(gate("No epic implements a non-goal", True, "review",
                          detail="Non-goal compliance validated by lint_taskplan.py"))

    status = plan.get("status", "draft")
    return CompletenessScore(spec="taskplan", status=status, gates=gates)


def assess_glossary_full(spec: dict) -> CompletenessScore:
    terms = spec.get("terms", [])
    categories = {t.get("category") for t in terms if t.get("category")}
    has_domain = "domain" in categories

    base = assess_glossary(spec)
    base.gates.append(
        gate("Has domain-category terms", has_domain, "review",
             detail="No terms tagged 'domain' — consider categorising terms")
    )
    return base


# ── Assessor registry ─────────────────────────────────────────────────────────

# Registry: spec_name → assess_fn(spec, loaded)
# "loaded" is a dict of all previously-loaded specs by key name.
# Most assessors ignore loaded; apispec/testspec/plan extract what they need.
_ASSESSORS: dict[str, callable] = {
    "goalspec":    lambda s, _: assess_goalspec(s),
    "glossary":    lambda s, _: assess_glossary_full(s),
    "designspec":  lambda s, _: assess_designspec(s),
    "archspec":    lambda s, _: assess_archspec(s),
    "dataspec":    lambda s, _: assess_dataspec(s),
    "apispec":     lambda s, l: assess_apispec(s, l.get("data")),
    "testspec":    lambda s, l: assess_testspec(s, l.get("api")),
    "plan":        lambda s, l: assess_taskplan(s, l.get("goal"), l.get("design"), l.get("arch")),
}


def assess(spec_name: str, spec: dict, loaded: dict) -> CompletenessScore:
    """Dispatch to the assessor for the given spec name.

    Args:
        spec_name: e.g. "goalspec", "apispec", "plan"
        spec: the spec dict to assess
        loaded: dict of all previously-loaded specs by key name
    """
    fn = _ASSESSORS.get(spec_name)
    if fn is None:
        raise ValueError(f"No assessor for spec '{spec_name}'")
    return fn(spec, loaded)


def suite_completeness_pct(scores: list[CompletenessScore]) -> int:
    """Compute overall suite completeness as average of individual scores."""
    if not scores:
        return 0
    return sum(s.score_pct for s in scores) // len(scores)


SPEC_ORDER = ["goalspec", "glossary", "designspec", "archspec",
              "dataspec", "apispec", "testspec", "plan", "issues"]

