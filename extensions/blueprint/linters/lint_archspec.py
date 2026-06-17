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
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str
    category: str
    message: str
    hint: str = ""


@dataclass
class LintResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    def add(self, severity: str, category: str, message: str, hint: str = ""):
        issue = Issue(severity, category, message, hint)
        if severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)

    @property
    def clean(self) -> bool:
        return len(self.errors) == 0

    @property
    def all_issues(self):
        return self.errors + self.warnings


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_duplicates(ids: list[str], label: str, result: LintResult):
    seen = set()
    for id_ in ids:
        if id_ in seen:
            result.add("error", "duplicate_id",
                f"Duplicate {label} id '{id_}'.",
                hint=f"Each {label} must have a unique identifier.")
        seen.add(id_)


def detect_cycle(graph: dict[str, list[str]]) -> Optional[list[str]]:
    """Return a cycle path if one exists in the dependency graph, else None."""
    visited = set()
    path = []

    def dfs(node):
        if node in path:
            return path[path.index(node):]
        if node in visited:
            return None
        visited.add(node)
        path.append(node)
        for dep in graph.get(node, []):
            cycle = dfs(dep)
            if cycle:
                return cycle
        path.pop()
        return None

    for node in graph:
        if node not in visited:
            cycle = dfs(node)
            if cycle:
                return cycle
    return None


# ── Checks ────────────────────────────────────────────────────────────────────

def check_project_match(spec: dict, goal: dict, result: LintResult):
    if spec["project"] != goal["project"]:
        result.add("error", "project_match",
            f"Project mismatch: archspec='{spec['project']}' goalspec='{goal['project']}'.",
            hint="Both specs must have identical 'project' values.")


def check_version_pins(spec: dict, goal: dict, result: LintResult):
    pinned = spec.get("goalSpecVersion")
    if pinned and pinned != goal["version"]:
        result.add("error", "version_drift",
            f"archspec.goalSpecVersion='{pinned}' does not match goalspec.version='{goal['version']}'.",
            hint="Re-review architecture against updated GoalSpec, then update goalSpecVersion.")


def check_components(spec: dict, result: LintResult) -> set[str]:
    components = spec.get("components", [])
    ids = [c["id"] for c in components]
    check_duplicates(ids, "component", result)
    component_ids = set(ids)

    # Build dependency graph for cycle detection
    dep_graph: dict[str, list[str]] = {}
    for comp in components:
        cid = comp["id"]
        deps = comp.get("dependencies", [])
        dep_graph[cid] = deps

        # Dependency references must exist
        for dep in deps:
            if dep not in component_ids:
                result.add("error", "dependency_ref",
                    f"Component '{cid}': dependency '{dep}' is not a defined component.",
                    hint=f"Add a component with id='{dep}' or correct the dependency reference.")

        # Warn: component with no reqRefs at non-draft status
        if not comp.get("reqRefs") and spec.get("status") in ("review", "confirmed"):
            result.add("warning", "component_no_reqs",
                f"Component '{cid}' has no reqRefs.",
                hint="Link each component to the requirements it helps satisfy.")

    # Circular dependency check
    cycle = detect_cycle(dep_graph)
    if cycle:
        result.add("error", "circular_dependency",
            f"Circular component dependency detected: {' → '.join(cycle + [cycle[0]])}.",
            hint="Refactor to break the cycle — introduce an abstraction or invert a dependency.")

    # Overlapping responsibilities
    all_responsibilities: dict[str, str] = {}  # responsibility → first component that claimed it
    for comp in components:
        for resp in comp.get("responsibilities", []):
            resp_norm = resp.strip().lower().rstrip(".")
            if resp_norm in all_responsibilities:
                result.add("warning", "overlapping_responsibility",
                    f"Component '{comp['id']}' responsibility '{resp}' "
                    f"is identical or near-identical to one claimed by '{all_responsibilities[resp_norm]}'.",
                    hint="Each responsibility must be owned by exactly one component.")
            else:
                all_responsibilities[resp_norm] = comp["id"]

    return component_ids


