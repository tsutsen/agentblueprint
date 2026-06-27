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

import json
import sys
from pathlib import Path
from typing import Optional

from shared import (
    BaseLinter,
    LayerResult,
    SemanticRule,
    find_cycles,
)

# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # Components must have reqRefs
    {
        "type": "non_empty",
        "target": "components.reqRefs",
        "target_label": "Component",
        "category": "component_no_reqs",
        "hint": "Link each component to the requirements it helps satisfy.",
    },
    # Flow steps must reference valid components
    {
        "type": "exists",
        "target": "dataFlow.steps.componentRef",
        "inside": "components",
        "target_label": "Flow step",
        "ref_label": "component",
        "category": "flow_component_ref",
    },
    # Subsystems must have componentRefs
    {
        "type": "non_empty",
        "target": "overview.subsystems.componentRefs",
        "target_label": "Subsystem",
        "category": "subsystem_empty",
    },
    # Components not assigned to any subsystem
    {
        "type": "covers_all",
        "target": "overview.subsystems.componentRefs",
        "should_cover_all": "components",
        "category": "component_unassigned",
        "covered_label": "Component",
        "target_label": "Subsystem",
    },
    # Subsystems must not overlap
    {
        "type": "not_shared",
        "target": "overview.subsystems.componentRefs",
        "target_label": "Subsystem",
        "category": "subsystem_overlap",
    },
    # Flow must have at least 2 steps
    {
        "type": "has_item_count",
        "target": "dataFlow.steps",
        "count": 2,
        "compare_mode": -1,
        "target_label": "Flow",
        "category": "flow_too_short",
        "hint": "A data flow must show at least a source and a sink step.",
    },
    # Constraints must not mention implementation
    {
        "type": "contains_patterns",
        "target": "constraints.description",
        "patterns": [
            "postgres", "mysql", "redis", "sqlite", "mongodb",
            "fastapi", "flask", "django", "docker", "kubernetes",
            "s3", "lambda", "python", "typescript", "rust",
            "golang", "java",
        ],
        "target_label": "Constraint",
        "category": "constraint_implementation_leak",
        "hint": "Constraints should describe what is required, not which technology satisfies it.",
    },
    # Flow descriptions must not be empty
    {
        "type": "non_empty",
        "target": "dataFlow.description",
        "target_label": "Flow",
        "category": "flow_empty_description",
    },
    # Flow steps must have dataRef
    {
        "type": "non_empty",
        "target": "dataFlow.steps.dataRef",
        "target_label": "Flow step",
        "category": "flow_step_empty_data_ref",
    },
    # Components must not have too many responsibilities
    {
        "type": "has_item_count",
        "target": "components.responsibilities",
        "count": 8,
        "compare_mode": 1,
        "target_label": "Component",
        "category": "component_responsibility_count",
    },
    # Flows must not have too many steps
    {
        "type": "has_item_count",
        "target": "dataFlow.steps",
        "count": 15,
        "compare_mode": 1,
        "target_label": "Flow",
        "category": "flow_step_count",
    },
    # Components must not have vague responsibilities
    {
        "type": "contains_patterns",
        "target": "components.responsibilities",
        "patterns": [
            (r"\bconsist(?:ent|ently)\b", "consistent/consistently"),
            (r"\bacross all\b", "across all"),
            (r"\bthe system\b", "the system"),
            (r"\bprovide\s+(a |an )?\b", "provide a/an"),
            (r"\bhandle\s+(all |the |any )?\b", "handle all/the/any"),
            (r"\bmanage\s+(the |all |any )?\b", "manage the/all/any"),
            (r"\bensure\s+(that |the |all )?\b", "ensure that/the/all"),
        ],
        "target_label": "Component",
        "category": "vague_responsibility",
        "hint": "Break into specific, actionable responsibilities. Avoid generic statements.",
        "max_count": 1,
    },
    # Responsibilities must not contain inline refs
    {
        "type": "contains_patterns",
        "target": "components.responsibilities",
        "patterns": [
            (r"\bkey\s+flow\s+\w+\b", "key flow references"),
            (r"\bflow\s+\d+[a-z]?\b", "flow number references"),
            (r"\bsection\s+\d+\b", "section references"),
        ],
        "target_label": "Component",
        "category": "inline_ref_in_responsibility",
        "hint": "Move requirement references to the reqRefs/nfrRefs arrays.",
    },
    # Components must not be isolated (no deps, no dependents)
    {
        "type": "not_orphan",
        "target": "components",
        "category": "isolated",
        "target_label": "Component",
        "hint": "An isolated component may indicate a design issue.",
    },
    # GoalSpec FRs must be covered by components
    {
        "type": "covers_all",
        "target": "components.reqRefs",
        "should_cover_all": "goal:functionalRequirements",
        "category": "fr_uncovered",
        "covered_label": "GoalSpec FR",
        "target_label": "component",
    },
    # GoalSpec NFRs must be covered by components or constraints
    {
        "type": "covers_all",
        "target": "components.nfrRefs",
        "should_cover_all": "goal:nonFunctionalRequirements",
        "category": "nfr_uncovered",
        "covered_label": "GoalSpec NFR",
        "target_label": "component",
    },
    # Components must reference valid GoalSpec REQ
    {
        "type": "exists",
        "target": "components.reqRefs",
        "inside": "goal:functionalRequirements.id",
        "target_label": "Component",
        "ref_label": "GoalSpec requirement",
        "category": "req_ref_missing",
    },
    # Components must reference valid GoalSpec NFR
    {
        "type": "exists",
        "target": "components.nfrRefs",
        "inside": "goal:nonFunctionalRequirements.id",
        "target_label": "Component",
        "ref_label": "GoalSpec NFR",
        "category": "nfr_ref_missing",
    },
    # Flow reqRefs must reference valid GoalSpec REQ
    {
        "type": "exists",
        "target": "dataFlow.reqRefs",
        "inside": "goal:functionalRequirements.id",
        "target_label": "Flow",
        "ref_label": "GoalSpec requirement",
        "category": "req_ref_missing",
    },
    # Constraints must reference valid GoalSpec NFR
    {
        "type": "exists",
        "target": "constraints.nfrRefs",
        "inside": "goal:nonFunctionalRequirements.id",
        "target_label": "Constraint",
        "ref_label": "GoalSpec NFR",
        "category": "nfr_ref_missing",
    },
]


