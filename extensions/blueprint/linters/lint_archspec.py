#!/usr/bin/env python3
"""
lint_archspec.py — Validate an ArchSpec JSON against its schema and semantic rules.
Optionally cross-checks against a GoalSpec for REQ/NFR reference resolution.

What this catches beyond JSON Schema:
  - Duplicate component IDs, constraint IDs, flow IDs
  - Component dependency references that don't exist
  - Subsystem componentRefs that don't exist
  - Data flow step componentRefs that don't exist
  - REQ/NFR refs that don't exist in the GoalSpec (if provided)
  - Components with no REQ coverage at confirmed status
  - Overlapping responsibilities across components
  - Circular component dependencies
  - project/goalSpecVersion mismatch against loaded GoalSpec
  - FRs in GoalSpec not covered by any component
  - Constraints with implementation smells

Usage:
    python lint_archspec.py <archspec.json> [--schema archspec.schema.json]
                            [--goal goalspec.json] [--strict] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from shared import (
    BaseLinter,
    LayerResult,
    find_cycles,
    find_orphans,
    find_patterns,
    print_human,
    print_json_output,
    validate_coverage,
)


# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES = [
    # Components must have reqRefs
    {
        "type": "non_empty",
        "section": "components",
        "key": "reqRefs",
        "id_key": "id",
        "label": "Component",
        "category": "component_no_reqs",
        "hint": "Link each component to the requirements it helps satisfy.",
    },
    
    # Flow steps must reference valid components
    {
        "type": "exists",
        "section": "dataFlow",
        "nested_key": "componentRef",
        "valid_section": "components",
        "valid_key": "id",
        "label": "Flow step",
        "ref_label": "component",
        "category": "flow_component_ref",
    },
    
    # Subsystems must have componentRefs
    {
        "type": "non_empty",
        "section": "overview.subsystems",
        "key": "componentRefs",
        "id_key": "name",
        "label": "Subsystem",
        "category": "subsystem_empty",
    },
    
    # Components not assigned to any subsystem
    {
        "type": "coverage",
        "covered_section": "components",
        "source_section": "overview.subsystems",
        "covered_key": "id",
        "refs_key": "componentRefs",
        "covered_label": "Component",
        "source_label": "Subsystem",
    },
    
    # Subsystems must not overlap
    {
        "type": "no_overlap",
        "section": "overview.subsystems",
        "refs_key": "componentRefs",
        "id_key": "name",
        "label": "Subsystem",
        "category": "subsystem_overlap",
    },
    
    # Flow must have at least 2 steps
    {
        "type": "item_count",
        "section": "dataFlow",
        "key": "steps",
        "count": 2,
        "compare_mode": -1,
        "id_key": "id",
        "label": "Flow",
        "category": "flow_too_short",
        "hint": "A data flow must show at least a source and a sink step.",
    },
    
    # Constraints must not mention implementation
    {
        "type": "patterns",
        "section": "constraints",
        "text_key": "description",
        "patterns": [
            ("postgres", "postgres"), ("mysql", "mysql"), ("redis", "redis"),
            ("sqlite", "sqlite"), ("mongodb", "mongodb"), ("fastapi", "fastapi"),
            ("flask", "flask"), ("django", "django"), ("docker", "docker"),
            ("kubernetes", "kubernetes"), ("s3", "s3"), ("lambda", "lambda"),
            ("python", "python"), ("typescript", "typescript"), ("rust", "rust"),
            ("golang", "golang"), ("java", "java"),
        ],
        "label": "Constraint",
        "category": "constraint_implementation_leak",
        "hint": "Constraints should describe what is required, not which technology satisfies it.",
        "match_fn": lambda item, patterns: [
            (s[0], [s[0]]) for s in patterns if s[0] in item.get("description", "").lower()
        ],
    },
    
    # Flow descriptions must not be empty
    {
        "type": "non_empty",
        "section": "dataFlow",
        "key": "description",
        "id_key": "id",
        "label": "Flow",
        "category": "flow_empty_description",
    },
    
    # Flow steps must have dataRef
    {
        "type": "non_empty",
        "section": "dataFlow",
        "nested_key": "dataRef",
        "id_key": "componentRef",
        "label": "Flow step",
        "category": "flow_step_empty_data_ref",
    },
    
    # Components must not have too many responsibilities
    {
        "type": "item_count",
        "section": "components",
        "key": "responsibilities",
        "count": 8,
        "compare_mode": 1,
        "id_key": "id",
        "label": "Component",
        "category": "component_responsibility_count",
    },
    
    # Flows must not have too many steps
    {
        "type": "item_count",
        "section": "dataFlow",
        "key": "steps",
        "count": 15,
        "compare_mode": 1,
        "id_key": "id",
        "label": "Flow",
        "category": "flow_step_count",
    },
]


# ── Glossary Checks ───────────────────────────────────────────────────────────

GLOSSARY_CHECKS = [
    ("Component", "glossaryRefs", lambda s: s.get("components", [])),
    ("Flow", "glossaryRefs", lambda s: s.get("dataFlow", [])),
    ("Constraint", "glossaryRefs", lambda s: s.get("constraints", [])),
]


# ── Custom Checks ─────────────────────────────────────────────────────────────

def _check_circular_dependencies(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check for circular component dependencies."""
    components = spec.get("components", [])
    component_ids = {c["id"] for c in components}
    
    find_cycles(
        components,
        "id",
        "dependencies",
        component_ids,
        result,
        label="Component",
        category="circular_dependency",
        hint="Refactor to break the cycle — introduce an abstraction or invert a dependency.",
    )


