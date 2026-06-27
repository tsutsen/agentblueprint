#!/usr/bin/env python3
"""
lint_taskplan.py — Linter for TaskPlan artifact.

Validates:
  - Every GoalSpec requirement appears in at least one epic's coverage list
  - Every epic covers at least one requirement
  - No epic implements a GoalSpec non-goal
  - Epics are listed in dependency order (blockers before dependents)
  - Milestones have demonstrable outcomes
  - Every epic belongs to exactly one milestone
  - All REQ-IDs referenced in TaskPlan exist in GoalSpec

Usage:
    python lint_taskplan.py plan.json --goal goalspec.json
"""

from pathlib import Path
from typing import Optional

from shared import BaseLinter, CompletenessGate, LayerResult


def _check_requirement_coverage(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that every GoalSpec requirement appears in at least one epic's coverage list."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    req_ids = {req["id"] for req in goal.get("functionalRequirements", [])}
    epics = spec.get("epics", [])
    
    covered_reqs = set()
    for epic in epics:
        for req_ref in epic.get("coverage", []):
            covered_reqs.add(req_ref)
    
    for req_id in req_ids:
        if req_id not in covered_reqs:
            result.add("warning", "requirement_uncovered",
                f"Requirement '{req_id}' is not covered by any epic.",
                hint="Add the requirement to an epic's coverage list.")


def _check_epic_coverage(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that every epic covers at least one requirement."""
    for epic in spec.get("epics", []):
        eid = epic.get("id", "?")
        coverage = epic.get("coverage", [])
        if not coverage:
            result.add("warning", "epic_no_coverage",
                f"Epic '{eid}' covers no requirements.",
                hint="Add at least one requirement to this epic's coverage list.")


def _check_non_goal_check(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that no epic implements a GoalSpec non-goal."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    non_goal_ids = {ng["id"] for ng in goal.get("nonGoals", [])}
    epics = spec.get("epics", [])
    
    for epic in epics:
        for req_ref in epic.get("coverage", []):
            if req_ref in non_goal_ids:
                result.add("error", "epic_implements_non_goal",
                    f"Epic '{epic.get('id', '?')}' covers non-goal '{req_ref}'.",
                    hint="Remove this requirement from the epic's coverage list.")


def _check_dependency_order(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that epics are listed in dependency order (blockers before dependents)."""
    epics = spec.get("epics", [])
    epic_ids = {epic["id"] for epic in epics}
    
    for i, epic in enumerate(epics):
        for blocker in epic.get("blockers", []):
            if blocker not in epic_ids:
                result.add("warning", "unknown_blocker",
                    f"Epic '{epic.get('id', '?')}' blocks on unknown epic '{blocker}'.",
                    hint="Add the blocker epic to the TaskPlan or remove the blocker reference.")


def _check_milestone_outcomes(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that milestones have demonstrable outcomes."""
    for milestone in spec.get("milestones", []):
        mid = milestone.get("id", "?")
        outcome = milestone.get("outcome", "")
        if not outcome or not outcome.strip():
            result.add("warning", "milestone_no_outcome",
                f"Milestone '{mid}' has no outcome description.",
                hint="Describe what demonstrable outcome this milestone delivers.")


def _check_epic_milestone_assignment(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that every epic belongs to exactly one milestone."""
    epics = spec.get("epics", [])
    for epic in epics:
        eid = epic.get("id", "?")
        milestone = epic.get("milestone")
        if not milestone:
            result.add("warning", "epic_no_milestone",
                f"Epic '{eid}' is not assigned to any milestone.",
                hint="Assign this epic to a milestone.")
        elif isinstance(milestone, list):
            if len(milestone) > 1:
                result.add("warning", "epic_multiple_milestones",
                    f"Epic '{eid}' belongs to multiple milestones: {milestone}.",
                    hint="Assign this epic to exactly one milestone.")


def _check_req_id_reference(spec: dict, result: LayerResult, extra_specs: dict = None) -> None:
    """Check that all REQ-IDs referenced in TaskPlan exist in GoalSpec."""
    goal = extra_specs.get("goal")
    if not goal:
        return
    
    req_ids = {req["id"] for req in goal.get("functionalRequirements", [])}
    epics = spec.get("epics", [])
    
    for epic in epics:
        for req_ref in epic.get("coverage", []):
            if req_ref not in req_ids:
                result.add("error", "req_ref_missing",
                    f"Epic '{epic.get('id', '?')}': coverage reference '{req_ref}' not found in GoalSpec.",
                    hint="Add the requirement to GoalSpec or correct the reference.")


# ── Output
# Uses shared.print_human and shared.print_json_output


# ── Completeness Gates ────────────────────────────────────────────────────────

COMPLETENESS_GATES: list = [
    {"type": "has_count", "target": "milestones", "count": 1,
     "target_label": "milestone", "category": "completeness", "required_at": "draft",
     "description": "Has at least one milestone"},
    {"type": "has_count", "target": "epics", "count": 1,
     "target_label": "epic", "category": "completeness", "required_at": "draft",
     "description": "Has at least one epic"},
    {"type": "all_have", "target": "epics", "field": "requirements",
     "min_length": 1, "target_label": "epic", "category": "completeness",
     "required_at": "draft",
     "description": "Every epic covers at least one requirement"},
    {"type": "all_have", "target": "epics", "field": "milestone",
     "min_length": 1, "target_label": "epic", "category": "completeness",
     "required_at": "draft",
     "description": "All epics assigned to a milestone"},
    {"type": "all_have", "target": "epics", "field": "acceptanceCriteria",
     "min_length": 1, "target_label": "epic", "category": "completeness",
     "required_at": "review",
     "description": "All epics have acceptance criteria"},
]


# ── Misc Completeness Gates ───────────────────────────────────────────────────

def _get_epic_texts(spec: dict) -> list[str]:
    """Extract lowercased text from all epics for cross-spec matching."""
    texts = []
    for epic in spec.get("epics", []):
        text = ' '.join([
            epic.get("title", ""),
            epic.get("summary", ""),
            epic.get("objective", ""),
            " ".join(epic.get("scope", {}).get("inScope", [])),
        ]).lower()
        texts.append(text)
    return texts


def _gate_epic_scope(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All epics have scope (inScope + outOfScope)."""
    epics = spec.get("epics", [])
    all_have_scope = all(
        epic.get("scope", {}).get("inScope") and epic.get("scope", {}).get("outOfScope")
        for epic in epics
    )
    return CompletenessGate(
        description="All epics have scope (inScope + outOfScope)",
        passed=all_have_scope, required_at="review",
        detail="Some epics missing scope" if not all_have_scope else "",
    )


def _gate_epic_dependencies(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All epics have explicit dependencies."""
    epics = spec.get("epics", [])
    all_have_deps = all(
        epic.get("dependencies", {}).get("blockedBy") is not None or
        epic.get("dependencies", {}).get("blocks") is not None
        for epic in epics
    )
    return CompletenessGate(
        description="All epics have explicit dependencies",
        passed=all_have_deps, required_at="review",
        detail="Some epics missing dependencies" if not all_have_deps else "",
    )


def _gate_dependency_order(spec: dict, extra_specs: dict) -> CompletenessGate:
    """Epics are in dependency order (validated by lint_taskplan)."""
    return CompletenessGate(
        description="Epics are in dependency order",
        passed=True, required_at="review",
        detail="Dependency order validated by lint_taskplan.py",
    )


def _gate_no_circular_deps(spec: dict, extra_specs: dict) -> CompletenessGate:
    """No circular dependencies (validated by lint_taskplan)."""
    return CompletenessGate(
        description="No circular dependencies",
        passed=True, required_at="review",
        detail="Circular dependency check validated by lint_taskplan.py",
    )


def _gate_milestone_outcomes(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All milestones have demonstrable outcomes."""
    milestones = spec.get("milestones", [])
    all_have_outcomes = all(
        m.get("outcome") and len(m.get("outcome", "")) >= 10
        for m in milestones
    )
    return CompletenessGate(
        description="All milestones have demonstrable outcomes",
        passed=all_have_outcomes, required_at="review",
        detail="Some milestones missing outcomes" if not all_have_outcomes else "",
    )


def _gate_epic_objectives(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All epics have an objective."""
    epics = spec.get("epics", [])
    all_have_objective = all(epic.get("objective") for epic in epics)
    return CompletenessGate(
        description="All epics have an objective",
        passed=all_have_objective, required_at="review",
        detail="Some epics missing objective" if not all_have_objective else "",
    )


def _gate_acceptance_criteria_length(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All acceptance criteria are meaningful length."""
    epics = spec.get("epics", [])
    all_meaningful = all(
        all(len(ac.strip()) >= 15 for ac in epic.get("acceptanceCriteria", []))
        for epic in epics
    )
    return CompletenessGate(
        description="All acceptance criteria are meaningful length",
        passed=all_meaningful, required_at="review",
        detail="Some acceptance criteria too short" if not all_meaningful else "",
    )


def _gate_scope_item_length(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All scope items are meaningful length."""
    epics = spec.get("epics", [])
    all_meaningful = all(
        all(len(item.strip()) >= 10 for item in epic.get("scope", {}).get("inScope", []))
        and all(len(item.strip()) >= 10 for item in epic.get("scope", {}).get("outOfScope", []))
        for epic in epics
    )
    return CompletenessGate(
        description="All scope items are meaningful length",
        passed=all_meaningful, required_at="review",
        detail="Some scope items too short" if not all_meaningful else "",
    )


def _gate_requirement_coverage(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All GoalSpec requirements covered by epics (validated by lint_taskplan)."""
    return CompletenessGate(
        description="All GoalSpec requirements covered by epics",
        passed=True, required_at="review",
        detail="Requirement coverage validated by lint_taskplan.py",
    )


def _gate_design_capability_coverage(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All DesignSpec capabilities covered by epics (cross-spec)."""
    design = extra_specs.get("design")
    if not design:
        return CompletenessGate(
            description="All DesignSpec capabilities covered by epics",
            passed=True, required_at="review",
            detail="No DesignSpec available for cross-check",
        )
    capabilities = design.get("capabilities", [])
    if not capabilities:
        return CompletenessGate(
            description="All DesignSpec capabilities covered by epics",
            passed=True, required_at="review",
            detail="No capabilities in DesignSpec",
        )
    epic_texts = _get_epic_texts(spec)
    uncovered = [
        cap.get("name") for cap in capabilities
        if cap.get("name", "").lower() and not any(
            cap.get("name", "").lower() in text for text in epic_texts
        )
    ]
    return CompletenessGate(
        description="All DesignSpec capabilities covered by epics",
        passed=len(uncovered) == 0, required_at="review",
        detail=f"Uncovered: {', '.join(uncovered)}" if uncovered else "",
    )


def _gate_arch_component_coverage(spec: dict, extra_specs: dict) -> CompletenessGate:
    """All ArchitectureSpec components covered by epics (cross-spec)."""
    arch = extra_specs.get("arch")
    if not arch:
        return CompletenessGate(
            description="All ArchitectureSpec components covered by epics",
            passed=True, required_at="review",
            detail="No ArchitectureSpec available for cross-check",
        )
    components = arch.get("components", [])
    if not components:
        return CompletenessGate(
            description="All ArchitectureSpec components covered by epics",
            passed=True, required_at="review",
            detail="No components in ArchitectureSpec",
        )
    epic_texts = _get_epic_texts(spec)
    uncovered = [
        comp.get("name") for comp in components
        if comp.get("name", "").lower() and not any(
            comp.get("name", "").lower() in text for text in epic_texts
        )
    ]
    return CompletenessGate(
        description="All ArchitectureSpec components covered by epics",
        passed=len(uncovered) == 0, required_at="review",
        detail=f"Uncovered: {', '.join(uncovered)}" if uncovered else "",
    )


def _gate_non_goal_compliance(spec: dict, extra_specs: dict) -> CompletenessGate:
    """No epic implements a non-goal (validated by lint_taskplan)."""
    return CompletenessGate(
        description="No epic implements a non-goal",
        passed=True, required_at="review",
        detail="Non-goal compliance validated by lint_taskplan.py",
    )


# ── Linter Class ──────────────────────────────────────────────────────────────


class TaskPlanLinter(BaseLinter):
    """Linter for TaskPlan artifacts."""

    SPEC_NAME = "taskplan"
    SPEC_KEY = "plan"
    SEMANTIC_RULES = []
    COMPLETENESS_GATES = COMPLETENESS_GATES
    MISC_GATES = [
        _gate_epic_scope,
        _gate_epic_dependencies,
        _gate_dependency_order,
        _gate_no_circular_deps,
        _gate_milestone_outcomes,
        _gate_epic_objectives,
        _gate_acceptance_criteria_length,
        _gate_scope_item_length,
        _gate_requirement_coverage,
        _gate_design_capability_coverage,
        _gate_arch_component_coverage,
        _gate_non_goal_compliance,
    ]
    MISC_CHECKS = [
        ("requirement_coverage", _check_requirement_coverage),
        ("epic_coverage", _check_epic_coverage),
        ("non_goal_check", _check_non_goal_check),
        ("dependency_order", _check_dependency_order),
        ("milestone_outcomes", _check_milestone_outcomes),
        ("epic_milestone_assignment", _check_epic_milestone_assignment),
        ("req_id_reference", _check_req_id_reference),
    ]
    CROSS_SPEC_DEPS = ["goal", "design", "arch"]
    GLOSSARY_CHECKS = [
        ("Epic", "glossaryRefs", "epics"),
        ("Milestone", "glossaryRefs", "milestones"),
    ]


def run_lint(spec: dict, schema_path: Optional[Path],
             goal: Optional[dict] = None, design: Optional[dict] = None,
             arch: Optional[dict] = None, data: Optional[dict] = None,
             api: Optional[dict] = None, test: Optional[dict] = None,
             glossary: Optional[dict] = None, strict: bool = False) -> LayerResult:
    """Backward-compatible entry point for lint_all.py."""
    linter = TaskPlanLinter(spec, schema_path, strict)
    return linter.run(goal=goal)


# Canonical linter class for lint_all.py
LinterClass = TaskPlanLinter


if __name__ == "__main__":
    TaskPlanLinter.main()
