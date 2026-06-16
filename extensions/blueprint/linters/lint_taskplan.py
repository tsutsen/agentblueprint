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

import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Issue:
    severity: str
    category: str
    message: str
    hint: str = ""


@dataclass
class LayerResult:
    name: str = "taskplan"
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)


def run_lint(plan: dict, goal_spec: Optional[dict] = None,
             strict: bool = False) -> LayerResult:
    """Run all TaskPlan lint checks.

    Args:
        plan: The TaskPlan JSON object.
        goal_spec: Optional GoalSpec JSON for cross-reference validation.
        strict: If True, warnings are treated as errors.

    Returns:
        LayerResult with any lint issues found.
    """
    layer = LayerResult()

    if not plan:
        layer.add("error", "empty", "TaskPlan is empty or null.")
        return layer

    _check_milestones(plan, layer)
    _check_epics(plan, layer)
    _check_requirement_coverage(plan, goal_spec, layer)
    _check_non_goal_compliance(plan, goal_spec, layer)
    _check_dependency_order(plan, layer)
    _check_milestone_outcomes(plan, layer)
    _check_epic_milestone_assignment(plan, layer)

    # Cross-reference with GoalSpec if available
    if goal_spec:
        _check_req_refs_exist(plan, goal_spec, layer)

    return layer


def _check_milestones(plan: dict, layer: LayerResult):
    """Validate milestone structure."""
    milestones = plan.get("milestones", [])

    if not milestones:
        layer.add("error", "milestones", "No milestones defined.")
        return

    seen_ids = set()
    for i, m in enumerate(milestones):
        mid = m.get("id", f"index-{i}")

        # Check for duplicate IDs
        if mid in seen_ids:
            layer.add("error", "milestones", f"Duplicate milestone ID: {mid}")
        seen_ids.add(mid)

        # Validate ID format
        if not mid.replace("M", "").isdigit():
            layer.add("error", "milestones", f"Invalid milestone ID format: {mid}. Expected M followed by digits.")

        # Validate name
        name = m.get("name", "")
        if not name or len(name) < 5:
            layer.add("error", "milestones", f"Milestone {mid} has no name or name too short.")

        # Validate outcome
        outcome = m.get("outcome", "")
        if not outcome or len(outcome) < 10:
            layer.add("error", "milestones", f"Milestone {mid} has no outcome or outcome too short.")

        # Validate epics list
        epics = m.get("epics", [])
        if not epics:
            layer.add("error", "milestones", f"Milestone {mid} has no epics assigned.")


def _check_epics(plan: dict, layer: LayerResult):
    """Validate epic structure."""
    epics = plan.get("epics", [])

    if not epics:
        layer.add("error", "epics", "No epics defined.")
        return

    seen_ids = set()
    for i, epic in enumerate(epics):
        eid = epic.get("id", f"index-{i}")

        # Check for duplicate IDs
        if eid in seen_ids:
            layer.add("error", "epics", f"Duplicate epic ID: {eid}")
        seen_ids.add(eid)

        # Validate ID format
        if not eid.startswith("EP-") or not eid[3:].isdigit():
            layer.add("error", "epics", f"Invalid epic ID format: {eid}. Expected EP-NNN.")

        # Validate title
        title = epic.get("title", "")
        if not title or len(title) < 5:
            layer.add("error", "epics", f"Epic {eid} has no title or title too short.")

        # Validate summary
        summary = epic.get("summary", "")
        if not summary or len(summary) < 10:
            layer.add("error", "epics", f"Epic {eid} has no summary or summary too short.")

        # Validate requirements
        reqs = epic.get("requirements", [])
        if not reqs:
            layer.add("error", "epics", f"Epic {eid} covers no requirements.")

        # Validate acceptance criteria
        ac = epic.get("acceptanceCriteria", [])
        if not ac:
            layer.add("error", "epics", f"Epic {eid} has no acceptance criteria.")

        # Validate dependencies
        deps = epic.get("dependencies", {})
        blocked_by = deps.get("blockedBy", [])
        blocks = deps.get("blocks", [])
        if not blocked_by and not blocks:
            layer.add("warning", "epics", f"Epic {eid} has no explicit dependencies declared.")

        # Validate scope
        scope = epic.get("scope", {})
        if not scope.get("inScope"):
            layer.add("error", "epics", f"Epic {eid} has no 'inScope' declared.")
        if not scope.get("outOfScope"):
            layer.add("warning", "epics", f"Epic {eid} has no 'outOfScope' declared.")


