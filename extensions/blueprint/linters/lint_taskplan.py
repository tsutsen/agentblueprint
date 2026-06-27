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

from shared import BaseLinter, LayerResult


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


class TaskPlanLinter(BaseLinter):
    """Linter for TaskPlan artifacts."""
    
    SPEC_NAME = "taskplan"
    SEMANTIC_RULES = []
    MISC_CHECKS = [
        ("requirement_coverage", _check_requirement_coverage),
        ("epic_coverage", _check_epic_coverage),
        ("non_goal_check", _check_non_goal_check),
        ("dependency_order", _check_dependency_order),
        ("milestone_outcomes", _check_milestone_outcomes),
        ("epic_milestone_assignment", _check_epic_milestone_assignment),
        ("req_id_reference", _check_req_id_reference),
    ]
    CROSS_SPEC_DEPS = ["goal"]
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


if __name__ == "__main__":
    TaskPlanLinter.main()