def _check_vague_responsibilities(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Warn if a component has only one responsibility that is vague/generic."""
    vague_patterns = [
        r"\bconsist(?:ent|ently)\b",
        r"\bacross all\b",
        r"\bthe system\b",
        r"\bprovide\s+(a |an )?\b",
        r"\bhandle\s+(all |the |any )?\b",
        r"\bmanage\s+(the |all |any )?\b",
        r"\bensure\s+(that |the |all )?\b",
    ]
    find_patterns(
        spec.get("components", []),
        patterns=vague_patterns,
        result=result,
        label="Component",
        category="vague_responsibility",
        hint="Break into specific, actionable responsibilities. Avoid generic statements like 'consistent error handling across all components'.",
        nested_key="responsibilities",
        max_count=1,
    )


def _check_inline_refs_in_responsibilities(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Warn if responsibilities contain text that looks like non-standard refs."""
    non_standard_patterns = [
        (r"\bkey\s+flow\s+\w+\b", "key flow references"),
        (r"\bflow\s+\d+[a-z]?\b", "flow number references"),
        (r"\bsection\s+\d+\b", "section references"),
    ]
    find_patterns(
        spec.get("components", []),
        patterns=non_standard_patterns,
        result=result,
        label="Component",
        category="inline_ref_in_responsibility",
        hint="Move requirement references to the reqRefs/nfrRefs arrays. Use glossaryRefs for term references.",
        nested_key="responsibilities",
    )


def _check_components_in_data_flows(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Warn if a component is not referenced in any data flow step."""
    components = spec.get("components", [])
    comp_ids = {c["id"] for c in components}
    
    flow_components = set()
    for flow in spec.get("dataFlow", []):
        for step in flow.get("steps", []):
            ref = step.get("componentRef")
            if ref:
                flow_components.add(ref)
    
    for cid in comp_ids:
        if cid not in flow_components:
            result.add(
                "warning",
                "component_not_in_flow",
                f"Component '{cid}' is not referenced in any data flow step.",
                hint="Either add this component to a relevant data flow or remove it from the architecture if it's not part of the data pipeline.",
            )


def _check_orphan_components(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Warn if components have no dependencies and no dependents."""
    find_orphans(
        spec.get("components", []),
        "id",
        "dependencies",
        result,
        label="Component",
    )


def _check_req_nfr_refs(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Resolve all REQ/NFR refs across components, flows, and constraints against GoalSpec."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    goal_req_ids = {r["id"] for r in goal.get("functionalRequirements", [])}
    goal_nfr_ids = {r["id"] for r in goal.get("nonFunctionalRequirements", [])}
    valid_refs = {"reqRefs": goal_req_ids, "nfrRefs": goal_nfr_ids}
    
    from shared import validate_exists
    
    validate_exists(
        spec.get("components", []),
        ["reqRefs", "nfrRefs"],
        valid_refs,
        result,
        label="Component",
        ref_label="GoalSpec requirement",
        category="req_ref_missing",
    )
    validate_exists(
        spec.get("dataFlow", []),
        ["reqRefs"],
        valid_refs,
        result,
        label="Flow",
        ref_label="GoalSpec requirement",
        category="req_ref_missing",
    )
    validate_exists(
        spec.get("constraints", []),
        ["nfrRefs"],
        valid_refs,
        result,
        label="Constraint",
        ref_label="GoalSpec NFR",
        category="nfr_ref_missing",
    )


def _check_fr_coverage(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check that GoalSpec FRs are covered by components."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    validate_coverage(
        goal.get("functionalRequirements", []),
        spec.get("components", []),
        "id",
        "reqRefs",
        result,
        covered_label="GoalSpec FR",
        source_label="component",
    )


def _check_nfr_coverage(spec: dict, result: LayerResult, extra_specs: dict) -> None:
    """Check that GoalSpec NFRs are covered by components or constraints."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    all_nfr_source = spec.get("components", []) + spec.get("constraints", [])
    validate_coverage(
        goal.get("nonFunctionalRequirements", []),
        all_nfr_source,
        "id",
        "nfrRefs",
        result,
        covered_label="GoalSpec NFR",
        source_label="component or constraint",
    )


# ── Linter Class ──────────────────────────────────────────────────────────────

class ArchSpecLinter(BaseLinter):
    SPEC_NAME = "archspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    GLOSSARY_CHECKS = GLOSSARY_CHECKS
    CROSS_SPEC_DEPS = ["goal", "data", "api"]
    MISC_CHECKS = [
        ("circular_deps", _check_circular_dependencies),
        ("vague_responsibilities", _check_vague_responsibilities),
        ("inline_refs", _check_inline_refs_in_responsibilities),
        ("components_in_flows", _check_components_in_data_flows),
        ("orphan_components", _check_orphan_components),
        ("req_nfr_refs", _check_req_nfr_refs),
        ("fr_coverage", _check_fr_coverage),
        ("nfr_coverage", _check_nfr_coverage),
    ]


# ── Backward Compatibility ────────────────────────────────────────────────────

def run_lint(spec, schema_path, goal, strict, glossary=None, data_spec=None, api_spec=None):
    """Backward-compatible entry point for lint_all.py."""
    linter = ArchSpecLinter(spec, schema_path, strict)
    return linter.run(goal=goal, data=data_spec, api=api_spec, glossary=glossary)


# ── Output ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lint an ArchSpec JSON.")
    parser.add_argument("input", help="Path to archspec JSON")
    parser.add_argument("--schema", help="Path to archspec.schema.json")
    parser.add_argument("--goal", help="Path to goalspec JSON for cross-spec checks")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    spec = json.loads(Path(args.input).read_text())
    schema_path = Path(args.schema) if args.schema else None
    goal = json.loads(Path(args.goal).read_text()) if args.goal else None
    
    linter = ArchSpecLinter(spec, schema_path, args.strict)
    result = linter.run(goal=goal)
    
    if args.json:
        print_json_output(result)
    else:
        print_human(result, args.input)
    
    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