# ── Glossary Checks ───────────────────────────────────────────────────────────

GLOSSARY_CHECKS = [
    ("Component", "glossaryRefs", "components"),
    ("Flow", "glossaryRefs", "dataFlow"),
    ("Constraint", "glossaryRefs", "constraints"),
]


# ── Custom Checks ─────────────────────────────────────────────────────────────


def _check_circular_dependencies(
    spec: dict, result: LayerResult, extra_specs: dict
) -> None:
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


def _check_components_in_data_flows(
    spec: dict, result: LayerResult, extra_specs: dict
) -> None:
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


# ── Linter Class ──────────────────────────────────────────────────────────────


class ArchSpecLinter(BaseLinter):
    SPEC_NAME = "archspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    GLOSSARY_CHECKS = GLOSSARY_CHECKS
    CROSS_SPEC_DEPS = ["goal", "data", "api"]
    MISC_CHECKS = [
        ("circular_deps", _check_circular_dependencies),
        ("components_in_flows", _check_components_in_data_flows),
    ]


# ── Backward Compatibility ────────────────────────────────────────────────────


def run_lint(
    spec, schema_path, goal, strict, glossary=None, data_spec=None, api_spec=None
):
    """Backward-compatible entry point for lint_all.py."""
    linter = ArchSpecLinter(spec, schema_path, strict)
    return linter.run(goal=goal, data=data_spec, api=api_spec, glossary=glossary)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ArchSpecLinter.main(
        [
            (
                "--goal",
                {
                    "help": "Path to goalspec JSON for cross-spec checks",
                    "spec_name": "goal",
                },
            ),
        ]
    )