def check_subsystems(spec: dict, component_ids: set[str], result: LintResult):
    subsystems = spec.get("overview", {}).get("subsystems", [])
    all_comp_refs = []
    comp_to_subs: dict[str, list[str]] = {}

    for sub in subsystems:
        refs = sub.get("componentRefs", [])
        
        # Check for empty subsystem
        if not refs:
            result.add("warning", "subsystem_empty",
                f"Subsystem '{sub['name']}' has no components assigned.",
                hint="Assign components to this subsystem or remove it.")
        
        for ref in refs:
            if ref not in component_ids:
                result.add("error", "subsystem_ref",
                    f"Subsystem '{sub['name']}': componentRef '{ref}' is not a defined component.",
                    hint=f"Add a component with id='{ref}' or correct the reference.")
            all_comp_refs.append(ref)
            comp_to_subs.setdefault(ref, []).append(sub["name"])

    # Warn: components not assigned to any subsystem
    for cid in component_ids:
        if cid not in all_comp_refs:
            result.add("warning", "component_no_subsystem",
                f"Component '{cid}' is not assigned to any subsystem.",
                hint="Assign every component to a subsystem in overview.subsystems.")
    
    # Warn: component assigned to multiple subsystems
    for comp, subs in comp_to_subs.items():
        if len(subs) > 1:
            result.add("warning", "subsystem_overlap",
                f"Component '{comp}' is assigned to multiple subsystems: {', '.join(subs)}.",
                hint="Each component should belong to exactly one subsystem.")


def check_data_flows(spec: dict, component_ids: set[str], result: LintResult):
    flows = spec.get("dataFlow", [])
    ids = [f["id"] for f in flows]
    check_duplicates(ids, "dataFlow", result)

    for flow in flows:
        fid = flow["id"]
        steps = flow.get("steps", [])

        for i, step in enumerate(steps):
            ref = step.get("componentRef")
            if ref and ref not in component_ids:
                result.add("error", "flow_component_ref",
                    f"Flow '{fid}' step {i+1}: componentRef '{ref}' is not a defined component.",
                    hint=f"Add a component with id='{ref}' or correct the reference.")

        # Flow with only one step is not a flow
        if len(steps) < 2:
            result.add("error", "flow_too_short",
                f"Flow '{fid}' has fewer than 2 steps — not a valid flow.",
                hint="A data flow must show at least a source and a sink step.")


def check_constraints(spec: dict, result: LintResult):
    constraints = spec.get("constraints", [])
    ids = [c["id"] for c in constraints]
    check_duplicates(ids, "constraint", result)

    # Implementation smells in constraints
    impl_smells = ["postgres", "mysql", "redis", "sqlite", "mongodb", "fastapi",
                   "flask", "django", "docker", "kubernetes", "s3", "lambda",
                   "python", "typescript", "rust", "golang", "java"]
    for con in constraints:
        desc_lower = con.get("description", "").lower()
        found = [s for s in impl_smells if s in desc_lower]
        if found:
            result.add("warning", "constraint_implementation_leak",
                f"{con['id']}: constraint mentions specific technology: {found}.",
                hint="Constraints should describe what is required, not which technology satisfies it.")


def check_req_nfr_refs(spec: dict, goal: Optional[dict], result: LintResult):
    """Resolve all REQ/NFR refs across components, flows, and constraints against GoalSpec."""
    if not goal:
        return

    goal_req_ids = {r["id"] for r in goal.get("functionalRequirements", [])}
    goal_nfr_ids = {r["id"] for r in goal.get("nonFunctionalRequirements", [])}

    def check_req(ref: str, source: str):
        if ref not in goal_req_ids:
            result.add("error", "req_ref_missing",
                f"{source}: REQ ref '{ref}' not found in GoalSpec.",
                hint=f"Add '{ref}' to GoalSpec functionalRequirements or correct the reference.")

    def check_nfr(ref: str, source: str):
        if ref not in goal_nfr_ids:
            result.add("error", "nfr_ref_missing",
                f"{source}: NFR ref '{ref}' not found in GoalSpec.",
                hint=f"Add '{ref}' to GoalSpec nonFunctionalRequirements or correct the reference.")

    for comp in spec.get("components", []):
        for ref in comp.get("reqRefs", []):
            check_req(ref, f"Component '{comp['id']}'")
        for ref in comp.get("nfrRefs", []):
            check_nfr(ref, f"Component '{comp['id']}'")

    for flow in spec.get("dataFlow", []):
        for ref in flow.get("reqRefs", []):
            check_req(ref, f"Flow '{flow['id']}'")

    for con in spec.get("constraints", []):
        for ref in con.get("nfrRefs", []):
            check_nfr(ref, f"Constraint '{con['id']}'")


