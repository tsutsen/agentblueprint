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


def _check_self_referencing_dependencies(plan: dict, layer: LayerResult):
    """Warn if an epic lists itself as a dependency."""
    epics = plan.get("epics", [])
    for epic in epics:
        eid = epic["id"]
        deps = epic.get("dependencies", {})
        if eid in deps.get("blockedBy", []):
            layer.add("error", "self-dependency",
                       f"Epic {eid} lists itself as blockedBy.")
        if eid in deps.get("blocks", []):
            layer.add("error", "self-dependency",
                       f"Epic {eid} lists itself as blocks.")


def _check_unknown_blocked_by(plan: dict, layer: LayerResult):
    """Warn if blockedBy references an epic not in the plan."""
    epics = plan.get("epics", [])
    epic_ids = {e["id"] for e in epics}
    for epic in epics:
        for dep_id in epic.get("dependencies", {}).get("blockedBy", []):
            if dep_id not in epic_ids:
                layer.add("error", "unknown-dependency",
                           f"Epic {epic['id']} blocked by unknown epic: {dep_id}")


def _check_unknown_blocks(plan: dict, layer: LayerResult):
    """Warn if blocks references an epic not in the plan."""
    epics = plan.get("epics", [])
    epic_ids = {e["id"] for e in epics}
    for epic in epics:
        for dep_id in epic.get("dependencies", {}).get("blocks", []):
            if dep_id not in epic_ids:
                layer.add("error", "unknown-dependency",
                           f"Epic {epic['id']} blocks unknown epic: {dep_id}")


def _check_duplicate_milestone_name(plan: dict, layer: LayerResult):
    """Warn if two milestones share the same name."""
    milestones = plan.get("milestones", [])
    names = {}
    for m in milestones:
        name = m.get("name", "")
        if name in names:
            layer.add("warning", "duplicate-milestone-name",
                       f"Duplicate milestone name: '{name}' ({names[name]} and {m['id']})")
        else:
            names[name] = m["id"]


def _check_duplicate_milestone_outcome(plan: dict, layer: LayerResult):
    """Warn if two milestones have identical outcomes."""
    milestones = plan.get("milestones", [])
    outcomes = {}
    for m in milestones:
        outcome = m.get("outcome", "")
        if outcome in outcomes:
            layer.add("warning", "duplicate-milestone-outcome",
                       f"Duplicate milestone outcome: '{outcome[:50]}...' ({outcomes[m['id']]} and {m['id']})")
        else:
            outcomes[outcome] = m["id"]


def _check_duplicate_epic_title(plan: dict, layer: LayerResult):
    """Warn if two epics have identical titles."""
    epics = plan.get("epics", [])
    titles = {}
    for epic in epics:
        title = epic.get("title", "")
        if title in titles:
            layer.add("warning", "duplicate-epic-title",
                       f"Duplicate epic title: '{title}' ({titles[title]} and {epic['id']})")
        else:
            titles[title] = epic["id"]


def _check_acceptance_criteria_length(plan: dict, layer: LayerResult):
    """Warn if acceptance criteria are too short to be meaningful."""
    epics = plan.get("epics", [])
    for epic in epics:
        for i, ac in enumerate(epic.get("acceptanceCriteria", [])):
            if len(ac.strip()) < 15:
                layer.add("warning", "ac-length",
                           f"Epic {epic['id']} AC #{i+1}: too short ({len(ac.strip())} chars).",
                           hint="Acceptance criteria should be specific and measurable.")


def _check_scope_item_length(plan: dict, layer: LayerResult):
    """Warn if scope items are too short to be meaningful."""
    epics = plan.get("epics", [])
    for epic in epics:
        scope = epic.get("scope", {})
        for i, item in enumerate(scope.get("inScope", [])):
            if len(item.strip()) < 10:
                layer.add("warning", "scope-length",
                           f"Epic {epic['id']} inScope #{i+1}: too short ({len(item.strip())} chars).")
        for i, item in enumerate(scope.get("outOfScope", [])):
            if len(item.strip()) < 10:
                layer.add("warning", "scope-length",
                           f"Epic {epic['id']} outOfScope #{i+1}: too short ({len(item.strip())} chars).")


