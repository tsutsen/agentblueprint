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

from schema_validator import SchemaValidator
from shared import (
    Issue,
    LayerResult,
    find_cycles,
    find_duplicates,
    find_orphans,
    find_patterns,
    find_patterns_nested,
    find_vague_patterns,
    print_human,
    print_json_output,
    validate_coverage,
    validate_exists,
    validate_item_count,
    validate_no_overlap,
    validate_non_empty,
    validate_project_and_version,
    validate_spec_ids,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


# ── Checks ────────────────────────────────────────────────────────────────────


def check_components(spec: dict, result: LayerResult) -> set[str]:
    components = spec.get("components", [])
    ids = [c["id"] for c in components]
    find_duplicates(ids, "component", result)

    component_ids = set(ids)

    # Build dependency graph, validate refs, and check for cycles
    find_cycles(
        components, "id", "dependencies", component_ids,
        result, label="Component", category="circular_dependency",
        hint="Refactor to break the cycle — introduce an abstraction or invert a dependency."
    )

    # Warn: component with no reqRefs
    for comp in components:
        validate_non_empty(
            [comp], "reqRefs", "id", result,
            label="Component", category="component_no_reqs",
            hint="Link each component to the requirements it helps satisfy."
        )

    # Overlapping responsibilities
    find_duplicates_nested(
        components, "responsibilities", "id", result,
        label="Component", category="overlapping_responsibility",
        hint="Each responsibility must be owned by exactly one component.",
        normalize=lambda r: r.strip().lower().rstrip(".")
    )

    return component_ids


def check_subsystems(spec: dict, component_ids: set[str], result: LayerResult):
    subsystems = spec.get("overview", {}).get("subsystems", [])
    all_comp_refs = []
    comp_to_subs: dict[str, list[str]] = {}

    # Check for empty subsystems
    validate_non_empty(
        subsystems,
        "componentRefs",
        "name",
        result,
        label="Subsystem",
        category="subsystem_empty",
    )

    for sub in subsystems:
        refs = sub.get("componentRefs", [])

        # Check for invalid component refs
        validate_exists(
            [{"id": ref} for ref in refs],
            "id",
            component_ids,
            result,
            label=f"Subsystem '{sub['name']}'",
            ref_label="component",
            category="subsystem_ref",
        )

        for ref in refs:
            all_comp_refs.append(ref)
            comp_to_subs.setdefault(ref, []).append(sub["name"])

    # Warn: components not assigned to any subsystem
    validate_coverage(
        [{"id": cid} for cid in component_ids],
        [
            {"componentRefs": refs}
            for refs in [sub.get("componentRefs", []) for sub in subsystems]
        ],
        "id",
        "componentRefs",
        result,
        covered_label="Component",
        source_label="Subsystem",
    )

    # Warn: component assigned to multiple subsystems
    validate_no_overlap(
        subsystems,
        "componentRefs",
        "name",
        result,
        label="Subsystem",
        category="subsystem_overlap",
    )


def check_data_flows(spec: dict, component_ids: set[str], result: LayerResult):
    flows = spec.get("dataFlow", [])
    ids = [f["id"] for f in flows]
    find_duplicates(ids, "FLW", result)

    # Validate componentRef exists
    all_steps = [step for flow in flows for step in flow.get("steps", [])]
    validate_exists(
        all_steps,
        "componentRef",
        component_ids,
        result,
        label="Flow step",
        ref_label="component",
        category="flow_component_ref",
    )

    # Validate flow has at least 2 steps
    validate_item_count(
        flows,
        "steps",
        2,
        -1,
        "id",
        result,
        label="Flow",
        category="flow_too_short",
        hint="A data flow must show at least a source and a sink step.",
    )


def check_constraints(spec: dict, result: LayerResult):
    constraints = spec.get("constraints", [])
    ids = [c["id"] for c in constraints]
    find_duplicates(ids, "CON", result)

    # Implementation smells in constraints
    impl_smells = [
        "postgres",
        "mysql",
        "redis",
        "sqlite",
        "mongodb",
        "fastapi",
        "flask",
        "django",
        "docker",
        "kubernetes",
        "s3",
        "lambda",
        "python",
        "typescript",
        "rust",
        "golang",
        "java",
    ]
    find_patterns(
        constraints,
        text_key="description",
        patterns=[(s, s) for s in impl_smells],
        result=result,
        label="Constraint",
        category="constraint_implementation_leak",
        hint="Constraints should describe what is required, not which technology satisfies it.",
        match_fn=lambda item, smells: [
            (s, [s]) for s in smells if s in item.get("description", "").lower()
        ],
    )


def check_req_nfr_refs(spec: dict, goal: Optional[dict], result: LayerResult):
    """Resolve all REQ/NFR refs across components, flows, and constraints against GoalSpec."""
    if not goal:
        return

    goal_req_ids = {r["id"] for r in goal.get("functionalRequirements", [])}
    goal_nfr_ids = {r["id"] for r in goal.get("nonFunctionalRequirements", [])}
    valid_refs = {"reqRefs": goal_req_ids, "nfrRefs": goal_nfr_ids}

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


def check_subsystem_empty(spec: dict, component_ids: set[str], result: LayerResult):
    """Warn if a subsystem has no components assigned."""
    validate_non_empty(
        spec.get("overview", {}).get("subsystems", []),
        "componentRefs",
        "name",
        result,
        label="Subsystem",
    )


def check_subsystem_overlap(spec: dict, result: LayerResult):
    """Warn if a component is assigned to multiple subsystems."""
    validate_no_overlap(
        spec.get("overview", {}).get("subsystems", []),
        "componentRefs",
        "name",
        result,
        label="Subsystem",
    )


def check_data_ref_valid(spec: dict, data_spec: Optional[dict], result: LayerResult):
    """Warn if data flow steps reference non-existent DataSpec entities."""
    if not data_spec:
        return

    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    all_steps = [
        step for flow in spec.get("dataFlow", []) for step in flow.get("steps", [])
    ]
    validate_exists(
        all_steps,
        "dataRef",
        entity_names,
        result,
        label="Flow step",
        ref_label="DataSpec entity",
        category="data_ref_missing",
    )


def check_component_responsibility_count(spec: dict, result: LayerResult):
    """Warn if a component has too many responsibilities (>5)."""
    validate_item_count(
        spec.get("components", []),
        "responsibilities",
        8,
        1,
        "id",
        result,
        label="Component",
        category="component_responsibility_count",
    )


def check_data_flow_step_count(spec: dict, result: LayerResult):
    """Warn if a data flow has too many steps (>10)."""
    validate_item_count(
        spec.get("dataFlow", []),
        "steps",
        15,
        1,
        "id",
        result,
        label="Flow",
        category="flow_step_count",
    )


def check_external_component_count(spec: dict, result: LayerResult):
    """Warn if too many components are external (>30% of total)."""
    components = spec.get("components", [])
    if not components:
        return
    external_count = sum(1 for c in components if c.get("visibility") == "external")
    if external_count > len(components) * 0.5:
        result.add(
            "warning",
            "external_component_count",
            f"{external_count}/{len(components)} components ({external_count / len(components):.0%}) are external.",
            hint="Too many external components may indicate over-exposure. Review which components truly need to be external.",
        )


def check_dependency_depth(spec: dict, result: LayerResult):
    """Warn if any component has a dependency chain >3 levels deep."""
    components = spec.get("components", [])
    comp_deps = {c["id"]: c.get("dependencies", []) for c in components}

    def get_depth(comp_id, visited=None):
        if visited is None:
            visited = set()
        if comp_id in visited:
            return 0  # Circular, stop
        visited.add(comp_id)
        deps = comp_deps.get(comp_id, [])
        if not deps:
            return 0
        return 1 + max(get_depth(d, visited.copy()) for d in deps)

    for comp_id in comp_deps:
        depth = get_depth(comp_id)
        if depth > 5:
            result.add(
                "warning",
                "dependency_depth",
                f"Component '{comp_id}' has a dependency chain of {depth} levels.",
                hint="Deep dependency chains can make the system hard to understand and maintain.",
            )


def check_flow_descriptions(spec: dict, result: LayerResult):
    """Warn if data flow descriptions are empty."""
    validate_non_empty(
        spec.get("dataFlow", []),
        "description",
        "id",
        result,
        label="Flow",
        category="flow_empty_description",
    )


def check_flow_data_refs(spec: dict, result: LayerResult):
    """Warn if flow steps have empty dataRef fields."""
    all_steps = [
        step for flow in spec.get("dataFlow", []) for step in flow.get("steps", [])
    ]
    validate_non_empty(
        all_steps,
        "dataRef",
        "componentRef",
        result,
        label="Flow step",
        category="flow_step_empty_data_ref",
    )


def check_vague_responsibilities(spec: dict, result: LayerResult):
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


def check_inline_req_refs_in_responsibilities(spec: dict, result: LayerResult):
    """Warn if responsibilities contain text that looks like non-standard refs (e.g. 'key flow 9b')."""
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


def check_components_in_data_flows(spec: dict, result: LayerResult):
    """Warn if a component is not referenced in any data flow step."""
    components = spec.get("components", [])
    comp_ids = {c["id"] for c in components}

    # Collect all componentRefs from data flow steps
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


def check_cross_spec_versions(
    spec: dict, data_spec: Optional[dict], api_spec: Optional[dict], result: LayerResult
):
    """Warn if dataSpecVersion/apiSpecVersion don't match loaded specs."""
    pinned_data = spec.get("dataSpecVersion")
    pinned_api = spec.get("apiSpecVersion")

    if pinned_data and data_spec:
        if pinned_data != data_spec.get("version"):
            result.add(
                "warning",
                "dataspec_version_mismatch",
                f"archspec.dataSpecVersion='{pinned_data}' does not match dataspec.version='{data_spec.get('version')}'.",
                hint="Update dataSpecVersion to match the DataSpec's version.",
            )

    if pinned_api and api_spec:
        if pinned_api != api_spec.get("version"):
            result.add(
                "warning",
                "apispec_version_mismatch",
                f"archspec.apiSpecVersion='{pinned_api}' does not match apispec.version='{api_spec.get('version')}'.",
                hint="Update apiSpecVersion to match the ApiSpec's version.",
            )


def run_lint(
    spec: dict,
    schema_path: Optional[Path],
    goal: Optional[dict],
    strict: bool,
    glossary: Optional[dict] = None,
    data_spec: Optional[dict] = None,
    api_spec: Optional[dict] = None,
) -> LayerResult:
    result = LayerResult()

    # JSON Schema validation (auto-generated from schema)
    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        schema_issues = SchemaValidator(schema).validate(spec)
        for issue in schema_issues:
            result.add(issue.severity, issue.category, issue.message, issue.hint)

    # ID format validation
    validate_spec_ids(
        {
            "comp": spec.get("components", []),
            "flw": spec.get("dataFlow", []),
            "con": spec.get("constraints", []),
        },
        result,
    )

    #
    # GoalSpec cross-checks
    if goal:
        validate_project_and_version(spec, "archspec", goal, result)
        # version check handled by validate_project_and_version

    # Structural checks
    component_ids = check_components(spec, result)
    check_subsystems(spec, component_ids, result)
    check_data_flows(spec, component_ids, result)
    check_constraints(spec, result)

    # Cross-spec ref resolution
    check_req_nfr_refs(spec, goal, result)
    validate_coverage(
        goal.get("functionalRequirements", []),
        spec.get("components", []),
        "id",
        "reqRefs",
        result,
        covered_label="GoalSpec FR",
        source_label="component",
    )
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

    # Quality checks (new)
    find_orphans(spec.get("components", []), "id", "dependencies", result, "Component")
    check_flow_descriptions(spec, result)
    check_flow_data_refs(spec, result)
    check_vague_responsibilities(spec, result)
    check_inline_req_refs_in_responsibilities(spec, result)
    check_components_in_data_flows(spec, result)
    check_cross_spec_versions(spec, data_spec, api_spec, result)
    validate_glossary_refs(
        glossary,
        result,
        [
            ("Component", "glossaryRefs", spec.get("components", [])),
            ("Flow", "glossaryRefs", spec.get("dataFlow", [])),
            ("Constraint", "glossaryRefs", spec.get("constraints", [])),
        ],
    )

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output
# Uses shared.print_human and shared.print_json_output


def main():
    parser = argparse.ArgumentParser(description="Lint an ArchSpec JSON.")
    parser.add_argument("input", help="Path to archspec JSON")
    parser.add_argument("--schema", help="Path to archspec.schema.json")
    parser.add_argument("--goal", help="Path to goalspec JSON for cross-spec checks")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    spec = json.loads(Path(args.input).read_text())
    schema_path = Path(args.schema) if args.schema else None
    goal = json.loads(Path(args.goal).read_text()) if args.goal else None

    result = run_lint(spec, schema_path, goal, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, args.input)

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