def check_fr_coverage(spec: dict, goal: Optional[dict], result: LintResult):
    """Every FR in GoalSpec should be covered by at least one component."""
    if not goal:
        return

    covered_reqs = set()
    for comp in spec.get("components", []):
        for ref in comp.get("reqRefs", []):
            covered_reqs.add(ref)

    for fr in goal.get("functionalRequirements", []):
        if fr["id"] not in covered_reqs:
            result.add("warning", "fr_uncovered",
                f"GoalSpec {fr['id']} ('{fr['description'][:60]}...') is not covered by any component.",
                hint=f"Add reqRef '{fr['id']}' to the component responsible for this requirement.")


def check_nfr_coverage(spec: dict, goal: Optional[dict], result: LintResult):
    """Every NFR in GoalSpec should be covered by at least one component or constraint."""
    if not goal:
        return

    covered_nfrs = set()
    for comp in spec.get("components", []):
        for ref in comp.get("nfrRefs", []):
            covered_nfrs.add(ref)
    for con in spec.get("constraints", []):
        for ref in con.get("nfrRefs", []):
            covered_nfrs.add(ref)

    for nfr in goal.get("nonFunctionalRequirements", []):
        if nfr["id"] not in covered_nfrs:
            result.add("warning", "nfr_uncovered",
                f"GoalSpec {nfr['id']} ('{nfr['description'][:60]}...') is not covered by any component or constraint.",
                hint=f"Add nfrRef '{nfr['id']}' to a component or constraint responsible for this NFR.")


def check_subsystem_empty(spec: dict, component_ids: set[str], result: LintResult):
    """Warn if a subsystem has no components assigned."""
    subsystems = spec.get("overview", {}).get("subsystems", [])
    for sub in subsystems:
        refs = sub.get("componentRefs", [])
        if not refs:
            result.add("warning", "subsystem_empty",
                f"Subsystem '{sub['name']}' has no components assigned.",
                hint="Assign components to this subsystem or remove it.")


def check_subsystem_overlap(spec: dict, result: LintResult):
    """Warn if a component is assigned to multiple subsystems."""
    subsystems = spec.get("overview", {}).get("subsystems", [])
    comp_to_subs: dict[str, list[str]] = {}
    for sub in subsystems:
        for ref in sub.get("componentRefs", []):
            comp_to_subs.setdefault(ref, []).append(sub["name"])
    
    for comp, subs in comp_to_subs.items():
        if len(subs) > 1:
            result.add("warning", "subsystem_overlap",
                f"Component '{comp}' is assigned to multiple subsystems: {', '.join(subs)}.",
                hint="Each component should belong to exactly one subsystem.")


def check_data_ref_valid(spec: dict, data_spec: Optional[dict], result: LintResult):
    """Warn if data flow steps reference non-existent DataSpec entities."""
    if not data_spec:
        return
    
    entity_names = {e["name"] for e in data_spec.get("entities", [])}
    for flow in spec.get("dataFlow", []):
        for step in flow.get("steps", []):
            data_ref = step.get("dataRef", "")
            if data_ref and data_ref not in entity_names:
                result.add("warning", "data_ref_missing",
                    f"Flow '{flow['id']}' step references data '{data_ref}' which is not a defined DataSpec entity.",
                    hint=f"Add '{data_ref}' to DataSpec or correct the dataRef.")