def _check_epic_objective(plan: dict, layer: LayerResult):
    """Warn if an epic has no objective field."""
    epics = plan.get("epics", [])
    for epic in epics:
        if not epic.get("objective"):
            layer.add("warning", "missing-objective",
                       f"Epic {epic['id']} has no objective field.")


def _check_duplicate_epic_requirements(plan: dict, layer: LayerResult):
    """Warn when multiple epics cover the same requirements.

    While some overlap is acceptable (e.g., cross-cutting concerns),
    significant overlap may indicate redundant epics.
    """
    epics = plan.get("epics", [])
    req_to_epics = {}

    for epic in epics:
        for req_id in epic.get("requirements", []):
            req_to_epics.setdefault(req_id, []).append(epic["id"])

    for req_id, epic_ids in req_to_epics.items():
        if len(epic_ids) > 1:
            layer.add("warning", "duplicate-requirements",
                       f"Requirement {req_id} is covered by multiple epics: {', '.join(epic_ids)}",
                       hint="If this is intentional (cross-cutting concern), ignore. Otherwise, consolidate.")


def _check_milestone_epic_count(plan: dict, layer: LayerResult):
    """Warn if a milestone has too few or too many epics.

    A milestone with < 1 epic is an error (already caught elsewhere).
    A milestone with > 10 epics may be too large to deliver in one milestone.
    """
    milestones = plan.get("milestones", [])
    for m in milestones:
        epics = m.get("epics", [])
        if len(epics) > 10:
            layer.add("warning", "milestone-size",
                       f"Milestone {m['id']} has {len(epics)} epics — consider splitting.",
                       hint="Large milestones are hard to track and deliver value incrementally.")


def _check_epic_id_sequential(plan: dict, layer: LayerResult):
    """Warn if epic IDs are not sequential (e.g., EP-001, EP-003 missing EP-002)."""
    import re
    epics = plan.get("epics", [])
    ids = []
    for epic in epics:
        eid = epic.get("id", "")
        match = re.match(r"^EP-(\d+)$", eid)
        if match:
            ids.append(int(match.group(1)))

    if ids:
        expected = set(range(min(ids), max(ids) + 1))
        actual = set(ids)
        missing = expected - actual
        if missing:
            layer.add("warning", "id-sequence",
                       f"Missing epic IDs: {', '.join(f'EP-{n:03d}' for n in sorted(missing))}",
                       hint="Epic IDs should be sequential with no gaps.")


def _check_milestone_id_sequential(plan: dict, layer: LayerResult):
    """Warn if milestone IDs are not sequential (e.g., M1, M3 missing M2)."""
    import re
    milestones = plan.get("milestones", [])
    ids = []
    for m in milestones:
        mid = m.get("id", "")
        match = re.match(r"^M(\d+)$", mid)
        if match:
            ids.append(int(match.group(1)))

    if ids:
        expected = set(range(min(ids), max(ids) + 1))
        actual = set(ids)
        missing = expected - actual
        if missing:
            layer.add("warning", "id-sequence",
                       f"Missing milestone IDs: {', '.join(f'M{n}' for n in sorted(missing))}",
                       hint="Milestone IDs should be sequential with no gaps.")


def _check_epic_file_exists(plan: dict, layer: LayerResult):
    """Check that epic files exist at the expected paths."""
    import os
    epics = plan.get("epics", [])
    for epic in epics:
        file_path = epic.get("filePath", "")
        if file_path and not os.path.isfile(file_path):
            layer.add("error", "file-exists",
                       f"Epic {epic['id']}: file '{file_path}' does not exist.")


