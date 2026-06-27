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

from rules import SemanticRule
from shared import (
    BaseLinter,
    CompletenessGate,
    LayerResult,
)

# ── Semantic Rules ────────────────────────────────────────────────────────────

SEMANTIC_RULES: list[SemanticRule] = [
    # Components must have reqRefs
    {
        "target": "components.reqRefs",
        "check": "non_empty",
        "target_label": "Component",
        "category": "component_no_reqs",
        "hint": "Link each component to the requirements it helps satisfy.",
    },
    # Flow steps must reference valid components
    {
        "target": "dataFlow.steps.componentRef",
        "check": "exists",
        "inside": "components",
        "target_label": "Flow step",
        "ref_label": "component",
        "category": "flow_component_ref",
    },
    # Subsystems must have componentRefs
    {
        "target": "overview.subsystems.componentRefs",
        "check": "non_empty",
        "target_label": "Subsystem",
        "category": "subsystem_empty",
    },
    # Components not assigned to any subsystem
    {
        "target": "overview.subsystems.componentRefs",
        "check": "covers_all",
        "should_cover_all": "components",
        "category": "component_unassigned",
        "covered_label": "Component",
        "target_label": "Subsystem",
    },
    # Subsystems must not overlap
    {
        "target": "overview.subsystems.componentRefs",
        "check": "not_shared",
        "target_label": "Subsystem",
        "category": "subsystem_overlap",
    },
    # Flow must have at least 2 steps
    {
        "target": "dataFlow.steps",
        "check": "has_item_count",
        "count": 2,
        "compare_mode": "less",
        "target_label": "Flow",
        "category": "flow_too_short",
        "hint": "A data flow must show at least a source and a sink step.",
    },
    # Constraints must not mention implementation
    {
        "target": "constraints.description",
        "check": "contains_patterns",
        "patterns": [
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
        ],
        "target_label": "Constraint",
        "category": "constraint_implementation_leak",
        "hint": "Constraints should describe what is required, not which technology satisfies it.",
    },
    # Flow descriptions must not be empty
    {
        "target": "dataFlow.description",
        "check": "non_empty",
        "target_label": "Flow",
        "category": "flow_empty_description",
    },
    # Flow steps must have dataRef
    {
        "target": "dataFlow.steps.dataRef",
        "check": "non_empty",
        "target_label": "Flow step",
        "category": "flow_step_empty_data_ref",
    },
    # Components must not have too many responsibilities
    {
        "target": "components.responsibilities",
        "check": "has_item_count",
        "count": 8,
        "compare_mode": "more",
        "target_label": "Component",
        "category": "component_responsibility_count",
    },
    # Flows must not have too many steps
    {
        "target": "dataFlow.steps",
        "check": "has_item_count",
        "count": 15,
        "compare_mode": "more",
        "target_label": "Flow",
        "category": "flow_step_count",
    },
    # Components must not have vague responsibilities
    {
        "target": "components.responsibilities",
        "check": "contains_patterns",
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
        "target": "components.responsibilities",
        "check": "contains_patterns",
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
        "target": "components",
        "check": "not_orphan",
        "category": "isolated",
        "target_label": "Component",
        "hint": "An isolated component may indicate a design issue.",
    },
    # GoalSpec FRs must be covered by components
    {
        "target": "components.reqRefs",
        "check": "covers_all",
        "should_cover_all": "goal:functionalRequirements",
        "category": "fr_uncovered",
        "covered_label": "GoalSpec FR",
        "target_label": "component",
    },
    # GoalSpec NFRs must be covered by components or constraints
    {
        "target": "components.nfrRefs",
        "check": "covers_all",
        "should_cover_all": "goal:nonFunctionalRequirements",
        "category": "nfr_uncovered",
        "covered_label": "GoalSpec NFR",
        "target_label": "component",
    },
    # Components must reference valid GoalSpec REQ
    {
        "target": "components.reqRefs",
        "check": "exists",
        "inside": "goal:functionalRequirements.id",
        "target_label": "Component",
        "ref_label": "GoalSpec requirement",
        "category": "req_ref_missing",
    },
    # Components must reference valid GoalSpec NFR
    {
        "target": "components.nfrRefs",
        "check": "exists",
        "inside": "goal:nonFunctionalRequirements.id",
        "target_label": "Component",
        "ref_label": "GoalSpec NFR",
        "category": "nfr_ref_missing",
    },
    # Flow reqRefs must reference valid GoalSpec REQ
    {
        "target": "dataFlow.reqRefs",
        "check": "exists",
        "inside": "goal:functionalRequirements.id",
        "target_label": "Flow",
        "ref_label": "GoalSpec requirement",
        "category": "req_ref_missing",
    },
    # Constraints must reference valid GoalSpec NFR
    {
        "target": "constraints.nfrRefs",
        "check": "exists",
        "inside": "goal:nonFunctionalRequirements.id",
        "target_label": "Constraint",
        "ref_label": "GoalSpec NFR",
        "category": "nfr_ref_missing",
    },
    # Glossary refs: Components must reference valid glossary terms
    {
        "target": "components.glossaryRefs",
        "check": "exists",
        "inside": "glossary.terms.id",
        "target_label": "Component",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Glossary refs: DataFlow must reference valid glossary terms
    {
        "target": "dataFlow.glossaryRefs",
        "check": "exists",
        "inside": "glossary.terms.id",
        "target_label": "Flow",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Glossary refs: Constraints must reference valid glossary terms
    {
        "target": "constraints.glossaryRefs",
        "check": "exists",
        "inside": "glossary.terms.id",
        "target_label": "Constraint",
        "ref_label": "Glossary",
        "category": "glossary_ref_missing",
    },
    # Component dependencies must reference valid component IDs
    {
        "target": "components.dependencies",
        "check": "exists",
        "inside": "components.id",
        "target_label": "Component",
        "ref_label": "component",
        "category": "dependency_ref",
    },
    # Component dependency graph must have no cycles
    {
        "target": "components",
        "check": "has_no_cycles",
        "deps": "dependencies",
        "target_label": "Component",
        "category": "circular_dependency",
        "hint": "Refactor to break the cycle — introduce an abstraction or invert a dependency.",
    },
]


# ── Custom Checks ─────────────────────────────────────────────────────────────


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


# ── Completeness Gates ────────────────────────────────────────────────────────

COMPLETENESS_GATES: list = [
    {
        "target": "overview.subsystems",
        "check": "has_count",
        "count": 1,
        "target_label": "subsystem",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has at least one subsystem",
    },
    {
        "target": "components",
        "check": "has_count",
        "count": 2,
        "target_label": "component",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has at least 2 components",
    },
    {
        "target": "dataFlow",
        "check": "has_count",
        "count": 1,
        "target_label": "data flow",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has at least one data flow",
    },
    {
        "target": "constraints",
        "check": "has_count",
        "count": 1,
        "target_label": "constraint",
        "category": "completeness",
        "required_at": "draft",
        "description": "Has at least one constraint",
    },
    {
        "target": "components",
        "check": "all_have",
        "field": "reqRefs",
        "min_length": 1,
        "target_label": "component",
        "category": "completeness",
        "required_at": "review",
        "description": "All components have REQ refs",
    },
    {
        "target": "goalSpecVersion",
        "check": "value_check",
        "expected": "truthy",
        "target_label": "goalSpecVersion",
        "category": "completeness",
        "required_at": "review",
        "description": "goalSpecVersion is set",
    },
    {
        "target": "dataSpecVersion",
        "check": "value_check",
        "expected": "truthy",
        "target_label": "dataSpecVersion",
        "category": "completeness",
        "required_at": "confirmed",
        "description": "dataSpecVersion is set",
    },
    {
        "target": "apiSpecVersion",
        "check": "value_check",
        "expected": "truthy",
        "target_label": "apiSpecVersion",
        "category": "completeness",
        "required_at": "confirmed",
        "description": "apiSpecVersion is set",
    },
]


# ── Misc Completeness Gates ───────────────────────────────────────────────────


def _gate_overview_summary(spec: dict, extra_specs: dict) -> CompletenessGate:
    """Has system overview summary (>= 30 chars)."""
    summary = spec.get("overview", {}).get("summary", "")
    return CompletenessGate(
        description="Has system overview summary",
        passed=len(summary) >= 30,
        required_at="draft",
        detail=f"overview.summary is too short ({len(summary)} chars)"
        if len(summary) < 30
        else "",
    )


def _gate_component_dependencies(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All components participate in at least one dependency."""
    components = spec.get("components", [])
    deps_or_dependents = set()
    for c in components:
        for dep in c.get("dependencies", []):
            deps_or_dependents.add(c["id"])
            deps_or_dependents.add(dep)
    return CompletenessGate(
        description="All components participate in at least one dependency",
        passed=len(deps_or_dependents) == len(components),
        required_at="review",
        detail="Isolated components found"
        if len(deps_or_dependents) < len(components)
        else "",
    )


# ── Linter Class ──────────────────────────────────────────────────────────────


class ArchSpecLinter(BaseLinter):
    SPEC_NAME = "archspec"
    SPEC_KEY = "archspec"
    SEMANTIC_RULES = SEMANTIC_RULES
    COMPLETENESS_GATES = COMPLETENESS_GATES
    MISC_GATES = [_gate_overview_summary, _gate_component_dependencies]
    MISC_CHECKS = [_check_components_in_data_flows]
    CROSS_SPEC_DEPS = ["goal", "data", "api", "glossary"]


# Canonical linter class for lint_all.py
LinterClass = ArchSpecLinter


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ArchSpecLinter.main()