def check_component_responsibility_count(spec: dict, result: LintResult):
    """Warn if a component has too many responsibilities (>5)."""
    for comp in spec.get("components", []):
        resps = comp.get("responsibilities", [])
        if len(resps) > 8:
            result.add("warning", "component_responsibility_count",
                f"Component '{comp['id']}' has {len(resps)} responsibilities — consider splitting.",
                hint="A component with >5 responsibilities may be doing too much. Consider splitting into multiple components.")


def check_data_flow_step_count(spec: dict, result: LintResult):
    """Warn if a data flow has too many steps (>10)."""
    for flow in spec.get("dataFlow", []):
        steps = flow.get("steps", [])
        if len(steps) > 15:
            result.add("warning", "flow_step_count",
                f"Flow '{flow['id']}' has {len(steps)} steps — consider splitting.",
                hint="A data flow with >10 steps may be too complex. Consider splitting into multiple flows.")


def check_external_component_count(spec: dict, result: LintResult):
    """Warn if too many components are external (>30% of total)."""
    components = spec.get("components", [])
    if not components:
        return
    external_count = sum(1 for c in components if c.get("visibility") == "external")
    if external_count > len(components) * 0.5:
        result.add("warning", "external_component_count",
            f"{external_count}/{len(components)} components ({external_count/len(components):.0%}) are external.",
            hint="Too many external components may indicate over-exposure. Review which components truly need to be external.")


def check_dependency_depth(spec: dict, result: LintResult):
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
            result.add("warning", "dependency_depth",
                f"Component '{comp_id}' has a dependency chain of {depth} levels.",
                hint="Deep dependency chains can make the system hard to understand and maintain.")

# ── Runner ────────────────────────────────────────────────────────────────────

def run_lint(spec: dict, schema_path: Optional[Path],
             goal: Optional[dict], strict: bool) -> LintResult:
    result = LintResult()

    # JSON Schema validation
    if schema_path and HAS_JSONSCHEMA:
        schema = json.loads(schema_path.read_text())
        for err in jsonschema.Draft7Validator(schema).iter_errors(spec):
            result.add("error", "schema", f"{err.json_path}: {err.message}")
    elif schema_path and not HAS_JSONSCHEMA:
        result.add("warning", "schema_skipped",
            "jsonschema not installed — skipping schema validation.",
            hint="pip install jsonschema")

    # GoalSpec cross-checks
    if goal:
        check_project_match(spec, goal, result)
        check_version_pins(spec, goal, result)

    # Structural checks
    component_ids = check_components(spec, result)
    check_subsystems(spec, component_ids, result)
    check_data_flows(spec, component_ids, result)
    check_constraints(spec, result)

    # Cross-spec ref resolution
    check_req_nfr_refs(spec, goal, result)
    check_fr_coverage(spec, goal, result)

    if strict:
        for w in result.warnings:
            w.severity = "error"
            result.errors.append(w)
        result.warnings.clear()

    return result


# ── Output ────────────────────────────────────────────────────────────────────

def print_human(result: LintResult, path: str, goal_path: Optional[str]):
    print(f"\n{'─'*60}")
    print(f"  ArchSpec Lint Report — {path}")
    if goal_path:
        print(f"  GoalSpec — {goal_path}")
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


def print_json_output(result: LintResult):
    print(json.dumps({
        "clean": result.clean,
        "errors": [{"category": e.category, "message": e.message, "hint": e.hint} for e in result.errors],
        "warnings": [{"category": w.category, "message": w.message, "hint": w.hint} for w in result.warnings]
    }, indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lint an ArchSpec JSON.")
    parser.add_argument("input", help="Path to archspec JSON")
    parser.add_argument("--schema", help="Path to archspec.schema.json")
    parser.add_argument("--goal",   help="Path to goalspec JSON for cross-spec checks")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json",   action="store_true", help="Output as JSON")
    args = parser.parse_args()

    spec = json.loads(Path(args.input).read_text())
    schema_path = Path(args.schema) if args.schema else None
    goal = json.loads(Path(args.goal).read_text()) if args.goal else None

    result = run_lint(spec, schema_path, goal, args.strict)

    if args.json:
        print_json_output(result)
    else:
        print_human(result, args.input, args.goal)

    sys.exit(0 if result.clean else 1)


if __name__ == "__main__":
    main()