def _check_acceptance_criteria_quality(plan: dict, layer: LayerResult):
    """Check that acceptance criteria are verifiable and specific.

    Warns if criteria contain vague words like 'correctly', 'properly', 'efficiently',
    or describe implementation instead of behaviour.
    """
    vague_words = ["correctly", "properly", "efficiently", "well", "smoothly",
                   "robust", "intuitively", "seamlessly"]
    implementation_words = ["implement", "write", "create", "build", "code",
                           "use", "add", "install", "configure"]

    epics = plan.get("epics", [])
    for epic in epics:
        eid = epic.get("id", "?")
        for i, ac in enumerate(epic.get("acceptanceCriteria", [])):
            ac_lower = ac.lower()
            # Check for vague words
            for word in vague_words:
                if word in ac_lower:
                    layer.add("warning", "ac-quality",
                               f"Epic {eid} AC #{i+1}: contains vague word '{word}'. "
                               f"Make it measurable.",
                               hint="Replace with measurable outcome, e.g. 'User receives error within 2s'.")
                    break
            # Check for implementation language
            for word in implementation_words:
                if word in ac_lower and "should" not in ac_lower and "must" not in ac_lower:
                    layer.add("warning", "ac-quality",
                               f"Epic {eid} AC #{i+1}: describes implementation, not behaviour.",
                               hint="Describe what the user can do, not how it's built.")
                    break


def _check_title_action_oriented(plan: dict, layer: LayerResult):
    """Check that epic titles are action-oriented, not technical layer descriptions.

    Warns if title looks like a single technical task (e.g. 'Write database migrations',
    'Implement parser', 'Set up infrastructure').
    """
    technical_patterns = [
        r"(write|implement|create|build|set up|configure|install|add)\s+(all\s+)?(database|schema|migration|parser|infra|framework|library|module|class|function|endpoint|api)",
        r"database\s+(migration|schema|setup)",
        r"infrastructure\s+(setup|config|deployment)",
        r"(set up|configure|install)\s+(the\s+)?(server|database|infra|framework)",
    ]
    import re
    epics = plan.get("epics", [])
    for epic in epics:
        title = epic.get("title", "")
        for pattern in technical_patterns:
            if re.search(pattern, title.lower()):
                layer.add("warning", "title-action",
                           f"Epic {epic['id']}: title appears to describe a technical layer, not a capability.",
                           hint="Reframe as user-facing capability, e.g. 'Enable document upload' instead of 'Write database migrations'.")
                break


def _check_outofscope_specificity(plan: dict, layer: LayerResult):
    """Check that outOfScope items are specific, not vague.

    Warns if outOfScope contains vague phrases like 'advanced features', 'future work',
    'nice to have', 'later', etc.
    """
    vague_phrases = [
        "advanced", "future", "nice to have", "later", "pending", "tbd",
        "todo", "to be determined", "as needed", "when ready", "eventually",
        "someday", "backlog", "roadmap", "phase 2", "v2", "version 2",
    ]
    epics = plan.get("epics", [])
    for epic in epics:
        eid = epic.get("id", "?")
        scope = epic.get("scope", {})
        for item in scope.get("outOfScope", []):
            item_lower = item.lower()
            for phrase in vague_phrases:
                if phrase in item_lower:
                    layer.add("warning", "scope-specific",
                               f"Epic {eid} outOfScope: '{item}' is vague.",
                               hint="Be specific about what is deferred, e.g. 'Batch upload of >10 files' instead of 'Advanced features'.")
                    break