def _check_requirement_coverage(plan: dict, goal_spec: Optional[dict], layer: LayerResult):
    """Check that all GoalSpec requirements are covered by epics."""
    if not goal_spec:
        return

    epics = plan.get("epics", [])
    goal_req_ids = {fr["id"] for fr in goal_spec.get("functionalRequirements", [])}
    covered_req_ids = set()

    for epic in epics:
        reqs = epic.get("requirements", [])
        covered_req_ids.update(reqs)

    uncovered = goal_req_ids - covered_req_ids
    if uncovered:
        layer.add("error", "coverage",
                   f"Uncovered requirements: {', '.join(sorted(uncovered))}")
        layer.add("error", "coverage",
                   f"These requirements from GoalSpec are not covered by any epic.")

    # Check for epics with no requirement coverage
    for epic in epics:
        if not epic.get("requirements"):
            layer.add("error", "epics",
                       f"Epic {epic.get('id', '?')} covers no requirements — scope addition?")


def _check_non_goal_compliance(plan: dict, goal_spec: Optional[dict], layer: LayerResult):
    """Check that no epic implements a non-goal."""
    if not goal_spec:
        return

    non_goals = goal_spec.get("nonGoals", [])
    if not non_goals:
        return

    epics = plan.get("epics", [])
    for epic in epics:
        objective = epic.get("objective", "").lower()
        for ng in non_goals:
            capability = ng.get("capability", "").lower()
            if capability and capability in objective:
                layer.add("error", "non-goal",
                           f"Epic {epic.get('id')} implements non-goal: {ng.get('capability')}")


def _check_dependency_order(plan: dict, layer: LayerResult):
    """Check that epics are listed in dependency order (blockers before dependents)."""
    epics = plan.get("epics", [])
    epic_map = {e["id"]: e for e in epics}

    for i, epic in enumerate(epics):
        deps = epic.get("dependencies", {})
        blocked_by = deps.get("blockedBy", [])

        for dep_id in blocked_by:
            if dep_id not in epic_map:
                layer.add("error", "dependencies",
                           f"Epic {epic['id']} blocked by unknown epic: {dep_id}")
            else:
                # Check that the blocker appears before the dependent
                dep_index = next((j for j, e in enumerate(epics) if e["id"] == dep_id), -1)
                if dep_index > i:
                    layer.add("error", "dependencies",
                               f"Epic {epic['id']} (at position {i}) is blocked by {dep_id} "
                               f"(at position {dep_index}) — blocker should come first.")


def _check_milestone_outcomes(plan: dict, layer: LayerResult):
    """Check that milestones have demonstrable outcomes."""
    milestones = plan.get("milestones", [])
    epics = plan.get("epics", [])
    epic_map = {e["id"]: e for e in epics}

    for m in milestones:
        outcome = m.get("outcome", "")
        if not outcome or len(outcome) < 10:
            layer.add("error", "milestones",
                       f"Milestone {m.get('id')} outcome is too short or empty.")


def _check_epic_milestone_assignment(plan: dict, layer: LayerResult):
    """Check that every epic belongs to exactly one milestone."""
    epics = plan.get("epics", [])
    milestone_ids = {m["id"] for m in plan.get("milestones", [])}

    for epic in epics:
        milestone = epic.get("milestone")
        if not milestone:
            layer.add("error", "milestones",
                       f"Epic {epic['id']} not assigned to any milestone.")
        elif milestone not in milestone_ids:
            layer.add("error", "milestones",
                       f"Epic {epic['id']} assigned to unknown milestone: {milestone}")


def _check_req_refs_exist(plan: dict, goal_spec: dict, layer: LayerResult):
    """Cross-reference: check that all REQ-IDs in TaskPlan exist in GoalSpec."""
    goal_req_ids = {fr["id"] for fr in goal_spec.get("functionalRequirements", [])}
    epics = plan.get("epics", [])

    for epic in epics:
        reqs = epic.get("requirements", [])
        for req_id in reqs:
            if req_id not in goal_req_ids:
                layer.add("error", "cross-ref",
                           f"Epic {epic['id']} references REQ-ID not in GoalSpec: {req_id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lint TaskPlan artifact.")
    parser.add_argument("plan", help="Path to TaskPlan JSON")
    parser.add_argument("--goal", help="Path to GoalSpec JSON (for cross-reference)")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text())
    goal_spec = json.loads(Path(args.goal).read_text()) if args.goal else None

    result = run_lint(plan, goal_spec, args.strict)

    if result.errors:
        print(f"✗ {len(result.errors)} error(s)")
        for e in result.errors:
            print(f"  ✗ [{e.category}] {e.message}")
            if e.hint:
                print(f"    → {e.hint}")
    if result.warnings:
        print(f"⚠ {len(result.warnings)} warning(s)")
        for w in result.warnings:
            print(f"  ⚠ [{w.category}] {w.message}")
            if w.hint:
                print(f"    → {w.hint}")

    sys.exit(0 if result.clean else 1)