def _check_milestone_epic_consistency(plan: dict, layer: LayerResult):
    """Check that milestone epic lists match each epic's milestone field.

    If milestone M1 lists EP-001, then EP-001's milestone field must be M1.
    """
    milestones = plan.get("milestones", [])
    epics = plan.get("epics", [])

    # Build expected mapping: milestone_id -> set of epic_ids
    milestone_epics = {}
    for m in milestones:
        mid = m["id"]
        milestone_epics[mid] = set(m.get("epics", []))

    # Check each epic's milestone field
    for epic in epics:
        eid = epic["id"]
        epic_milestone = epic.get("milestone")
        if not epic_milestone:
            continue  # Already caught by _check_epic_milestone_assignment

        # Check that this epic is listed in its milestone's epic list
        if epic_milestone in milestone_epics:
            if eid not in milestone_epics[epic_milestone]:
                layer.add("error", "milestone-consistency",
                           f"Epic {eid} has milestone '{epic_milestone}' but that milestone doesn't list it.")

        # Check that each epic in the milestone has the correct milestone field
        for listed_eid in milestone_epics.get(epic_milestone, []):
            listed_epic = next((e for e in epics if e["id"] == listed_eid), None)
            if listed_epic and listed_epic.get("milestone") != epic_milestone:
                layer.add("error", "milestone-consistency",
                           f"Milestone {epic_milestone} lists {listed_eid}, but {listed_eid}'s milestone is '{listed_epic.get('milestone')}'.")


def _check_circular_dependencies(plan: dict, layer: LayerResult):
    """Detect circular dependencies among epics.

    Uses DFS to find cycles in the dependency graph.
    """
    epics = plan.get("epics", [])
    epic_map = {e["id"]: e for e in epics}

    # Build adjacency list: epic -> epics it depends on
    graph = {}
    for epic in epics:
        eid = epic["id"]
        deps = epic.get("dependencies", {}).get("blockedBy", [])
        graph[eid] = [d for d in deps if d in epic_map]

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {eid: WHITE for eid in graph}
    path = []

    def dfs(node):
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, []):
            if color[neighbor] == GRAY:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                layer.add("error", "circular-dependency",
                           f"Circular dependency detected: {' → '.join(cycle)}")
                return True
            elif color[neighbor] == WHITE:
                if dfs(neighbor):
                    return True
        path.pop()
        color[node] = BLACK
        return False

    for eid in graph:
        if color[eid] == WHITE:
            if dfs(eid):
                break  # Report first cycle only


def _check_cross_spec_coverage(plan: dict, goal_spec: Optional[dict],
                                design_spec: Optional[dict],
                                arch_spec: Optional[dict],
                                data_spec: Optional[dict],
                                api_spec: Optional[dict],
                                test_spec: Optional[dict],
                                layer: LayerResult):
    """Check that epics cover requirements from all specs, not just GoalSpec."""
    epics = plan.get("epics", [])

    # Collect all covered REQ-IDs
    covered_reqs = set()
    for epic in epics:
        covered_reqs.update(epic.get("requirements", []))

    # Check non-functional requirements from GoalSpec
    if goal_spec:
        nfrs = goal_spec.get("nonFunctionalRequirements", [])
        for nfr in nfrs:
            nfr_id = nfr.get("id", "")
            if nfr_id and nfr_id not in covered_reqs:
                # Check if it's referenced under a different naming convention
                layer.add("warning", "nfr-coverage",
                           f"Non-functional requirement {nfr_id} is not covered by any epic.")

    # Check DesignSpec capabilities
    if design_spec:
        capabilities = design_spec.get("capabilities", [])
        for cap in capabilities:
            cap_name = cap.get("name", "").lower()
            if not cap_name:
                continue
            # Check if capability name appears in any epic title or summary
            found = False
            for epic in epics:
                title = epic.get("title", "").lower()
                summary = epic.get("summary", "").lower()
                objective = epic.get("objective", "").lower()
                if cap_name in title or cap_name in summary or cap_name in objective:
                    found = True
                    break
            if not found:
                layer.add("warning", "cross-spec-coverage",
                           f"DesignSpec capability '{cap.get('name')}' may not be covered by any epic.")

    # Check ArchitectureSpec components
    if arch_spec:
        components = arch_spec.get("components", [])
        for comp in components:
            comp_name = comp.get("name", "").lower()
            if not comp_name:
                continue
            found = False
            for epic in epics:
                title = epic.get("title", "").lower()
                summary = epic.get("summary", "").lower()
                objective = epic.get("objective", "").lower()
                if comp_name in title or comp_name in summary or comp_name in objective:
                    found = True
                    break
            if not found:
                layer.add("warning", "cross-spec-coverage",
                           f"ArchitectureSpec component '{comp.get('name')}' may not be covered by any epic.")

    # Check DataSpec entities
    if data_spec:
        entities = data_spec.get("entities", [])
        entity_names = {e.get("name", "").lower() for e in entities}
        for ename in entity_names:
            if not ename:
                continue
            found = False
            for epic in epics:
                title = epic.get("title", "").lower()
                summary = epic.get("summary", "").lower()
                objective = epic.get("objective", "").lower()
                if ename in title or ename in summary or ename in objective:
                    found = True
                    break
            if not found:
                layer.add("warning", "cross-spec-coverage",
                           f"DataSpec entity '{ename}' may not be covered by any epic.")

    # Check ApiSpec endpoints
    if api_spec:
        functions = api_spec.get("functions", [])
        for fn in functions:
            fn_id = fn.get("id", "").lower()
            fn_name = fn.get("name", "").lower()
            if not fn_name:
                continue
            found = False
            for epic in epics:
                title = epic.get("title", "").lower()
                summary = epic.get("summary", "").lower()
                objective = epic.get("objective", "").lower()
                if fn_name in title or fn_name in summary or fn_name in objective:
                    found = True
                    break
            if not found:
                layer.add("warning", "cross-spec-coverage",
                           f"ApiSpec function '{fn.get('id')}' may not be covered by any epic.")

    # Check TestSpec scenarios
    if test_spec:
        scenarios = test_spec.get("scenarios", [])
        for scenario in scenarios:
            scenario_desc = scenario.get("description", "").lower()
            if not scenario_desc:
                continue
            # Extract key terms from scenario description
            words = set(w for w in scenario_desc.split() if len(w) > 4)
            found = False
            for word in words:
                for epic in epics:
                    title = epic.get("title", "").lower()
                    summary = epic.get("summary", "").lower()
                    objective = epic.get("objective", "").lower()
                    if word in title or word in summary or word in objective:
                        found = True
                        break
                if found:
                    break
            if not found:
                layer.add("warning", "cross-spec-coverage",
                           f"TestSpec scenario may not be covered by any epic: '{scenario.get('description', '')[:80]}...'")


def _check_epic_glossary_refs(plan: dict, glossary: Optional[dict], layer: LayerResult):
    """Check that epics link domain concepts to glossary terms.

    Checks epic titles and objectives for glossary references.
    Skips generic actor terms (User, System) to avoid noise.
    """
    if not glossary:
        return

    # Build glossary term map (lowercase -> id)
    glossary_lower = {}
    for t in glossary.get("terms", []):
        glossary_lower[t["term"].lower()] = t["id"]

    # Generic actors that appear everywhere — skip from "has domain concept" check
    skip_terms = {"user", "system"}

    def has_domain_concept(text: str) -> bool:
        """Check if text contains glossary terms (excluding generic actors)."""
        text_lower = text.lower()
        for term in glossary_lower:
            if term in skip_terms:
                continue
            if len(term) > 3 and term in text_lower:
                return True
        return False

    def find_glossary_refs(text: str) -> list:
        """Find glossary term IDs referenced in text (excluding generic actors)."""
        text_lower = text.lower()
        refs = []
        for term, tid in glossary_lower.items():
            if term in skip_terms:
                continue
            if len(term) > 3 and term in text_lower:
                refs.append(tid)
        return refs

    for epic in plan.get("epics", []):
        eid = epic.get("id", "?")

        # Check title
        title = epic.get("title", "")
        if title and has_domain_concept(title):
            refs = epic.get("glossaryRefs", [])
            if not refs:
                # Find what refs should be there
                expected_refs = find_glossary_refs(title)
                layer.add("warning", "title_no_glossary_refs",
                           f"Epic {eid} title '{title}' references glossary terms "
                           f"({', '.join(expected_refs)}) but has no glossaryRefs.",
                           hint="Add glossaryRefs (GL-NNN) for domain concepts in this epic's title.")

        # Check objective
        objective = epic.get("objective", "")
        if objective and has_domain_concept(objective):
            refs = epic.get("glossaryRefs", [])
            if not refs:
                expected_refs = find_glossary_refs(objective)
                layer.add("warning", "objective_no_glossary_refs",
                           f"Epic {eid} objective references glossary terms "
                           f"({', '.join(expected_refs)}) but has no glossaryRefs.",
                           hint="Add glossaryRefs (GL-NNN) for domain concepts in this epic's objective.")


def run_lint(plan: dict, goal_spec: Optional[dict] = None,
             design_spec: Optional[dict] = None,
             arch_spec: Optional[dict] = None,
             data_spec: Optional[dict] = None,
             api_spec: Optional[dict] = None,
             test_spec: Optional[dict] = None,
             glossary: Optional[dict] = None,
             strict: bool = False) -> LayerResult:
    """Run all TaskPlan lint checks.

    Args:
        plan: The TaskPlan JSON object.
        goal_spec: Optional GoalSpec JSON for cross-reference validation.
        design_spec: Optional DesignSpec JSON for capability coverage.
        arch_spec: Optional ArchitectureSpec JSON for component coverage.
        data_spec: Optional DataSpec JSON for entity coverage.
        api_spec: Optional ApiSpec JSON for endpoint coverage.
        test_spec: Optional TestSpec JSON for scenario coverage.
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
    _check_epic_file_exists(plan, layer)
    _check_acceptance_criteria_quality(plan, layer)
    _check_title_action_oriented(plan, layer)
    _check_outofscope_specificity(plan, layer)
    _check_milestone_epic_consistency(plan, layer)
    _check_circular_dependencies(plan, layer)
    _check_epic_objective(plan, layer)
    _check_duplicate_epic_requirements(plan, layer)
    _check_milestone_epic_count(plan, layer)

    # Cross-reference with GoalSpec if available
    if goal_spec:
        _check_req_refs_exist(plan, goal_spec, layer)

    # Cross-spec coverage check
    _check_cross_spec_coverage(plan, goal_spec, design_spec, arch_spec,
                               data_spec, api_spec, test_spec, layer)

    # Glossary reference checks
    _check_epic_glossary_refs(plan, glossary, layer)

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
    """Check that no epic implements a non-goal.

    Uses word-boundary matching to reduce false positives.
    A non-goal like 'real-time processing' won't match
    'batch processing with real-time monitoring' because
    the full phrase 'real-time processing' doesn't appear.
    """
    if not goal_spec:
        return

    non_goals = goal_spec.get("nonGoals", [])
    if not non_goals:
        return

    import re
    epics = plan.get("epics", [])
    for epic in epics:
        objective = epic.get("objective", "").lower()
        for ng in non_goals:
            capability = ng.get("capability", "").lower()
            if capability and re.search(r'\b' + re.escape(capability) + r'\b', objective):
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
    parser.add_argument("--design", help="Path to DesignSpec JSON (for capability coverage)")
    parser.add_argument("--arch", help="Path to ArchitectureSpec JSON (for component coverage)")
    parser.add_argument("--data", help="Path to DataSpec JSON (for entity coverage)")
    parser.add_argument("--api", help="Path to ApiSpec JSON (for endpoint coverage)")
    parser.add_argument("--test", help="Path to TestSpec JSON (for scenario coverage)")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text())
    goal_spec = json.loads(Path(args.goal).read_text()) if args.goal else None
    design_spec = json.loads(Path(args.design).read_text()) if args.design else None
    arch_spec = json.loads(Path(args.arch).read_text()) if args.arch else None
    data_spec = json.loads(Path(args.data).read_text()) if args.data else None
    api_spec = json.loads(Path(args.api).read_text()) if args.api else None
    test_spec = json.loads(Path(args.test).read_text()) if args.test else None

    result = run_lint(plan, goal_spec, design_spec, arch_spec, data_spec,
                      api_spec, test_spec, args.strict)

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
